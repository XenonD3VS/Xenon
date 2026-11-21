"""Builds the architectural shell (interior + exterior + site) and collision from layout.py."""
import math

import numpy as np

import layout as LY
from mesh import Mesh, Collision
import materials as M

RES = 0.1
NX, NY = 560, 500
SITE_Z = -0.1

MLO_ROOMS = ["limbo", "l1", "l2", "l3", "stair_a", "stair_b", "garage"]
MLO_IDX = {n: i for i, n in enumerate(MLO_ROOMS)}

INT_COLOUR = (255, 255, 255, 255)
EXT_COLOUR = (255, 255, 255, 255)

DOOR_MODELS = {
    "std": "v_ilev_ph_gendoor004",
    "glass": "v_ilev_ph_gendoor004",
    "exit": "v_ilev_ph_gendoor004",
    "sec": "v_ilev_arm_secdoor",
    "cell": "v_ilev_ph_cellgate",
    "cell_hs": "v_ilev_ph_cellgate",
}


def mlo_room_of(room):
    if room.rid.startswith("stair_a"):
        return "stair_a"
    if room.rid.startswith("stair_b"):
        return "stair_b"
    if room.rid == "garage":
        return "garage"
    return ["l1", "l2", "l3", "stair_a"][room.level]


for _r in LY.ROOMS:
    _r.mlo_room = mlo_room_of(_r)


def wall_height(level):
    return 3.3 if level == 3 else LY.FLOOR_H


def room_ceil(room):
    if room.rtype == "stair":
        return LY.FLOOR_H if room.level < 3 else 3.3
    return room.ceil


class Shell:
    def __init__(self):
        self.int = {n: Mesh(INT_COLOUR) for n in MLO_ROOMS[1:]}
        self.ext = Mesh(EXT_COLOUR)
        self.site = Mesh(EXT_COLOUR)
        self.lod = Mesh(EXT_COLOUR)
        self.col_int = Collision()
        self.col_ext = Collision()
        self.portals = []        # dict(from, to, corners)
        self.doors = []          # entity dicts
        self.props_ext = []      # outdoor vanilla props
        self.notes = []

    # ------------------------------------------------------------ helpers
    def imesh(self, room):
        return self.int[room.mlo_room]

    def rid(self, room):
        return MLO_IDX[room.mlo_room]


# ====================================================================== walls
def label_grid(level):
    lab = np.full((NX, NY), -1, dtype=np.int32)
    for r in LY.rooms_on(level):
        for (x0, y0, x1, y1) in r.rects:
            lab[int(round(x0 / RES)):int(round(x1 / RES)), int(round(y0 / RES)):int(round(y1 / RES))] = r.idx
    return lab


def runs(level, lab):
    """Yield wall runs: (orient, line_coord, start, end, low_room_idx, high_room_idx, ext_start, ext_end)."""
    out = []
    # vertical lines x = i*RES (orient 'v')
    for i in range(NX + 1):
        left = lab[i - 1, :] if i > 0 else np.full(NY, -1)
        right = lab[i, :] if i < NX else np.full(NY, -1)
        j = 0
        while j < NY:
            a, b = left[j], right[j]
            if a == b:
                j += 1
                continue
            j0 = j
            while j < NY and left[j] == a and right[j] == b:
                j += 1
            out.append(("v", i * RES, j0 * RES, j * RES, int(a), int(b), False, False))
    for j in range(NY + 1):
        lo = lab[:, j - 1] if j > 0 else np.full(NX, -1)
        hi = lab[:, j] if j < NY else np.full(NX, -1)
        i = 0
        while i < NX:
            a, b = lo[i], hi[i]
            if a == b:
                i += 1
                continue
            i0 = i
            while i < NX and lo[i] == a and hi[i] == b:
                i += 1
            ext0 = ext1 = False
            if a == -1 or b == -1:
                # convex corner extension for exterior 'h' runs
                def outside(ii, jj):
                    if ii < 0 or ii >= NX or jj < 0 or jj >= NY:
                        return True
                    return lab[ii, jj] == -1
                ext0 = outside(i0 - 1, j - 1) and outside(i0 - 1, j)
                ext1 = outside(i, j - 1) and outside(i, j)
            out.append(("h", j * RES, i0 * RES, i * RES, int(a), int(b), ext0, ext1))
    return out


def openings_for(level, orient, c, s, e):
    ops = []
    for d in LY.DOORS:
        if d.level == level and d.orient == orient:
            along = d.x if orient == "h" else d.y
            line = d.y if orient == "h" else d.x
            if abs(line - c) < 0.01 and s - 1e-6 <= along - d.width / 2 and along + d.width / 2 <= e + 1e-6:
                ops.append(dict(a=along - d.width / 2, b=along + d.width / 2, sill=0.0, head=d.height, kind=d.kind, door=d))
    for w in LY.WINDOWS:
        if w.level == level and w.orient == orient and abs(w.pos - c) < 0.01 and s - 1e-6 <= w.a and w.b <= e + 1e-6:
            ops.append(dict(a=w.a, b=w.b, sill=w.sill, head=w.head, kind=w.kind, win=w))
    ops.sort(key=lambda o: o["a"])
    return ops


def wbox(orient, c0, c1, a0, a1, z0, z1):
    """Convert wall-space (thickness c0..c1, along a0..a1) into xyz box."""
    if orient == "v":
        return (c0, a0, z0, c1, a1, z1)
    return (a0, c0, z0, a1, c1, z1)


def face_name(orient, positive):
    if orient == "v":
        return "+x" if positive else "-x"
    return "+y" if positive else "-y"


def build_walls(sh, level):
    lab = label_grid(level)
    z0 = LY.LEVEL_Z[level]
    H = wall_height(level)
    z1 = z0 + H
    rooms = LY.ROOMS
    for (orient, c, s, e, ai, bi, ext0, ext1) in runs(level, lab):
        A = rooms[ai] if ai >= 0 else None
        B = rooms[bi] if bi >= 0 else None
        exterior = A is None or B is None
        if exterior:
            inner = B if A is None else A
            if A is None:          # outside is on the low side
                c0, c1 = c - LY.EXT_T, c
                in_face_pos, out_face_pos = True, False
            else:
                c0, c1 = c, c + LY.EXT_T
                in_face_pos, out_face_pos = False, True
        else:
            c0, c1 = c - LY.INT_T / 2, c + LY.INT_T / 2
        ss = s - (LY.EXT_T if ext0 else 0)
        ee = e + (LY.EXT_T if ext1 else 0)
        ops = openings_for(level, orient, c, s, e)
        # solid pieces: (a0, a1, zb, zt)
        pieces = []
        cur = ss
        for o in ops:
            if o["a"] > cur + 1e-4:
                pieces.append((cur, o["a"], z0, z1))
            if o["sill"] > 0:
                pieces.append((o["a"], o["b"], z0, z0 + o["sill"]))
            if z0 + o["head"] < z1 - 1e-4:
                pieces.append((o["a"], o["b"], z0 + o["head"], z1))
            cur = o["b"]
        if cur < ee - 1e-4:
            pieces.append((cur, ee, z0, z1))

        for (a0, a1, zb, zt) in pieces:
            box = wbox(orient, c0, c1, a0, a1, zb, zt)
            if exterior:
                m_in = inner.mats[1]
                ceil_top = z0 + room_ceil(inner)
                fi = face_name(orient, in_face_pos)
                fo = face_name(orient, out_face_pos)
                if zb < ceil_top - 1e-4:
                    ib = list(box)
                    ib[5] = min(zt, ceil_top)
                    sh.imesh(inner).box(m_in, *ib, faces=(fi,))
                facade = facade_mat(level, zb, zt)
                sh.ext.box(facade, *box, faces=(fo,))
                if ext0 and abs(a0 - ss) < 1e-6 and orient == "h":
                    sh.ext.box(facade, *box, faces=("-x",))
                if ext1 and abs(a1 - ee) < 1e-6 and orient == "h":
                    sh.ext.box(facade, *box, faces=("+x",))
                colmat = M.get(facade).col
                sh.col_int.box(*box, col=M.get(m_in).col, room=sh.rid(inner))
                if level == 0 and zb <= z0 + 1e-6:
                    # foundation skirt below finished floor down into the ground
                    fb = list(box)
                    fb[2], fb[5] = SITE_Z - 1.5, z0
                    sh.ext.box("lspd_stone", *fb, faces=(fo,))
                    sh.col_ext.box(*fb, col="CONCRETE")
                    # stone plinth band (slightly proud of the facade)
                    pb = list(box)
                    off = 0.04
                    if orient == "v":
                        if out_face_pos:
                            pb[3] += off
                        else:
                            pb[0] -= off
                    else:
                        if out_face_pos:
                            pb[4] += off
                        else:
                            pb[1] -= off
                    pb[2], pb[5] = SITE_Z, min(zt, z0 + 0.55)
                    sh.ext.box("lspd_stone", *pb, faces=(fo, "+z"))
            else:
                ca = z0 + room_ceil(A)
                cb = z0 + room_ceil(B)
                fa = face_name(orient, False)
                fb_ = face_name(orient, True)
                if zb < ca - 1e-4:
                    bb = list(box)
                    bb[5] = min(zt, ca)
                    sh.imesh(A).box(A.mats[1], *bb, faces=(fa,))
                if zb < cb - 1e-4:
                    bb = list(box)
                    bb[5] = min(zt, cb)
                    sh.imesh(B).box(B.mats[1], *bb, faces=(fb_,))
                sh.col_int.box(*box, col=M.get(A.mats[1]).col, room=sh.rid(A))
                # skirting boards
                for R_, f_, cc in ((A, fa, c0), (B, fb_, c1)):
                    if zb <= z0 + 1e-6 and R_.rtype not in ("stair", "cell", "cell_hs", "garage", "showers", "wc_public", "kitchen"):
                        d = -0.012 if f_ in ("-x", "-y") else 0.012
                        sk = wbox(orient, cc + min(0, d), cc + max(0, d), a0, a1, z0, z0 + 0.1)
                        sh.imesh(R_).box("lspd_metal_dark", *sk, faces=(f_, "+z"))
        # openings: jambs, glass, frames, portals, doors
        for o in ops:
            build_opening(sh, level, orient, c, c0, c1, o, A, B, exterior, z0)


def facade_mat(level, zb, zt):
    # dark granite base storey, light precast panels above, anthracite roof hut
    if level == 0:
        return "lspd_stone"
    if level == 3:
        return "lspd_ext_metal"
    return "lspd_ext_panel"


def build_opening(sh, level, orient, c, c0, c1, o, A, B, exterior, z0):
    a0, a1 = o["a"], o["b"]
    zb, zt = z0 + o["sill"], z0 + o["head"]
    kind = o["kind"]
    if exterior:
        inner = B if A is None else A
        mesh_j = sh.ext
        jm = "lspd_ext_metal"
    else:
        inner = A
        mesh_j = sh.imesh(A)
        jm = "lspd_metal_dark"
    # jambs (both ends) + head soffit + sill top
    if orient == "v":
        mesh_j.box(jm, c0, a0 - 0.001, zb, c1, a0, zt, faces=("+y",))
        mesh_j.box(jm, c0, a1, zb, c1, a1 + 0.001, zt, faces=("-y",))
    else:
        mesh_j.box(jm, a0 - 0.001, c0, zb, a0, c1, zt, faces=("+x",))
        mesh_j.box(jm, a1, c0, zb, a1 + 0.001, c1, zt, faces=("-x",))
    if zt < z0 + wall_height(level) - 1e-4:
        mesh_j.box(jm, *wbox(orient, c0, c1, a0, a1, zt, zt + 0.001), faces=("-z",))
    if o["sill"] > 0:
        sillmat = "lspd_stone" if exterior else ("lspd_laminate" if kind == "counter" else "lspd_metal_dark")
        mesh_j.box(sillmat, *wbox(orient, c0, c1, a0, a1, zb - 0.001, zb), faces=("+z",))

    if exterior:
        out_pos = A is None and False or (B is None)
        # direction from wall line to outside: if A is None outside is low side
        out_sign = -1 if A is None else 1
        is_window = "win" in o
        if is_window:
            gc = c + out_sign * LY.EXT_T * 0.55
            gb = wbox(orient, gc - 0.01, gc + 0.01, a0, a1, zb, zt)
            sh.ext.box("glass_ext", *gb, faces=(face_name(orient, True), face_name(orient, False)))
            sh.col_ext.box(*gb, col="GLASS_BULLETPROOF")
            sh.col_int.box(*gb, col="GLASS_BULLETPROOF", room=sh.rid(inner))
            # frame + mullions on outer side
            fc0, fc1 = sorted((gc - 0.05, gc + 0.05))
            fr = 0.06
            for (p0, p1, q0, q1) in ((a0, a0 + fr, zb, zt), (a1 - fr, a1, zb, zt), (a0, a1, zb, zb + fr), (a0, a1, zt - fr, zt)):
                sh.ext.box("lspd_ext_metal", *wbox(orient, fc0, fc1, p0, p1, q0, q1))
            width = a1 - a0
            nm = int(width // 1.6)
            for k in range(1, nm + 1):
                p = a0 + width * k / (nm + 1)
                sh.ext.box("lspd_ext_metal", *wbox(orient, fc0, fc1, p - 0.03, p + 0.03, zb, zt))
            if o["kind"] == "curtain":
                tz = zb + 2.4
                sh.ext.box("lspd_ext_metal", *wbox(orient, fc0, fc1, a0, a1, tz - 0.03, tz + 0.03))
            # interior window sill board
            if o["sill"] > 0.3:
                d = -out_sign
                sh.imesh(inner).box("lspd_laminate", *wbox(orient, min(c, c + d * 0.12), max(c, c + d * 0.12), a0, a1, zb - 0.03, zb + 0.0),
                                    faces=("+z", face_name(orient, d > 0)))
        else:
            # exterior door way: threshold
            sh.ext.box("lspd_stone", *wbox(orient, c0, c1, a0, a1, z0 - 0.02, z0), faces=("+z",))
        # portal at the inner wall face (room -> limbo)
        corners = portal_corners(orient, c, a0, a1, zb, zt)
        sh.portals.append(dict(frm=sh.rid(inner), to=0, corners=corners, kind=kind))
    else:
        mid = (c0 + c1) / 2
        if kind in ("mirror",):
            mside = A if A.rtype in ("interrogation", "lineup") else B
            positive = mside is B
            fb = wbox(orient, mid - 0.01, mid + 0.01, a0, a1, zb, zt)
            sh.imesh(mside).box("mirror", *fb, faces=(face_name(orient, positive),))
            sh.col_int.box(*fb, col="GLASS_BULLETPROOF", room=sh.rid(A))
            # thin frame
            other = B if mside is A else A
            for m_ in (mside, other):
                pos = m_ is B
                cc = c1 if pos else c0
                d = 0.02 if pos else -0.02
                for (p0, p1, q0, q1) in ((a0 - 0.05, a0, zb - 0.05, zt + 0.05), (a1, a1 + 0.05, zb - 0.05, zt + 0.05),
                                         (a0, a1, zb - 0.05, zb), (a0, a1, zt, zt + 0.05)):
                    sh.imesh(m_).box("lspd_metal_dark", *wbox(orient, min(cc, cc + d), max(cc, cc + d), p0, p1, q0, q1))
        elif kind in ("glass", "counter"):
            fb = wbox(orient, mid - 0.006, mid + 0.006, a0, a1, zb, zt)
            sh.imesh(A).box("glass_int", *fb, faces=(face_name(orient, True), face_name(orient, False)))
            sh.col_int.box(*fb, col="GLASS_BULLETPROOF", room=sh.rid(A))
            if kind == "counter":
                # transaction counter top protruding both sides, with a pass-through slot
                ct = wbox(orient, c0 - 0.35, c1 + 0.35, a0 - 0.05, a1 + 0.05, zb - 0.05, zb)
                sh.imesh(A).box("lspd_laminate_dark", *ct)
                sh.col_int.box(*ct, col="WOOD_SOLID_MEDIUM", room=sh.rid(A))
                # vertical mullion with speak grille
                m0 = (a0 + a1) / 2
                sh.imesh(A).box("lspd_metal", *wbox(orient, mid - 0.02, mid + 0.02, m0 - 0.03, m0 + 0.03, zb, zt))
        # door entity / portal between MLO rooms
        if "door" in o and A.mlo_room != B.mlo_room:
            corners = portal_corners(orient, c, a0, a1, zb, zt)
            sh.portals.append(dict(frm=sh.rid(A), to=sh.rid(B), corners=corners, kind=kind))
    if "door" in o and kind in DOOR_MODELS:
        d = o["door"]
        if orient == "h":
            pos = (a0 + 0.02, c, z0)
            heading = 0.0
        else:
            pos = (c, a0 + 0.02, z0)
            heading = 90.0
        room = inner
        sh.doors.append(dict(model=DOOR_MODELS[kind], pos=pos, heading=heading, room=room, kind=kind,
                             level=level, width=d.width))
        # door frame trim on both faces
        for side_c, mesh_ in ((c0, sh.imesh(A) if A else sh.ext), (c1, sh.imesh(B) if B else sh.ext)):
            dd = -0.03 if side_c == c0 else 0.03
            lo, hi = min(side_c, side_c + dd), max(side_c, side_c + dd)
            for (p0, p1, q0, q1) in ((a0 - 0.07, a0, z0, zt + 0.07), (a1, a1 + 0.07, z0, zt + 0.07), (a0, a1, zt, zt + 0.07)):
                mesh_.box("lspd_metal_dark", *wbox(orient, lo, hi, p0, p1, q0, q1))


def portal_corners(orient, c, a0, a1, zb, zt):
    if orient == "v":
        return [(c, a0, zt), (c, a1, zt), (c, a1, zb), (c, a0, zb)]
    return [(a0, c, zt), (a1, c, zt), (a1, c, zb), (a0, c, zb)]


# ============================================================= floors/ceilings
def build_floors(sh):
    for r in LY.ROOMS:
        z0 = LY.LEVEL_Z[r.level]
        fm, wm, cm, _ = r.mats
        mesh = sh.imesh(r)
        rid = sh.rid(r)
        top_stair = r.rid in ("stair_a4", "stair_b3")
        for (x0, y0, x1, y1) in r.rects:
            if r.rtype != "stair" or r.level == 0:
                mesh.box(fm, x0, y0, z0 - 0.3, x1, y1, z0, faces=("+z",))
                sh.col_int.box(x0, y0, z0 - 0.3, x1, y1, z0, col=M.get(fm).col, room=rid)
            elif r.level > 0:
                # stair landing at this floor (entry landing)
                pass
            ceil = room_ceil(r)
            if r.rtype != "stair" or top_stair:
                zc = z0 + ceil
                mesh.box(cm, x0, y0, zc, x1, y1, zc + 0.05, faces=("-z",))
                if top_stair:
                    sh.col_int.box(x0, y0, zc, x1, y1, zc + 0.25, col="CONCRETE", room=rid)
        build_lighting(sh, r)


def build_lighting(sh, r):
    """Ceiling light fixtures (emissive panels) + point lights."""
    z0 = LY.LEVEL_Z[r.level]
    zc = z0 + room_ceil(r)
    mesh = sh.imesh(r)
    t = r.rtype
    warm = t in ("office_exec", "conference", "break", "dining")
    colour = (255, 236, 210) if warm else (240, 244, 255)
    for (x0, y0, x1, y1) in r.rects:
        w, d = x1 - x0, y1 - y0
        if t == "stair":
            if r.level < 3:
                for (lx, ly) in ((x0 + 1.7, y0 + 0.8), (x0 + 1.7, y0 + 6.2)):
                    lz = z0 + 3.9 if ly > y0 + 3 else z0 + 3.2
                    mesh.box("emi_light", lx - 0.3, ly - 0.15, lz - 0.04, lx + 0.3, ly + 0.15, lz, faces=("-z",))
                    mesh.light(lx, ly, lz - 0.1, colour, 2.5, 5.0, 16.0)
            else:
                mesh.box("emi_light", x0 + 1.4, y0 + 0.6, zc - 0.04, x0 + 2.0, y0 + 1.2, zc, faces=("-z",))
                mesh.light(x0 + 1.7, y0 + 1.0, zc - 0.1, colour, 2.5, 5.0, 16.0)
            continue
        # panel grid spacing ~2.4 m
        nx = max(1, int(round(w / 2.6)))
        ny = max(1, int(round(d / 2.6)))
        for i in range(nx):
            for j in range(ny):
                cx = x0 + w * (i + 0.5) / nx
                cy = y0 + d * (j + 0.5) / ny
                if t in ("corridor", "detention_corridor"):
                    pw, pd = (0.3, 1.2) if d > w else (1.2, 0.3)
                elif t in ("garage", "sallyport", "gym", "armory", "riot", "technical", "janitor", "maintenance"):
                    pw, pd = (1.4, 0.2) if w > d else (0.2, 1.4)
                elif t in ("cell", "cell_hs"):
                    pw, pd = 0.5, 0.5
                else:
                    pw, pd = 0.58, 0.58
                mesh.box("emi_light", cx - pw / 2, cy - pd / 2, zc - 0.03, cx + pw / 2, cy + pd / 2, zc, faces=("-z",))
                mesh.box("lspd_metal", cx - pw / 2 - 0.02, cy - pd / 2 - 0.02, zc - 0.035, cx + pw / 2 + 0.02, cy + pd / 2 + 0.02, zc - 0.03,
                         faces=("+x", "-x", "+y", "-y"))
        # point lights: roughly one per 20 m^2
        area = w * d
        n = max(1, int(round(area / 28.0)))
        lnx = max(1, int(round(math.sqrt(n * w / d))))
        lny = max(1, int(round(n / lnx)))
        fall = max(4.5, min(9.0, math.sqrt(area / n) * 1.25))
        inten = 2.2 if t not in ("dispatch", "observation", "lineup_view", "interrogation") else 1.4
        if t in ("garage", "sallyport", "gym"):
            inten = 3.0
        for i in range(lnx):
            for j in range(lny):
                mesh.light(x0 + w * (i + 0.5) / lnx, y0 + d * (j + 0.5) / lny, zc - 0.25, colour, inten, fall, 16.0)


# ===================================================================== stairs
STEP_R = 0.175
STEP_T = 0.28
N_RISE = 12


def build_stairs(sh):
    for col, sx, levels in (("a", 0.0, (0, 1, 2)), ("b", 52.6, (0, 1))):
        for lv in range(0, 4 if col == "a" else 3):
            room = next(r for r in LY.ROOMS if r.rid == f"stair_{col}{lv + 1}")
            mesh = sh.imesh(room)
            rid = sh.rid(room)
            z0 = LY.LEVEL_Z[lv]
            if lv > 0:
                # entry landing slab
                mesh.box("lspd_concrete", sx, 20.4, z0 - 0.25, sx + 3.4, 22.0, z0, faces=("+z", "-z", "+y"))
                sh.col_int.box(sx, 20.4, z0 - 0.25, sx + 3.4, 22.0, z0, col="CONCRETE", room=rid)
                mesh.box("img_stripe", sx + 0.1, 21.9, z0, sx + 3.3, 22.0, z0 + 0.003, faces=("+z",))
            if lv not in levels:
                # top of this stair column: guard rail on the landing edge over the void
                rail_x0 = sx + 1.75 if lv == levels[-1] + 1 else sx
                mesh.box("lspd_metal", sx + 0.1, 21.95, z0, sx + 3.3, 22.0, z0 + 1.05)
                sh.col_int.box(sx + 0.1, 21.9, z0, sx + 3.3, 22.05, z0 + 1.1, col="METAL_SOLID_MEDIUM", room=rid)
                continue
            # flight 1: east half, northwards, z0 -> z0+2.1
            fx0, fx1 = sx + 1.75, sx + 3.3
            y = 22.0
            for k in range(N_RISE):
                top = z0 + STEP_R * (k + 1)
                ya, yb = y + STEP_T * k, y + STEP_T * (k + 1) if k < N_RISE - 1 else 25.08
                mesh.box("lspd_concrete", fx0, ya, z0 if lv == 0 else top - 0.45, fx1, yb, top, faces=("+z", "-y", "+x", "-x"))
                mesh.box("img_stripe", fx0, ya, top, fx1, ya + 0.04, top + 0.002, faces=("+z",))
            if lv > 0:
                mesh.ramp("lspd_concrete_dark", fx1, fx0, 22.0, z0 - 0.45, 25.08, z0 + 2.1 - 0.45)
            sh.col_int.ramp_solid(fx0, fx1, 22.0, z0, 25.08, z0 + 2.1, room=rid)
            # mid landing
            zl = z0 + 2.1
            mesh.box("lspd_concrete", sx, 25.08, zl - 0.25, sx + 3.4, 28.0, zl, faces=("+z", "-z", "-y"))
            sh.col_int.box(sx, 25.08, zl - 0.25, sx + 3.4, 28.0, zl, col="CONCRETE", room=rid)
            # flight 2: west half, southwards, z0+2.1 -> z0+4.2
            gx0, gx1 = sx + 0.1, sx + 1.65
            for k in range(N_RISE):
                top = zl + STEP_R * (k + 1)
                yb = 25.08 - STEP_T * k
                ya = yb - STEP_T if k < N_RISE - 1 else 22.0
                mesh.box("lspd_concrete", gx0, ya, top - 0.45, gx1, yb, top, faces=("+z", "+y", "+x", "-x"))
                mesh.box("img_stripe", gx0, yb - 0.04, top, gx1, yb, top + 0.002, faces=("+z",))
            mesh.ramp("lspd_concrete_dark", gx0, gx1, 25.08, zl - 0.45, 22.0, zl + 2.1 - 0.45)
            sh.col_int.ramp_solid(gx0, gx1, 25.08, zl, 22.0, zl + 2.1, room=rid)
            # central divider wall + handrails
            mesh.box("lspd_paint_grey", sx + 1.65, 22.0, z0, sx + 1.75, 25.08, z0 + LY.FLOOR_H, faces=("+x", "-x", "-y"))
            sh.col_int.box(sx + 1.65, 22.0, z0, sx + 1.75, 25.08, z0 + LY.FLOOR_H, col="CONCRETE", room=rid)
            for (rx, y_a, z_a, y_b, z_b) in ((sx + 1.78, 22.0, z0 + 0.9, 25.08, z0 + 3.0),
                                             (sx + 3.33, 22.0, z0 + 0.9, 25.08, z0 + 3.0),
                                             (sx + 1.62, 25.08, zl + 0.9, 22.0, zl + 3.0),
                                             (sx + 0.07, 25.08, zl + 0.9, 22.0, zl + 3.0)):
                rail(mesh, rx, y_a, z_a, y_b, z_b)
            # level number sign on the landing wall
            sign_quad(mesh, f"LEVEL {lv + 1}", "-x" if False else "+y", sx + 0.6, 20.42, z0 + 1.9, 2.2, 0.55, facing="+y")


def rail(mesh, x, ya, za, yb, zb, r=0.025):
    n = 6
    for i in range(n):
        y0 = ya + (yb - ya) * i / n
        y1 = ya + (yb - ya) * (i + 1) / n
        zz = za + (zb - za) * (i + 0.5) / n
        mesh.box("lspd_metal", x - r, min(y0, y1), zz - r, x + r, max(y0, y1), zz + r)


def sign_quad(mesh, text, _unused, x, y, z, w, h, facing="+y", emissive=False):
    """Room/department sign plate (2:1 cell from the sign atlas)."""
    import textures as T
    u0, v0, u1, v1 = T.sign_uv(text)
    mat = "emi_signs" if emissive else "img_signs"
    t = 0.02
    if facing == "+y":
        b = (x, y, z, x + w, y + t, z + h)
        mesh.box("lspd_metal_navy", *b, faces=("+x", "-x", "+z", "-z"))
        mesh.box(mat, *b, faces=("+y",), uv=("sub", u0, v0, u1, v1))
    elif facing == "-y":
        b = (x, y - t, z, x + w, y, z + h)
        mesh.box("lspd_metal_navy", *b, faces=("+x", "-x", "+z", "-z"))
        mesh.box(mat, *b, faces=("-y",), uv=("sub", u0, v0, u1, v1))
    elif facing == "+x":
        b = (x, y, z, x + t, y + w, z + h)
        mesh.box("lspd_metal_navy", *b, faces=("+y", "-y", "+z", "-z"))
        mesh.box(mat, *b, faces=("+x",), uv=("sub", u0, v0, u1, v1))
    else:  # -x
        b = (x - t, y, z, x, y + w, z + h)
        mesh.box("lspd_metal_navy", *b, faces=("+y", "-y", "+z", "-z"))
        mesh.box(mat, *b, faces=("-x",), uv=("sub", u0, v0, u1, v1))


# =================================================================== exterior
def build_exterior(sh):
    E = sh.ext
    T = LY.EXT_T
    # ---- main roof (z 12.6) with stair hut cut-out
    zr = 12.6
    for (x0, y0, x1, y1) in ((-T, -T, 56 + T, 20.4), (3.4, 20.4, 56 + T, 28), (-T, 28, 56 + T, 36 + T)):
        E.box("lspd_roof", x0, y0, zr - 0.3, x1, y1, zr, faces=("+z",))
        sh.col_ext.box(x0, y0, zr - 0.3, x1, y1, zr, col="CONCRETE")
    E.box("lspd_roof", -T, 20.4, zr - 0.3, 0, 28, zr, faces=("+z",))
    parapet(sh, [(-T, -T), (56 + T, -T), (56 + T, 36 + T), (-T, 36 + T)], zr, 1.0)
    # floor bands
    for zb in (4.2, 8.4):
        band(sh, -T, -T, 56 + T, 36 + T, zb, skip_north=(zb == 4.2))
    # ---- stair hut roof
    E.box("lspd_roof", -T, 20.4 - T, zr + 3.3, 3.4 + T, 28 + T, zr + 3.55, faces=("+z", "+x", "-x", "+y", "-y"))
    sh.col_ext.box(-T, 20.4 - T, zr + 3.3, 3.4 + T, 28 + T, zr + 3.55, col="CONCRETE")
    # ---- garage annex roof (z 4.5)
    zg = 4.5
    E.box("lspd_roof", 15 - T, 36 + T, zg - 0.3, 56 + T, 50 + T, zg, faces=("+z",))
    sh.col_ext.box(15 - T, 36 + T, zg - 0.3, 56 + T, 50 + T, zg, col="CONCRETE")
    E.box("lspd_ext_panel", 15 - T, 36 + T, 4.2, 56 + T, 50 + T, zg, faces=("+x", "-x", "+y"))
    parapet(sh, [(15 - T, 36 + T), (15 - T, 50 + T), (56 + T, 50 + T), (56 + T, 36 + T)], zg, 0.6, closed=False)
    # ---- entrance canopy
    E.box({"+z": "lspd_metal_dark", "-z": "lspd_ceiling", "+x": "lspd_ext_metal", "-x": "lspd_ext_metal",
           "-y": "lspd_ext_metal"}, 21, -5.5, 3.7, 35, -T, 4.0)
    sh.col_ext.box(21, -5.5, 3.7, 35, -T, 4.0, col="METAL_SOLID_MEDIUM")
    for cx in (21.6, 34.4):
        E.cylinder("lspd_metal_dark", cx, -4.9, SITE_Z, 3.7, 0.18, 16)
        sh.col_ext.box(cx - 0.18, -5.08, SITE_Z, cx + 0.18, -4.72, 3.7, col="METAL_SOLID_MEDIUM")
    # canopy fascia sign
    E.box("lspd_ext_metal", 23.8, -5.62, 3.55, 32.2, -5.5, 4.15, faces=("+x", "-x", "+z", "-z"))
    E.box("emi_sign_main", 23.8, -5.62, 3.55, 32.2, -5.5, 4.15, faces=("-y",))
    for i in range(4):
        x = 22.5 + i * 3.6
        E.box("emi_light", x - 0.25, -3.25, 3.69, x + 0.25, -2.75, 3.7, faces=("-z",))
        E.light(x, -3.0, 3.5, (255, 240, 220), 3.0, 7.0, 16.0)
    # rooftop main sign
    sx0, sx1, sz0, sz1 = 22.0, 34.0, zr + 1.2, zr + 4.2
    E.box("emi_sign_main", sx0, -T - 0.02, sz0, sx1, -T + 0.12, sz1, faces=("-y",))
    E.box("lspd_ext_metal", sx0, -T - 0.02, sz0, sx1, -T + 0.12, sz1, faces=("+x", "-x", "+z", "-z", "+y"))
    for px_ in (sx0 + 1, (sx0 + sx1) / 2, sx1 - 1):
        E.box("lspd_metal_dark", px_ - 0.08, -T + 0.12, zr + 1.0, px_ + 0.08, 0.8, sz1 - 0.2)
    sh.col_ext.box(sx0, -T - 0.02, sz0, sx1, 0.8, sz1, col="METAL_SOLID_MEDIUM")
    # sign uplights
    E.light((sx0 + sx1) / 2, -2.0, zr + 1.0, (255, 250, 240), 4.0, 8.0, 8.0, kind="Point")
    # helipad
    E.box("img_helipad", 38, 19, zr, 52, 33, zr + 0.01, faces=("+z",))
    for (hx, hy) in ((38, 19), (52, 19), (38, 33), (52, 33), (45, 19), (45, 33), (38, 26), (52, 26)):
        E.box("emi_light", hx - 0.12, hy - 0.12, zr, hx + 0.12, hy + 0.12, zr + 0.08)
    # rooftop HVAC units and vents
    for (hx, hy, w, d) in ((8, 4, 4, 2.6), (14, 4, 4, 2.6), (8, 30, 3.2, 3.2), (20, 30, 6, 3)):
        E.box({"+z": "lspd_metal", "+x": "lspd_metal", "-x": "lspd_metal", "+y": "lspd_metal", "-y": "lspd_metal"},
              hx, hy, zr, hx + w, hy + d, zr + 1.6)
        for k in range(int(w // 1.3)):
            E.cylinder("mat_black", hx + 0.65 + k * 1.3, hy + d / 2, zr + 1.6, zr + 1.62, 0.5, 14)
        sh.col_ext.box(hx, hy, zr, hx + w, hy + d, zr + 1.6, col="METAL_SOLID_MEDIUM")
    # antenna mast
    E.cylinder("lspd_metal", 5.5, 24, zr + 3.55, zr + 9.0, 0.06, 8)
    E.cylinder("lspd_metal", 30, 18, zr, zr + 4.0, 0.08, 8)
    # facade vertical fins (anthracite) at the stair cores
    for (x0, x1) in ((-T - 0.25, -T), ):
        E.box("lspd_ext_metal", x0, 20.4, SITE_Z, x1, 28, zr + 3.55)
    E.box("lspd_ext_metal", 56 + T, 20.4, SITE_Z, 56 + T + 0.25, 28, zr + 1.0)
    sh.col_ext.box(-T - 0.25, 20.4, SITE_Z, -T, 28, zr + 3.55, col="METAL_SOLID_MEDIUM")
    sh.col_ext.box(56 + T, 20.4, SITE_Z, 56 + T + 0.25, 28, zr + 1.0, col="METAL_SOLID_MEDIUM")
    # facade wall-pack lights
    for (lx, ly, d) in ((-0.5, 32, (-1, 0, 0)), (56.5, 43, (1, 0, 0)), (56.5, 32, (1, 0, 0)), (25, 50.5, (0, 1, 0)), (43, 50.5, (0, 1, 0))):
        E.box("emi_light", lx - 0.15, ly - 0.15, 4.4, lx + 0.15, ly + 0.15, 4.6)
        E.light(lx + d[0] * 1.0, ly + d[1] * 1.0, 4.3, (255, 240, 225), 4.0, 12.0, 12.0)
    # roll-up door housings (exterior side) above vehicle openings
    for d in LY.DOORS:
        if d.kind == "vehicle":
            hw = d.width / 2
            if d.orient == "h":
                E.box("lspd_metal_dark", d.x - hw - 0.1, d.y + T, 3.8, d.x + hw + 0.1, d.y + T + 0.35, 4.15)
            else:
                E.box("lspd_metal_dark", d.x + T, d.y - hw - 0.1, 3.8, d.x + T + 0.35, d.y + hw + 0.1, 4.15)
    # automatic entrance doors: parked sliding panels inside a glass vestibule frame (open position)
    E.box("lspd_ext_metal", 26.4, -T, 2.6, 29.6, 0.0, 3.0)
    for x0 in (24.7, 29.8):
        E.box("glass_ext", x0, -0.2, 0.02, x0 + 1.5, -0.18, 2.55, faces=("+y", "-y"))
        E.box("lspd_ext_metal", x0, -0.21, 0.0, x0 + 1.5, -0.17, 0.08)
        E.box("lspd_ext_metal", x0, -0.21, 2.5, x0 + 1.5, -0.17, 2.58)
    # LOD model
    L = sh.lod
    L.box({"+x": "lspd_ext_panel", "-x": "lspd_ext_panel", "+y": "lspd_ext_panel", "-y": "lspd_ext_panel",
           "+z": "lspd_roof"}, -T, -T, SITE_Z, 56 + T, 36 + T, zr + 1.0)
    L.box({"+x": "lspd_ext_panel", "-x": "lspd_ext_panel", "+y": "lspd_ext_panel", "+z": "lspd_roof"},
          15 - T, 36 + T, SITE_Z, 56 + T, 50 + T, zg + 0.6)
    L.box("lspd_ext_panel", -T, 20.4 - T, zr, 3.4 + T, 28 + T, zr + 3.55, faces=("+x", "-x", "+y", "-y", "+z"))
    L.box("lspd_metal_dark", 21, -5.5, 3.7, 35, -T, 4.0)
    L.box("emi_sign_main", sx0, -T - 0.05, sz0, sx1, -T, sz1, faces=("-y",))
    L.box("lspd_asphalt", SITE[0], SITE[1], SITE_Z - 0.05, SITE[2], SITE[3], SITE_Z - 0.04, faces=("+z",))


def parapet(sh, pts, z, h, closed=True):
    E = sh.ext
    n = len(pts)
    segs = [(pts[i], pts[(i + 1) % n]) for i in range(n if closed else n - 1)]
    t = 0.3
    for (a, b) in segs:
        x0, y0 = min(a[0], b[0]), min(a[1], b[1])
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        if x1 - x0 < 1e-6:
            # vertical line: wall thickness inward depends on side
            inward = 1 if a[0] < 28 else -1
            bx = (x0, y0, z, x0 + t * inward, y1, z + h)
        else:
            inward = 1 if a[1] < 25 else -1
            bx = (x0, y0, z, x1, y0 + t * inward, z + h)
        bx = (min(bx[0], bx[3]), min(bx[1], bx[4]), bx[2], max(bx[0], bx[3]), max(bx[1], bx[4]), bx[5])
        E.box({"+x": "lspd_ext_panel", "-x": "lspd_ext_panel", "+y": "lspd_ext_panel", "-y": "lspd_ext_panel"}, *bx)
        E.box("lspd_metal_dark", bx[0] - 0.03, bx[1] - 0.03, bx[5], bx[3] + 0.03, bx[4] + 0.03, bx[5] + 0.06)
        sh.col_ext.box(*bx[:5], bx[5] + 0.06, col="CONCRETE")


def band(sh, x0, y0, x1, y1, z, skip_north=False):
    E = sh.ext
    o = 0.08
    E.box("lspd_ext_metal", x0 - o, y0 - o, z - 0.2, x1 + o, y0, z + 0.2)
    E.box("lspd_ext_metal", x0 - o, y0, z - 0.2, x0, y1, z + 0.2)
    E.box("lspd_ext_metal", x1, y0, z - 0.2, x1 + o, y1, z + 0.2)
    if not skip_north:
        E.box("lspd_ext_metal", x0 - o, y1, z - 0.2, x1 + o, y1 + o, z + 0.2)


# ======================================================================= site
SITE = (-16.0, -26.0, 72.0, 66.0)


def build_site(sh):
    S = sh.site
    C = sh.col_ext
    z = SITE_Z
    x0, y0, x1, y1 = SITE

    def ground(mat, a, b, c, d, zz=z, col=None):
        S.box(mat, a, b, zz - 0.3, c, d, zz, faces=("+z",))
        C.box(a, b, zz - 0.3, c, d, zz, col=col or M.get(mat).col)

    # front parking + drive aisle (asphalt)
    ground("lspd_asphalt", x0, y0, x1, -9.0)
    # west parking strip
    ground("lspd_asphalt", x0, -9.0, -5.0, 36.3)
    # north yard / covered parking / east driveway
    ground("lspd_asphalt", x0, 36.3, 15 - 0.3, y1)
    ground("lspd_asphalt", 15 - 0.3, 50.3, x1, y1)
    ground("lspd_asphalt", 61.0, -9.0, x1, 50.3)
    # sidewalks / plaza (pavers) around the building
    ground("lspd_pavers", -5.0, -9.0, 61.0, -0.3)
    ground("lspd_pavers", -5.0, -0.3, -0.3, 36.3)
    ground("lspd_pavers", 56.3, -0.3, 61.0, 50.3)
    # entrance plaza feature: dark stone inlay under canopy
    S.box("lspd_stone", 21, -5.5, z, 35, -0.3, z + 0.005, faces=("+z",))
    # planters (raised, grass topped)
    for (a, b, c, d) in ((2, -7.5, 18, -3.0), (38, -7.5, 54, -3.0), (-4.2, 2, -1.2, 18), (57.2, 2, 60.2, 18)):
        S.box("lspd_concrete", a, b, z, c, d, z + 0.45, faces=("+x", "-x", "+y", "-y"))
        S.box("lspd_grass", a + 0.15, b + 0.15, z + 0.4, c - 0.15, d - 0.15, z + 0.42, faces=("+z",))
        S.box("lspd_concrete", a, b, z + 0.45, c, b + 0.15, z + 0.47, faces=("+z",))
        S.box("lspd_concrete", a, d - 0.15, z + 0.45, c, d, z + 0.47, faces=("+z",))
        S.box("lspd_concrete", a, b, z + 0.45, a + 0.15, d, z + 0.47, faces=("+z",))
        S.box("lspd_concrete", c - 0.15, b, z + 0.45, c, d, z + 0.47, faces=("+z",))
        C.box(a, b, z, c, d, z + 0.47, col="CONCRETE")
        # shrubs from the base game inside the planters
        n = int(max(c - a, d - b) // 3)
        for k in range(n):
            t = (k + 0.5) / n
            px_ = a + (c - a) * t if (c - a) > (d - b) else (a + c) / 2
            py_ = (b + d) / 2 if (c - a) > (d - b) else b + (d - b) * t
            sh.props_ext.append(dict(model="prop_bush_med_03", pos=(px_, py_, z + 0.42), heading=k * 47.0, lod=120))
    # curb line between plaza and parking
    S.box("lspd_concrete", x0 + 11, -9.15, z, x1 - 11, -9.0, z + 0.12, faces=("+z", "-y"))
    # front parking stalls (2.6 m wide, 5.5 m deep) on both sides of the aisle
    for row_y0, row_y1 in ((-24.5, -19.0), (-14.5, -9.0)):
        xs = x0 + 3.0
        while xs + 2.6 <= x1 - 3.0:
            S.box("mat_white", xs, row_y0, z, xs + 0.1, row_y1, z + 0.004, faces=("+z",))
            xs += 2.6
        S.box("mat_white", xs, row_y0, z, xs + 0.1, row_y1, z + 0.004, faces=("+z",))
    # accessible stalls marking near entrance
    S.box("mat_white", 20, -13.0, z, 31, -12.9, z + 0.004, faces=("+z",))
    # west stalls
    yy = -6.0
    while yy + 2.6 <= 34:
        S.box("mat_white", x0 + 0.5, yy, z, x0 + 6.0, yy + 0.1, z + 0.004, faces=("+z",))
        yy += 2.6
    # drive aisle centre arrows / stop bar at the secure gate
    S.box("mat_white", 61.2, 45.0, z, 71.8, 45.4, z + 0.004, faces=("+z",))
    # covered parking structure (carport) behind the building
    cz = 3.6
    S.box({"+z": "lspd_metal_dark", "-z": "lspd_metal", "+x": "lspd_ext_metal", "-x": "lspd_ext_metal",
           "+y": "lspd_ext_metal", "-y": "lspd_ext_metal"}, -1.0, 37.0, cz, 14.5, 52.0, cz + 0.3)
    C.box(-1.0, 37.0, cz, 14.5, 52.0, cz + 0.3, col="METAL_SOLID_MEDIUM")
    for px_ in (-0.6, 7.0, 14.1):
        for py_ in (37.4, 51.6):
            S.box("lspd_metal_dark", px_ - 0.15, py_ - 0.15, z, px_ + 0.15, py_ + 0.15, cz)
            C.box(px_ - 0.15, py_ - 0.15, z, px_ + 0.15, py_ + 0.15, cz, col="METAL_SOLID_MEDIUM")
    for k in range(5):
        S.box("mat_white", -1.0, 38.5 + k * 2.8, z, 4.5, 38.6 + k * 2.8, z + 0.004, faces=("+z",))
        S.box("mat_white", 8.5, 38.5 + k * 2.8, z, 14.0, 38.6 + k * 2.8, z + 0.004, faces=("+z",))
        S.box("emi_light", 2.0 + (k % 2) * 8, 39 + k * 2.6, cz - 0.02, 3.2 + (k % 2) * 8, 39.3 + k * 2.6, cz, faces=("-z",))
    S.light(3, 42, cz - 0.3, (240, 244, 255), 3.0, 8.0, 12.0)
    S.light(11, 42, cz - 0.3, (240, 244, 255), 3.0, 8.0, 12.0)
    S.light(3, 48, cz - 0.3, (240, 244, 255), 3.0, 8.0, 12.0)
    S.light(11, 48, cz - 0.3, (240, 244, 255), 3.0, 8.0, 12.0)
    # secure yard perimeter wall (north + east), with gate openings
    wall_h = 2.6
    segments = [((x0, y1 - 0.3), (x1, y1)),                 # north edge
                ((x1 - 0.3, 22.0), (x1, 40.0)),              # east edge (gap 40..50 = gate, gap <22 = open front)
                ((x1 - 0.3, 50.0), (x1, y1)),
                ((x0, 36.3), (x0 + 0.3, y1)),                # west edge behind carport
                ((61.0, 21.7), (x1, 22.0))]                  # short return wall
    for (a, b) in segments:
        S.box({"+x": "lspd_ext_panel", "-x": "lspd_ext_panel", "+y": "lspd_ext_panel", "-y": "lspd_ext_panel",
               "+z": "lspd_metal_dark"}, a[0], a[1], z - 0.3, b[0], b[1], z + wall_h)
        C.box(a[0], a[1], z - 0.3, b[0], b[1], z + wall_h, col="CONCRETE")
    # gate barriers (base game props)
    sh.props_ext.append(dict(model="prop_sec_barrier_ld_01a", pos=(x1 - 0.6, 49.6, z), heading=90.0, lod=150))
    sh.props_ext.append(dict(model="prop_sec_barrier_ld_01a", pos=(61.6, 22.6, z), heading=0.0, lod=150))
    # bollards in front of the entrance
    for k in range(9):
        bx = 22.0 + k * 1.5
        S.cylinder("lspd_metal_dark", bx, -6.6, z, z + 0.95, 0.11, 10)
        S.cylinder("emi_light", bx, -6.6, z + 0.8, z + 0.86, 0.115, 10, caps=False)
        C.box(bx - 0.11, -6.71, z, bx + 0.11, -6.49, z + 0.95, col="METAL_SOLID_MEDIUM")
    # ground skirt around the site edge (hides terrain gaps)
    for (a, b, c, d) in ((x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)):
        if a == c:
            S.box("lspd_concrete", a - 0.05, b, z - 4.0, a, d, z - 0.3, faces=("-x" if a == x0 else "+x",))
        else:
            S.box("lspd_concrete", a, b - 0.05, z - 4.0, c, b, z - 0.3, faces=("-y" if b == y0 else "+y",))
    # props: flags, benches, bins, lamp posts, bike rack
    sh.props_ext += [
        dict(model="prop_flagpole_1a", pos=(19.0, -7.8, z), heading=0, lod=250),
        dict(model="prop_flagpole_1a", pos=(37.0, -7.8, z), heading=0, lod=250),
        dict(model="prop_bench_01a", pos=(15.0, -2.2, z), heading=180, lod=100),
        dict(model="prop_bench_01a", pos=(41.0, -2.2, z), heading=180, lod=100),
        dict(model="prop_bin_05a", pos=(20.3, -1.2, z), heading=0, lod=80),
        dict(model="prop_bin_05a", pos=(35.7, -1.2, z), heading=0, lod=80),
    ]
    for lx in range(-10, 72, 16):
        sh.props_ext.append(dict(model="prop_streetlight_01", pos=(lx, -16.75, z), heading=0, lod=300))
    for ly in range(4, 36, 12):
        sh.props_ext.append(dict(model="prop_streetlight_01", pos=(-6.0, ly, z), heading=90, lod=300))


def build_all():
    sh = Shell()
    for lv in range(4):
        build_walls(sh, lv)
    build_floors(sh)
    build_stairs(sh)
    build_exterior(sh)
    build_site(sh)
    return sh


if __name__ == "__main__":
    sh = build_all()
    for k, m in sh.int.items():
        print(k, m.tri_count(), "tris", len(m.lights), "lights")
    print("ext", sh.ext.tri_count(), "site", sh.site.tri_count(), "lod", sh.lod.tri_count())
    print("col int", len(sh.col_int.tris), "col ext", len(sh.col_ext.tris))
    print("portals", len(sh.portals), "doors", len(sh.doors))
