"""Procedural texture generation for xenon_police.

Every texture is generated from code (no third-party image assets), saved as PNG
and converted to DXT-compressed DDS with full mip chains via ImageMagick.
"""
import math
import os
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_DIR = "/usr/share/fonts/opentype/inter"
FONT_BOLD = os.path.join(FONT_DIR, "Inter-Bold.otf")
FONT_SEMI = os.path.join(FONT_DIR, "Inter-SemiBold.otf")
FONT_REG = os.path.join(FONT_DIR, "Inter-Medium.otf")
FONT_BLACK = os.path.join(FONT_DIR, "Inter-ExtraBold.otf")
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

RNG = np.random.default_rng(1337)

# Palette (sRGB)
NAVY = (22, 38, 66)
NAVY_DARK = (14, 24, 42)
ANTHRACITE = (46, 49, 54)
GREY = (128, 132, 138)
LIGHT_GREY = (196, 199, 203)
WHITE = (236, 237, 238)
ACCENT = (86, 156, 214)
GOLD = (196, 160, 82)


def font(path, size):
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------- noise utils
def tile_noise(size, beta=2.0, seed=None):
    """Seamlessly tileable 1/f^beta noise in range 0..1 (FFT based)."""
    rng = np.random.default_rng(seed) if seed is not None else RNG
    w = rng.standard_normal((size, size))
    f = np.fft.fft2(w)
    fy = np.fft.fftfreq(size)[:, None]
    fx = np.fft.fftfreq(size)[None, :]
    r = np.sqrt(fx * fx + fy * fy)
    r[0, 0] = 1.0
    f = f / (r ** (beta / 2.0))
    f[0, 0] = 0
    n = np.real(np.fft.ifft2(f))
    n -= n.min()
    n /= max(n.max(), 1e-9)
    return n


def speckle(size, density, seed=None):
    rng = np.random.default_rng(seed) if seed is not None else RNG
    return (rng.random((size, size)) < density).astype(np.float32)


def colorize(base, amount, n):
    """base rgb tuple, n 0..1 array -> HxWx3 float array 0..255."""
    b = np.array(base, dtype=np.float32)[None, None, :]
    return np.clip(b * (1.0 + (n[..., None] - 0.5) * amount), 0, 255)


def to_img(arr):
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def normal_from_height(h, strength=2.0):
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * strength
    dy = (np.roll(h, -1, axis=0) - np.roll(h, 1, axis=0)) * strength
    nz = np.ones_like(h)
    l = np.sqrt(dx * dx + dy * dy + nz * nz)
    nx, ny, nz = -dx / l, dy / l, nz / l
    rgb = np.stack([(nx * 0.5 + 0.5), (ny * 0.5 + 0.5), (nz * 0.5 + 0.5)], axis=-1) * 255
    return to_img(rgb)


def spec_from(v, lo, hi):
    g = np.clip(lo + v * (hi - lo), 0, 1) * 255
    return to_img(np.stack([g, g, g], axis=-1))


def grid_mask(size, cells, line_px):
    m = np.zeros((size, size), np.float32)
    step = size / cells
    for i in range(cells):
        p = int(round(i * step))
        m[:, max(0, p - line_px // 2): p + (line_px + 1) // 2] = 1
        m[max(0, p - line_px // 2): p + (line_px + 1) // 2, :] = 1
    # wrap line at 0 (half on both edges)
    return m


# ------------------------------------------------------------- tiled surfaces
def tex_terrazzo(s=512):
    n = tile_noise(s, 1.2, 1)
    base = colorize((205, 205, 200), 0.10, n)
    rng = np.random.default_rng(2)
    img = to_img(base)
    d = ImageDraw.Draw(img)
    for _ in range(2600):
        x, y = rng.integers(0, s, 2)
        r = rng.integers(1, 4)
        c = rng.choice([(70, 72, 78), (150, 152, 156), (240, 240, 236), (60, 82, 112), (120, 110, 100)])
        for ox in (-s, 0, s):
            for oy in (-s, 0, s):
                d.ellipse([x + ox - r, y + oy - r, x + ox + r, y + oy + r], fill=tuple(int(v) for v in c))
    a = np.asarray(img).astype(np.float32)
    # thin brass/steel divider strips every 1 m (texture covers 2 m)
    a[:, s // 2 - 1: s // 2 + 1] = (150, 150, 150)
    a[s // 2 - 1: s // 2 + 1, :] = (150, 150, 150)
    a[:, 0:1] = a[:, -1:] = (150, 150, 150)
    a[0:1, :] = a[-1:, :] = (150, 150, 150)
    h = n * 0.2
    return to_img(a), normal_from_height(h, 1.0), spec_from(np.ones_like(n) * 0.8 + n * 0.2, 0.25, 0.55)


def tex_carpet(s=512, base=(34, 46, 68)):
    # carpet tiles 50cm, texture = 1m (2x2 tiles), alternating pile direction
    n1 = tile_noise(s, 0.6, 3)
    n2 = tile_noise(s, 2.5, 4)
    a = colorize(base, 0.35, n1 * 0.7 + n2 * 0.3)
    half = s // 2
    yy, xx = np.mgrid[0:s, 0:s]
    stripe = (np.sin((xx + yy * ((xx // half + yy // half) % 2 * 2 - 1)) * 0.9) * 0.5 + 0.5)
    a *= (0.93 + stripe[..., None] * 0.07)
    seam = np.zeros((s, s), np.float32)
    for p in (0, half, s - 1):
        seam[:, max(0, p - 1):p + 1] = 1
        seam[max(0, p - 1):p + 1, :] = 1
    a *= (1 - seam[..., None] * 0.25)
    h = n1 * 0.6 + stripe * 0.2 - seam * 0.5
    return to_img(a), normal_from_height(h, 1.5), spec_from(n1, 0.02, 0.08)


def tex_vinyl(s=512):
    n = tile_noise(s, 1.0, 5)
    a = colorize((150, 153, 156), 0.12, n)
    sp = speckle(s, 0.02, 6)
    a = a * (1 - sp[..., None] * 0.3) + sp[..., None] * 0.0
    sp2 = speckle(s, 0.01, 7)
    a = a * (1 - sp2[..., None]) + sp2[..., None] * np.array([215, 217, 220])
    # 60cm sheet seams (texture = 1.2 m)
    seam = grid_mask(s, 2, 2)
    a *= (1 - seam[..., None] * 0.15)
    return to_img(a), normal_from_height(n * 0.1 - seam * 0.3, 1.0), spec_from(n, 0.3, 0.5)


def tex_epoxy(s=512):
    n = tile_noise(s, 1.8, 8)
    n2 = tile_noise(s, 0.8, 9)
    a = colorize((112, 116, 118), 0.25, n * 0.6 + n2 * 0.4)
    stains = np.clip((tile_noise(s, 2.6, 10) - 0.65) * 3, 0, 1)
    a *= (1 - stains[..., None] * 0.25)
    return to_img(a), normal_from_height(n2 * 0.2, 1.0), spec_from(1 - stains, 0.2, 0.7)


def tex_tile(s=512, base=(232, 233, 232), grout=(160, 162, 160), cells=4, gw=4):
    n = tile_noise(s, 1.0, 11)
    a = colorize(base, 0.06, n)
    m = grid_mask(s, cells, gw)
    a = a * (1 - m[..., None]) + m[..., None] * np.array(grout)
    rng = np.random.default_rng(12)
    step = s // cells
    for i in range(cells):
        for j in range(cells):
            a[j * step + gw // 2:(j + 1) * step - gw // 2, i * step + gw // 2:(i + 1) * step - gw // 2] *= (0.97 + rng.random() * 0.05)
    h = 1 - m
    return to_img(a), normal_from_height(h * 0.6, 2.0), spec_from(1 - m, 0.1, 0.9)


def tex_rubber(s=512):
    n = tile_noise(s, 1.0, 13)
    a = colorize((38, 39, 41), 0.25, n)
    sp = speckle(s, 0.03, 14)
    rng = np.random.default_rng(15)
    cols = np.array([[70, 90, 130], [110, 112, 116], [60, 60, 62]])
    idx = rng.integers(0, 3, (s, s))
    a = a * (1 - sp[..., None]) + sp[..., None] * cols[idx]
    m = grid_mask(s, 1, 3)
    a *= (1 - m[..., None] * 0.4)
    return to_img(a), normal_from_height(n * 0.3 - m, 1.5), spec_from(n, 0.02, 0.1)


def tex_concrete(s=512, base=(150, 150, 146), seed=16, contrast=0.22):
    n = tile_noise(s, 1.9, seed)
    n2 = tile_noise(s, 0.9, seed + 1)
    a = colorize(base, contrast, n * 0.6 + n2 * 0.4)
    pores = speckle(s, 0.004, seed + 2)
    pores = np.asarray(to_img(np.stack([pores * 255] * 3, -1)).filter(ImageFilter.GaussianBlur(0.7)))[..., 0] / 255.0
    a *= (1 - pores[..., None] * 0.6)
    return to_img(a), normal_from_height(n2 * 0.3 - pores * 0.8, 1.2), spec_from(n, 0.05, 0.2)


def tex_wood_planks(s=512, base=(150, 108, 70)):
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    plank_h = s // 4
    row = (yy // plank_h).astype(int)
    rng = np.random.default_rng(17)
    offs = rng.integers(0, s, 8)
    tint = 0.85 + rng.random(8) * 0.25
    n = tile_noise(s, 1.4, 18)
    grain = np.sin((yy * 0.35 + n * 40 + xx * 0.01) * 1.0) * 0.5 + 0.5
    a = colorize(base, 0.25, grain * 0.6 + n * 0.4) * tint[row][..., None]
    gap = ((yy % plank_h) < 2).astype(np.float32)
    for r in range(4):
        x = offs[r] % s
        gap[r * plank_h:(r + 1) * plank_h, max(0, x - 1):x + 1] = 1
    a *= (1 - gap[..., None] * 0.55)
    return to_img(a), normal_from_height(grain * 0.15 - gap, 1.5), spec_from(grain, 0.25, 0.45)


def tex_wood_veneer(s=512, base=(120, 84, 54)):
    yy, xx = np.mgrid[0:s, 0:s].astype(np.float32)
    n = tile_noise(s, 1.6, 19)
    grain = np.sin((xx * 0.12 + n * 30) * 1.0) * 0.5 + 0.5
    a = colorize(base, 0.3, grain * 0.55 + n * 0.45)
    # vertical panel reveals every 0.6m (texture = 1.2m)
    m = np.zeros((s, s), np.float32)
    for p in (0, s // 2, s - 1):
        m[:, max(0, p - 2):p + 2] = 1
    a *= (1 - m[..., None] * 0.7)
    return to_img(a), normal_from_height(grain * 0.1 - m, 2.0), spec_from(grain, 0.3, 0.5)


def tex_paint(s=512, base=(226, 226, 222), seed=20):
    n = tile_noise(s, 2.2, seed)
    n2 = tile_noise(s, 0.4, seed + 1)
    a = colorize(base, 0.05, n * 0.7 + n2 * 0.3)
    return to_img(a), normal_from_height(n2 * 0.05, 1.0), spec_from(n, 0.05, 0.12)


def tex_block(s=512, base=(214, 214, 208)):
    # painted CMU blocks 40x20cm, texture = 1.2 x 1.2 m -> 3 x 6 blocks
    n = tile_noise(s, 1.2, 21)
    a = colorize(base, 0.08, n)
    yy, xx = np.mgrid[0:s, 0:s]
    bh = s // 6
    bw = s // 3
    row = yy // bh
    xo = (xx + (row % 2) * (bw // 2)) % bw
    m = ((yy % bh) < 4) | (xo < 4)
    m = m.astype(np.float32)
    a *= (1 - m[..., None] * 0.18)
    h = 1 - m + n * 0.2
    return to_img(a), normal_from_height(h * 0.6, 2.0), spec_from(1 - m, 0.05, 0.2)


def tex_acoustic_wall(s=512, base=(70, 78, 92)):
    n = tile_noise(s, 0.5, 22)
    a = colorize(base, 0.2, n)
    m = np.zeros((s, s), np.float32)
    for p in (0, s // 2, s - 1):
        m[:, max(0, p - 3):p + 3] = 1
        m[max(0, p - 3):p + 3, :] = 1
    yy, xx = np.mgrid[0:s, 0:s]
    cx = ((xx % (s // 2)) - s // 4) / (s / 4)
    cy = ((yy % (s // 2)) - s // 4) / (s / 4)
    pillow = np.clip(1 - (cx ** 4 + cy ** 4), 0, 1)
    a *= (0.85 + pillow[..., None] * 0.15) * (1 - m[..., None] * 0.5)
    return to_img(a), normal_from_height(pillow * 3 - m * 2, 2.0), spec_from(n, 0.02, 0.06)


def tex_ceiling_tile(s=512):
    # 60 cm acoustic tiles, texture = 1.2m (2x2), with T-bar grid
    n = tile_noise(s, 0.3, 23)
    a = colorize((232, 232, 230), 0.08, n)
    sp = speckle(s, 0.05, 24)
    a *= (1 - sp[..., None] * 0.12)
    m = grid_mask(s, 2, 6)
    a = a * (1 - m[..., None]) + m[..., None] * np.array([245, 245, 245])
    return to_img(a), normal_from_height(n * 0.1 + m, 2.0), spec_from(m, 0.02, 0.4)


def tex_metal_brushed(s=512, base=(170, 173, 176)):
    rng = np.random.default_rng(25)
    line = rng.random(s)
    a = np.tile(line[None, :], (s, 1))
    a = np.asarray(to_img(np.stack([a * 255] * 3, -1)).filter(ImageFilter.GaussianBlur(0.6)))[..., 0] / 255.0
    n = tile_noise(s, 1.5, 26)
    v = a * 0.5 + n * 0.5
    img = colorize(base, 0.12, v)
    return to_img(img), normal_from_height(a * 0.05, 1.0), spec_from(v, 0.6, 0.9)


def tex_metal_painted(s=512, base=ANTHRACITE):
    n = tile_noise(s, 1.8, 27)
    a = colorize(base, 0.1, n)
    return to_img(a), normal_from_height(n * 0.05, 1.0), spec_from(n, 0.3, 0.5)


def tex_laminate(s=512, base=(226, 224, 218)):
    n = tile_noise(s, 1.5, 28)
    a = colorize(base, 0.04, n)
    return to_img(a), normal_from_height(n * 0.02, 1.0), spec_from(n, 0.3, 0.45)


def tex_fabric(s=512, base=(48, 56, 72)):
    yy, xx = np.mgrid[0:s, 0:s]
    weave = ((np.sin(xx * 1.6) * np.sin(yy * 1.6)) * 0.5 + 0.5)
    n = tile_noise(s, 1.0, 29)
    a = colorize(base, 0.2, weave * 0.4 + n * 0.6)
    return to_img(a), normal_from_height(weave * 0.4, 1.5), spec_from(n, 0.01, 0.04)


def tex_ext_panel(s=512):
    # architectural precast concrete panels 3.0 x 1.5 m; texture = 3 x 3 m (2 rows)
    n = tile_noise(s, 1.9, 30)
    n2 = tile_noise(s, 0.8, 31)
    a = colorize((176, 176, 172), 0.16, n * 0.5 + n2 * 0.5)
    m = np.zeros((s, s), np.float32)
    for p in (0, s - 1):
        m[:, max(0, p - 3):p + 3] = 1
    for p in (0, s // 2, s - 1):
        m[max(0, p - 3):p + 3, :] = 1
    a *= (1 - m[..., None] * 0.55)
    streak = np.clip(tile_noise(s, 2.8, 32) - 0.55, 0, 1) * np.linspace(0.2, 1, s)[:, None]
    a *= (1 - streak[..., None] * 0.35)
    return to_img(a), normal_from_height(n2 * 0.3 - m * 2, 1.5), spec_from(n, 0.05, 0.15)


def tex_ext_metal(s=512):
    # vertical standing-seam anthracite cladding, 0.5 m spacing (texture = 1m)
    n = tile_noise(s, 1.5, 33)
    a = colorize((52, 55, 60), 0.12, n)
    m = np.zeros((s, s), np.float32)
    for p in (0, s // 2, s - 1):
        m[:, max(0, p - 3):p + 3] = 1
    a *= (1 + m[..., None] * 0.35)
    return to_img(a), normal_from_height(m * 2, 2.0), spec_from(n, 0.35, 0.55)


def tex_stone(s=512):
    # dark granite plinth blocks 1.2 x 0.6m, texture 1.2m
    n = tile_noise(s, 0.5, 34)
    n2 = tile_noise(s, 1.8, 35)
    a = colorize((70, 72, 76), 0.4, n * 0.6 + n2 * 0.4)
    sp = speckle(s, 0.04, 36)
    a = a * (1 - sp[..., None] * 0.5) + sp[..., None] * 90
    m = np.zeros((s, s), np.float32)
    for p in (0, s - 1):
        m[:, max(0, p - 2):p + 2] = 1
    for p in (0, s // 2, s - 1):
        m[max(0, p - 2):p + 2, :] = 1
    a *= (1 - m[..., None] * 0.5)
    return to_img(a), normal_from_height(-m, 2.0), spec_from(n, 0.3, 0.7)


def tex_roof(s=512):
    n = tile_noise(s, 0.4, 37)
    n2 = tile_noise(s, 1.6, 38)
    a = colorize((118, 120, 122), 0.3, n * 0.5 + n2 * 0.5)
    return to_img(a), normal_from_height(n * 0.6, 1.5), spec_from(n, 0.02, 0.08)


def tex_asphalt(s=512):
    n = tile_noise(s, 0.3, 39)
    n2 = tile_noise(s, 1.7, 40)
    a = colorize((58, 59, 61), 0.4, n * 0.5 + n2 * 0.5)
    sp = speckle(s, 0.03, 41)
    a = a * (1 - sp[..., None] * 0.3) + sp[..., None] * 40
    return to_img(a), normal_from_height(n * 0.5, 1.5), spec_from(n2, 0.05, 0.2)


def tex_pavers(s=512):
    # 0.6 x 0.3 m concrete pavers, texture 1.2m
    n = tile_noise(s, 1.2, 42)
    a = colorize((168, 166, 160), 0.15, n)
    yy, xx = np.mgrid[0:s, 0:s]
    bh = s // 4
    bw = s // 2
    row = yy // bh
    xo = (xx + (row % 2) * (bw // 2)) % bw
    m = (((yy % bh) < 3) | (xo < 3)).astype(np.float32)
    a *= (1 - m[..., None] * 0.35)
    return to_img(a), normal_from_height((1 - m) * 0.6, 2.0), spec_from(n, 0.05, 0.15)


def tex_grass(s=512):
    n = tile_noise(s, 0.8, 43)
    n2 = tile_noise(s, 2.0, 44)
    a = colorize((70, 96, 48), 0.5, n * 0.5 + n2 * 0.5)
    return to_img(a), normal_from_height(n * 0.6, 1.5), spec_from(n, 0.01, 0.05)


def tex_glass(s=128, tint=(60, 90, 115), alpha=110):
    n = tile_noise(s, 2.5, 45)
    rgb = colorize(tint, 0.1, n)
    a = np.full((s, s, 1), alpha, np.float32)
    return Image.fromarray(np.concatenate([rgb, a], -1).astype(np.uint8), "RGBA")


def tex_flat(color, s=32):
    return Image.new("RGB", (s, s), color)


def tex_mirror(s=256):
    # one-way observation mirror: dark, slightly reflective with soft streaks
    yy, xx = np.mgrid[0:s, 0:s]
    g = 40 + (xx + yy) / (2 * s) * 30 + tile_noise(s, 2.0, 46) * 10
    a = np.stack([g * 0.95, g, g * 1.08], -1)
    return to_img(a)


def tex_black_glass_spec(s=64):
    return Image.new("RGB", (s, s), (240, 240, 240))


# --------------------------------------------------------------- signage etc
def draw_badge(d, cx, cy, r, fill=GOLD, outline=(120, 92, 40), text_col=NAVY):
    # stylized 7-point star badge inside a shield-like ring (original artwork)
    pts = []
    for i in range(14):
        ang = -math.pi / 2 + i * math.pi / 7
        rr = r if i % 2 == 0 else r * 0.62
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    d.polygon(pts, fill=fill, outline=outline)
    for i in range(0, 14, 2):
        x, y = pts[i]
        d.ellipse([x - r * 0.07, y - r * 0.07, x + r * 0.07, y + r * 0.07], fill=fill, outline=outline)
    d.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45], fill=NAVY, outline=outline, width=max(1, int(r * 0.03)))
    f = font(FONT_BLACK, int(r * 0.25))
    d.text((cx, cy - r * 0.04), "LSPD", font=f, fill=GOLD, anchor="mm")
    f2 = font(FONT_BOLD, int(r * 0.075))
    d.text((cx, cy + r * 0.26), "LOS SANTOS", font=f2, fill=(220, 220, 220), anchor="mm")


def tex_main_sign():
    w, h = 2048, 512
    img = Image.new("RGB", (w, h), (34, 37, 42))
    d = ImageDraw.Draw(img)
    draw_badge(d, 250, 256, 200)
    d.text((500, 170), "LOS SANTOS", font=font(FONT_BLACK, 150), fill=(238, 238, 238), anchor="lm")
    d.text((505, 330), "POLICE DEPARTMENT", font=font(FONT_BOLD, 110), fill=(150, 190, 228), anchor="lm")
    d.rectangle([500, 420, 1960, 432], fill=(86, 156, 214))
    return img


def tex_lobby_wall_logo():
    s = 1024
    img = Image.new("RGB", (s, s), NAVY)
    d = ImageDraw.Draw(img)
    n = tile_noise(s, 2.0, 47)
    a = np.asarray(img).astype(np.float32) * (0.92 + n[..., None] * 0.1)
    img = to_img(a)
    d = ImageDraw.Draw(img)
    draw_badge(d, s // 2, 400, 300)
    d.text((s // 2, 790), "LOS SANTOS POLICE", font=font(FONT_BLACK, 78), fill=(236, 236, 236), anchor="mm")
    d.text((s // 2, 890), "TO PROTECT  •  TO SERVE", font=font(FONT_SEMI, 48), fill=(150, 190, 228), anchor="mm")
    return img


SIGNS = [
    "RECEPTION", "PUBLIC LOBBY", "REPORT ROOM", "RESTROOMS", "SECURITY CHECK", "AUTHORIZED PERSONNEL ONLY",
    "DISPATCH CENTER", "INTERROGATION 1", "INTERROGATION 2", "OBSERVATION", "EVIDENCE", "FORENSIC LAB",
    "BOOKING", "DETENTION", "ARMORY", "BRIEFING ROOM",
    "CHIEF OF POLICE", "DEPUTY CHIEF", "CONFERENCE", "LOCKER ROOM", "FITNESS", "BREAK ROOM", "SERVER ROOM", "ARCHIVE",
    "STAIRS", "GARAGE", "SALLY PORT", "DETECTIVES", "ANALYSIS", "LINEUP", "RECORDS", "COMMAND STAFF",
    "MUGSHOT", "FINGERPRINTS", "PROPERTY", "WATCH COMMANDER", "PATROL", "EQUIPMENT", "MAINTENANCE", "RIOT GEAR",
    "KITCHEN", "DINING", "SHOWERS", "TECHNICAL", "JANITOR", "DOCUMENTS", "RADIO ROOM", "SUPERVISOR",
    "ROOF ACCESS", "MEETING ROOM", "OFFICERS", "SERGEANT", "CITIZEN SERVICES", "VEHICLE INTAKE", "CELL BLOCK", "CONTROL ROOM",
    "LEVEL 1", "LEVEL 2", "LEVEL 3", "EXIT", "CASE ROOM", "INTERVIEW", "HOLDING", "OPERATIONS",
]
SIGN_COLS, SIGN_ROWS = 8, 8  # atlas grid, each cell 256x128 => 2048 x 1024


def tex_sign_atlas():
    cw, ch = 256, 128
    img = Image.new("RGB", (cw * SIGN_COLS, ch * SIGN_ROWS), NAVY)
    d = ImageDraw.Draw(img)
    for i, name in enumerate(SIGNS):
        cx, cy = (i % SIGN_COLS) * cw, (i // SIGN_COLS) * ch
        d.rectangle([cx, cy, cx + cw - 1, cy + ch - 1], fill=NAVY)
        d.rectangle([cx + 6, cy + 6, cx + cw - 7, cy + ch - 7], outline=(86, 156, 214), width=2)
        size = 30
        f = font(FONT_BOLD, size)
        while d.textlength(name, font=f) > cw - 40 and size > 12:
            size -= 1
            f = font(FONT_BOLD, size)
        if d.textlength(name, font=f) > cw - 40:
            parts = name.split(" ")
            mid = len(parts) // 2
            l1, l2 = " ".join(parts[:mid]), " ".join(parts[mid:])
            f = font(FONT_BOLD, 22)
            d.text((cx + cw / 2, cy + ch / 2 - 14), l1, font=f, fill=(240, 240, 240), anchor="mm")
            d.text((cx + cw / 2, cy + ch / 2 + 14), l2, font=f, fill=(240, 240, 240), anchor="mm")
        else:
            d.text((cx + cw / 2, cy + ch / 2), name, font=f, fill=(240, 240, 240), anchor="mm")
        # tiny badge marker
        d.ellipse([cx + 14, cy + 14, cx + 26, cy + 26], fill=GOLD)
    return img


def sign_uv(name):
    i = SIGNS.index(name)
    c, r = i % SIGN_COLS, i // SIGN_COLS
    return (c / SIGN_COLS, r / SIGN_ROWS, (c + 1) / SIGN_COLS, (r + 1) / SIGN_ROWS)


def tex_screen_map(s=1024):
    """Generic stylized city map for the dispatch video wall (original procedural layout)."""
    img = Image.new("RGB", (s, s), (10, 18, 30))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(48)
    # coastline / water
    pts = [(0, s * 0.72)]
    for i in range(1, 21):
        pts.append((i * s / 20, s * (0.72 + 0.08 * math.sin(i * 0.9) + rng.random() * 0.04)))
    pts += [(s, s), (0, s)]
    d.polygon(pts, fill=(8, 34, 58))
    # districts
    for _ in range(60):
        x, y = rng.integers(0, s, 2)
        w, h = rng.integers(40, 140, 2)
        if y > s * 0.7:
            continue
        d.rectangle([x, y, x + w, y + h], fill=(16 + rng.integers(0, 10), 28 + rng.integers(0, 12), 44 + rng.integers(0, 14)))
    # street grid
    for i in range(0, s, 48):
        d.line([(i, 0), (i + rng.integers(-30, 30), s * 0.75)], fill=(40, 60, 84), width=2)
        d.line([(0, i), (s, i + rng.integers(-20, 20))], fill=(40, 60, 84), width=2)
    # highways
    d.line([(0, s * 0.3), (s, s * 0.42)], fill=(214, 170, 70), width=6)
    d.line([(s * 0.35, 0), (s * 0.55, s * 0.75)], fill=(214, 170, 70), width=6)
    d.line([(s * 0.75, 0), (s * 0.68, s * 0.7)], fill=(214, 170, 70), width=5)
    # unit markers
    for _ in range(26):
        x, y = rng.integers(40, s - 40), rng.integers(40, int(s * 0.7))
        col = [(80, 160, 255), (255, 80, 80), (90, 220, 120)][rng.integers(0, 3)]
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=col, outline=(240, 240, 240))
        d.text((x + 10, y - 8), f"{rng.integers(1, 9)}A{rng.integers(10, 99)}", font=font(FONT_MONO, 13), fill=(220, 230, 240))
    # incident
    for _ in range(4):
        x, y = rng.integers(80, s - 80), rng.integers(80, int(s * 0.65))
        for r in (26, 18, 10):
            d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 70, 70), width=2)
    d.rectangle([0, 0, s, 44], fill=(14, 26, 44))
    d.text((16, 22), "LSPD  •  LIVE UNIT TRACKING", font=font(FONT_BOLD, 24), fill=(150, 190, 228), anchor="lm")
    d.text((s - 16, 22), "AVL ONLINE", font=font(FONT_BOLD, 20), fill=(90, 220, 120), anchor="rm")
    return img


def tex_screen_cctv(s=1024):
    img = Image.new("RGB", (s, s), (6, 8, 10))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(49)
    cams = ["LOBBY", "ENTRANCE", "SALLY PORT", "CELL 1", "CELL 2", "BOOKING", "GARAGE", "PARKING N", "PARKING S",
            "ARMORY", "EVIDENCE", "ROOF", "CORRIDOR L1", "CORRIDOR L2", "STAIR A", "STAIR B"]
    cs = s // 4
    for i, name in enumerate(cams):
        x, y = (i % 4) * cs, (i // 4) * cs
        n = tile_noise(cs, 1.6, 100 + i)
        base = 40 + rng.integers(0, 50)
        g = base + n * 60
        # simple perspective "room": floor trapezoid + walls
        tile = np.stack([g, g, g * 1.05], -1)
        timg = to_img(tile)
        td = ImageDraw.Draw(timg)
        td.polygon([(0, cs), (cs, cs), (cs * 0.7, cs * 0.55), (cs * 0.3, cs * 0.55)], fill=(int(base * 0.6),) * 3)
        td.rectangle([cs * 0.3, cs * 0.2, cs * 0.7, cs * 0.55], fill=(int(base * 1.3),) * 3)
        for _ in range(rng.integers(0, 3)):
            px = rng.integers(int(cs * 0.3), int(cs * 0.7))
            td.rectangle([px, cs * 0.45, px + 8, cs * 0.7], fill=(20, 20, 24))
        img.paste(timg, (x, y))
        d.rectangle([x, y, x + cs - 1, y + cs - 1], outline=(30, 30, 30), width=3)
        d.text((x + 8, y + 8), f"CAM {i + 1:02d}  {name}", font=font(FONT_MONO, 15), fill=(230, 230, 230))
        d.text((x + 8, y + cs - 22), "2026-11-21  REC", font=font(FONT_MONO, 13), fill=(255, 80, 80))
    return img


def tex_screen_cad(s=1024):
    img = Image.new("RGB", (s, s), (12, 20, 32))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(50)
    d.rectangle([0, 0, s, 50], fill=(22, 38, 66))
    d.text((16, 25), "LSPD CAD  —  ACTIVE CALLS", font=font(FONT_BOLD, 26), fill=(236, 236, 236), anchor="lm")
    hdr = ["CALL#", "PRI", "TYPE", "LOCATION", "UNITS", "STATUS"]
    xs = [16, 140, 210, 420, 760, 880]
    for x, t in zip(xs, hdr):
        d.text((x, 70), t, font=font(FONT_BOLD, 18), fill=(150, 190, 228))
    types = ["TRAFFIC STOP", "ALARM", "THEFT", "DISTURBANCE", "MVA", "WELFARE CHK", "SUSPICIOUS", "ASSAULT", "PURSUIT"]
    streets = ["VINE AVE", "MAIN ST", "HARBOR BLVD", "OAK DR", "5TH ST", "BAY RD", "PALM WAY", "HILL CRES", "PORT ST"]
    stat = [("ENRT", (230, 190, 60)), ("ONSC", (90, 220, 120)), ("PEND", (255, 90, 90)), ("CLR", (140, 140, 140))]
    for r in range(22):
        y = 104 + r * 38
        if r % 2 == 0:
            d.rectangle([0, y - 6, s, y + 28], fill=(16, 27, 42))
        st = stat[rng.integers(0, 4)]
        vals = [f"26-{rng.integers(10000, 99999)}", str(rng.integers(1, 4)), types[rng.integers(0, len(types))],
                f"{rng.integers(100, 9999)} {streets[rng.integers(0, len(streets))]}", f"{rng.integers(1, 9)}A{rng.integers(10, 99)}"]
        for x, t in zip(xs, vals):
            d.text((x, y), t, font=font(FONT_MONO, 18), fill=(210, 220, 230))
        d.text((xs[5], y), st[0], font=font(FONT_BOLD, 18), fill=st[1])
    return img


def tex_screen_desktop(s=512):
    img = Image.new("RGB", (s, s), (18, 30, 50))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s, 28], fill=(22, 38, 66))
    d.text((10, 14), "LSPD RECORDS MANAGEMENT", font=font(FONT_BOLD, 15), fill=(230, 230, 230), anchor="lm")
    rng = np.random.default_rng(51)
    for r in range(14):
        y = 44 + r * 30
        d.rectangle([12, y, s - 12, y + 22], fill=(26, 42, 66) if r % 2 else (22, 36, 58))
        d.text((20, y + 11), f"CASE 26-{rng.integers(1000, 9999)}   {['OPEN', 'REVIEW', 'CLOSED'][rng.integers(0, 3)]}",
               font=font(FONT_MONO, 13), fill=(200, 215, 230), anchor="lm")
    return img


def tex_light_panel(s=64):
    img = Image.new("RGB", (s, s), (255, 252, 244))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s - 1, s - 1], outline=(200, 200, 200), width=2)
    return img


def tex_whiteboard(s=512):
    img = Image.new("RGB", (s, s // 2), (244, 245, 246))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(52)
    d.rectangle([0, 0, s - 1, s // 2 - 1], outline=(150, 152, 156), width=8)
    f = font(FONT_SEMI, 18)
    lines = ["SHIFT BRIEFING", "- BOLO: grey sedan, plate 4LSP221", "- Patrol zones A/B/C reassigned",
             "- Court duty: Ofc. Novak 0900", "- Vest inspection Friday", "STAY SAFE"]
    for i, t in enumerate(lines):
        col = [(30, 60, 160), (20, 20, 20), (180, 30, 30)][i % 3]
        d.text((26, 22 + i * 36), t, font=f, fill=col)
    return img


def tex_corkboard(s=512):
    n = tile_noise(s, 1.0, 53)
    a = colorize((170, 128, 82), 0.35, n)
    img = to_img(a).crop((0, 0, s, s // 2))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(54)
    pins = []
    for i in range(9):
        x, y = 30 + (i % 5) * 96 + rng.integers(-8, 8), 20 + (i // 5) * 120 + rng.integers(-6, 6)
        w, h = 70, 90
        d.rectangle([x, y, x + w, y + h], fill=(235, 235, 230))
        d.rectangle([x + 6, y + 6, x + w - 6, y + h - 24], fill=(int(80 + rng.integers(0, 60)),) * 3)
        d.ellipse([x + 22, y + 14, x + 48, y + 40], fill=(40, 40, 44))
        d.rectangle([x + 16, y + 40, x + 54, y + h - 24], fill=(50, 50, 56))
        d.text((x + 6, y + h - 18), f"#{rng.integers(100, 999)}", font=font(FONT_MONO, 12), fill=(20, 20, 20))
        pins.append((x + w // 2, y + 4))
        d.ellipse([x + w // 2 - 4, y, x + w // 2 + 4, y + 8], fill=(200, 30, 30))
    for a_, b_ in zip(pins, pins[2:]):
        d.line([a_, b_], fill=(200, 30, 30), width=2)
    return img


def tex_height_chart(s=512):
    img = Image.new("RGB", (s, s), (226, 228, 230))
    d = ImageDraw.Draw(img)
    # chart covers 2.5 m tall in texture space (v 0..1 -> 2.5m..0m)
    for cm in range(0, 251, 5):
        y = s - cm / 250 * s
        lw = 3 if cm % 25 == 0 else 1
        d.line([(0, y), (s, y)], fill=(40, 40, 40), width=lw)
        if cm % 25 == 0 and cm > 0:
            ft = cm / 30.48
            d.text((8, y + 2), f"{cm}", font=font(FONT_BOLD, 20), fill=(20, 20, 20))
            d.text((s - 70, y + 2), f"{ft:.1f}ft", font=font(FONT_BOLD, 18), fill=(20, 20, 20))
    return img


def tex_mugshot_backdrop(s=512):
    img = Image.new("RGB", (s, s), (150, 170, 196))
    d = ImageDraw.Draw(img)
    for cm in range(140, 211, 10):
        y = s - (cm - 100) / 120 * s
        d.line([(0, y), (s, y)], fill=(40, 50, 70), width=2)
        d.text((10, y - 22), f"{cm}", font=font(FONT_BOLD, 18), fill=(20, 30, 50))
    return img


def tex_helipad(s=1024):
    n = tile_noise(s, 0.5, 55)
    a = colorize((88, 92, 96), 0.2, n)
    img = to_img(a)
    d = ImageDraw.Draw(img)
    c = s // 2
    d.ellipse([c - 440, c - 440, c + 440, c + 440], outline=(236, 236, 236), width=26)
    d.ellipse([c - 470, c - 470, c + 470, c + 470], outline=(214, 170, 60), width=10)
    f = font(FONT_BLACK, 520)
    d.text((c, c - 20), "H", font=f, fill=(236, 236, 236), anchor="mm")
    d.text((c, c + 330), "LSPD AIR", font=font(FONT_BOLD, 70), fill=(214, 170, 60), anchor="mm")
    return img


def tex_parking_lines(s=512):
    # asphalt with a white parking stall line at u=0 (stalls 2.6 m; texture = 2.6 x 2.6 m)
    img = tex_asphalt(s)[0]
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 10, s], fill=(220, 220, 214))
    return img


def tex_safety_stripe(s=256):
    img = Image.new("RGB", (s, s), (230, 190, 40))
    d = ImageDraw.Draw(img)
    for i in range(-s, s * 2, 64):
        d.polygon([(i, 0), (i + 32, 0), (i + 32 - s, s), (i - s, s)], fill=(28, 28, 30))
    return img


def tex_rug_logo(s=512):
    img = Image.new("RGB", (s, s), NAVY_DARK)
    d = ImageDraw.Draw(img)
    d.rectangle([12, 12, s - 13, s - 13], outline=GOLD, width=6)
    draw_badge(d, s // 2, s // 2 - 20, 170)
    d.text((s // 2, s - 60), "LOS SANTOS POLICE", font=font(FONT_BLACK, 34), fill=(220, 220, 220), anchor="mm")
    n = tile_noise(s, 1.0, 56)
    a = np.asarray(img).astype(np.float32) * (0.9 + n[..., None] * 0.15)
    return to_img(a)


def tex_flag_board(s=512):
    # framed portrait / commendation board for chief office
    img = Image.new("RGB", (s, s // 2), (30, 26, 22))
    d = ImageDraw.Draw(img)
    for i in range(4):
        x = 20 + i * 122
        d.rectangle([x, 20, x + 102, 236], fill=(232, 228, 216), outline=(170, 140, 70), width=4)
        draw_badge(d, x + 51, 90, 38)
        d.text((x + 51, 170), "MERIT", font=font(FONT_BOLD, 16), fill=NAVY, anchor="mm")
        d.text((x + 51, 196), f"{2019 + i}", font=font(FONT_SEMI, 14), fill=(60, 60, 60), anchor="mm")
    return img


def tex_poster_wanted(s=512):
    img = Image.new("RGB", (s // 2 + 128, s), (238, 234, 222))
    d = ImageDraw.Draw(img)
    w = img.width
    d.text((w // 2, 50), "WANTED", font=font(FONT_BLACK, 64), fill=(150, 20, 20), anchor="mm")
    d.rectangle([60, 100, w - 60, 330], fill=(120, 120, 120))
    d.ellipse([w // 2 - 50, 140, w // 2 + 50, 240], fill=(60, 60, 64))
    d.rectangle([w // 2 - 80, 240, w // 2 + 80, 330], fill=(50, 50, 54))
    for i, t in enumerate(["ARMED ROBBERY", "CALL 911 OR LSPD TIP LINE", "REWARD $10,000"]):
        d.text((w // 2, 370 + i * 40), t, font=font(FONT_BOLD, 22), fill=(20, 20, 20), anchor="mm")
    return img


def tex_info_board(s=512):
    img = Image.new("RGB", (s, s // 2), (240, 240, 238))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, s, 50], fill=NAVY)
    d.text((s // 2, 25), "PUBLIC INFORMATION", font=font(FONT_BOLD, 26), fill=(240, 240, 240), anchor="mm")
    items = ["Emergency: 911", "Non-emergency: 311", "Records requests: Window 2", "Lost & found: Front desk",
             "Office hours: 24/7"]
    for i, t in enumerate(items):
        d.text((24, 70 + i * 34), "•  " + t, font=font(FONT_SEMI, 20), fill=(30, 30, 30))
    return img


def tex_evidence_shelf_labels(s=512):
    img = Image.new("RGB", (s, s // 4), (230, 230, 226))
    d = ImageDraw.Draw(img)
    for i in range(8):
        x = i * s // 8
        d.rectangle([x + 4, 8, x + s // 8 - 4, s // 4 - 8], outline=(40, 40, 40), width=2)
        d.text((x + s // 16, s // 8), f"E-{i + 1:02d}", font=font(FONT_BOLD, 18), fill=(20, 20, 20), anchor="mm")
    return img


def tex_cardboard(s=256):
    n = tile_noise(s, 1.5, 57)
    a = colorize((176, 140, 96), 0.15, n)
    img = to_img(a)
    d = ImageDraw.Draw(img)
    d.rectangle([s * 0.3, s * 0.4, s * 0.7, s * 0.6], fill=(240, 240, 236))
    d.text((s // 2, s // 2), "EVIDENCE", font=font(FONT_BOLD, 18), fill=(150, 20, 20), anchor="mm")
    return img


def tex_locker(s=512):
    # front of a bank of lockers: 0.4 m doors; texture = 1.2 m wide x 1.8 m tall-ish
    img = Image.new("RGB", (s, s), (60, 74, 98))
    d = ImageDraw.Draw(img)
    n = tile_noise(s, 1.8, 58)
    w = s // 3
    for i in range(3):
        x = i * w
        d.rectangle([x + 3, 3, x + w - 4, s - 4], outline=(30, 38, 52), width=4)
        for v in range(6):
            d.line([(x + w * 0.25, 30 + v * 10), (x + w * 0.75, 30 + v * 10)], fill=(30, 38, 52), width=3)
        d.rectangle([x + w - 30, s // 2 - 30, x + w - 18, s // 2 + 30], fill=(180, 184, 190))
        d.rectangle([x + 20, s // 2 + 60, x + 70, s // 2 + 84], fill=(232, 232, 228))
    a = np.asarray(img).astype(np.float32) * (0.93 + n[..., None] * 0.1)
    return to_img(a)


def tex_server_rack(s=512):
    img = Image.new("RGB", (s // 2, s), (22, 24, 28))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(59)
    w = s // 2
    for u in range(0, s, 22):
        d.rectangle([10, u + 2, w - 10, u + 19], fill=(34, 36, 40), outline=(50, 52, 58))
        for k in range(8):
            if rng.random() < 0.7:
                col = [(60, 220, 90), (60, 160, 255), (255, 170, 40)][rng.integers(0, 3)]
                d.rectangle([18 + k * 10, u + 8, 22 + k * 10, u + 12], fill=col)
        d.rectangle([w - 60, u + 6, w - 16, u + 15], fill=(20, 20, 22))
    return img


def tex_carpet_logo_red(s=64):
    return Image.new("RGB", (s, s), (130, 30, 34))


TEXTURES = {}


def register(name, fn, fmt="DXT1", normal=False):
    TEXTURES[name] = (fn, fmt, normal)


def build_all(out_dir):
    """Generate every texture. Returns dict name -> (w, h, fmt, filename)."""
    os.makedirs(out_dir, exist_ok=True)
    info = {}

    def save(name, img, fmt):
        png = os.path.join(out_dir, name + ".png")
        dds = os.path.join(out_dir, name + ".dds")
        if fmt == "DXT5" and img.mode != "RGBA":
            img = img.convert("RGBA")
        if fmt == "DXT1" and img.mode != "RGB":
            img = img.convert("RGB")
        img.save(png)
        mips = int(math.log2(min(img.width, img.height))) - 1
        mips = max(1, mips)
        subprocess.run(["convert", png, "-define", f"dds:compression={fmt.lower()}",
                        "-define", f"dds:mipmaps={mips}", dds], check=True)
        os.remove(png)
        info[name] = (img.width, img.height, fmt, mips + 1)

    def surface(name, triple):
        d, n, s = triple
        save(name, d, "DXT1")
        save(name + "_n", n.resize((256, 256), Image.LANCZOS), "DXT1")
        save(name + "_s", s.resize((128, 128), Image.LANCZOS), "DXT1")

    surface("lspd_terrazzo", tex_terrazzo())
    surface("lspd_carpet_navy", tex_carpet(base=(34, 46, 68)))
    surface("lspd_carpet_grey", tex_carpet(base=(78, 82, 88)))
    surface("lspd_vinyl", tex_vinyl())
    surface("lspd_epoxy", tex_epoxy())
    surface("lspd_tile_white", tex_tile())
    surface("lspd_tile_dark", tex_tile(base=(70, 74, 80), grout=(50, 52, 56), cells=2, gw=3))
    surface("lspd_rubber", tex_rubber())
    surface("lspd_concrete", tex_concrete())
    surface("lspd_concrete_dark", tex_concrete(base=(96, 98, 100), seed=60, contrast=0.3))
    surface("lspd_wood_floor", tex_wood_planks())
    surface("lspd_wood_veneer", tex_wood_veneer())
    surface("lspd_wood_light", tex_wood_veneer(base=(186, 150, 108)))
    surface("lspd_paint_white", tex_paint())
    surface("lspd_paint_grey", tex_paint(base=(168, 172, 176), seed=61))
    surface("lspd_paint_navy", tex_paint(base=NAVY, seed=62))
    surface("lspd_paint_blue", tex_paint(base=(120, 160, 200), seed=63))
    surface("lspd_block", tex_block())
    surface("lspd_acoustic", tex_acoustic_wall())
    surface("lspd_ceiling", tex_ceiling_tile())
    surface("lspd_metal", tex_metal_brushed())
    surface("lspd_metal_dark", tex_metal_painted())
    surface("lspd_metal_navy", tex_metal_painted(base=(36, 52, 80)))
    surface("lspd_laminate", tex_laminate())
    surface("lspd_laminate_dark", tex_laminate(base=(58, 60, 64)))
    surface("lspd_fabric", tex_fabric())
    surface("lspd_fabric_grey", tex_fabric(base=(96, 98, 102)))
    surface("lspd_ext_panel", tex_ext_panel())
    surface("lspd_ext_metal", tex_ext_metal())
    surface("lspd_stone", tex_stone())
    surface("lspd_roof", tex_roof())
    surface("lspd_asphalt", tex_asphalt())
    surface("lspd_pavers", tex_pavers())
    surface("lspd_grass", tex_grass())
    save("lspd_glass", tex_glass(), "DXT5")
    save("lspd_glass_int", tex_glass(tint=(170, 190, 200), alpha=60), "DXT5")
    save("lspd_glass_n", tex_flat((128, 128, 255)), "DXT1")
    save("lspd_mirror", tex_mirror(), "DXT1")
    save("lspd_sign_main", tex_main_sign(), "DXT1")
    save("lspd_wall_logo", tex_lobby_wall_logo(), "DXT1")
    save("lspd_signs", tex_sign_atlas(), "DXT1")
    save("lspd_scr_map", tex_screen_map(), "DXT1")
    save("lspd_scr_cctv", tex_screen_cctv(), "DXT1")
    save("lspd_scr_cad", tex_screen_cad(), "DXT1")
    save("lspd_scr_desk", tex_screen_desktop(), "DXT1")
    save("lspd_light", tex_light_panel(), "DXT1")
    save("lspd_whiteboard", tex_whiteboard(), "DXT1")
    save("lspd_corkboard", tex_corkboard(), "DXT1")
    save("lspd_height", tex_height_chart(), "DXT1")
    save("lspd_mugshot", tex_mugshot_backdrop(), "DXT1")
    save("lspd_helipad", tex_helipad(), "DXT1")
    save("lspd_parking", tex_parking_lines(), "DXT1")
    save("lspd_stripe", tex_safety_stripe(), "DXT1")
    save("lspd_rug", tex_rug_logo(), "DXT1")
    save("lspd_merit", tex_flag_board(), "DXT1")
    save("lspd_wanted", tex_poster_wanted(), "DXT1")
    save("lspd_infoboard", tex_info_board(), "DXT1")
    save("lspd_shelflabel", tex_evidence_shelf_labels(), "DXT1")
    save("lspd_cardboard", tex_cardboard(), "DXT1")
    save("lspd_locker", tex_locker(), "DXT1")
    save("lspd_rack", tex_server_rack(), "DXT1")
    save("lspd_red", tex_carpet_logo_red(), "DXT1")
    save("lspd_black", tex_flat((14, 14, 16)), "DXT1")
    save("lspd_white", tex_flat((240, 240, 240)), "DXT1")
    save("lspd_flat_n", tex_flat((128, 128, 255)), "DXT1")
    save("lspd_spec_lo", tex_flat((40, 40, 40)), "DXT1")
    return info


if __name__ == "__main__":
    import sys
    i = build_all(sys.argv[1] if len(sys.argv) > 1 else "out_tex")
    print(len(i), "textures")
