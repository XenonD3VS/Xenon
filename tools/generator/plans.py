"""Renders floor plan images (docs/plans/*.png) from layout.py."""
import os

from PIL import Image, ImageDraw, ImageFont

import layout as LY

FONT = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
SC = 22          # px per metre
M = 40           # margin px


def px(x, y, h):
    return M + x * SC, M + (h - y) * SC


def render(level, path):
    H = 50 if level == 0 else 36
    W = 56
    img = Image.new("RGB", (int(W * SC + 2 * M), int(H * SC + 2 * M + 60)), (250, 250, 250))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 11)
    ft = ImageFont.truetype(FONT, 20)
    for r in LY.rooms_on(level):
        col = LY.ZONE_COLORS[r.zone]
        for a in r.rects:
            x0, y0 = px(a[0], a[3], H)
            x1, y1 = px(a[2], a[1], H)
            d.rectangle([x0, y0, x1, y1], fill=col, outline=(40, 40, 40), width=2)
        bx0, by0, bx1, by1 = max(r.rects, key=lambda a: (a[2] - a[0]) * (a[3] - a[1]))
        cx, cy = px((bx0 + bx1) / 2, (by0 + by1) / 2, H)
        words = r.title.split(" ")
        lines, cur = [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) > (bx1 - bx0) * SC - 6 and cur:
                lines.append(cur)
                cur = w
            else:
                cur = t
        lines.append(cur)
        for i, t in enumerate(lines):
            d.text((cx, cy + (i - (len(lines) - 1) / 2) * 13), t, font=f, fill=(20, 20, 20), anchor="mm")
    for dr in LY.DOORS:
        if dr.level != level:
            continue
        hw = dr.width / 2
        if dr.orient == "h":
            a, b = px(dr.x - hw, dr.y, H), px(dr.x + hw, dr.y, H)
            d.rectangle([a[0], a[1] - 3, b[0], b[1] + 3], fill=(255, 255, 255))
        else:
            a, b = px(dr.x, dr.y + hw, H), px(dr.x, dr.y - hw, H)
            d.rectangle([a[0] - 3, a[1], b[0] + 3, b[1]], fill=(255, 255, 255))
        c = {"sec": (200, 40, 40), "cell": (120, 0, 0), "cell_hs": (120, 0, 0), "vehicle": (40, 40, 200),
             "auto": (0, 120, 200), "exit": (0, 150, 0)}.get(dr.kind, (90, 90, 90))
        if dr.orient == "h":
            d.line([a, b], fill=c, width=3)
        else:
            d.line([a, b], fill=c, width=3)
    for w in LY.WINDOWS:
        if w.level != level:
            continue
        if w.orient == "h":
            a, b = px(w.a, w.pos, H), px(w.b, w.pos, H)
        else:
            a, b = px(w.pos, w.b, H), px(w.pos, w.a, H)
        c = {"mirror": (60, 60, 60), "counter": (160, 110, 40)}.get(w.kind, (40, 150, 230))
        d.line([a, b], fill=c, width=5)
    d.text((M, H * SC + M + 20), f"xenon_police — LSPD  —  {LY.LEVEL_NAMES[level]}   (1 grid = 1 m, north up)",
           font=ft, fill=(20, 20, 20))
    x = M + 620
    for z, c in LY.ZONE_COLORS.items():
        d.rectangle([x, H * SC + M + 22, x + 16, H * SC + M + 38], fill=c, outline=(40, 40, 40))
        d.text((x + 20, H * SC + M + 30), z, font=f, fill=(20, 20, 20), anchor="lm")
        x += 105
    img.save(path)


def render_all(out):
    os.makedirs(out, exist_ok=True)
    for lv in range(4):
        render(lv, os.path.join(out, f"plan_{LY.LEVEL_NAMES[lv].lower()}.png"))


if __name__ == "__main__":
    import sys
    render_all(sys.argv[1])
