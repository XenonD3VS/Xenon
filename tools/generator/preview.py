"""Software preview renderer (QA only): rasterizes the generated meshes with their textures.

Base-game props cannot be rendered here (their models live in the game files) - they are drawn
as small orange markers so their placement can be checked.
"""
import math
import os
import sys

import numpy as np
from PIL import Image

import building as B
import furnish as F
import materials as M

TEX_CACHE = {}


def tex(name, tex_dir):
    if name not in TEX_CACHE:
        p = os.path.join(tex_dir, name + ".dds")
        img = Image.open(p).convert("RGBA")
        if img.width > 256:
            img = img.resize((256, max(1, int(256 * img.height / img.width))))
        TEX_CACHE[name] = np.asarray(img).astype(np.float32) / 255.0
    return TEX_CACHE[name]


def look_at(eye, target, up=(0, 0, 1)):
    f = np.array(target, float) - np.array(eye, float)
    f /= np.linalg.norm(f)
    r = np.cross(f, up)
    r /= np.linalg.norm(r)
    u = np.cross(r, f)
    return np.array(eye, float), r, u, f


def render(meshes, cam, out, tex_dir, W=1280, H=720, fov=70.0, markers=(), ortho=None, sky=(170, 196, 222),
           clip_z=None):
    eye, r, u, f = cam
    zbuf = np.full((H, W), np.inf, np.float32)
    img = np.zeros((H, W, 3), np.float32)
    img[:] = np.array(sky, np.float32) / 255.0
    foc = (W / 2) / math.tan(math.radians(fov) / 2)
    L = np.array([0.4, -0.3, 0.85])
    L /= np.linalg.norm(L)

    def project(P):
        d = P - eye
        x = d @ r
        y = d @ u
        z = d @ f
        if ortho:
            return np.stack([W / 2 + x * ortho, H / 2 - y * ortho, z], -1)
        return np.stack([W / 2 + foc * x / z, H / 2 - foc * y / z, z], -1)

    for mesh in meshes:
        for mat, (verts, idx) in mesh.parts.items():
            if not idx:
                continue
            m = M.get(mat)
            t = tex(m.diffuse, tex_dir)
            th, tw = t.shape[:2]
            V = np.array([v[:8] for v in verts], np.float32)
            P = V[:, :3]
            N = V[:, 3:6]
            UV = V[:, 6:8]
            S = project(P)
            tris = np.array(idx).reshape(-1, 3)
            emissive = m.shader == "emissive"
            alpha = m.alpha
            NEAR = 0.06
            work = []
            for (a, b, c) in tris:
                if clip_z is not None and min(P[a, 2], P[b, 2], P[c, 2]) > clip_z:
                    continue
                n = N[a]
                view = P[a] - eye if not ortho else f
                if np.dot(n, view) > 0 and not alpha:
                    continue
                za, zb, zc = S[a, 2], S[b, 2], S[c, 2]
                if min(za, zb, zc) >= NEAR or ortho:
                    work.append(((S[a], S[b], S[c]), (UV[a], UV[b], UV[c]), n))
                    continue
                if max(za, zb, zc) < NEAR:
                    continue
                # clip polygon against the near plane in camera depth
                poly = [(P[i], UV[i], S[i, 2]) for i in (a, b, c)]
                outp = []
                for k in range(3):
                    p1, u1, d1 = poly[k]
                    p2, u2, d2 = poly[(k + 1) % 3]
                    if d1 >= NEAR:
                        outp.append((p1, u1))
                    if (d1 >= NEAR) != (d2 >= NEAR):
                        t_ = (NEAR - d1) / (d2 - d1)
                        outp.append((p1 + (p2 - p1) * t_, u1 + (u2 - u1) * t_))
                pp = [project(q[0][None, :])[0] for q in outp]
                for k in range(1, len(outp) - 1):
                    work.append(((pp[0], pp[k], pp[k + 1]), (outp[0][1], outp[k][1], outp[k + 1][1]), n))
            for (sa, sb, sc), (ua, ub, uc), n in work:
                za, zb, zc = sa[2], sb[2], sc[2]
                xs = np.array([sa[0], sb[0], sc[0]])
                ys = np.array([sa[1], sb[1], sc[1]])
                x0, x1 = int(max(0, math.floor(xs.min()))), int(min(W - 1, math.ceil(xs.max())))
                y0, y1 = int(max(0, math.floor(ys.min()))), int(min(H - 1, math.ceil(ys.max())))
                if x0 > x1 or y0 > y1:
                    continue
                area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
                if abs(area) < 1e-9:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / area
                w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / area
                w2 = 1 - w0 - w1
                inside = (w0 >= -1e-4) & (w1 >= -1e-4) & (w2 >= -1e-4)
                if not inside.any():
                    continue
                if ortho:
                    iz = w0 * za + w1 * zb + w2 * zc
                    depth = iz
                    pw0, pw1, pw2 = w0, w1, w2
                else:
                    iz = w0 / za + w1 / zb + w2 / zc
                    depth = 1 / iz
                    pw0, pw1, pw2 = w0 / za / iz, w1 / zb / iz, w2 / zc / iz
                zb_ = zbuf[y0:y1 + 1, x0:x1 + 1]
                vis = inside & (depth < zb_)
                if not vis.any():
                    continue
                uu = pw0 * ua[0] + pw1 * ub[0] + pw2 * uc[0]
                vv = pw0 * ua[1] + pw1 * ub[1] + pw2 * uc[1]
                ti = (np.mod(vv, 1.0) * th).astype(int).clip(0, th - 1)
                tj = (np.mod(uu, 1.0) * tw).astype(int).clip(0, tw - 1)
                col = t[ti, tj]
                if emissive:
                    shade = 1.15
                else:
                    shade = 0.45 + 0.55 * max(0.0, float(np.dot(n, L))) + 0.15 * abs(n[2])
                rgb = col[..., :3] * shade
                region = img[y0:y1 + 1, x0:x1 + 1]
                if alpha:
                    a_ = 0.35
                    region[vis] = region[vis] * (1 - a_) + np.array([0.55, 0.7, 0.8]) * a_
                else:
                    region[vis] = rgb[vis]
                    zb_[vis] = depth[vis]
    out_img = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    # prop markers
    if markers:
        from PIL import ImageDraw
        d = ImageDraw.Draw(out_img)
        for p in markers:
            P = np.array(p["pos"], float)
            if clip_z is not None and P[2] > clip_z:
                continue
            s = project(P[None, :])[0]
            if s[2] <= 0.05 or not (0 <= s[0] < W and 0 <= s[1] < H):
                continue
            yy, xx = int(s[1]), int(s[0])
            if zbuf[yy, xx] + 0.4 < s[2] and not ortho:
                continue
            rad = 3 if ortho else max(2, int(180 / s[2]))
            d.ellipse([xx - rad, yy - rad, xx + rad, yy + rad], fill=(255, 140, 0), outline=(90, 40, 0))
    out_img.save(out)
    print("wrote", out)


def main(tex_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    sh = B.build_all()
    F.furnish_all(sh)
    ints = list(sh.int.values())
    allm = ints + [sh.ext, sh.site]
    props = sh.props_int + [dict(pos=d["pos"]) for d in sh.doors]
    jobs = sys.argv[3:] or ["aerial", "front", "plans", "lobby", "dispatch", "cells", "chief", "lab"]
    if "aerial" in jobs:
        render([sh.ext, sh.site], look_at((-40, -60, 55), (28, 20, 4)), os.path.join(out_dir, "aerial.png"), tex_dir,
               markers=sh.props_ext)
    if "front" in jobs:
        render([sh.ext, sh.site], look_at((28, -38, 3.5), (28, 0, 6)), os.path.join(out_dir, "front.png"), tex_dir, fov=75)
    if "plans" in jobs:
        for lv, zc in ((0, 2.9), (1, 7.1), (2, 11.3)):
            ms = [m for k, m in sh.int.items()]
            render(ms, look_at((28, 25, 60), (28, 25.001, 0), up=(0, 1, 0)), os.path.join(out_dir, f"top_l{lv + 1}.png"), tex_dir,
                   W=1400, H=1250, ortho=23.0, markers=[p for p in props if B.LY.LEVEL_Z[lv] - 0.1 < p["pos"][2] < B.LY.LEVEL_Z[lv] + 3.5],
                   clip_z=zc, sky=(30, 30, 34))
    if "lobby" in jobs:
        render(allm, look_at((12.0, 1.0, 1.7), (30, 10, 1.6)), os.path.join(out_dir, "lobby.png"), tex_dir, markers=props)
    if "dispatch" in jobs:
        render(allm, look_at((37.0, 16.5, 4.2 + 2.6), (18, 8, 4.2 + 1.2)), os.path.join(out_dir, "dispatch.png"), tex_dir, markers=props)
    if "cells" in jobs:
        render(allm, look_at((25.5, 29.2, 1.6), (44, 32, 1.0)), os.path.join(out_dir, "cells.png"), tex_dir, markers=props)
    if "chief" in jobs:
        render(allm, look_at((9.0, 1.0, 8.4 + 1.7), (3, 10, 8.4 + 1.0)), os.path.join(out_dir, "chief.png"), tex_dir, markers=props)
    if "lab" in jobs:
        render(allm, look_at((27, 21.5, 4.2 + 1.8), (37, 34, 4.2 + 0.8)), os.path.join(out_dir, "lab.png"), tex_dir, markers=props)
    if "gym" in jobs:
        render(allm, look_at((39, 21, 8.4 + 1.8), (52, 34, 8.4 + 0.8)), os.path.join(out_dir, "gym.png"), tex_dir, markers=props)
    if "stair" in jobs:
        render(allm, look_at((1.0, 20.8, 1.7), (2.5, 26.0, 2.5)), os.path.join(out_dir, "stair.png"), tex_dir, markers=props)
    if "garage" in jobs:
        render(allm, look_at((16, 37, 2.0), (50, 48, 1.0)), os.path.join(out_dir, "garage.png"), tex_dir, markers=props)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
