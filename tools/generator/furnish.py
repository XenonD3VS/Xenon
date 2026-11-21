"""Interior furnishing: custom-built fixtures (geometry + collision) and base-game props.

Base-game prop convention used here: pivot at the bottom centre, front facing local -Y.
`heading_to(dx, dy)` returns the heading that makes a prop's front face the given direction.
"""
import math
import random

import building as B
import layout as LY
import materials as M
import textures as T

rnd = random.Random(2026)

CHAIRS_OFFICE = ["prop_off_chair_01", "prop_off_chair_04", "prop_off_chair_05", "prop_off_chair_03"]
CHAIRS_VISITOR = ["prop_chair_01a", "prop_chair_02"]
PLANTS = ["prop_plant_int_01a", "prop_plant_int_01b", "prop_plant_int_02a", "prop_plant_int_03a", "prop_plant_int_04a"]
BINS = ["prop_bin_05a", "prop_cs_bin_02", "prop_bin_10a"]


def heading_to(dx, dy):
    return math.degrees(math.atan2(dx, -dy)) % 360.0


class Room:
    """Furnishing context for one room."""

    def __init__(self, sh, room, rect=None):
        self.sh = sh
        self.r = room
        self.mesh = sh.imesh(room)
        self.rid = sh.rid(room)
        self.z = LY.LEVEL_Z[room.level]
        self.rect = rect or max(room.rects, key=lambda a: (a[2] - a[0]) * (a[3] - a[1]))
        x0, y0, x1, y1 = self.rect
        m = 0.09
        self.x0, self.y0, self.x1, self.y1 = x0 + m, y0 + m, x1 - m, y1 - m
        self.cx, self.cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.w, self.d = x1 - x0, y1 - y0
        self.ceil = B.room_ceil(room)
        self.blocked = []
        # door clearance zones
        for d in LY.DOORS:
            if d.level != room.level:
                continue
            r_ = d.width / 2 + 0.75
            if d.kind == "vehicle":
                r_ = d.width / 2 + 2.5
            self.blocked.append((d.x - r_, d.y - r_, d.x + r_, d.y + r_, 0))
        for w in LY.WINDOWS:
            if w.level != room.level or w.kind in ("counter",):
                continue
            if w.orient == "h":
                self.blocked.append((w.a, w.pos - 0.7, w.b, w.pos + 0.7, w.sill))
            else:
                self.blocked.append((w.pos - 0.7, w.a, w.pos + 0.7, w.b, w.sill))

    # ------------------------------------------------------------ checks
    def free(self, x0, y0, x1, y1, h=1.0):
        if x0 < self.x0 - 1e-3 or y0 < self.y0 - 1e-3 or x1 > self.x1 + 1e-3 or y1 > self.y1 + 1e-3:
            return False
        for (a, b, c, d, sill) in self.blocked:
            if x0 < c and a < x1 and y0 < d and b < y1 and h > sill - 0.05:
                return False
        return True

    def occupy(self, x0, y0, x1, y1, h=3.0):
        self.blocked.append((x0, y0, x1, y1, -1))

    # ------------------------------------------------------------ primitives
    def box(self, mat, x0, y0, z0, x1, y1, z1, col=True, faces=None, uv=None, colmat=None):
        kw = {}
        if faces:
            kw["faces"] = faces
        self.mesh.box(mat, x0, y0, self.z + z0, x1, y1, self.z + z1, uv=uv, **kw)
        if col:
            m = mat if isinstance(mat, str) else next(iter(mat.values()))
            self.sh.col_int.box(x0, y0, self.z + z0, x1, y1, self.z + z1, col=colmat or M.get(m).col, room=self.rid)

    def cyl(self, mat, x, y, z0, z1, r, seg=12, col=True):
        self.mesh.cylinder(mat, x, y, self.z + z0, self.z + z1, r, seg)
        if col:
            self.sh.col_int.box(x - r, y - r, self.z + z0, x + r, y + r, self.z + z1, col=M.get(mat).col, room=self.rid)

    def prop(self, model, x, y, z=0.0, heading=0.0, lod=40.0):
        self.sh.props_int.append(dict(model=model, pos=(x, y, self.z + z), heading=heading % 360.0,
                                      mlo_room=self.r.mlo_room, lod=lod))

    def image(self, mat, wall, a0, a1, z0, z1, off=0.012, thick=0.02, frame="lspd_metal_dark"):
        """Flat picture/board on a wall. wall in {'n','s','e','w'} relative to this room's rect."""
        x0, y0, x1, y1 = self.rect
        if wall == "n":
            yy = y1 - B.LY.INT_T / 2 - off
            self.box(frame, a0 - 0.03, yy - thick, z0 - 0.03, a1 + 0.03, yy, z1 + 0.03, col=False)
            self.mesh.box(mat, a0, yy - thick - 0.002, self.z + z0, a1, yy - thick, self.z + z1, faces=("-y",))
        elif wall == "s":
            yy = y0 + B.LY.INT_T / 2 + off
            self.box(frame, a0 - 0.03, yy, z0 - 0.03, a1 + 0.03, yy + thick, z1 + 0.03, col=False)
            self.mesh.box(mat, a0, yy + thick, self.z + z0, a1, yy + thick + 0.002, self.z + z1, faces=("+y",))
        elif wall == "e":
            xx = x1 - B.LY.INT_T / 2 - off
            self.box(frame, xx - thick, a0 - 0.03, z0 - 0.03, xx, a1 + 0.03, z1 + 0.03, col=False)
            self.mesh.box(mat, xx - thick - 0.002, a0, self.z + z0, xx - thick, a1, self.z + z1, faces=("-x",))
        else:
            xx = x0 + B.LY.INT_T / 2 + off
            self.box(frame, xx, a0 - 0.03, z0 - 0.03, xx + thick, a1 + 0.03, z1 + 0.03, col=False)
            self.mesh.box(mat, xx + thick, a0, self.z + z0, xx + thick + 0.002, a1, self.z + z1, faces=("+x",))

    def wall_free(self, wall, a0, a1, z0, z1):
        """True when no door/window opening on that wall overlaps the span (for wall-mounted items)."""
        x0, y0, x1, y1 = self.rect
        for d in LY.DOORS:
            if d.level != self.r.level:
                continue
            if wall in ("n", "s") and d.orient == "h" and abs(d.y - (y1 if wall == "n" else y0)) < 0.05:
                if a0 < d.x + d.width / 2 + 0.15 and d.x - d.width / 2 - 0.15 < a1 and z0 < d.height + 0.1:
                    return False
            if wall in ("e", "w") and d.orient == "v" and abs(d.x - (x1 if wall == "e" else x0)) < 0.05:
                if a0 < d.y + d.width / 2 + 0.15 and d.y - d.width / 2 - 0.15 < a1 and z0 < d.height + 0.1:
                    return False
        for w in LY.WINDOWS:
            if w.level != self.r.level:
                continue
            if wall in ("n", "s") and w.orient == "h" and abs(w.pos - (y1 if wall == "n" else y0)) < 0.05:
                if a0 < w.b + 0.1 and w.a - 0.1 < a1 and z0 < w.head and w.sill < z1:
                    return False
            if wall in ("e", "w") and w.orient == "v" and abs(w.pos - (x1 if wall == "e" else x0)) < 0.05:
                if a0 < w.b + 0.1 and w.a - 0.1 < a1 and z0 < w.head and w.sill < z1:
                    return False
        return True

    def try_image(self, mat, wall, a0, a1, z0, z1, **kw):
        if self.wall_free(wall, a0, a1, z0, z1):
            self.image(mat, wall, a0, a1, z0, z1, **kw)
            return True
        return False

    # ------------------------------------------------------------ furniture
    def monitor(self, x, y, facing, z=0.76, screen="emi_desk", w=0.56, h=0.34):
        """Custom flat monitor on a stand; facing = (dx,dy) unit axis the screen faces."""
        dx, dy = facing
        t = 0.03
        zs = z + 0.12
        if dx == 0:
            y0, y1 = y - t / 2, y + t / 2
            self.box("mat_black", x - w / 2, y0, zs, x + w / 2, y1, zs + h, col=False)
            f = "+y" if dy > 0 else "-y"
            uv = [(1, 1), (0, 1), (0, 0), (1, 0)] if dy > 0 else [(0, 1), (1, 1), (1, 0), (0, 0)]
            yy = y1 if dy > 0 else y0
            self.mesh.box(screen, x - w / 2 + 0.015, min(yy, yy + dy * 0.002), self.z + zs + 0.015,
                          x + w / 2 - 0.015, max(yy, yy + dy * 0.002), self.z + zs + h - 0.015, faces=(f,))
            self.box("mat_black", x - 0.03, y - dy * 0.06 - 0.03, z, x + 0.03, y - dy * 0.06 + 0.03, zs + 0.05, col=False)
            self.box("mat_black", x - 0.12, y - dy * 0.06 - 0.09, z, x + 0.12, y - dy * 0.06 + 0.09, z + 0.015, col=False)
        else:
            x0, x1 = x - t / 2, x + t / 2
            self.box("mat_black", x0, y - w / 2, zs, x1, y + w / 2, zs + h, col=False)
            f = "+x" if dx > 0 else "-x"
            uv = [(0, 1), (1, 1), (1, 0), (0, 0)] if dx > 0 else [(1, 1), (0, 1), (0, 0), (1, 0)]
            xx = x1 if dx > 0 else x0
            self.mesh.box(screen, min(xx, xx + dx * 0.002), y - w / 2 + 0.015, self.z + zs + 0.015,
                          max(xx, xx + dx * 0.002), y + w / 2 - 0.015, self.z + zs + h - 0.015, faces=(f,))
            self.box("mat_black", x - dx * 0.06 - 0.03, y - 0.03, z, x - dx * 0.06 + 0.03, y + 0.03, zs + 0.05, col=False)
            self.box("mat_black", x - dx * 0.06 - 0.09, y - 0.12, z, x - dx * 0.06 + 0.09, y + 0.12, z + 0.015, col=False)

    def keyboard(self, x, y, facing, z=0.76):
        dx, dy = facing
        if dx == 0:
            self.box("mat_black", x - 0.22, y - 0.07, z, x + 0.22, y + 0.07, z + 0.025, col=False)
            self.box("mat_black", x + 0.3, y - 0.05, z, x + 0.36, y + 0.05, z + 0.03, col=False)
        else:
            self.box("mat_black", x - 0.07, y - 0.22, z, x + 0.07, y + 0.22, z + 0.025, col=False)
            self.box("mat_black", x - 0.05, y + 0.3, z, x + 0.05, y + 0.36, z + 0.03, col=False)

    def papers(self, x, y, z=0.76, n=None):
        n = n if n is not None else rnd.randint(1, 3)
        for k in range(n):
            ox, oy = rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05)
            h = rnd.uniform(0.01, 0.05)
            mat = rnd.choice(["mat_white", "mat_white", "lspd_metal_navy", "mat_red"])
            self.box(mat, x + ox - 0.11, y + oy - 0.15, z + k * 0.05, x + ox + 0.11, y + oy + 0.15, z + k * 0.05 + h, col=False)

    def desk(self, x, y, w, d, facing, top="lspd_laminate", chair=True, monitors=1, phone=True, pc=True,
             screen="emi_desk", body="lspd_metal_dark", chair_model=None, h=0.76):
        """Desk centred at (x, y); `facing` = direction the seated person looks (screen faces opposite)."""
        dx, dy = facing
        if dx == 0:
            bx0, by0, bx1, by1 = x - w / 2, y - d / 2, x + w / 2, y + d / 2
        else:
            bx0, by0, bx1, by1 = x - d / 2, y - w / 2, x + d / 2, y + w / 2
        if not self.free(bx0, by0, bx1, by1, 1.0):
            return False
        self.occupy(bx0, by0, bx1, by1)
        self.box(top, bx0, by0, h - 0.04, bx1, by1, h)
        # side panels + modesty panel
        lt = 0.04
        if dx == 0:
            self.box(body, bx0, by0 + 0.03, 0, bx0 + lt, by1 - 0.03, h - 0.04)
            self.box(body, bx1 - lt, by0 + 0.03, 0, bx1, by1 - 0.03, h - 0.04)
            back = by1 - 0.06 if dy > 0 else by0 + 0.02
            self.box(body, bx0 + lt, back, 0.25, bx1 - lt, back + 0.04, h - 0.04)
            # drawer pedestal
            self.box({"+x": body, "-x": body, "+y": top, "-y": top, "+z": body}, bx1 - 0.5, by0 + 0.08, 0, bx1 - lt, by1 - 0.08, 0.62)
        else:
            self.box(body, bx0 + 0.03, by0, 0, bx1 - 0.03, by0 + lt, h - 0.04)
            self.box(body, bx0 + 0.03, by1 - lt, 0, bx1 - 0.03, by1, h - 0.04)
            back = bx1 - 0.06 if dx > 0 else bx0 + 0.02
            self.box(body, back, by0 + lt, 0.25, back + 0.04, by1 - lt, h - 0.04)
            self.box({"+x": top, "-x": top, "+y": body, "-y": body, "+z": body}, bx0 + 0.08, by1 - 0.5, 0, bx1 - 0.08, by1 - lt, 0.62)
        # screen(s) at the far side, facing the user
        far = 0.65 * d / 2
        for k in range(monitors):
            off = (k - (monitors - 1) / 2) * 0.6
            mx = x + (off if dx == 0 else dx * far)
            my = y + (dy * far if dx == 0 else off)
            self.monitor(mx, my, (-dx, -dy), z=h, screen=screen)
        kx, ky = x - dx * 0.05, y - dy * 0.05
        self.keyboard(kx, ky, facing, z=h)
        if phone:
            px_ = x + (w / 2 - 0.25 if dx == 0 else dx * 0.05)
            py_ = y + (dy * 0.05 if dx == 0 else w / 2 - 0.25)
            self.prop("prop_office_phone_tnt", px_, py_, h, heading_to(-dx, -dy), lod=25)
        if pc:
            # tower PC under the desk next to the pedestal
            if dx == 0:
                self.box("mat_black", bx0 + 0.15, y - 0.22, 0, bx0 + 0.35, y + 0.22, 0.45, col=False)
            else:
                self.box("mat_black", x - 0.22, by0 + 0.15, 0, x + 0.22, by0 + 0.35, 0.45, col=False)
        # paperwork
        if rnd.random() < 0.8:
            ppx = x + (-(w / 2 - 0.3) if dx == 0 else 0.0)
            ppy = y + (0.0 if dx == 0 else -(w / 2 - 0.3))
            self.papers(ppx, ppy, h)
        if chair:
            cx, cy = x - dx * (d / 2 + 0.35), y - dy * (d / 2 + 0.35)
            self.prop(chair_model or rnd.choice(CHAIRS_OFFICE), cx, cy, 0, heading_to(dx, dy), lod=35)
        return True

    def shelf(self, x0, y0, x1, y1, h=2.1, levels=5, mat="lspd_metal", boxes=True, files=False):
        if not self.free(x0, y0, x1, y1, h):
            return False
        self.occupy(x0, y0, x1, y1)
        t = 0.04
        for (a, b) in ((x0, y0), (x1 - t, y0), (x0, y1 - t), (x1 - t, y1 - t)):
            self.box(mat, a, b, 0, a + t, b + t, h, col=False)
        self.sh.col_int.box(x0, y0, self.z, x1, y1, self.z + h, col="METAL_SOLID_MEDIUM", room=self.rid)
        for k in range(levels):
            zz = 0.12 + k * (h - 0.2) / (levels - 1)
            self.box(mat, x0, y0, zz - 0.02, x1, y1, zz, col=False)
            if k < levels - 1 and (boxes or files):
                long_x = (x1 - x0) >= (y1 - y0)
                L = (x1 - x0) if long_x else (y1 - y0)
                n = int(L // 0.45)
                for i in range(n):
                    if rnd.random() < 0.18:
                        continue
                    a = (x0 if long_x else y0) + 0.05 + i * 0.45
                    bh = rnd.uniform(0.22, min(0.34, (h - 0.2) / (levels - 1) - 0.06))
                    if files:
                        mat_b = rnd.choice(["lspd_metal_navy", "mat_white", "mat_red", "lspd_laminate_dark"])
                        if long_x:
                            self.box(mat_b, a, y0 + 0.04, zz, a + 0.38, y1 - 0.04, zz + bh, col=False)
                        else:
                            self.box(mat_b, x0 + 0.04, a, zz, x1 - 0.04, a + 0.38, zz + bh, col=False)
                    else:
                        uv = None
                        if long_x:
                            self.box("img_cardboard", a, y0 + 0.03, zz, a + 0.4, y1 - 0.03, zz + bh, col=False)
                        else:
                            self.box("img_cardboard", x0 + 0.03, a, zz, x1 - 0.03, a + 0.4, zz + bh, col=False)
        return True

    def lockers(self, x0, y0, x1, y1, facing, h=1.95):
        if not self.free(x0, y0, x1, y1, h):
            return False
        self.occupy(x0, y0, x1, y1)
        dx, dy = facing
        f = {(0, 1): "+y", (0, -1): "-y", (1, 0): "+x", (-1, 0): "-x"}[(dx, dy)]
        others = [k for k in ("+x", "-x", "+y", "-y", "+z") if k != f]
        self.box("lspd_metal_navy", x0, y0, 0.12, x1, y1, h, faces=others)
        L = (x1 - x0) if dx == 0 else (y1 - y0)
        n = max(1, int(round(L / 1.2)))
        seg = L / n
        for i in range(n):
            if dx == 0:
                a, b = x0 + i * seg, x0 + (i + 1) * seg
                uv = [(0, 1), (1, 1), (1, 0), (0, 0)] if dy < 0 else [(1, 1), (0, 1), (0, 0), (1, 0)]
                self.mesh.box("img_locker", a, y0, self.z + 0.12, b, y1, self.z + h, faces=(f,))
            else:
                a, b = y0 + i * seg, y0 + (i + 1) * seg
                uv = [(0, 1), (1, 1), (1, 0), (0, 0)] if dx > 0 else [(1, 1), (0, 1), (0, 0), (1, 0)]
                self.mesh.box("img_locker", x0, a, self.z + 0.12, x1, b, self.z + h, faces=(f,))
        self.box("mat_black", x0, y0, 0, x1, y1, 0.12, faces=(f, "+z"), col=False)
        return True

    def bench(self, x0, y0, x1, y1, h=0.45, seat="lspd_wood_light", leg="lspd_metal"):
        if not self.free(x0, y0, x1, y1, h):
            return False
        self.occupy(x0, y0, x1, y1)
        self.box(seat, x0, y0, h - 0.05, x1, y1, h)
        long_x = (x1 - x0) > (y1 - y0)
        L = (x1 - x0) if long_x else (y1 - y0)
        for t in (0.15, L - 0.2):
            if long_x:
                self.box(leg, x0 + t, y0 + 0.05, 0, x0 + t + 0.05, y1 - 0.05, h - 0.05, col=False)
            else:
                self.box(leg, x0 + 0.05, y0 + t, 0, x1 - 0.05, y0 + t + 0.05, h - 0.05, col=False)
        return True

    def table(self, x0, y0, x1, y1, h=0.75, top="lspd_wood_veneer", leg="lspd_metal_dark"):
        if not self.free(x0, y0, x1, y1, h):
            return False
        self.occupy(x0, y0, x1, y1)
        self.box(top, x0, y0, h - 0.05, x1, y1, h)
        for (a, b) in ((x0 + 0.08, y0 + 0.08), (x1 - 0.14, y0 + 0.08), (x0 + 0.08, y1 - 0.14), (x1 - 0.14, y1 - 0.14)):
            self.box(leg, a, b, 0, a + 0.06, b + 0.06, h - 0.05, col=False)
        self.sh.col_int.box(x0, y0, self.z, x1, y1, self.z + h, col="WOOD_SOLID_MEDIUM", room=self.rid)
        return True

    def chairs_around(self, x0, y0, x1, y1, spacing=0.75, model=None, ends=True):
        model = model or rnd.choice(CHAIRS_OFFICE)
        n = max(1, int((x1 - x0 - 0.2) // spacing)) if (x1 - x0) > (y1 - y0) else max(1, int((y1 - y0 - 0.2) // spacing))
        if (x1 - x0) >= (y1 - y0):
            for i in range(n):
                cx = x0 + (x1 - x0) * (i + 0.5) / n
                self.prop(model, cx, y0 - 0.4, 0, heading_to(0, 1))
                self.prop(model, cx, y1 + 0.4, 0, heading_to(0, -1))
            if ends:
                self.prop(model, x0 - 0.45, (y0 + y1) / 2, 0, heading_to(1, 0))
                self.prop(model, x1 + 0.45, (y0 + y1) / 2, 0, heading_to(-1, 0))
        else:
            for i in range(n):
                cy = y0 + (y1 - y0) * (i + 0.5) / n
                self.prop(model, x0 - 0.4, cy, 0, heading_to(1, 0))
                self.prop(model, x1 + 0.4, cy, 0, heading_to(-1, 0))
            if ends:
                self.prop(model, (x0 + x1) / 2, y0 - 0.45, 0, heading_to(0, 1))
                self.prop(model, (x0 + x1) / 2, y1 + 0.45, 0, heading_to(0, -1))

    def counter(self, x0, y0, x1, y1, h=1.05, front="lspd_metal_navy", top="lspd_laminate_dark", front_face="-y"):
        if not self.free(x0, y0, x1, y1, h):
            return False
        self.occupy(x0, y0, x1, y1)
        faces = {k: front for k in ("+x", "-x", "+y", "-y")}
        self.box(faces, x0, y0, 0, x1, y1, h - 0.04)
        self.box(top, x0 - 0.03, y0 - 0.03, h - 0.04, x1 + 0.03, y1 + 0.03, h)
        return True

    def plant(self, x, y):
        if self.free(x - 0.3, y - 0.3, x + 0.3, y + 0.3, 1.5):
            self.prop(rnd.choice(PLANTS), x, y, 0, rnd.uniform(0, 360), lod=40)
            self.occupy(x - 0.3, y - 0.3, x + 0.3, y + 0.3)

    def bin(self, x, y):
        if self.free(x - 0.2, y - 0.2, x + 0.2, y + 0.2, 0.6):
            self.prop(rnd.choice(BINS), x, y, 0, rnd.uniform(0, 360), lod=25)

    def corner_plants(self):
        for (x, y) in ((self.x0 + 0.4, self.y0 + 0.4), (self.x1 - 0.4, self.y1 - 0.4)):
            self.plant(x, y)

    def ceiling_cam(self, x, y, heading):
        self.prop("prop_cctv_cam_01a", x, y, self.ceil - 0.05, heading, lod=40)

    def filing(self, x, y, facing, n=2, h=1.32):
        """Row of 4-drawer filing cabinets against a wall."""
        dx, dy = facing
        w, d = 0.47 * n, 0.62
        if dx == 0:
            x0, y0, x1, y1 = x - w / 2, y - d / 2, x + w / 2, y + d / 2
        else:
            x0, y0, x1, y1 = x - d / 2, y - w / 2, x + d / 2, y + w / 2
        if not self.free(x0, y0, x1, y1, h):
            return False
        self.occupy(x0, y0, x1, y1)
        self.box("lspd_metal_dark", x0, y0, 0, x1, y1, h)
        f = {(0, 1): "+y", (0, -1): "-y", (1, 0): "+x", (-1, 0): "-x"}[(dx, dy)]
        for i in range(n):
            for k in range(4):
                zz = 0.05 + k * (h - 0.08) / 4
                if dx == 0:
                    a = x0 + i * 0.47
                    yy = y1 if dy > 0 else y0
                    self.box("lspd_metal", a + 0.17, min(yy, yy + dy * 0.03), zz + 0.2, a + 0.3, max(yy, yy + dy * 0.03), zz + 0.23, col=False)
                else:
                    a = y0 + i * 0.47
                    xx = x1 if dx > 0 else x0
                    self.box("lspd_metal", min(xx, xx + dx * 0.03), a + 0.17, zz + 0.2, max(xx, xx + dx * 0.03), a + 0.3, zz + 0.23, col=False)
        return True

    def sofa(self, x0, y0, x1, y1, facing, mat="lspd_fabric"):
        if not self.free(x0, y0, x1, y1, 0.85):
            return False
        self.occupy(x0, y0, x1, y1)
        dx, dy = facing
        self.box(mat, x0, y0, 0.0, x1, y1, 0.42)
        bt = 0.22
        if dx == 0:
            by = y1 - bt if dy < 0 else y0
            if dy > 0:
                by = y0
            else:
                by = y1 - bt
            self.box(mat, x0, by, 0.42, x1, by + bt, 0.85)
            self.box(mat, x0, y0, 0.42, x0 + 0.18, y1, 0.62)
            self.box(mat, x1 - 0.18, y0, 0.42, x1, y1, 0.62)
        else:
            bx = x0 if dx > 0 else x1 - bt
            self.box(mat, bx, y0, 0.42, bx + bt, y1, 0.85)
            self.box(mat, x0, y0, 0.42, x1, y0 + 0.18, 0.62)
            self.box(mat, x0, y1 - 0.18, 0.42, x1, y1, 0.62)
        return True

    def tv_wall(self, wall, a0, a1, z0, z1, screen="emi_cad"):
        return self.try_image(screen, wall, a0, a1, z0, z1, frame="mat_black", thick=0.05)


# ======================================================================= signs
def door_signs(sh):
    for d in LY.DOORS:
        if d.kind in ("vehicle", "auto", "open"):
            continue
        s1, s2 = LY.door_sides(d)
        for room, other, side in ((s1, s2, +1), (s2, s1, -1)):
            # sign of `room` placed on the `other` side of the wall
            if room is None or other is None or not room.sign or room.rtype == "corridor":
                continue
            if room.rtype in ("cell", "cell_hs"):
                continue
            mesh = sh.imesh(other)
            z = LY.LEVEL_Z[d.level] + d.height + 0.12
            w, h = 0.56, 0.28
            if z + h > LY.LEVEL_Z[d.level] + B.room_ceil(other) - 0.05:
                z = LY.LEVEL_Z[d.level] + B.room_ceil(other) - h - 0.08
            off = LY.INT_T / 2 + 0.005
            if d.orient == "h":
                # other room lies on side -side*... : s1 is below (y-), s2 above (y+)
                if other is s1:
                    B.sign_quad(mesh, room.sign, None, d.x - w / 2, d.y - off - 0.02, z, w, h, facing="-y")
                else:
                    B.sign_quad(mesh, room.sign, None, d.x - w / 2, d.y + off, z, w, h, facing="+y")
            else:
                if other is s1:
                    B.sign_quad(mesh, room.sign, None, d.x - off - 0.02, d.y - w / 2, z, w, h, facing="-x")
                else:
                    B.sign_quad(mesh, room.sign, None, d.x + off, d.y - w / 2, z, w, h, facing="+x")


# ================================================================= room types
def f_lobby(c):
    x0, y0, x1, y1 = c.rect   # 10..48 x 0..12
    # waiting area: benches + waiting seats in two groups
    for gx in (13.0, 41.0):
        for row in range(3):
            yy = 3.2 + row * 2.2
            c.prop("prop_waiting_seat_01", gx, yy, 0, heading_to(0, 1), lod=40)
            c.prop("prop_waiting_seat_01", gx + 1.6, yy, 0, heading_to(0, 1), lod=40)
            c.occupy(gx - 0.5, yy - 0.5, gx + 2.1, yy + 0.5)
        c.table(gx + 0.1, 9.4, gx + 1.5, 10.0, h=0.45, top="lspd_laminate_dark")
    # logo rug at the entrance
    c.mesh.box("img_rug", 25.5, 4.2, c.z + 0.002, 30.5, 9.2, c.z + 0.008, faces=("+z",))
    # security screening lane in front of the checkpoint door
    c.box("lspd_metal_dark", 34.3, 9.2, 0, 34.45, 11.2, 2.2)
    c.box("lspd_metal_dark", 37.05, 9.2, 0, 37.2, 11.2, 2.2)
    c.box("lspd_metal_dark", 34.3, 9.2, 2.1, 37.2, 11.2, 2.25, col=False)
    c.mesh.box("emi_light", 34.5, 9.4, c.z + 2.08, 37.0, 11.0, c.z + 2.1, faces=("-z",))
    # x-ray conveyor beside the lane
    c.box({"+z": "mat_black", "+x": "lspd_metal", "-x": "lspd_metal", "+y": "lspd_metal", "-y": "lspd_metal"}, 31.8, 8.6, 0, 33.6, 9.4, 0.8)
    c.box("lspd_metal", 32.2, 8.6, 0.8, 33.2, 9.4, 1.55)
    c.monitor(32.7, 8.0, (0, -1), z=1.0, screen="emi_cctv")
    c.occupy(31.6, 7.6, 37.4, 11.6)
    c.prop("prop_cs_office_chair", 32.7, 7.3, 0, heading_to(0, 1))
    # stanchions to queue for the counters
    for xx in (22.5, 27.0, 33.0):
        c.cyl("lspd_metal", xx, 9.0, 0, 0.95, 0.04, 8, col=False)
        c.cyl("lspd_metal", xx, 9.0, 0, 0.03, 0.18, 12, col=False)
    # accent cladding: wood band above the counters, navy wainscot below
    yy = 12 - LY.INT_T / 2 - 0.012
    c.mesh.box("lspd_wood_veneer", 10.1, yy - 0.01, c.z + 2.55, 34.0, yy, c.z + 3.6, faces=("-y",))
    c.mesh.box("lspd_metal_navy", 10.1, yy - 0.01, c.z + 0.1, 34.0, yy, c.z + 1.0, faces=("-y",))
    c.mesh.box("lspd_metal", 10.1, yy - 0.03, c.z + 1.0, 34.0, yy, c.z + 1.03, faces=("-y", "+z"))
    c.mesh.box("lspd_metal_navy", 37.6, yy - 0.01, c.z + 2.55, 47.9, yy, c.z + 3.6, faces=("-y",))
    # big wall logo between checkpoint and watch commander
    c.try_image("img_wall_logo", "n", 40.8, 44.2, 0.4, 3.3, thick=0.04)
    # info + wanted boards on the side walls
    c.try_image("img_infoboard", "w", 0.8, 2.6, 1.2, 2.1)
    c.try_image("img_wanted", "e", 0.6, 1.7, 1.2, 2.6)
    c.try_image("img_wanted", "e", 10.6, 11.5, 1.2, 2.4)
    # water cooler, plants, bins
    c.prop("prop_watercooler", 46.6, 11.3, 0, heading_to(0, -1))
    c.plant(10.6, 11.3); c.plant(47.3, 0.8); c.plant(10.6, 0.8)
    c.bin(20.6, 0.7); c.bin(36.0, 0.7)
    c.ceiling_cam(10.4, 0.4, 315); c.ceiling_cam(47.6, 0.4, 45); c.ceiling_cam(28.0, 11.6, 180)
    # hanging department sign over the front counter
    B.sign_quad(c.mesh, "RECEPTION", None, 26.6, 10.0, c.z + 2.8, 1.6, 0.8, facing="-y", emissive=True)
    B.sign_quad(c.mesh, "CITIZEN SERVICES", None, 15.2, 10.0, c.z + 2.8, 1.6, 0.8, facing="-y", emissive=True)


def f_counter_room(c, counters):
    """Staff side of the public counters (front desk / records)."""
    for (a, b) in counters:
        # staff work counter behind the glass
        c.box({"+x": "lspd_laminate", "-x": "lspd_laminate", "+y": "lspd_laminate", "-y": "lspd_laminate", "+z": "lspd_laminate_dark"},
              a, c.y0, 0, b, c.y0 + 0.65, 0.95)
        n = int((b - a) // 1.2)
        for i in range(n):
            xx = a + (b - a) * (i + 0.5) / n
            c.monitor(xx, c.y0 + 0.25, (0, 1), z=0.95)
            c.keyboard(xx, c.y0 + 0.5, (0, 1), z=0.95)
            c.prop("prop_cs_office_chair", xx, c.y0 + 1.15, 0, heading_to(0, -1))
        c.occupy(a, c.y0, b, c.y0 + 1.5)
    c.prop("prop_printer_01", c.x1 - 0.5, c.y1 - 0.5, 0, heading_to(-1, 0))
    c.filing(c.x0 + 0.35, c.y1 - 1.6, (1, 0), n=2)
    c.filing(c.x0 + 0.35, c.y1 - 3.2, (1, 0), n=2)
    c.try_image("img_whiteboard", "n", c.cx - 1.0, c.cx + 1.0, 1.0, 2.0) or c.try_image("img_whiteboard", "n", c.x0 + 0.4, c.x0 + 2.4, 1.0, 2.0)
    c.bin(c.x1 - 0.4, c.y0 + 1.7)


def f_report(c):
    # public report writing: 3 small desks with kiosks + a clerk desk
    for i in range(3):
        c.desk(1.6 + i * 2.8, 4.6, 1.4, 0.7, (0, 1), chair_model="prop_chair_02", monitors=1, phone=False)
    c.desk(5.0, 1.4, 1.8, 0.8, (0, 1), chair_model="prop_off_chair_04", monitors=2)
    c.prop("prop_chair_01a", 4.3, 2.6, 0, heading_to(0, -1)); c.prop("prop_chair_01a", 5.7, 2.6, 0, heading_to(0, -1))
    c.try_image("img_infoboard", "w", 2.0, 4.0, 1.2, 2.2)
    c.plant(9.4, 5.4); c.bin(0.5, 5.4)


def f_wc(c, men):
    x0, y0, x1, y1 = c.rect
    # stalls along the west wall
    n = 3
    for i in range(n):
        sy0 = y0 + 0.1 + i * 1.6
        c.box("lspd_laminate_dark", x0 + 0.1, sy0 + 1.55, 0.15, x0 + 1.7, sy0 + 1.6, 2.1)
        c.box("lspd_laminate_dark", x0 + 1.65, sy0 + 0.1, 0.15, x0 + 1.7, sy0 + 0.35, 2.1)
        c.box("lspd_laminate_dark", x0 + 1.65, sy0 + 1.25, 0.15, x0 + 1.7, sy0 + 1.6, 2.1)
        c.prop("prop_toilet_01", x0 + 0.45, sy0 + 0.8, 0, heading_to(1, 0), lod=30)
    c.occupy(x0, y0, x0 + 1.9, y1)
    # vanity counter with sinks on the opposite side
    vx = x1 - 0.65 if men else x1 - 0.65
    if c.free(vx - 0.05, y0 + 0.5, x1 - 0.09, y0 + 3.5, 1.0):
        c.box("lspd_stone", vx, y0 + 0.6, 0.82, x1 - 0.09, y0 + 3.4, 0.88)
        c.box("lspd_laminate_dark", vx, y0 + 0.6, 0.0, x1 - 0.09, y0 + 3.4, 0.82, col=True)
        for k in range(3):
            c.prop("prop_sink_06", vx + 0.25, y0 + 1.0 + k * 0.95, 0.0, heading_to(-1, 0), lod=25)
        c.image("mirror", "e", y0 + 0.7, y0 + 3.3, 1.05, 2.0, frame="lspd_metal")
    if men:
        for k in range(2):
            c.box("mat_white", x0 + 2.6 + k * 0.8, y1 - 0.45, 0.45, x0 + 3.0 + k * 0.8, y1 - 0.12, 1.1, col=False)
    c.prop("prop_handdry_01", x1 - 0.15, y1 - 0.9, 1.2, heading_to(-1, 0), lod=20)
    c.bin(x1 - 0.4, y1 - 0.5)


def f_interview_public(c):
    c.table(c.cx - 0.8, c.cy - 0.5, c.cx + 0.8, c.cy + 0.5)
    c.prop("prop_off_chair_04", c.cx, c.cy - 0.95, 0, heading_to(0, 1))
    c.prop("prop_chair_01a", c.cx - 0.4, c.cy + 0.95, 0, heading_to(0, -1))
    c.prop("prop_chair_01a", c.cx + 0.4, c.cy + 0.95, 0, heading_to(0, -1))
    c.monitor(c.cx - 0.3, c.cy - 0.2, (0, -1), z=0.75)
    c.plant(c.x1 - 0.4, c.y1 - 0.4)
    c.try_image("img_infoboard", "w", c.y0 + 1.2, c.y0 + 3.2, 1.1, 2.1)


def f_security(c):
    # CCTV monitoring desk facing a wall of screens on the west wall
    for k in range(3):
        c.tv_wall("w", c.y0 + 0.6 + k * 1.7, c.y0 + 2.1 + k * 1.7, 1.4, 2.3, screen="emi_cctv")
    c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_navy", "-x": "lspd_metal_navy", "+y": "lspd_metal_navy", "-y": "lspd_metal_navy"},
          c.x0 + 1.0, c.y0 + 0.6, 0, c.x0 + 1.8, c.y1 - 1.6, 0.76)
    c.occupy(c.x0, c.y0, c.x0 + 2.4, c.y1 - 1.5)
    for k in range(3):
        c.monitor(c.x0 + 1.25, c.y0 + 1.2 + k * 1.2, (1, 0), z=0.76, screen="emi_cctv")
        c.prop("prop_cs_office_chair", c.x0 + 2.3, c.y0 + 1.2 + k * 1.2, 0, heading_to(-1, 0))
    c.desk(7.5, c.y0 + 1.3, 1.6, 0.8, (0, -1) if False else (0, 1), monitors=2)
    c.lockers(c.x1 - 0.55, c.y0 + 2.4, c.x1 - 0.1, c.y0 + 4.8, (-1, 0))
    c.prop("prop_watercooler_dark", c.x1 - 0.4, c.y1 - 0.4, 0, heading_to(-1, 0))


def f_office_small(c, n=2, exec_=False, title=None):
    """Generic office: n desks + filing + whiteboard + plant."""
    w, d = c.w, c.d
    placed = 0
    if exec_:
        top = "lspd_wood_veneer"
        # door is on the north wall for both executive offices -> desk in front of the window wall facing the door
        c.desk(c.cx, c.y0 + 2.2, 2.2, 1.0, (0, 1), top=top, body="lspd_wood_veneer", monitors=2,
               chair_model="v_corp_offchair")
        c.prop("prop_chair_01a", c.cx - 0.55, c.y0 + 3.4, 0, heading_to(0, -1))
        c.prop("prop_chair_01a", c.cx + 0.55, c.y0 + 3.4, 0, heading_to(0, -1))
        c.occupy(c.cx - 1.2, c.y0 + 2.7, c.cx + 1.2, c.y0 + 3.9)
        if c.free(c.cx - 1.6, c.y0 + 0.1, c.cx + 1.6, c.y0 + 0.55, 0.8) or True:
            c.box("lspd_wood_veneer", c.cx - 1.6, c.y0 + 0.1, 0, c.cx + 1.6, c.y0 + 0.55, 0.8)
            c.prop("prop_coffee_mac_02", c.cx + 1.2, c.y0 + 0.33, 0.8, heading_to(0, 1), lod=20)
        c.mesh.box("img_rug", c.cx - 1.8, c.y0 + 0.9, c.z + 0.002, c.cx + 1.8, c.y0 + 4.2, c.z + 0.008, faces=("+z",))
        c.prop("prop_flag_us", c.x0 + 0.5, c.y0 + 0.5, 0, heading_to(1, 1), lod=40)
        c.try_image("img_merit", "e", c.y0 + 3.0, c.y0 + 5.2, 1.3, 2.4) or c.try_image("img_merit", "w", c.y0 + 3.0, c.y0 + 5.2, 1.3, 2.4)
        c.try_image("img_wall_logo", "n", c.x1 - 2.6, c.x1 - 1.2, 1.3, 2.7)
        c.sofa(c.x0 + 0.2, c.y1 - 3.6, c.x0 + 1.1, c.y1 - 1.6, (1, 0), mat="lspd_fabric")
        c.table(c.x0 + 1.5, c.y1 - 3.1, c.x0 + 2.3, c.y1 - 2.1, h=0.42, top="lspd_wood_veneer")
        c.prop("prop_chair_01a", c.x0 + 2.9, c.y1 - 2.6, 0, heading_to(-1, 0))
        c.shelf(c.x1 - 0.5, c.y1 - 4.2, c.x1 - 0.1, c.y1 - 1.8, h=2.0, mat="lspd_wood_veneer", boxes=False, files=True)
        c.corner_plants()
        return
    spots = []
    if w >= d:
        for i in range(n):
            spots.append((c.x0 + (c.x1 - c.x0) * (i + 0.5) / n, c.cy + 0.2, (0, -1)))
    else:
        for i in range(n):
            spots.append((c.cx + 0.2, c.y0 + (c.y1 - c.y0) * (i + 0.5) / n, (-1, 0)))
    for (x, y, fc) in spots:
        if c.desk(x, y, 1.6, 0.8, fc, monitors=2 if rnd.random() < 0.5 else 1):
            placed += 1
    c.filing(c.x0 + 0.6, c.y1 - 0.4, (0, -1), n=2) or c.filing(c.x1 - 0.6, c.y1 - 0.4, (0, -1), n=2)
    c.try_image("img_whiteboard", "w", c.cy - 1.0, c.cy + 1.0, 1.0, 2.0) or c.try_image("img_corkboard", "e", c.cy - 1.0, c.cy + 1.0, 1.0, 2.0)
    c.corner_plants()
    c.bin(c.x1 - 0.35, c.y0 + 0.35)


def f_open_office(c, rows=None, title=None, screen="emi_desk"):
    """Bullpen with pods of 4 workstations and low partitions."""
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    pod_w, pod_d = 3.4, 3.4
    nx = max(1, int((x1 - x0 - 1.2) // (pod_w + 1.2)))
    ny = max(1, int((y1 - y0 - 1.2) // (pod_d + 1.0)))
    gx = (x1 - x0 - nx * pod_w) / (nx + 1)
    gy = (y1 - y0 - ny * pod_d) / (ny + 1)
    for i in range(nx):
        for j in range(ny):
            px0 = x0 + gx + i * (pod_w + gx)
            py0 = y0 + gy + j * (pod_d + gy)
            pcx, pcy = px0 + pod_w / 2, py0 + pod_d / 2
            if not c.free(px0 - 0.5, py0 - 0.5, px0 + pod_w + 0.5, py0 + pod_d + 0.5, 1.2):
                continue
            # partitions (cross) 1.2 m
            c.box("lspd_fabric_grey", pcx - 1.6, pcy - 0.025, 0, pcx + 1.6, pcy + 0.025, 1.2)
            c.box("lspd_fabric_grey", pcx - 0.025, pcy - 0.8, 0, pcx + 0.025, pcy + 0.8, 1.2)
            c.box("lspd_metal", pcx - 1.6, pcy - 0.03, 1.2, pcx + 1.6, pcy + 0.03, 1.22, col=False)
            for (sx, sy) in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                dx_, dy_ = 0, -sy
                c.desk(pcx + sx * 0.8, pcy + sy * 0.42, 1.5, 0.78, (0, -sy), monitors=2, screen=screen)
    c.corner_plants()
    c.prop("prop_printer_02", x1 - 0.5, y1 - 0.5, 0, heading_to(-1, 0))
    c.prop("prop_watercooler", x0 + 0.4, y1 - 1.2, 0, heading_to(1, 0))
    c.filing(x1 - 0.4, (y0 + y1) / 2, (-1, 0), n=3)
    c.try_image("img_corkboard", "n", (x0 + x1) / 2 - 1.2, (x0 + x1) / 2 + 1.2, 1.1, 2.2) or \
        c.try_image("img_corkboard", "s", (x0 + x1) / 2 - 1.2, (x0 + x1) / 2 + 1.2, 1.1, 2.2)
    c.try_image("img_whiteboard", "e", (y0 + y1) / 2 + 1.0, (y0 + y1) / 2 + 3.0, 1.0, 2.0)


def f_briefing(c):
    # rows of tables facing a podium + screen on the west wall... (west wall x=3.4 is the stair wall)
    c.tv_wall("w", c.cy - 1.4, c.cy + 1.4, 1.0, 2.6, screen="emi_map")
    c.try_image("img_whiteboard", "w", c.cy + 1.7, c.cy + 3.4, 1.0, 2.0)
    c.box("lspd_wood_veneer", c.x0 + 0.9, c.cy - 2.2, 0, c.x0 + 1.4, c.cy - 1.6, 1.1)  # podium
    for row in range(4):
        xx = c.x0 + 3.0 + row * 1.9
        for half in (-1, 1):
            y_a = c.cy + half * 0.5 if half > 0 else c.cy - 0.5 - 2.4
            y_b = y_a + 2.4
            if c.table(xx, y_a, xx + 0.6, y_b, top="lspd_laminate"):
                for k in range(3):
                    c.prop("prop_chair_02", xx + 0.95, y_a + 0.4 + k * 0.8, 0, heading_to(-1, 0))
    c.prop("prop_flag_us", c.x0 + 0.5, c.y0 + 0.5, 0, 45, lod=40)
    c.plant(c.x1 - 0.4, c.y1 - 0.4)


def f_armory(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    # issue counter with cage just inside the door (door on west wall at y=24)
    c.counter(x0 + 1.8, y0 + 0.3, x0 + 2.4, y1 - 2.0, h=1.05, front="lspd_metal_dark")
    for k in range(6):
        c.box("lspd_metal", x0 + 2.05, y0 + 0.3 + k * 0.7, 1.05, x0 + 2.1, y0 + 0.33 + k * 0.7, 2.6, col=False)
    c.sh.col_int.box(x0 + 1.8, y0 + 0.3, c.z + 1.05, x0 + 2.4, y1 - 2.0, c.z + 2.6, col="METAL_GRILLE", room=c.rid)
    # rifle racks along the north, east and south walls
    for (rx0, ry0, rx1, ry1, face) in ((x1 - 0.45, y0 + 0.3, x1 - 0.1, y1 - 0.4, (-1, 0)),
                                       (x0 + 3.0, y1 - 0.45, x1 - 0.6, y1 - 0.1, (0, -1)),
                                       (x0 + 3.0, y0 + 0.1, x1 - 0.6, y0 + 0.45, (0, 1))):
        if not c.free(rx0, ry0, rx1, ry1, 2.0):
            continue
        c.box("lspd_metal_dark", rx0, ry0, 0, rx1, ry1, 0.9)
        c.box("lspd_metal_dark", rx0, ry0, 0.9, rx1, ry1, 2.0, faces=("+z",) if False else None)
        c.occupy(rx0, ry0, rx1, ry1)
        long_x = face[0] == 0
        L = (rx1 - rx0) if long_x else (ry1 - ry0)
        n = int(L // 0.35)
        for i in range(n):
            a = (rx0 if long_x else ry0) + 0.2 + i * 0.35
            model = "w_ar_carbinerifle" if i % 3 else "w_sg_pumpshotgun"
            if long_x:
                yy = ry0 - 0.1 if face[1] < 0 else ry1 + 0.1
                c.prop(model, a, yy, 1.45, 90.0, lod=25)
            else:
                xx = rx0 - 0.1 if face[0] < 0 else rx1 + 0.1
                c.prop(model, xx, a, 1.45, 0.0, lod=25)
        # ammo boxes on the cabinet top
        for i in range(max(1, n // 3)):
            a = (rx0 if long_x else ry0) + 0.3 + i * 1.0
            m = rnd.choice(["prop_box_ammo01a", "prop_box_ammo02a", "prop_box_ammo03a", "prop_box_ammo04a"])
            if long_x:
                c.prop(m, a, (ry0 + ry1) / 2, 0.9, 0, lod=20)
            else:
                c.prop(m, (rx0 + rx1) / 2, a, 0.9, 90, lod=20)
    # cleaning / loading bench in the middle
    c.table(c.cx - 0.2, c.cy - 0.9, c.cx + 0.9, c.cy + 0.9, h=0.95, top="lspd_metal")
    c.prop("w_pi_pistol", c.cx + 0.35, c.cy - 0.3, 0.95, 30, lod=15)
    c.prop("prop_box_guncase_01a", c.cx + 0.35, c.cy + 0.4, 0.95, 0, lod=20)
    c.prop("prop_cs_office_chair", c.x0 + 1.3, c.cy, 0, heading_to(1, 0))
    c.ceiling_cam(x1 - 0.3, y0 + 0.3, 135)
    B.sign_quad(c.mesh, "ARMORY", None, x0 + 2.0, y1 - 0.02, c.z + 2.4, 1.0, 0.5, facing="-y")


def f_equipment(c):
    # vest + duty belt lockers on both long walls
    c.lockers(c.x0 + 2.0, c.y0 + 0.05, c.x1 - 0.1, c.y0 + 0.5, (0, 1))
    c.lockers(c.x0 + 2.0, c.y1 - 0.5, c.x1 - 0.1, c.y1 - 0.05, (0, -1))
    c.bench(c.x0 + 2.4, c.cy - 0.2, c.x1 - 0.6, c.cy + 0.2)
    for k in range(4):
        c.prop("prop_bodyarmour_02", c.x0 + 2.8 + k * 1.1, c.cy, 0.45, 0, lod=20)
    c.prop("prop_cs_hand_radio", c.x1 - 0.8, c.cy, 0.45, 0, lod=15)
    c.prop("prop_cs_police_torch", c.x1 - 1.0, c.cy + 0.1, 0.45, 40, lod=15)


def f_riot(c):
    c.shelf(c.x0 + 0.05, c.y0 + 0.4, c.x0 + 0.55, c.y1 - 0.4, h=2.2, levels=4)
    c.shelf(c.x1 - 0.55, c.y0 + 0.4, c.x1 - 0.05, c.y1 - 0.4, h=2.2, levels=4)
    for k in range(4):
        c.prop("prop_riot_shield", c.cx - 0.6 + k * 0.4, c.y1 - 0.3, 0, 0, lod=20)
    c.prop("prop_ballistic_shield", c.cx, c.y0 + 1.2, 0, 180, lod=20)
    c.prop("prop_cs_heist_bag_01", c.cx + 0.4, c.cy, 0, 30, lod=20)


def f_maintenance(c):
    c.box({"+z": "lspd_metal", "+x": "lspd_metal_dark", "-x": "lspd_metal_dark", "+y": "lspd_metal_dark", "-y": "lspd_metal_dark"},
          c.x0 + 0.05, c.y1 - 0.75, 0, c.x1 - 0.05, c.y1 - 0.05, 0.92)
    c.occupy(c.x0, c.y1 - 0.8, c.x1, c.y1)
    c.try_image("img_rack", "n", c.x0 + 0.3, c.x0 + 1.3, 1.1, 2.0)
    c.prop("prop_toolchest_05", c.x1 - 0.5, c.y0 + 0.6, 0, heading_to(-1, 0), lod=25)
    c.prop("prop_toolchest_01", c.x0 + 0.5, c.y0 + 0.6, 0, heading_to(1, 0), lod=25)
    c.prop("w_pi_pistol", c.cx, c.y1 - 0.4, 0.92, 75, lod=15)
    c.prop("prop_cs_office_chair", c.cx, c.y1 - 1.3, 0, heading_to(0, 1))


def f_booking(c):
    # raised booking desk (L-shape) with officers' side behind
    c.counter(c.x0 + 2.0, c.y0 + 2.6, c.x1 - 0.8, c.y0 + 3.3, h=1.1)
    c.counter(c.x1 - 1.5, c.y0 + 3.3, c.x1 - 0.8, c.y1 - 2.0, h=1.1)
    for k in range(3):
        xx = c.x0 + 2.7 + k * 1.5
        c.monitor(xx, c.y0 + 2.75, (0, -1), z=1.1)
        c.prop("prop_cs_office_chair", xx, c.y0 + 1.9, 0, heading_to(0, 1))
    # detainee bench with cuff rail on the north side
    c.bench(c.x0 + 0.5, c.y1 - 0.65, c.x0 + 4.2, c.y1 - 0.15, seat="lspd_metal")
    c.box("lspd_metal", c.x0 + 0.5, c.y1 - 0.15, 0.7, c.x0 + 4.2, c.y1 - 0.1, 0.75, col=False)
    c.try_image("img_infoboard", "w", c.cy - 0.9, c.cy + 0.9, 1.4, 2.3)
    c.ceiling_cam(c.x0 + 0.3, c.y1 - 0.3, 225); c.ceiling_cam(c.x1 - 0.3, c.y0 + 0.3, 45)
    c.prop("prop_fingerprint_scanner_01" if False else "prop_printer_01", c.x0 + 2.4, c.y0 + 2.95, 1.1, 0, lod=20)
    c.bin(c.x0 + 0.4, c.y0 + 0.4)


def f_mugshot(c):
    # height chart backdrop on the east wall, camera on tripod facing it
    c.try_image("img_mugshot", "e", c.cy - 0.7, c.cy + 0.7, 0.0, 2.5, thick=0.01)
    c.mesh.box("mat_white", c.x1 - 0.75, c.cy - 0.25, c.z + 0.002, c.x1 - 0.25, c.cy + 0.25, c.z + 0.006, faces=("+z",))
    c.cyl("mat_black", c.x0 + 1.6, c.cy, 0, 1.4, 0.03, 6, col=False)
    c.box("mat_black", c.x0 + 1.5, c.cy - 0.12, 1.4, c.x0 + 1.75, c.cy + 0.12, 1.58, col=False)
    c.box("lspd_light" if False else "emi_light", c.x0 + 0.5, c.cy - 0.4, 1.6, c.x0 + 0.6, c.cy + 0.4, 2.2, col=False)
    c.desk(c.x0 + 0.9, c.y0 + 0.6, 1.2, 0.6, (0, -1) if False else (0, 1), monitors=1, phone=False)


def f_fingerprint(c):
    c.counter(c.x0 + 1.0, c.cy - 0.35, c.x0 + 2.4, c.cy + 0.35, h=0.95, front="lspd_metal")
    c.monitor(c.x0 + 1.4, c.cy, (1, 0), z=0.95)
    c.box("mat_black", c.x0 + 1.9, c.cy - 0.15, 0.95, c.x0 + 2.2, c.cy + 0.15, 1.02, col=False)  # live scan pad
    c.mesh.box("emi_light", c.x0 + 1.95, c.cy - 0.1, c.z + 1.02, c.x0 + 2.15, c.cy + 0.1, c.z + 1.021, faces=("+z",))
    c.prop("prop_cs_office_chair", c.x0 + 0.5, c.cy, 0, heading_to(1, 0))
    c.filing(c.x1 - 0.4, c.cy, (-1, 0), n=2)


def f_property(c):
    c.counter(c.x0 + 0.8, c.cy - 0.35, c.x0 + 3.2, c.cy + 0.35, h=1.0, front="lspd_metal")
    for k in range(3):
        c.prop("prop_cs_cardbox_01", c.x0 + 1.2 + k * 0.7, c.cy, 1.0, rnd.uniform(0, 30), lod=15)
    c.shelf(c.x1 - 0.5, c.y0 + 0.1, c.x1 - 0.05, c.y1 - 0.1, h=2.1, levels=5)


def f_det_control(c):
    # control console facing the glass to the cell corridor (north wall)
    c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_navy", "-x": "lspd_metal_navy", "+y": "lspd_metal_navy", "-y": "lspd_metal_navy"},
          c.x0 + 0.6, c.y1 - 1.3, 0, c.x1 - 0.6, c.y1 - 0.5, 0.8)
    c.occupy(c.x0 + 0.5, c.y1 - 1.4, c.x1 - 0.5, c.y1)
    for k in range(4):
        xx = c.x0 + 1.2 + k * 1.4
        c.monitor(xx, c.y1 - 0.75, (0, -1), z=0.8, screen="emi_cctv")
    for k in range(2):
        c.prop("prop_cs_office_chair", c.x0 + 2.0 + k * 2.6, c.y1 - 2.0, 0, heading_to(0, 1))
    c.tv_wall("w", c.y0 + 1.0, c.y0 + 3.6, 1.2, 2.7, screen="emi_cctv")
    c.lockers(c.x1 - 0.5, c.y0 + 0.6, c.x1 - 0.05, c.y0 + 3.0, (-1, 0))
    c.prop("prop_watercooler_dark", c.x0 + 0.4, c.y0 + 0.4, 0, heading_to(1, 1))


def f_intake(c):
    c.desk(c.cx - 1.4, c.cy + 0.5, 1.6, 0.8, (0, 1), monitors=2)
    c.desk(c.cx + 1.4, c.cy + 0.5, 1.6, 0.8, (0, 1), monitors=1)
    c.try_image("img_corkboard", "w", c.cy - 1.2, c.cy + 1.2, 1.1, 2.2)
    c.lockers(c.x1 - 0.5, c.y0 + 0.3, c.x1 - 0.05, c.y0 + 2.7, (-1, 0))
    c.prop("prop_printer_01", c.x0 + 0.5, c.y1 - 0.5, 0, heading_to(1, 0))


def f_cell(c, hs=False):
    x0, y0, x1, y1 = c.rect
    # concrete bunk against the north wall + steel toilet/sink combo
    c.box("lspd_concrete", x0 + 0.1, y1 - 0.9, 0, x1 - 1.1 if not hs else x1 - 0.1, y1 - 0.1, 0.45)
    c.box("lspd_fabric_grey", x0 + 0.15, y1 - 0.85, 0.45, x0 + 2.0, y1 - 0.15, 0.52, col=False)
    if not hs:
        c.box("lspd_metal", x1 - 0.65, y1 - 0.6, 0, x1 - 0.1, y1 - 0.1, 1.05)
        c.cyl("lspd_metal", x1 - 0.38, y1 - 0.75, 0.0, 0.42, 0.2, 10)
    else:
        c.box("lspd_metal", x1 - 0.6, y0 + 1.2, 0, x1 - 0.1, y0 + 1.75, 0.95)
    c.ceiling_cam(x0 + 0.3, y0 + 0.3, 225)


def f_cellcorr(c):
    c.box("img_stripe", c.x0, c.y0 + 0.95, 0.0, c.x1, c.y0 + 1.05, 0.004, col=False, faces=("+z",))
    for xx in (26.0, 34.0, 42.0):
        c.ceiling_cam(xx, c.y0 + 0.2, 0)
    c.bench(c.x1 - 3.0, c.y0 + 0.05, c.x1 - 0.8, c.y0 + 0.45, seat="lspd_metal")


def f_sallyport(c):
    c.box("img_stripe", c.x0 + 0.2, c.y0 + 0.2, 0, c.x0 + 0.5, c.y1 - 0.2, 0.004, col=False, faces=("+z",))
    c.box("img_stripe", c.x0 + 0.2, c.y1 - 0.5, 0, c.x1 - 2.8, c.y1 - 0.2, 0.004, col=False, faces=("+z",))
    # weapon lockers (officers must secure weapons before entering the cell block)
    c.lockers(c.x0 + 0.1, c.y0 + 2.0, c.x0 + 0.5, c.y0 + 4.0, (1, 0), h=1.4)
    c.try_image("img_infoboard", "w", c.y0 + 4.5, c.y0 + 6.3, 1.2, 2.1)
    c.ceiling_cam(c.x0 + 0.4, c.y1 - 0.4, 225)
    c.prop("prop_sacktruck_02a", c.x0 + 1.2, c.y1 - 0.6, 0, 0, lod=25)


def f_garage(c):
    x0, y0, x1, y1 = c.rect
    # parking bays painted along the south wall, workshop strip on the west
    for k in range(10):
        xx = x0 + 3.0 + k * 3.6
        if xx + 0.1 > x1 - 0.2:
            break
        c.mesh.box("mat_white", xx, y0 + 0.3, c.z + 0.002, xx + 0.1, y0 + 5.8, c.z + 0.005, faces=("+z",))
    c.box({"+z": "lspd_metal", "+x": "lspd_metal_dark", "-x": "lspd_metal_dark", "+y": "lspd_metal_dark", "-y": "lspd_metal_dark"},
          x0 + 0.15, y1 - 6.0, 0, x0 + 0.85, y1 - 0.5, 0.92)
    c.occupy(x0, y1 - 6.0, x0 + 1.0, y1 - 0.5)
    c.prop("prop_toolchest_05", x0 + 0.5, y1 - 7.0, 0, heading_to(1, 0), lod=30)
    c.prop("prop_tool_bench02", x0 + 0.6, y0 + 7.5, 0, heading_to(1, 0), lod=30)
    c.shelf(x0 + 3.0, y1 - 0.6, x0 + 6.0, y1 - 0.1, h=2.4, levels=4)
    c.shelf(x0 + 6.5, y1 - 0.6, x0 + 9.5, y1 - 0.1, h=2.4, levels=4)
    for (bx, by) in ((x0 + 2.0, y0 + 6.5), (x1 - 2.0, y0 + 6.5)):
        c.cyl("img_stripe", bx, by, 0, 1.0, 0.12, 10)
    c.try_image("img_infoboard", "w", y0 + 2.0, y0 + 3.8, 1.3, 2.2)
    c.ceiling_cam(x0 + 0.4, y0 + 0.4, 315); c.ceiling_cam(x1 - 0.4, y1 - 0.4, 135)


def f_interrogation(c):
    c.table(c.cx - 0.6, c.cy - 0.45, c.cx + 0.6, c.cy + 0.45, top="lspd_metal")
    c.box("lspd_metal", c.cx - 0.05, c.cy - 0.02, 0.75, c.cx + 0.05, c.cy + 0.02, 0.8, col=False)  # cuff ring
    c.prop("prop_chair_02", c.cx, c.cy - 0.9, 0, heading_to(0, 1))
    c.prop("prop_chair_02", c.cx - 0.35, c.cy + 0.9, 0, heading_to(0, -1))
    c.prop("prop_chair_02", c.cx + 0.35, c.cy + 0.9, 0, heading_to(0, -1))
    c.prop("prop_notepad_01", c.cx + 0.2, c.cy + 0.15, 0.75, 10, lod=10)
    c.prop("prop_pencil_01", c.cx + 0.35, c.cy + 0.1, 0.75, 80, lod=10)
    c.ceiling_cam(c.x0 + 0.3, c.y0 + 0.3 if c.r.rid == "interro2" else c.y1 - 0.3, 315)


def f_observation(c):
    # two observation desks facing each mirror
    for (yy, fy) in ((c.y0 + 0.6, -1), (c.y1 - 0.6, 1)):
        c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_dark", "-x": "lspd_metal_dark", "+y": "lspd_metal_dark", "-y": "lspd_metal_dark"},
              c.x0 + 0.8, yy - 0.3, 0, c.x1 - 0.8, yy + 0.3, 0.76)
        c.monitor(c.x0 + 1.4, yy, (0, -fy), z=0.76, screen="emi_cctv")
        c.monitor(c.x1 - 1.4, yy, (0, -fy), z=0.76, screen="emi_desk")
        c.prop("prop_cs_office_chair", c.cx, yy - fy * 0.75, 0, heading_to(0, fy))


def f_lineup(c):
    c.try_image("img_height", "s", c.x0 + 0.3, c.x1 - 0.3, 0.0, 2.5, thick=0.01)
    c.box("lspd_concrete_dark", c.x0 + 0.1, c.y0 + 0.1, 0, c.x1 - 0.1, c.y0 + 1.6, 0.15)
    for k in range(6):
        xx = c.x0 + 0.6 + k * (c.x1 - c.x0 - 1.2) / 5
        c.mesh.box("mat_white", xx - 0.15, c.y0 + 1.0, c.z + 0.152, xx + 0.15, c.y0 + 1.35, c.z + 0.155, faces=("+z",))
    c.mesh.light(c.cx, c.y0 + 2.2, c.z + 2.8, (255, 255, 255), 3.5, 5.0, 8.0)


def f_lineup_view(c):
    c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_dark", "-x": "lspd_metal_dark", "+y": "lspd_metal_dark", "-y": "lspd_metal_dark"},
          c.x0 + 0.5, c.y0 + 0.2, 0, c.x1 - 0.5, c.y0 + 0.6, 0.95)
    for k in range(3):
        c.prop("prop_chair_02", c.x0 + 1.4 + k * 1.6, c.y0 + 1.3, 0, heading_to(0, -1))
    c.prop("prop_cs_hand_radio" if False else "prop_notepad_01", c.cx, c.y0 + 0.4, 0.95, 0, lod=10)


def f_evidence(c):
    # intake counter at the door (west), high-density shelving rows
    c.counter(c.x0 + 0.1, c.y0 + 0.4, c.x0 + 0.8, c.y0 + 3.0, h=1.0, front="lspd_metal")
    c.try_image("img_rack", "s", c.x0 + 2.0, c.x0 + 2.5, 1.0, 2.0) if False else None
    for k in range(3):
        xx = c.x0 + 2.0 + k * 1.5
        c.shelf(xx, c.y0 + 3.4, xx + 0.55, c.y1 - 0.4, h=2.3, levels=5)
        c.try_image("img_shelflabel", "n", xx, xx + 0.55, 2.35, 2.5, thick=0.01) if False else None
    c.shelf(c.x1 - 0.55, c.y0 + 0.4, c.x1 - 0.05, c.y0 + 2.8, h=2.3, levels=5)
    c.prop("prop_cs_office_chair", c.x0 + 1.4, c.y0 + 1.6, 0, heading_to(-1, 0))
    c.monitor(c.x0 + 0.45, c.y0 + 1.6, (1, 0), z=1.0)
    c.ceiling_cam(c.x1 - 0.3, c.y1 - 0.3, 135)


def f_dispatch(c):
    x0, y0, x1, y1 = c.rect   # 16..38 x 0..18
    # video wall on the west wall: map in the middle, CCTV + CAD each side
    c.try_image("emi_cctv", "w", 2.4, 5.6, 0.9, 3.3, frame="mat_black", thick=0.06)
    c.try_image("emi_map", "w", 5.9, 12.1, 0.6, 3.4, frame="mat_black", thick=0.06)
    c.try_image("emi_cad", "w", 12.4, 15.6, 0.9, 3.3, frame="mat_black", thick=0.06)
    B.sign_quad(c.mesh, "DISPATCH CENTER", None, x0 + LY.INT_T / 2 + 0.06, 8.0, c.z + 3.4 - 0.05 - 0.15, 2.0, 0.0001, facing="+x") if False else None
    # three curved rows of operator consoles (approximated by straight segments) facing west
    for row, xx in enumerate((21.5, 25.5, 29.5)):
        n = 4
        for k in range(n):
            yy = 4.0 + k * 3.3
            ok = c.free(xx - 0.5, yy - 1.0, xx + 0.5, yy + 1.0, 1.0)
            if not ok:
                continue
            c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_navy", "-x": "lspd_metal_navy", "+y": "lspd_metal_navy", "-y": "lspd_metal_navy"},
                  xx - 0.45, yy - 1.2, 0, xx + 0.45, yy + 1.2, 0.76)
            c.occupy(xx - 0.45, yy - 1.2, xx + 0.45, yy + 1.2)
            for j, scr in enumerate(("emi_cad", "emi_map", "emi_desk")):
                c.monitor(xx - 0.25, yy - 0.62 + j * 0.62, (1, 0), z=0.76, screen=scr, w=0.58)
            c.keyboard(xx + 0.15, yy, (-1, 0), z=0.76)
            c.box("mat_black", xx + 0.0, yy + 0.45, 0.76, xx + 0.2, yy + 0.6, 0.86, col=False)  # radio console
            c.prop("prop_cs_office_chair", xx + 0.95, yy, 0, heading_to(-1, 0))
    # supervisor podium at the back (east side)
    c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_navy", "-x": "lspd_metal_navy", "+y": "lspd_metal_navy", "-y": "lspd_metal_navy"},
          33.5, 7.0, 0, 34.4, 11.0, 0.95)
    c.occupy(33.4, 6.9, 35.6, 11.1)
    for j in range(4):
        c.monitor(33.75, 7.5 + j * 0.95, (-1, 0) if False else (1, 0), z=0.95, screen=("emi_cctv", "emi_cad", "emi_map", "emi_desk")[j])
    c.prop("prop_cs_office_chair", 35.0, 9.0, 0, heading_to(-1, 0))
    c.prop("prop_watercooler_dark", x1 - 0.5, y1 - 0.5, 0, heading_to(-1, 0))
    c.prop("prop_printer_02", x1 - 0.5, y0 + 0.5, 0, heading_to(-1, 0))
    c.plant(x1 - 0.5, y1 - 1.4)
    # hanging DISPATCH sign
    B.sign_quad(c.mesh, "OPERATIONS", None, 26.0, 16.6, c.z + 2.9, 1.6, 0.8, facing="-y", emissive=True)


def f_disp_super(c):
    c.desk(c.cx, c.y1 - 2.0, 1.8, 0.85, (0, -1), monitors=3)
    c.tv_wall("e", c.y0 + 2.0, c.y0 + 5.0, 1.0, 2.6, screen="emi_map")
    c.filing(c.x0 + 0.4, c.y1 - 0.9, (1, 0), n=2)
    c.prop("prop_chair_01a", c.cx - 0.5, c.y1 - 3.2, 0, heading_to(0, 1))
    c.plant(c.x1 - 0.4, c.y1 - 0.4)


def f_radio(c):
    c.box({"+z": "lspd_laminate_dark", "+x": "lspd_metal_dark", "-x": "lspd_metal_dark", "+y": "lspd_metal_dark", "-y": "lspd_metal_dark"},
          c.x1 - 0.85, c.y0 + 0.5, 0, c.x1 - 0.1, c.y1 - 1.8, 0.76)
    c.occupy(c.x1 - 0.9, c.y0 + 0.4, c.x1, c.y1 - 1.7)
    for k in range(4):
        yy = c.y0 + 1.0 + k * 1.3
        c.box("mat_black", c.x1 - 0.55, yy - 0.35, 0.76, c.x1 - 0.15, yy + 0.35, 1.3, col=False)   # radio stacks
        c.monitor(c.x1 - 0.6, yy, (-1, 0), z=0.76, screen="emi_desk")
        c.prop("prop_cs_office_chair", c.x1 - 1.4, yy, 0, heading_to(1, 0))
    c.try_image("img_rack", "w", c.y0 + 1.0, c.y0 + 2.0, 0.2, 2.2)
    c.try_image("img_rack", "w", c.y0 + 2.2, c.y0 + 3.2, 0.2, 2.2)


def f_analysis(c):
    c.tv_wall("e", c.y0 + 3.0, c.y0 + 7.0, 0.9, 3.0, screen="emi_map")
    c.tv_wall("e", c.y0 + 7.4, c.y0 + 10.6, 0.9, 3.0, screen="emi_cctv")
    for i in range(2):
        for j in range(3):
            c.desk(c.x0 + 2.2 + i * 3.6, c.y0 + 3.0 + j * 4.0, 1.6, 0.8, (1, 0), monitors=2)
    c.try_image("img_corkboard", "w", c.y0 + 4.0, c.y0 + 6.4, 1.0, 2.2)
    c.try_image("img_corkboard", "w", c.y0 + 8.0, c.y0 + 10.4, 1.0, 2.2)
    c.table(c.x1 - 3.5, c.y1 - 2.0, c.x1 - 1.3, c.y1 - 1.0)
    c.chairs_around(c.x1 - 3.5, c.y1 - 2.0, c.x1 - 1.3, c.y1 - 1.0, ends=False)
    c.corner_plants()


def f_case_room(c):
    c.table(c.cx - 1.2, c.cy - 0.5, c.cx + 1.2, c.cy + 0.5)
    c.chairs_around(c.cx - 1.2, c.cy - 0.5, c.cx + 1.2, c.cy + 0.5, ends=False)
    c.try_image("img_corkboard", "w", c.cy - 1.2, c.cy + 1.2, 1.0, 2.2)
    c.try_image("img_whiteboard", "e", c.cy - 1.0, c.cy + 1.0, 1.0, 2.0)
    for k in range(3):
        c.papers(c.cx - 0.8 + k * 0.8, c.cy, 0.75, n=2)


def f_lab(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    # perimeter lab benches (epoxy tops) + 2 island benches
    for (a, b, cc, d) in ((x0, y0 + 2.0, x0 + 0.75, y1 - 1.5), (x1 - 0.75, y0 + 2.0, x1, y1 - 1.5),
                          (x0 + 2.0, y1 - 0.75, x1 - 2.0, y1)):
        if c.counter(a, b, cc, d, h=0.92, front="mat_white", top="lspd_laminate_dark"):
            long_x = (cc - a) > (d - b)
            L = (cc - a) if long_x else (d - b)
            for k in range(int(L // 1.6)):
                p = (a if long_x else b) + 0.8 + k * 1.6
                item = k % 4
                if long_x:
                    if item == 0:
                        c.box("mat_white", p - 0.25, b + 0.15, 0.92, p + 0.25, b + 0.6, 1.35, col=False)   # analyser
                        c.mesh.box("emi_desk", p - 0.15, b + 0.149, c.z + 1.1, p + 0.15, b + 0.15, c.z + 1.28, faces=("-y",))
                    elif item == 1:
                        c.cyl("mat_black", p, b + 0.4, 0.92, 1.3, 0.05, 8, col=False)   # microscope
                        c.box("mat_black", p - 0.12, b + 0.25, 0.92, p + 0.12, b + 0.55, 0.97, col=False)
                    elif item == 2:
                        c.monitor(p, b + 0.45, (0, -1), z=0.92)
                    else:
                        for q in range(4):
                            c.cyl("glass_int", p - 0.2 + q * 0.13, b + 0.35, 0.92, 1.12, 0.035, 8, col=False)
                else:
                    xx = a + 0.4 if a < c.cx else cc - 0.4
                    face = (1, 0) if a < c.cx else (-1, 0)
                    if item == 0:
                        c.box("mat_white", xx - 0.22, p - 0.25, 0.92, xx + 0.22, p + 0.25, 1.35, col=False)
                    elif item == 1:
                        c.cyl("mat_black", xx, p, 0.92, 1.3, 0.05, 8, col=False)
                        c.box("mat_black", xx - 0.15, p - 0.12, 0.92, xx + 0.15, p + 0.12, 0.97, col=False)
                    elif item == 2:
                        c.monitor(xx, p, face, z=0.92)
                    else:
                        for q in range(4):
                            c.cyl("glass_int", xx, p - 0.2 + q * 0.13, 0.92, 1.12, 0.035, 8, col=False)
    for (ix, iy) in ((c.cx - 2.5, c.cy - 1.0), (c.cx + 2.5, c.cy - 1.0)):
        if c.counter(ix - 1.4, iy - 0.6, ix + 1.4, iy + 0.6, h=0.92, front="mat_white", top="lspd_laminate_dark"):
            c.box("lspd_metal", ix - 1.2, iy - 0.05, 0.92, ix + 1.2, iy + 0.05, 1.7, col=False)   # reagent shelf
            c.box("lspd_metal", ix - 1.2, iy - 0.18, 1.45, ix + 1.2, iy + 0.18, 1.48, col=False)
            for q in range(6):
                c.cyl("glass_int", ix - 1.0 + q * 0.4, iy, 1.48, 1.68, 0.05, 8, col=False)
            c.prop("prop_cs_office_chair", ix - 0.6, iy - 1.0, 0, heading_to(0, 1))
            c.prop("prop_cs_office_chair", ix + 0.6, iy + 1.0, 0, heading_to(0, -1))
    # fume hood
    c.box({"+z": "mat_white", "+x": "mat_white", "-x": "mat_white", "+y": "mat_white", "-y": "glass_int"},
          x1 - 2.0, y0 + 0.05, 0.92, x1 - 0.2, y0 + 0.8, 2.3)
    c.box("mat_white", x1 - 2.0, y0 + 0.05, 0, x1 - 0.2, y0 + 0.8, 0.92)
    c.mesh.light(x1 - 1.1, y0 + 0.4, c.z + 2.2, (255, 255, 255), 1.5, 2.5, 8.0)
    c.prop("prop_fridge_03", x0 + 0.5, y0 + 0.5, 0, heading_to(1, 0), lod=30)
    c.try_image("img_whiteboard", "s", x0 + 3.0, x0 + 5.0, 1.0, 2.0)


def f_archive(c, docs=False):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    n = int((x1 - x0 - 1.0) // 1.5)
    for k in range(n):
        xx = x0 + 0.5 + k * 1.5
        c.shelf(xx, y0 + 1.6, xx + 0.5, y1 - 0.4, h=2.4, levels=6, files=not docs, boxes=docs)
    c.desk(c.cx, y0 + 0.7, 1.4, 0.7, (0, -1) if False else (0, 1), monitors=1, phone=False)


def f_server(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    for k in range(2):
        yy = y0 + 1.6 + k * 2.6
        if c.free(x0 + 0.6, yy, x1 - 0.6, yy + 0.8, 2.2):
            c.box("mat_black", x0 + 0.6, yy, 0, x1 - 0.6, yy + 0.8, 2.1)
            c.occupy(x0 + 0.6, yy, x1 - 0.6, yy + 0.8)
            nr = int((x1 - x0 - 1.2) // 0.62)
            for r in range(nr):
                a = x0 + 0.62 + r * 0.62
                c.mesh.box("img_rack", a, yy - 0.002, c.z + 0.05, a + 0.58, yy, c.z + 2.05, faces=("-y",))
                c.mesh.box("img_rack", a, yy + 0.8, c.z + 0.05, a + 0.58, yy + 0.802, c.z + 2.05, faces=("+y",))
            c.box("lspd_metal", x0 + 0.6, yy - 0.1, 2.3, x1 - 0.6, yy + 0.9, 2.35, col=False)   # cable tray
    c.box("mat_white", x1 - 0.8, y1 - 0.9, 0, x1 - 0.1, y1 - 0.1, 1.9)   # CRAC unit
    c.mesh.light(c.cx, c.cy, c.z + 2.9, (180, 210, 255), 1.0, 5.0, 8.0)


def f_technical(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    c.box("lspd_metal", x0 + 0.2, y0 + 0.2, 0, x0 + 1.8, y0 + 1.2, 1.8)      # electrical panel
    c.box("lspd_metal_dark", x0 + 2.2, y0 + 0.2, 0, x0 + 3.0, y0 + 0.8, 2.1)
    c.cyl("lspd_metal", x1 - 1.0, y1 - 1.0, 0, 1.9, 0.45, 16)                 # water heater
    c.cyl("lspd_metal_navy", x1 - 2.2, y1 - 1.0, 0, 1.2, 0.35, 16)
    for k in range(4):
        c.cyl("lspd_metal", x0 + 4.0 + k * 0.5, y0 + 0.3, 0.0, 3.2, 0.06, 8, col=False)   # risers
    c.box("lspd_metal", x0 + 3.8, y0 + 0.1, 2.9, x1 - 0.2, y0 + 0.5, 3.0, col=False)
    c.prop("prop_toolchest_01", x1 - 0.5, y0 + 0.6, 0, heading_to(-1, 0), lod=25)


def f_janitor(c):
    c.shelf(c.x0 + 0.1, c.y1 - 0.5, c.x0 + 2.5, c.y1 - 0.05, h=2.0, levels=4)
    c.prop("prop_cleaning_trolly", c.x1 - 1.0, c.cy, 0, heading_to(-1, 0), lod=25)
    c.prop("prop_bucket_01a", c.x1 - 2.0, c.cy - 0.3, 0, 0, lod=15)
    c.box("mat_white", c.x1 - 0.7, c.y1 - 0.6, 0, c.x1 - 0.1, c.y1 - 0.1, 0.6)   # mop sink


def f_locker(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    c.lockers(x0 + 0.05, y0 + 1.6, x0 + 0.5, y1 - 0.2, (1, 0))
    c.lockers(x1 - 0.5, y0 + 1.6, x1 - 0.05, y1 - 0.2, (-1, 0))
    c.lockers(x0 + 1.4, y1 - 0.5, x1 - 1.4, y1 - 0.05, (0, -1))
    c.bench(c.cx - 1.6, c.cy - 0.2, c.cx + 1.6, c.cy + 0.2)
    c.prop("prop_ld_shirt_01", c.cx - 0.6, c.cy, 0.45, 20, lod=15)
    c.image("mirror", "s", c.cx - 0.6, c.cx + 0.6, 1.0, 2.0, frame="lspd_metal") if c.wall_free("s", c.cx - 0.6, c.cx + 0.6, 1.0, 2.0) else None


def f_showers(c, men):
    x0, y0, x1, y1 = c.rect
    # shower stalls along the north wall, WC stalls along the west, vanity east
    n = int((x1 - x0 - 4.5) // 1.3)
    for k in range(n):
        sx = x0 + 4.0 + k * 1.3
        c.box("lspd_tile_white", sx, y1 - 1.4, 0, sx + 0.08, y1 - 0.1, 2.1)
        c.box("lspd_metal", sx + 0.5, y1 - 0.2, 1.9, sx + 0.7, y1 - 0.1, 2.0, col=False)  # shower head
        c.box("lspd_tile_dark", sx + 0.08, y1 - 1.35, 0.0, sx + 1.3, y1 - 0.1, 0.02, col=False)
    c.occupy(x0 + 4.0, y1 - 1.5, x1, y1)
    for k in range(3):
        sy0 = y0 + 0.4 + k * 1.6
        c.box("lspd_laminate_dark", x0 + 0.1, sy0 + 1.55, 0.15, x0 + 1.7, sy0 + 1.6, 2.1)
        c.box("lspd_laminate_dark", x0 + 1.65, sy0 + 0.1, 0.15, x0 + 1.7, sy0 + 0.35, 2.1)
        c.prop("prop_toilet_01", x0 + 0.45, sy0 + 0.8, 0, heading_to(1, 0), lod=30)
    c.occupy(x0, y0, x0 + 1.9, y0 + 5.4)
    if c.free(x1 - 0.7, y0 + 0.5, x1 - 0.09, y0 + 3.5, 1.0):
        c.box("lspd_stone", x1 - 0.65, y0 + 0.6, 0.82, x1 - 0.09, y0 + 3.4, 0.88)
        c.box("lspd_laminate_dark", x1 - 0.65, y0 + 0.6, 0.0, x1 - 0.09, y0 + 3.4, 0.82)
        for k in range(3):
            c.prop("prop_sink_06", x1 - 0.4, y0 + 1.0 + k * 0.95, 0.0, heading_to(-1, 0), lod=25)
        c.image("mirror", "e", y0 + 0.7, y0 + 3.3, 1.05, 2.0, frame="lspd_metal")
    c.bench(c.cx - 1.0, c.cy - 0.2, c.cx + 1.0, c.cy + 0.2)
    c.prop("prop_towel_rail_02", x1 - 0.2, y1 - 2.0, 1.0, heading_to(-1, 0), lod=20)


def f_break(c):
    c.sofa(c.x0 + 0.2, c.y1 - 3.6, c.x0 + 1.1, c.y1 - 1.0, (1, 0))
    c.sofa(c.x0 + 1.6, c.y1 - 1.0, c.x0 + 4.4, c.y1 - 0.15, (0, -1))
    c.table(c.x0 + 1.6, c.y1 - 3.0, c.x0 + 3.0, c.y1 - 1.8, h=0.42, top="lspd_wood_veneer")
    c.tv_wall("e", c.y1 - 3.6, c.y1 - 1.6, 1.2, 2.3, screen="emi_map")
    for k in range(2):
        c.table(c.cx - 0.6, c.y0 + 2.0 + k * 3.0, c.cx + 0.6, c.y0 + 3.0 + k * 3.0, top="lspd_laminate")
        c.chairs_around(c.cx - 0.6, c.y0 + 2.0 + k * 3.0, c.cx + 0.6, c.y0 + 3.0 + k * 3.0, model="prop_chair_02", ends=False)
    c.prop("prop_vend_soda_01", c.x1 - 0.5, c.y0 + 0.6, 0, heading_to(-1, 0), lod=40)
    c.prop("prop_vend_snak_01", c.x1 - 0.5, c.y0 + 1.7, 0, heading_to(-1, 0), lod=40)
    c.prop("prop_vend_coffe_01", c.x1 - 0.5, c.y0 + 2.8, 0, heading_to(-1, 0), lod=40)
    c.try_image("img_corkboard", "w", c.y0 + 2.0, c.y0 + 4.0, 1.1, 2.1)
    c.corner_plants()


def f_kitchen(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    c.counter(x0, y0 + 0.5, x0 + 0.65, y1 - 0.3, h=0.92, front="lspd_laminate", top="lspd_stone")
    c.counter(x0 + 0.65, y1 - 0.65, x1 - 0.8, y1, h=0.92, front="lspd_laminate", top="lspd_stone")
    c.box("lspd_laminate", x0, y0 + 0.5, 1.5, x0 + 0.35, y1 - 0.3, 2.3)            # wall cabinets
    c.prop("prop_micro_01", x0 + 0.3, y0 + 1.5, 0.92, heading_to(1, 0), lod=20)
    c.prop("prop_coffee_mac_02", x0 + 0.3, y0 + 2.5, 0.92, heading_to(1, 0), lod=20)
    c.prop("prop_kettle", x0 + 0.3, y0 + 3.2, 0.92, heading_to(1, 0), lod=15)
    c.prop("prop_toaster_01", x0 + 0.3, y0 + 3.8, 0.92, heading_to(1, 0), lod=15)
    c.prop("prop_sink_04", x0 + 1.8, y1 - 0.35, 0.0, heading_to(0, -1), lod=25)
    c.prop("prop_fridge_01", x1 - 0.45, y1 - 0.45, 0, heading_to(0, -1), lod=30)
    c.table(c.cx - 0.2, c.cy - 0.8, c.cx + 0.9, c.cy + 0.4, h=0.92, top="lspd_stone")


def f_dining(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    for i in range(2):
        for j in range(2):
            tx = x0 + 1.6 + i * 4.4
            ty = y0 + 1.5 + j * 3.6
            if c.table(tx, ty, tx + 2.0, ty + 0.9, top="lspd_wood_light"):
                c.chairs_around(tx, ty, tx + 2.0, ty + 0.9, model="prop_chair_02", ends=False, spacing=0.9)
    c.prop("prop_watercooler", x1 - 0.4, y0 + 0.4, 0, heading_to(-1, 1))
    c.corner_plants()
    c.try_image("img_merit", "n", x0 + 2.0, x0 + 4.4, 1.2, 2.4)


def f_gym(c):
    x0, y0, x1, y1 = c.x0, c.y0, c.x1, c.y1
    c.mesh.box("lspd_rubber", x0 + 0.5, y0 + 0.5, c.z + 0.002, x1 - 0.5, y1 - 0.5, c.z + 0.012, faces=("+z",))
    items = [("prop_muscle_bench_01", 0), ("prop_muscle_bench_03", 0), ("prop_muscle_bench_05", 90), ("prop_weight_bench_02", 0),
             ("prop_muscle_bench_02", 90), ("prop_muscle_bench_06", 0)]
    for k, (m, h) in enumerate(items):
        xx = x0 + 1.8 + (k % 3) * 3.2
        yy = y0 + 2.5 + (k // 3) * 4.0
        c.prop(m, xx, yy, 0, h, lod=40)
        c.occupy(xx - 1.0, yy - 1.2, xx + 1.0, yy + 1.2)
    c.prop("prop_weight_rack_01", x1 - 0.6, y0 + 2.0, 0, heading_to(-1, 0), lod=40)
    c.prop("prop_weight_rack_02", x1 - 0.6, y0 + 4.0, 0, heading_to(-1, 0), lod=40)
    for k in range(3):
        c.prop("prop_exer_bike_01", x0 + 1.5 + k * 1.4, y1 - 1.2, 0, heading_to(0, 1), lod=40)
    c.image("mirror", "w", y0 + 1.0, y0 + 6.0, 0.4, 2.4, frame="lspd_metal") if c.wall_free("w", y0 + 1.0, y0 + 6.0, 0.4, 2.4) else None
    c.tv_wall("w", y0 + 7.0, y0 + 9.0, 1.6, 2.7, screen="emi_map")
    c.prop("prop_watercooler", x0 + 0.4, y1 - 0.4, 0, heading_to(1, -1))
    c.lockers(x1 - 0.5, y1 - 3.0, x1 - 0.05, y1 - 0.6, (-1, 0), h=1.8)


def f_conference(c):
    x0, y0, x1, y1 = c.rect
    tx0, tx1 = c.cx - 4.0, c.cx + 4.0
    ty0, ty1 = c.cy - 0.75, c.cy + 0.75
    if c.table(tx0, ty0, tx1, ty1, top="lspd_wood_veneer"):
        c.chairs_around(tx0, ty0, tx1, ty1, model="v_corp_offchair", spacing=0.95)
        for k in range(5):
            c.papers(tx0 + 0.8 + k * 1.6, c.cy, 0.75, n=1)
    c.tv_wall("e", c.cy - 1.5, c.cy + 1.5, 0.9, 2.7, screen="emi_map")
    c.try_image("img_wall_logo", "w", c.cy - 1.2, c.cy + 1.2, 0.8, 3.0)
    c.prop("prop_flag_us", c.x0 + 0.5, c.y1 - 0.5, 0, 135, lod=40)
    c.corner_plants()
    c.box("lspd_wood_veneer", c.x1 - 0.55, c.y0 + 0.5, 0, c.x1 - 0.1, c.y0 + 3.0, 0.85)   # credenza
    c.prop("prop_coffee_mac_02", c.x1 - 0.3, c.y0 + 1.0, 0.85, heading_to(-1, 0), lod=20)


def f_meeting(c):
    if c.table(c.cx - 1.6, c.cy - 0.6, c.cx + 1.6, c.cy + 0.6, top="lspd_wood_light"):
        c.chairs_around(c.cx - 1.6, c.cy - 0.6, c.cx + 1.6, c.cy + 0.6, spacing=0.9)
    c.tv_wall("w", c.cy - 1.0, c.cy + 1.0, 1.0, 2.2, screen="emi_cad")
    c.try_image("img_whiteboard", "e", c.cy - 1.0, c.cy + 1.0, 1.0, 2.0)
    c.corner_plants()


def f_admin(c):
    # executive assistants + waiting chairs
    c.desk(c.x0 + 3.0, c.cy, 1.8, 0.8, (0, -1), monitors=2)
    c.desk(c.x1 - 3.0, c.cy, 1.8, 0.8, (0, -1), monitors=2)
    for k in range(3):
        c.prop("prop_waiting_seat_01", c.cx - 1.6 + k * 1.6, c.y0 + 0.55, 0, heading_to(0, 1))
    c.filing(c.x0 + 0.4, c.y1 - 1.0, (1, 0), n=2)
    c.filing(c.x1 - 0.4, c.y1 - 1.0, (-1, 0), n=2)
    c.prop("prop_copier_01", c.cx + 3.2, c.y1 - 0.6, 0, heading_to(0, -1), lod=30)
    c.try_image("img_merit", "n", c.cx - 1.2, c.cx + 1.2, 1.3, 2.5)
    c.corner_plants()


def f_corridor(c):
    x0, y0, x1, y1 = c.rect
    long_x = (x1 - x0) > (y1 - y0)
    L = (x1 - x0) if long_x else (y1 - y0)
    for k in range(int(L // 14) + 1):
        if long_x:
            xx = x0 + 3.0 + k * 14.0
            if xx < x1 - 1:
                c.ceiling_cam(xx, y0 + 0.2, 0)
        else:
            yy = y0 + 2.0 + k * 14.0
            if yy < y1 - 1:
                c.ceiling_cam(x0 + 0.2, yy, 270)
    # wall boards / art / benches where the wall is free
    if long_x:
        for k in range(int(L // 9)):
            a = x0 + 4.5 + k * 9.0
            if rnd.random() < 0.5:
                c.try_image(rnd.choice(["img_wanted", "img_infoboard", "img_merit"]), "n", a, a + 1.4, 1.2, 2.1)
            else:
                c.try_image(rnd.choice(["img_wanted", "img_infoboard", "img_merit"]), "s", a, a + 1.4, 1.2, 2.1)
        # navy wainscot accent band
        c.mesh.box("lspd_metal_navy", x0, y1 - LY.INT_T / 2 - 0.005, c.z + 1.0, x1, y1 - LY.INT_T / 2, c.z + 1.08, faces=("-y",))
        c.mesh.box("lspd_metal_navy", x0, y0 + LY.INT_T / 2, c.z + 1.0, x1, y0 + LY.INT_T / 2 + 0.005, c.z + 1.08, faces=("+y",))
        if c.r.level == 0:
            c.prop("prop_watercooler", x0 + 0.5 + 20.0, y1 - 0.35, 0, heading_to(0, -1))
    # level/zone floor stripe at secure transitions is drawn by the door signs


FURNISH = {
    "lobby": f_lobby,
    "report": f_report,
    "interview_public": f_interview_public,
    "security_office": f_security,
    "office": lambda c: f_office_small(c, n=3 if c.w * c.d > 50 else 2),
    "office_cmd": lambda c: f_office_small(c, n=1),
    "office_exec": lambda c: f_office_small(c, exec_=True),
    "admin": f_admin,
    "conference": f_conference,
    "meeting": f_meeting,
    "officers": f_open_office,
    "briefing": f_briefing,
    "patrol_bullpen": f_open_office,
    "armory": f_armory,
    "equipment": f_equipment,
    "riot": f_riot,
    "maintenance": f_maintenance,
    "booking": f_booking,
    "mugshot": f_mugshot,
    "fingerprint": f_fingerprint,
    "property": f_property,
    "detention_control": f_det_control,
    "detention_corridor": f_cellcorr,
    "cell": f_cell,
    "cell_hs": lambda c: f_cell(c, hs=True),
    "sallyport": f_sallyport,
    "vehicle_intake": f_intake,
    "garage": f_garage,
    "interrogation": f_interrogation,
    "observation": f_observation,
    "case_room": f_case_room,
    "lineup": f_lineup,
    "lineup_view": f_lineup_view,
    "evidence": f_evidence,
    "dispatch": f_dispatch,
    "dispatch_super": f_disp_super,
    "radio": f_radio,
    "analysis": f_analysis,
    "detectives": f_open_office,
    "lab": f_lab,
    "archive": f_archive,
    "documents": lambda c: f_archive(c, docs=True),
    "server": f_server,
    "technical": f_technical,
    "janitor": f_janitor,
    "locker": f_locker,
    "showers": lambda c: f_showers(c, c.r.rid.endswith("_m")),
    "break": f_break,
    "kitchen": f_kitchen,
    "dining": f_dining,
    "gym": f_gym,
    "corridor": f_corridor,
    "wc_public": lambda c: f_wc(c, c.r.rid.endswith("_m")),
    "front_desk": lambda c: f_counter_room(c, [(23.0, 26.8), (29.2, 33.0)]),
    "records_counter": lambda c: f_counter_room(c, [(11.8, 15.6), (16.4, 20.2)]),
    "checkpoint": lambda c: (c.ceiling_cam(c.x0 + 0.2, c.y0 + 0.2, 315),
                             c.box("img_stripe", c.x0, c.y1 - 0.6, 0, c.x1, c.y1 - 0.5, 0.004, col=False, faces=("+z",))),
    "stair": lambda c: None,
}


def furnish_all(sh):
    sh.props_int = []
    for r in LY.ROOMS:
        fn = FURNISH.get(r.rtype)
        if fn is None:
            raise RuntimeError(f"no furnishing for {r.rtype}")
        for rect in r.rects:
            fn(Room(sh, r, rect))
    door_signs(sh)
    # level directory signs in the main corridors next to the stairs
    for lv, rid in ((0, "corr1"), (1, "corr2"), (2, "corr3")):
        r = next(x for x in LY.ROOMS if x.rid == rid)
        mesh = sh.imesh(r)
        z = LY.LEVEL_Z[lv]
        B.sign_quad(mesh, f"LEVEL {lv + 1}", None, 3.6, 20.4 - LY.INT_T / 2 - 0.02, z + 1.6, 0.9, 0.45, facing="-y")
        B.sign_quad(mesh, f"LEVEL {lv + 1}", None, 51.5, 20.4 - LY.INT_T / 2 - 0.02, z + 1.6, 0.9, 0.45, facing="-y")
