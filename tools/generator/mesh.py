"""Minimal mesh + collision builders with world-space UV mapping."""
import math

import materials as M

FACES = ("+x", "-x", "+y", "-y", "+z", "-z")
NORM = {"+x": (1, 0, 0), "-x": (-1, 0, 0), "+y": (0, 1, 0), "-y": (0, -1, 0), "+z": (0, 0, 1), "-z": (0, 0, -1)}
# right (u) and up (-v) direction for each face as seen from outside
RIGHT = {"+x": (0, 1, 0), "-x": (0, -1, 0), "+y": (-1, 0, 0), "-y": (1, 0, 0), "+z": (1, 0, 0), "-z": (-1, 0, 0)}
UP = {"+x": (0, 0, 1), "-x": (0, 0, 1), "+y": (0, 0, 1), "-y": (0, 0, 1), "+z": (0, 1, 0), "-z": (0, 1, 0)}


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def norm(a):
    l = math.sqrt(dot(a, a)) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


class Mesh:
    def __init__(self, colour=(255, 255, 255, 255)):
        self.parts = {}     # mat -> [verts, indices]
        self.colour = colour
        self.lights = []

    def _part(self, mat):
        if mat not in self.parts:
            self.parts[mat] = [[], []]
        return self.parts[mat]

    def tri_count(self):
        return sum(len(p[1]) // 3 for p in self.parts.values())

    def add_poly(self, mat, pts, uvs, normal=None, colour=None):
        """Convex polygon, CCW seen from the front."""
        if normal is None:
            normal = norm(cross(sub(pts[1], pts[0]), sub(pts[2], pts[0])))
        # tangent from first triangle uv gradient
        p0, p1, p2 = pts[0], pts[1], pts[2]
        (u0, v0), (u1, v1), (u2, v2) = uvs[0], uvs[1], uvs[2]
        e1, e2 = sub(p1, p0), sub(p2, p0)
        du1, dv1, du2, dv2 = u1 - u0, v1 - v0, u2 - u0, v2 - v0
        r = du1 * dv2 - du2 * dv1
        if abs(r) < 1e-9:
            t = (1.0, 0.0, 0.0)
            b = (0.0, 1.0, 0.0)
        else:
            f = 1.0 / r
            t = tuple((e1[i] * dv2 - e2[i] * dv1) * f for i in range(3))
            b = tuple((e2[i] * du1 - e1[i] * du2) * f for i in range(3))
        t = sub(t, tuple(normal[i] * dot(normal, t) for i in range(3)))
        t = norm(t)
        w = 1.0 if dot(cross(normal, t), tuple(-x for x in b)) >= 0 else -1.0
        part = self._part(mat)
        base = len(part[0])
        col = colour or self.colour
        for p, uv in zip(pts, uvs):
            part[0].append((p[0], p[1], p[2], normal[0], normal[1], normal[2], uv[0], uv[1], t[0], t[1], t[2], w, col))
        for i in range(1, len(pts) - 1):
            part[1].extend((base, base + i, base + i + 1))

    def face_uv(self, mat, face, pts, explicit=None):
        m = M.get(mat)
        sub = None
        if isinstance(explicit, tuple) and explicit and explicit[0] == "sub":
            sub = explicit[1:]
            explicit = None
        if explicit is not None:
            return explicit
        if m.tile <= 0 or sub:
            r, u = RIGHT[face], UP[face]
            us = [dot(p, r) for p in pts]
            vs = [dot(p, u) for p in pts]
            umin, umax, vmin, vmax = min(us), max(us), min(vs), max(vs)
            res = [((a - umin) / ((umax - umin) or 1), (vmax - b) / ((vmax - vmin) or 1)) for a, b in zip(us, vs)]
            if sub:
                u0, v0, u1, v1 = sub
                res = [(u0 + (u1 - u0) * a, v0 + (v1 - v0) * b) for a, b in res]
            return res
        r, u = RIGHT[face], UP[face]
        return [(dot(p, r) / m.tile, -dot(p, u) / m.tile) for p in pts]

    def quad_face(self, mat, face, x0, y0, z0, x1, y1, z1, uv=None, colour=None):
        """Axis aligned rectangle lying on the face plane of box [x0..x1]x[y0..y1]x[z0..z1]."""
        if face == "+x":
            pts = [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]
        elif face == "-x":
            pts = [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)]
        elif face == "+y":
            pts = [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)]
        elif face == "-y":
            pts = [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]
        elif face == "+z":
            pts = [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        else:
            pts = [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)]
        self.add_poly(mat, pts, self.face_uv(mat, face, pts, uv), NORM[face], colour)

    def box(self, mat, x0, y0, z0, x1, y1, z1, faces=FACES, uv=None, colour=None):
        """mat: material name or dict face->material."""
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if z1 < z0:
            z0, z1 = z1, z0
        for f in faces:
            m = mat.get(f) if isinstance(mat, dict) else mat
            if m:
                self.quad_face(m, f, x0, y0, z0, x1, y1, z1, uv.get(f) if isinstance(uv, dict) else uv, colour)

    def cylinder(self, mat, cx, cy, z0, z1, r, seg=12, caps=True):
        for i in range(seg):
            a0, a1 = 2 * math.pi * i / seg, 2 * math.pi * (i + 1) / seg
            p0 = (cx + math.cos(a0) * r, cy + math.sin(a0) * r)
            p1 = (cx + math.cos(a1) * r, cy + math.sin(a1) * r)
            pts = [(p0[0], p0[1], z0), (p1[0], p1[1], z0), (p1[0], p1[1], z1), (p0[0], p0[1], z1)]
            uv = [(i / seg * 2, 0), ((i + 1) / seg * 2, 0), ((i + 1) / seg * 2, -(z1 - z0)), (i / seg * 2, -(z1 - z0))]
            n = norm((math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2), 0))
            self.add_poly(mat, pts, uv, n)
        if caps:
            top = [(cx + math.cos(2 * math.pi * i / seg) * r, cy + math.sin(2 * math.pi * i / seg) * r, z1) for i in range(seg)]
            self.add_poly(mat, top, [(p[0], -p[1]) for p in top], (0, 0, 1))

    def ramp(self, mat, x0, x1, ya, za, yb, zb, width_axis="x"):
        """Sloped quad from line y=ya,z=za to y=yb,z=zb spanning x0..x1 (upward facing)."""
        if yb > ya:
            pts = [(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)]
        else:
            pts = [(x1, ya, za), (x0, ya, za), (x0, yb, zb), (x1, yb, zb)]
        uvs = [(p[0] / 1.0, -p[1] / 1.0) for p in pts]
        self.add_poly(mat, pts, uvs)

    def light(self, x, y, z, colour=(255, 244, 230), intensity=3.0, falloff=7.0, exponent=16.0, kind="Point",
              direction=(0, 0, -1), cone_in=30.0, cone_out=60.0, extent=(1, 1, 1), corona=0.0):
        self.lights.append(dict(pos=(x, y, z), colour=colour, intensity=intensity, falloff=falloff,
                                exponent=exponent, kind=kind, direction=direction, cone_in=cone_in,
                                cone_out=cone_out, extent=extent, corona=corona))

    def merge(self, other):
        for mat, (v, i) in other.parts.items():
            part = self._part(mat)
            base = len(part[0])
            part[0].extend(v)
            part[1].extend(x + base for x in i)
        self.lights.extend(other.lights)

    def bounds(self):
        mn = [1e9] * 3
        mx = [-1e9] * 3
        for v, _ in self.parts.values():
            for p in v:
                for k in range(3):
                    mn[k] = min(mn[k], p[k])
                    mx[k] = max(mx[k], p[k])
        for l in self.lights:
            for k in range(3):
                mn[k] = min(mn[k], l["pos"][k])
                mx[k] = max(mx[k], l["pos"][k])
        if mn[0] > mx[0]:
            return (0, 0, 0), (0, 0, 0)
        return tuple(mn), tuple(mx)


STAIR_FLAG = "FLAG_STAIRS"


class Collision:
    """Triangle soup grouped by (collision material, room id, flags)."""

    def __init__(self):
        self.tris = []   # (p0, p1, p2, key)

    def add_tri(self, a, b, c, key):
        self.tris.append((a, b, c, key))

    def box(self, x0, y0, z0, x1, y1, z1, col="CONCRETE", room=0, flags="NONE", faces=FACES):
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if z1 < z0:
            z0, z1 = z1, z0
        if (x1 - x0) < 1e-4 or (y1 - y0) < 1e-4 or (z1 - z0) < 1e-4:
            return
        key = (M.COL[col], room, flags)
        q = {
            "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            "-x": [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)],
            "+y": [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)],
            "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
            "-z": [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)],
        }
        for f in faces:
            p = q[f]
            self.add_tri(p[0], p[1], p[2], key)
            self.add_tri(p[0], p[2], p[3], key)

    def quad(self, pts, col="CONCRETE", room=0, flags="NONE"):
        key = (M.COL[col], room, flags)
        self.add_tri(pts[0], pts[1], pts[2], key)
        self.add_tri(pts[0], pts[2], pts[3], key)

    def ramp_solid(self, x0, x1, ya, za, yb, zb, col="CONCRETE", room=0, thick=0.25):
        """Walkable sloped slab (top face + underside + sides) for stairs."""
        fl = "FLAG_STAIRS"
        lo = min(ya, yb)
        if yb > ya:
            top = [(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)]
        else:
            top = [(x1, ya, za), (x0, ya, za), (x0, yb, zb), (x1, yb, zb)]
        self.quad(top, col, room, fl)
        bot = [(p[0], p[1], p[2] - thick) for p in reversed(top)]
        self.quad(bot, col, room, "NONE")
        # side faces
        key = (M.COL[col], room, "NONE")
        for x in (x0, x1):
            a, b = (x, ya, za), (x, yb, zb)
            c, d = (x, yb, zb - thick), (x, ya, za - thick)
            if x == x0:
                self.add_tri(a, d, c, key); self.add_tri(a, c, b, key)
            else:
                self.add_tri(a, b, c, key); self.add_tri(a, c, d, key)
