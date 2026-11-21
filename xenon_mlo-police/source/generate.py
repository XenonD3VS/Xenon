#!/usr/bin/env python3
"""
xenon_mlo-police - procedural generator for a FiveM police station MLO.

Produces CodeWalker XML sources (+ DDS textures) for:
  * xenon_police_<room>.ydr   - one interior shell drawable per room (walls, floor, ceiling, lights)
  * xenon_police_ext.ydr      - exterior shell (facade, roof, foundation, windows, sign)
  * xenon_police_col.ybn      - static collision (room IDs set per room for interior detection)
  * xenon_police.ytyp         - archetypes + MLO archetype (rooms, portals, props)
  * xenon_police.ymap         - placement of the exterior and the MLO instance

The XML files are converted to binary GTA V formats with CodeWalker (see README.md).

Usage:  python3 generate.py [--out build_xml]
Edit CONFIG below to move / rotate the building.
"""
import argparse
import math
import os
import random
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------------------
CONFIG = {
    # World position of the building origin (south-west floor corner) and heading in degrees.
    # Default = open flat ground at LSIA (test location). Change to wherever you want it,
    # then regenerate, or move the entities later in CodeWalker.
    "position": (-1620.0, -2780.0, 13.95),
    "heading": 0.0,
    "prefix": "xenon_police",
}

P = CONFIG["prefix"]
H = 3.2          # interior ceiling height
ROOF = 3.5       # roof surface height
TOP = 4.0        # parapet top
T_INT = 0.2      # interior wall thickness
T_EXT = 0.3      # exterior wall thickness
W, D = 32.0, 24.0  # footprint

# --------------------------------------------------------------------------------------
# LAYOUT
# --------------------------------------------------------------------------------------
# room: (name, rect(x0,y0,x1,y1), floor material, wall upper, wall lower)
ROOMS = [
    ("lobby",        (0, 0, 12, 8),    "floor_tile",   "wall_paint", "wall_lower"),
    ("hallway",      (0, 8, 32, 11),   "floor_tile",   "wall_paint", "wall_lower"),
    ("briefing",     (12, 0, 22, 8),   "floor_carpet", "wall_paint", "wall_lower"),
    ("chief",        (22, 0, 32, 8),   "floor_wood",   "wall_paint", "wall_lower"),
    ("office",       (0, 11, 14, 24),  "floor_carpet", "wall_paint", "wall_lower"),
    ("armory",       (14, 11, 20, 17), "floor_concrete", "wall_concrete", "wall_lower"),
    ("locker",       (14, 17, 20, 24), "floor_tile",   "wall_paint", "wall_lower"),
    ("interrogation", (20, 11, 25, 17), "floor_concrete", "wall_concrete", "wall_lower"),
    ("evidence",     (20, 17, 25, 24), "floor_concrete", "wall_concrete", "wall_lower"),
    ("cells",        (25, 11, 32, 24), "floor_concrete", "wall_concrete", "wall_lower"),
]
ROOM_INDEX = {r[0]: i + 1 for i, r in enumerate(ROOMS)}  # 0 = limbo

DOOR_H = 2.3
# wall: (axis, fixed coord, start, end, thickness, height, exterior?, openings[(a0,a1,h)])
# axis 'x' = wall runs along X at y=c ; axis 'y' = runs along Y at x=c
WALLS = [
    # exterior
    ("x", 0.0, 0.0, W, T_EXT, TOP, True, [(5.0, 7.0, 2.6)]),             # front, double door
    ("x", D, 0.0, W, T_EXT, TOP, True, []),
    ("y", 0.0, 0.0, D, T_EXT, TOP, True, []),
    ("y", W, 0.0, D, T_EXT, TOP, True, [(9.0, 10.4, DOOR_H)]),           # rear door
    # south block / hallway
    ("x", 8.0, 0.0, W, T_INT, H, False, [(9.5, 10.7, DOOR_H), (16.5, 17.7, DOOR_H), (26.5, 27.7, DOOR_H)]),
    ("x", 11.0, 0.0, W, T_INT, H, False, [(6.0, 7.2, DOOR_H), (16.4, 17.6, DOOR_H),
                                          (21.9, 23.1, DOOR_H), (25.6, 26.8, DOOR_H)]),
    ("y", 12.0, 0.0, 8.0, T_INT, H, False, []),
    ("y", 22.0, 0.0, 8.0, T_INT, H, False, []),
    # north block
    ("y", 14.0, 11.0, D, T_INT, H, False, [(20.0, 21.2, DOOR_H)]),
    ("y", 20.0, 11.0, D, T_INT, H, False, []),
    ("y", 25.0, 11.0, D, T_INT, H, False, []),
    ("x", 17.0, 14.0, 25.0, T_INT, H, False, [(21.9, 23.1, DOOR_H)]),
    # cell block (inside the "cells" room)
    ("y", 28.5, 11.0, D, T_INT, H, False, [(12.6, 13.6, DOOR_H), (16.9, 17.9, DOOR_H), (21.2, 22.2, DOOR_H)]),
    ("x", 15.33, 28.5, W, T_INT, H, False, []),
    ("x", 19.67, 28.5, W, T_INT, H, False, []),
]

# portals: (roomA, roomB, wall axis, fixed coord, a0, a1, h)  (roomB "limbo" = exterior)
PORTALS = [
    ("lobby", "limbo", "x", 0.0, 5.0, 7.0, 2.6),
    ("hallway", "limbo", "y", W, 9.0, 10.4, DOOR_H),
    ("lobby", "hallway", "x", 8.0, 9.5, 10.7, DOOR_H),
    ("briefing", "hallway", "x", 8.0, 16.5, 17.7, DOOR_H),
    ("chief", "hallway", "x", 8.0, 26.5, 27.7, DOOR_H),
    ("office", "hallway", "x", 11.0, 6.0, 7.2, DOOR_H),
    ("armory", "hallway", "x", 11.0, 16.4, 17.6, DOOR_H),
    ("interrogation", "hallway", "x", 11.0, 21.9, 23.1, DOOR_H),
    ("cells", "hallway", "x", 11.0, 25.6, 26.8, DOOR_H),
    ("office", "locker", "y", 14.0, 20.0, 21.2, DOOR_H),
    ("interrogation", "evidence", "x", 17.0, 21.9, 23.1, DOOR_H),
]

# Extra solid boxes (furniture built into the shell): (room, min, max, material)
SOLIDS = [
    ("lobby", (3.0, 5.4, 0.0), (8.0, 6.1, 1.1), "trim_wood"),     # reception counter
    ("lobby", (2.9, 5.3, 1.1), (8.1, 6.2, 1.16), "counter_top"),  # counter top
]

# Props (vanilla GTA V models) placed inside the MLO: (room, model, x, y, z, heading_deg)
PROPS = [
    # lobby
    ("lobby", "prop_off_chair_01", 4.5, 6.8, 0.0, 180),
    ("lobby", "prop_off_chair_01", 6.5, 6.8, 0.0, 180),
    ("lobby", "prop_monitor_01a", 4.5, 5.9, 1.16, 180),
    ("lobby", "prop_monitor_01a", 6.5, 5.9, 1.16, 180),
    ("lobby", "prop_waiting_seat_01", 1.0, 2.5, 0.0, 90),
    ("lobby", "prop_waiting_seat_01", 1.0, 4.5, 0.0, 90),
    ("lobby", "prop_waiting_seat_01", 10.9, 2.5, 0.0, 270),
    ("lobby", "prop_plant_int_01a", 0.6, 0.6, 0.0, 0),
    ("lobby", "prop_plant_int_01a", 11.4, 0.6, 0.0, 0),
    ("lobby", "prop_watercooler", 11.4, 4.5, 0.0, 270),
    # hallway
    ("hallway", "prop_vend_coffe_01", 1.0, 10.4, 0.0, 180),
    ("hallway", "prop_vend_snak_01", 2.2, 10.4, 0.0, 180),
    ("hallway", "prop_vend_soda_01", 3.4, 10.4, 0.0, 180),
    ("hallway", "prop_plant_int_03a", 31.4, 10.5, 0.0, 0),
    # briefing room
    ("briefing", "prop_tv_flat_01", 17.0, 7.75, 1.4, 180),
    ("briefing", "prop_table_02", 17.0, 6.5, 0.0, 0),
] + [
    ("briefing", "prop_chair_01a", 13.5 + c * 1.2, 1.5 + r * 1.3, 0.0, 0)
    for r in range(3) for c in range(7)
] + [
    # chief office
    ("chief", "prop_office_desk_01", 27.0, 3.0, 0.0, 0),
    ("chief", "prop_off_chair_04", 27.0, 2.0, 0.0, 0),
    ("chief", "prop_off_chair_01", 26.4, 4.2, 0.0, 180),
    ("chief", "prop_off_chair_01", 27.6, 4.2, 0.0, 180),
    ("chief", "prop_monitor_02", 27.0, 3.2, 0.77, 180),
    ("chief", "prop_plant_int_02a", 31.4, 0.6, 0.0, 0),
    ("chief", "prop_plant_int_02a", 22.6, 0.6, 0.0, 0),
] + [
    # open office: 3 rows x 3 desks
    item
    for r in range(3) for c in range(3)
    for item in (
        ("office", "prop_office_desk_01", 2.5 + c * 4.0, 14.0 + r * 3.3, 0.0, 0),
        ("office", "prop_off_chair_05", 2.5 + c * 4.0, 13.1 + r * 3.3, 0.0, 0),
        ("office", "prop_monitor_01a", 2.5 + c * 4.0, 14.2 + r * 3.3, 0.77, 180),
        ("office", "prop_keyboard_01a", 2.5 + c * 4.0, 13.8 + r * 3.3, 0.77, 180),
    )
] + [
    ("office", "prop_watercooler", 13.4, 23.4, 0.0, 270),
    ("office", "prop_plant_int_03a", 0.6, 23.4, 0.0, 0),
    # armory
    ("armory", "prop_cs_gunrack", 19.6, 13.0, 0.0, 270),
    ("armory", "prop_cs_gunrack", 19.6, 15.0, 0.0, 270),
    ("armory", "prop_mil_crate_01", 14.8, 16.0, 0.0, 0),
    ("armory", "prop_box_ammo03a", 14.8, 13.0, 0.0, 0),
    ("armory", "prop_box_ammo04a", 14.8, 13.8, 0.0, 0),
    # locker room
] + [
    ("locker", "p_cs_locker_01", 19.6, 18.0 + i * 0.6, 0.0, 270) for i in range(9)
] + [
    ("locker", "prop_bench_01a", 16.5, 20.5, 0.0, 90),
    # interrogation
    ("interrogation", "prop_table_02", 22.5, 14.0, 0.0, 0),
    ("interrogation", "prop_chair_01a", 22.5, 13.1, 0.0, 0),
    ("interrogation", "prop_chair_01a", 22.5, 14.9, 0.0, 180),
    ("interrogation", "prop_cctv_cam_01a", 24.7, 16.7, 2.9, 135),
    # evidence
    ("evidence", "prop_mil_crate_01", 21.0, 23.2, 0.0, 0),
    ("evidence", "prop_box_ammo03a", 24.2, 23.2, 0.0, 0),
    # cells
] + [
    item
    for i, (y0, y1) in enumerate([(11.0, 15.33), (15.33, 19.67), (19.67, 24.0)])
    for item in (
        ("cells", "prop_toilet_01", 31.5, y0 + 0.6, 0.0, 270),
        ("cells", "prop_wait_bench_01", 31.4, (y0 + y1) / 2 + 0.6, 0.0, 270),
    )
]

# Doors (vanilla Mission Row door models). Hinge at origin, door leaf along local +X.
# (portal index, model, hinge x, y, z, heading)
DOORS = [
    (0, "v_ilev_ph_door01", 5.0, 0.0, 0.0, 0),
    (0, "v_ilev_ph_door002", 7.0, 0.0, 0.0, 180),
    (1, "v_ilev_ph_gendoor004", W, 9.0, 0.0, 90),
    (2, "v_ilev_ph_gendoor004", 9.5, 8.0, 0.0, 0),
    (3, "v_ilev_ph_gendoor004", 16.5, 8.0, 0.0, 0),
    (4, "v_ilev_ph_gendoor004", 26.5, 8.0, 0.0, 0),
    (5, "v_ilev_ph_gendoor004", 6.0, 11.0, 0.0, 0),
    (6, "v_ilev_arm_secdoor", 16.4, 11.0, 0.0, 0),
    (7, "v_ilev_ph_gendoor004", 21.9, 11.0, 0.0, 0),
    (8, "v_ilev_ph_gendoor004", 25.6, 11.0, 0.0, 0),
    (9, "v_ilev_ph_gendoor004", 14.0, 20.0, 0.0, 90),
    (10, "v_ilev_ph_gendoor004", 21.9, 17.0, 0.0, 0),
]
CELL_GATES = [("v_ilev_ph_cellgate", 28.5, y, 0.0, 90) for y in (12.6, 16.9, 21.2)]

# Decorative exterior windows: (facade, a0, a1, z0, z1)
WINDOWS = (
    [("S", a, a + 2.4, 1.0, 2.4) for a in (1.0, 8.6, 13.4, 18.4, 23.4, 28.4)]
    + [("N", a, a + 2.4, 1.0, 2.4) for a in (1.5, 6.0, 10.5, 15.6, 21.0, 26.2)]
    + [("W", a, a + 2.4, 1.0, 2.4) for a in (2.5, 13.0, 17.5)]
    + [("E", a, a + 2.4, 1.0, 2.4) for a in (2.5, 13.5, 18.0)]
)


# --------------------------------------------------------------------------------------
# TEXTURES
# --------------------------------------------------------------------------------------
def _noise(size, scale, seed, amp):
    rng = np.random.default_rng(seed)
    small = rng.random((max(2, size // scale), max(2, size // scale)))
    img = Image.fromarray((small * 255).astype(np.uint8)).resize((size, size), Image.BICUBIC)
    return (np.asarray(img).astype(np.float32) / 255.0 - 0.5) * amp


def _fine(size, seed, amp):
    rng = np.random.default_rng(seed)
    return (rng.random((size, size)) - 0.5) * amp


def tex_solid(rgb, size=256, seed=0, amp=10, fine=6):
    a = np.zeros((size, size, 3), np.float32) + np.array(rgb, np.float32)
    n = _noise(size, 16, seed, amp) + _fine(size, seed + 1, fine)
    return np.clip(a + n[..., None], 0, 255)


def tex_tiles(base, grout, tiles=4, size=256, seed=0, gw=3):
    a = tex_solid(base, size, seed, amp=8, fine=4)
    rng = np.random.default_rng(seed)
    step = size // tiles
    for ty in range(tiles):
        for tx in range(tiles):
            a[ty * step:(ty + 1) * step, tx * step:(tx + 1) * step] += rng.uniform(-6, 6)
    for i in range(tiles):
        a[i * step:i * step + gw, :] = grout
        a[:, i * step:i * step + gw] = grout
    return np.clip(a, 0, 255)


def tex_wood(size=256, seed=3):
    y = np.linspace(0, 1, size)[:, None]
    x = np.linspace(0, 1, size)[None, :]
    rings = np.sin((x * 40 + _noise(size, 32, seed, 6)) * 1.0) * 0.5 + 0.5
    base = np.array([120, 78, 46], np.float32)
    a = base[None, None, :] * (0.8 + 0.25 * rings[..., None])
    planks = 6
    step = size // planks
    for i in range(planks):
        a[i * step:i * step + 2, :] *= 0.55
    a = a + 0 * y[..., None]
    return np.clip(a, 0, 255)


def tex_ceiling(size=256):
    a = tex_solid((228, 228, 224), size, 11, amp=6, fine=10)
    step = size // 2
    for i in range(2):
        a[i * step:i * step + 3, :] = (170, 170, 168)
        a[:, i * step:i * step + 3] = (170, 170, 168)
    return a


def tex_facade(size=256):
    a = tex_solid((196, 186, 168), size, 21, amp=14, fine=10)
    step = size // 2
    for i in range(2):
        a[i * step:i * step + 2, :] *= 0.75
        a[:, i * step:i * step + 2] *= 0.8
    return np.clip(a, 0, 255)


def tex_glass(size=128):
    y = np.linspace(0, 1, size)[:, None]
    x = np.linspace(0, 1, size)[None, :]
    g = 0.6 + 0.4 * np.clip(1.2 - (x + (1 - y)) * 0.8, 0, 1)
    base = np.array([38, 58, 78], np.float32)
    return np.clip(base[None, None, :] * g[..., None] + 10 * g[..., None], 0, 255)


def tex_sign(w=512, h=128):
    img = Image.new("RGB", (w, h), (18, 34, 78))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, w - 5, h - 5], outline=(235, 235, 240), width=4)
    try:
        font = ImageFont.load_default(size=86)
    except TypeError:
        font = ImageFont.load_default()
    text = "POLICE"
    bb = d.textbbox((0, 0), text, font=font)
    d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], (h - (bb[3] - bb[1])) / 2 - bb[1]), text,
           fill=(245, 245, 250), font=font)
    return np.asarray(img).astype(np.float32)


def tex_lightpanel(size=64):
    a = np.full((size, size, 3), 250, np.float32)
    a[:3, :] = a[-3:, :] = a[:, :3] = a[:, -3:] = 180
    return a


TEXTURES = {
    "xp_floor_tile": lambda: tex_tiles((205, 205, 200), (150, 150, 146), 4, seed=1),
    "xp_floor_carpet": lambda: tex_solid((70, 78, 96), seed=2, amp=10, fine=28),
    "xp_floor_wood": tex_wood,
    "xp_floor_concrete": lambda: tex_solid((140, 140, 136), seed=4, amp=22, fine=14),
    "xp_wall_paint": lambda: tex_solid((226, 224, 214), seed=5, amp=6, fine=5),
    "xp_wall_lower": lambda: tex_solid((52, 72, 110), seed=6, amp=6, fine=5),
    "xp_wall_concrete": lambda: tex_tiles((176, 176, 170), (150, 150, 145), 2, seed=7, gw=2),
    "xp_ceiling": tex_ceiling,
    "xp_facade": tex_facade,
    "xp_facade_base": lambda: tex_solid((96, 96, 100), seed=8, amp=18, fine=12),
    "xp_roof": lambda: tex_solid((92, 92, 90), seed=9, amp=20, fine=40),
    "xp_glass": tex_glass,
    "xp_frame": lambda: tex_solid((48, 50, 56), seed=10, amp=4, fine=4, size=64),
    "xp_trim_wood": tex_wood,
    "xp_counter_top": lambda: tex_solid((40, 42, 48), seed=12, amp=6, fine=8, size=64),
    "xp_sign": tex_sign,
    "xp_lightpanel": tex_lightpanel,
}

# material -> (texture, uv scale in metres per texture repeat)
MATERIALS = {
    "floor_tile": ("xp_floor_tile", 2.4),
    "floor_carpet": ("xp_floor_carpet", 2.0),
    "floor_wood": ("xp_floor_wood", 3.0),
    "floor_concrete": ("xp_floor_concrete", 3.0),
    "wall_paint": ("xp_wall_paint", 2.5),
    "wall_lower": ("xp_wall_lower", 2.5),
    "wall_concrete": ("xp_wall_concrete", 1.6),
    "ceiling": ("xp_ceiling", 1.2),
    "facade": ("xp_facade", 3.0),
    "facade_base": ("xp_facade_base", 2.0),
    "roof": ("xp_roof", 4.0),
    "glass": ("xp_glass", 0),      # 0 = stretch 0..1 over the face
    "frame": ("xp_frame", 1.0),
    "trim_wood": ("xp_trim_wood", 1.5),
    "counter_top": ("xp_counter_top", 1.0),
    "sign": ("xp_sign", 0),
    "lightpanel": ("xp_lightpanel", 0),
}


def write_dds(path, rgb):
    """Uncompressed A8R8G8B8 DDS with full mip chain."""
    img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    w, h = img.size
    mips = []
    cw, ch = w, h
    cur = img
    while True:
        arr = np.asarray(cur)
        bgra = arr[..., [2, 1, 0, 3]].tobytes()
        mips.append(bgra)
        if cw == 1 and ch == 1:
            break
        cw, ch = max(1, cw // 2), max(1, ch // 2)
        cur = img.resize((cw, ch), Image.LANCZOS)
        if len(mips) >= 8:
            break
    DDSD_CAPS, DDSD_HEIGHT, DDSD_WIDTH, DDSD_PITCH, DDSD_PIXELFORMAT, DDSD_MIPMAPCOUNT = 1, 2, 4, 8, 0x1000, 0x20000
    flags = DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PITCH | DDSD_PIXELFORMAT | DDSD_MIPMAPCOUNT
    pf = struct.pack("<II4sIIIII", 32, 0x41, b"\0\0\0\0", 32, 0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)
    caps = 0x1000 | 0x400000 | 0x8
    header = struct.pack("<4sIIIIIII44s", b"DDS ", 124, flags, h, w, w * 4, 0, len(mips), b"\0" * 44)
    header += pf + struct.pack("<IIIII", caps, 0, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(header)
        for m in mips:
            f.write(m)
    return w, h, len(mips)


# --------------------------------------------------------------------------------------
# GEOMETRY
# --------------------------------------------------------------------------------------
class Mesh:
    """Collects quads per material."""

    def __init__(self):
        self.mats = {}  # material -> (verts list, indices list)

    def quad(self, mat, p0, p1, p2, p3, n, uvs=None):
        """p0..p3 counter-clockwise when seen from the normal side."""
        verts, inds = self.mats.setdefault(mat, ([], []))
        tex, scale = MATERIALS[mat]
        pts = [p0, p1, p2, p3]
        if uvs is None:
            if scale == 0:
                uvs = [(0, 1), (1, 1), (1, 0), (0, 0)]
            else:
                ax = max(range(3), key=lambda i: abs(n[i]))
                if ax == 2:
                    uvs = [(p[0] / scale, -p[1] / scale) for p in pts]
                elif ax == 0:
                    sgn = 1 if n[0] > 0 else -1
                    uvs = [(sgn * p[1] / scale, -p[2] / scale) for p in pts]
                else:
                    sgn = -1 if n[1] > 0 else 1
                    uvs = [(sgn * p[0] / scale, -p[2] / scale) for p in pts]
        base = len(verts)
        for p, uv in zip(pts, uvs):
            verts.append((p, n, uv))
        inds += [base, base + 1, base + 2, base, base + 2, base + 3]

    def empty(self):
        return not self.mats


def box_faces(mn, mx):
    """Yield (normal, [4 corners CCW from outside]) for an axis-aligned box."""
    x0, y0, z0 = mn
    x1, y1, z1 = mx
    yield (0, 0, 1), [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    yield (0, 0, -1), [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)]
    yield (1, 0, 0), [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)]
    yield (-1, 0, 0), [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)]
    yield (0, 1, 0), [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)]
    yield (0, -1, 0), [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]


def rooms_at(x, y, z, grow=0.0):
    out = []
    if z < -0.05 or z > H + 0.05:
        return out
    for name, (x0, y0, x1, y1), *_ in ROOMS:
        if x0 - grow < x < x1 + grow and y0 - grow < y < y1 + grow:
            out.append(name)
    return out


def clip_z(pts, zmin, zmax):
    """Clip a vertical quad (two bottom, two top corners) to [zmin, zmax]; None if empty."""
    zs = [p[2] for p in pts]
    lo, hi = min(zs), max(zs)
    nlo, nhi = max(lo, zmin), min(hi, zmax)
    if nhi - nlo < 1e-4:
        return None
    return [(p[0], p[1], nlo if abs(p[2] - lo) < 1e-6 else nhi) for p in pts]


ROOM_MESH = {r[0]: Mesh() for r in ROOMS}
EXT_MESH = Mesh()
COLLISION = []  # (min, max, room_index)


def emit_vertical(mesh, pts, n, mat_upper, mat_lower, split):
    lower = clip_z(pts, -10, split)
    upper = clip_z(pts, split, 100)
    if lower:
        mesh.quad(mat_lower, *lower, n)
    if upper:
        mesh.quad(mat_upper, *upper, n)


def add_wall_box(mn, mx, exterior, skip_normals, axis, jamb_h=None):
    for n, pts in box_faces(mn, mx):
        if n in skip_normals:
            continue
        cx = sum(p[0] for p in pts) / 4
        cy = sum(p[1] for p in pts) / 4
        cz = sum(p[2] for p in pts) / 4
        if n[2] != 0:
            # top/bottom faces: top of exterior wall = parapet cap; bottoms of lintels = door heads
            if n[2] > 0:
                if exterior and cz > ROOF:
                    EXT_MESH.quad("facade_base", *pts, n)
                continue
            # lintel underside, visible from both sides of the opening
            rs = rooms_at(cx, cy, cz - 0.1, grow=0.2)
            for r in rs:
                ROOM_MESH[r].quad("frame", *pts, n)
            if exterior:
                EXT_MESH.quad("frame", *pts, n)
            continue
        tx, ty, tz = cx + n[0] * 0.25, cy + n[1] * 0.25, min(cz, 1.0)
        rs = rooms_at(tx, ty, tz)
        along = abs(n[0]) if axis == "x" else abs(n[1])
        if along > 0.5:
            # jamb face inside an opening (normal parallel to the wall axis)
            rs = rooms_at(cx + n[0] * 0.05, cy + n[1] * 0.05, 1.0, grow=0.25)
            jh = min(H, jamb_h.get(n, H)) if jamb_h else H
            for r in rs:
                c = clip_z(pts, -1, jh)
                if c:
                    ROOM_MESH[r].quad("frame", *c, n)
            if exterior:
                c = clip_z(pts, -1, jamb_h.get(n, TOP) if jamb_h else TOP)
                if c:
                    EXT_MESH.quad("frame", *c, n)
            continue
        if rs:
            room = next(r for r in ROOMS if r[0] == rs[0])
            c = clip_z(pts, -1, H)
            if c:
                emit_vertical(ROOM_MESH[rs[0]], c, n, room[3], room[4], 1.0)
            if exterior:
                c = clip_z(pts, ROOF, TOP)
                if c:
                    EXT_MESH.quad("facade_base", *c, n)
        elif exterior:
            emit_vertical(EXT_MESH, pts, n, "facade", "facade_base", 0.6)


def build_walls():
    room_cuts_x = sorted({r[1][0] for r in ROOMS} | {r[1][2] for r in ROOMS})
    room_cuts_y = sorted({r[1][1] for r in ROOMS} | {r[1][3] for r in ROOMS})
    for axis, c, a0, a1, t, h, ext, openings in WALLS:
        cuts = set([a0, a1])
        for o0, o1, _ in openings:
            cuts |= {o0, o1}
        for v in (room_cuts_x if axis == "x" else room_cuts_y):
            if a0 < v < a1:
                cuts.add(v)
        cuts = sorted(cuts)
        for s0, s1 in zip(cuts[:-1], cuts[1:]):
            op = next((o for o in openings if o[0] <= s0 + 1e-6 and s1 <= o[1] + 1e-6), None)
            z0 = op[2] if op else 0.0
            if z0 >= h:
                continue
            if axis == "x":
                mn, mx = (s0, c - t / 2, z0), (s1, c + t / 2, h)
                skip = set()
                if not any(abs(s0 - o[1]) < 1e-6 for o in openings) or op:
                    skip.add((-1, 0, 0))
                if not any(abs(s1 - o[0]) < 1e-6 for o in openings) or op:
                    skip.add((1, 0, 0))
            else:
                mn, mx = (c - t / 2, s0, z0), (c + t / 2, s1, h)
                skip = set()
                if not any(abs(s0 - o[1]) < 1e-6 for o in openings) or op:
                    skip.add((0, -1, 0))
                if not any(abs(s1 - o[0]) < 1e-6 for o in openings) or op:
                    skip.add((0, 1, 0))
            jamb_h = {}
            for o in openings:
                if abs(s0 - o[1]) < 1e-6:
                    jamb_h[(-1, 0, 0) if axis == "x" else (0, -1, 0)] = o[2]
                if abs(s1 - o[0]) < 1e-6:
                    jamb_h[(1, 0, 0) if axis == "x" else (0, 1, 0)] = o[2]
            add_wall_box(mn, mx, ext, skip, axis, jamb_h)
            mid = ((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2)
            off = 0.3 if axis == "x" else 0.0
            rs = rooms_at(mid[0] + (0 if axis == "x" else 0.3), mid[1] + off, 1.0)
            COLLISION.append((mn, mx, ROOM_INDEX[rs[0]] if rs else 0))


def build_floors_ceilings():
    for name, (x0, y0, x1, y1), floor, *_ in ROOMS:
        m = ROOM_MESH[name]
        m.quad(floor, (x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (0, 0, 1))
        m.quad("ceiling", (x0, y1, H), (x1, y1, H), (x1, y0, H), (x0, y0, H), (0, 0, -1))
        COLLISION.append(((x0, y0, -0.3), (x1, y1, 0.0), ROOM_INDEX[name]))


LIGHTS = {r[0]: [] for r in ROOMS}


def build_lights():
    for name, (x0, y0, x1, y1), *_ in ROOMS:
        nx = max(1, round((x1 - x0) / 4.0))
        ny = max(1, round((y1 - y0) / 4.0))
        for i in range(nx):
            for j in range(ny):
                cx = x0 + (i + 0.5) * (x1 - x0) / nx
                cy = y0 + (j + 0.5) * (y1 - y0) / ny
                hz = H - 0.005
                ROOM_MESH[name].quad("lightpanel", (cx - 0.3, cy + 0.6, hz), (cx + 0.3, cy + 0.6, hz),
                                     (cx + 0.3, cy - 0.6, hz), (cx - 0.3, cy - 0.6, hz), (0, 0, -1))
                LIGHTS[name].append((cx, cy, H - 0.15))


def build_solids():
    for room, mn, mx, mat in SOLIDS:
        for n, pts in box_faces(mn, mx):
            if n[2] < 0 and mn[2] <= 0.0:
                continue
            ROOM_MESH[room].quad(mat, *pts, n)
        COLLISION.append((mn, mx, ROOM_INDEX[room]))


def build_exterior():
    # foundation / sidewalk slab
    fmn, fmx = (-1.5, -3.0, -1.0), (W + 1.5, D + 1.5, -0.02)
    for n, pts in box_faces(fmn, fmx):
        if n[2] < 0:
            continue
        EXT_MESH.quad("facade_base", *pts, n)
    COLLISION.append((fmn, (fmx[0], fmx[1], -0.02), 0))
    # roof surface
    e = T_EXT / 2
    EXT_MESH.quad("roof", (e, e, ROOF), (W - e, e, ROOF), (W - e, D - e, ROOF), (e, D - e, ROOF), (0, 0, 1))
    COLLISION.append(((e, e, H), (W - e, D - e, ROOF), 0))
    # windows (decorative, exterior only)
    o = T_EXT / 2 + 0.015
    f = 0.08
    for side, a0, a1, z0, z1 in WINDOWS:
        def P(a, z, d=o):
            if side == "S":
                return (a, -d, z)
            if side == "N":
                return (W - a, D + d, z)
            if side == "W":
                return (-d, D - a, z)
            return (W + d, a, z)
        n = {"S": (0, -1, 0), "N": (0, 1, 0), "W": (-1, 0, 0), "E": (1, 0, 0)}[side]
        EXT_MESH.quad("glass", P(a0 + f, z0 + f), P(a1 - f, z0 + f), P(a1 - f, z1 - f), P(a0 + f, z1 - f), n)
        for (b0, b1, c0, c1) in ((a0, a1, z0, z0 + f), (a0, a1, z1 - f, z1),
                                 (a0, a0 + f, z0 + f, z1 - f), (a1 - f, a1, z0 + f, z1 - f)):
            d = o + 0.01
            EXT_MESH.quad("frame", P(b0, c0, d), P(b1, c0, d), P(b1, c1, d), P(b0, c1, d), n)
    # sign above the entrance
    d = T_EXT / 2 + 0.02
    EXT_MESH.quad("sign", (3.5, -d, 3.02), (8.5, -d, 3.02), (8.5, -d, 3.92), (3.5, -d, 3.92), (0, -1, 0))
    # entrance canopy
    cmn, cmx = (3.0, -2.2, 2.75), (9.0, -T_EXT / 2, 2.95)
    for n, pts in box_faces(cmn, cmx):
        if n == (0, 1, 0):
            continue
        EXT_MESH.quad("frame" if n[2] == 0 else "facade_base", *pts, n)
    COLLISION.append((cmn, cmx, 0))


# --------------------------------------------------------------------------------------
# XML WRITERS
# --------------------------------------------------------------------------------------
def f(v):
    s = ("%.6f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def v3(tag, v):
    return '<%s x="%s" y="%s" z="%s" />' % (tag, f(v[0]), f(v[1]), f(v[2]))


def bounds_of(points):
    a = np.array(points, np.float64)
    return a.min(axis=0), a.max(axis=0)


def drawable_xml(name, mesh, lights, outdir, used_textures):
    mats = sorted(mesh.mats.keys())
    allp = [v[0] for m in mats for v in mesh.mats[m][0]] + [l for l in lights]
    bmin, bmax = bounds_of(allp)
    cen = (bmin + bmax) / 2
    rad = float(np.linalg.norm(bmax - cen))
    tex_names = sorted({MATERIALS[m][0] for m in mats})
    L = []
    A = L.append
    A('<?xml version="1.0" encoding="UTF-8"?>')
    A("<Drawable>")
    A("  <Name>%s</Name>" % name)
    A("  " + v3("BoundingSphereCenter", cen))
    A('  <BoundingSphereRadius value="%s" />' % f(rad))
    A("  " + v3("BoundingBoxMin", bmin))
    A("  " + v3("BoundingBoxMax", bmax))
    A('  <LodDistHigh value="9998" />')
    A('  <LodDistMed value="9998" />')
    A('  <LodDistLow value="9998" />')
    A('  <LodDistVlow value="9998" />')
    A('  <FlagsHigh value="1" />')
    A('  <FlagsMed value="0" />')
    A('  <FlagsLow value="0" />')
    A('  <FlagsVlow value="0" />')
    A("  <ShaderGroup>")
    A("    <TextureDictionary>")
    for tn in tex_names:
        w, h, lv = used_textures[tn]
        A("      <Item>")
        A("        <Name>%s</Name>" % tn)
        A('        <Unk32 value="128" />')
        A("        <Usage>DIFFUSE</Usage>")
        A("        <UsageFlags>UNK24</UsageFlags>")
        A('        <ExtraFlags value="0" />')
        A('        <Width value="%d" />' % w)
        A('        <Height value="%d" />' % h)
        A('        <MipLevels value="%d" />' % lv)
        A("        <Format>D3DFMT_A8R8G8B8</Format>")
        A("        <FileName>%s.dds</FileName>" % tn)
        A("      </Item>")
    A("    </TextureDictionary>")
    A("    <Shaders>")
    for m in mats:
        tn = MATERIALS[m][0]
        A("      <Item>")
        A("        <Name>default</Name>")
        A("        <FileName>default.sps</FileName>")
        A('        <RenderBucket value="0" />')
        A("        <Parameters>")
        A('          <Item name="DiffuseSampler" type="Texture">')
        A("            <Name>%s</Name>" % tn)
        A("          </Item>")
        A('          <Item name="matMaterialColorScale" type="Vector" x="1" y="0" z="0" w="1" />')
        A('          <Item name="HardAlphaBlend" type="Vector" x="1" y="0" z="0" w="0" />')
        A('          <Item name="useTessellation" type="Vector" x="0" y="0" z="0" w="0" />')
        A('          <Item name="wetnessMultiplier" type="Vector" x="1" y="0" z="0" w="0" />')
        A('          <Item name="globalAnimUV1" type="Vector" x="0" y="1" z="0" w="0" />')
        A('          <Item name="globalAnimUV0" type="Vector" x="1" y="0" z="0" w="0" />')
        A("        </Parameters>")
        A("      </Item>")
    A("    </Shaders>")
    A("  </ShaderGroup>")
    A("  <DrawableModelsHigh>")
    A("    <Item>")
    A('      <RenderMask value="255" />')
    A('      <Flags value="0" />')
    A('      <HasSkin value="0" />')
    A('      <BoneIndex value="0" />')
    A('      <Unknown1 value="0" />')
    A("      <Geometries>")
    for si, m in enumerate(mats):
        verts, inds = mesh.mats[m]
        gmin, gmax = bounds_of([v[0] for v in verts])
        A("        <Item>")
        A('          <ShaderIndex value="%d" />' % si)
        A('          <BoundingBoxMin x="%s" y="%s" z="%s" w="0" />' % (f(gmin[0]), f(gmin[1]), f(gmin[2])))
        A('          <BoundingBoxMax x="%s" y="%s" z="%s" w="0" />' % (f(gmax[0]), f(gmax[1]), f(gmax[2])))
        A("          <VertexBuffer>")
        A('            <Flags value="0" />')
        A('            <Layout type="GTAV1">')
        A("              <Position />")
        A("              <Normal />")
        A("              <Colour0 />")
        A("              <TexCoord0 />")
        A("            </Layout>")
        A("            <Data>")
        for p, n, uv in verts:
            A("              %s %s %s   %s %s %s   255 255 255 255   %s %s" % (
                f(p[0]), f(p[1]), f(p[2]), f(n[0]), f(n[1]), f(n[2]), f(uv[0]), f(uv[1])))
        A("            </Data>")
        A("          </VertexBuffer>")
        A("          <IndexBuffer>")
        A("            <Data>")
        for i in range(0, len(inds), 24):
            A("              " + " ".join(str(x) for x in inds[i:i + 24]))
        A("            </Data>")
        A("          </IndexBuffer>")
        A("        </Item>")
    A("      </Geometries>")
    A("    </Item>")
    A("  </DrawableModelsHigh>")
    if lights:
        A("  <Lights>")
        for (x, y, z) in lights:
            A("    <Item>")
            A("      " + v3("Position", (x, y, z)))
            A('      <Colour r="255" g="244" b="226" />')
            A('      <Flashiness value="0" />')
            A('      <Intensity value="4" />')
            A('      <Flags value="0" />')
            A('      <BoneId value="0" />')
            A("      <Type>Point</Type>")
            A('      <GroupId value="0" />')
            A('      <TimeFlags value="16777215" />')
            A('      <Falloff value="6.5" />')
            A('      <FalloffExponent value="8" />')
            A('      <CullingPlaneNormal x="0" y="0" z="-1" />')
            A('      <CullingPlaneOffset value="0" />')
            A('      <Unknown45 value="0" />')
            A('      <Unknown46 value="0" />')
            A('      <VolumeIntensity value="1" />')
            A('      <VolumeSizeScale value="1" />')
            A('      <VolumeOuterColour r="255" g="255" b="255" />')
            A('      <LightHash value="0" />')
            A('      <VolumeOuterIntensity value="1" />')
            A('      <CoronaSize value="0" />')
            A('      <VolumeOuterExponent value="1" />')
            A('      <LightFadeDistance value="0" />')
            A('      <ShadowFadeDistance value="0" />')
            A('      <SpecularFadeDistance value="0" />')
            A('      <VolumetricFadeDistance value="0" />')
            A('      <ShadowNearClip value="0.01" />')
            A('      <CoronaIntensity value="0" />')
            A('      <CoronaZBias value="0.1" />')
            A('      <Direction x="0" y="0" z="-1" />')
            A('      <Tangent x="1" y="0" z="0" />')
            A('      <ConeInnerAngle value="0" />')
            A('      <ConeOuterAngle value="0" />')
            A('      <Extent x="1" y="1" z="1" />')
            A("      <ProjectedTextureHash />")
            A("    </Item>")
        A("  </Lights>")
    A("</Drawable>")
    with open(os.path.join(outdir, name + ".ydr.xml"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    return bmin, bmax, cen, rad


def bounds_xml(name, outdir):
    verts = []
    polys = []
    mats = []
    for mn, mx, room in COLLISION:
        key = (1, room)  # material 1 = CONCRETE
        if key not in mats:
            mats.append(key)
        mi = mats.index(key)
        x0, y0, z0 = mn
        x1, y1, z1 = mx
        b = len(verts)
        verts += [(x0, y0, z0), (x1, y1, z0), (x1, y0, z1), (x0, y1, z1)]
        polys.append((mi, b, b + 1, b + 2, b + 3))
    allc = [p for mn, mx, _ in COLLISION for p in (mn, mx)]
    bmin, bmax = bounds_of(allc)
    cen = (bmin + bmax) / 2
    rad = float(np.linalg.norm(bmax - cen))
    vol = float(np.prod(bmax - bmin))
    flags1 = "MAP_WEAPON, MAP_DYNAMIC, MAP_ANIMAL, MAP_COVER, MAP_VEHICLE"
    flags2 = ("VEHICLE_NOT_BVH, VEHICLE_BVH, PED, RAGDOLL, ANIMAL, ANIMAL_RAGDOLL, OBJECT, "
              "OBJECT_ENV_CLOTH, PLANT, PROJECTILE, EXPLOSION, FORKLIFT_FORKS, TEST_WEAPON, "
              "TEST_CAMERA, TEST_AI, TEST_SCRIPT, TEST_VEHICLE_WHEEL, GLASS")

    def common(ind, extra_room=0):
        return [
            ind + v3("BoxMin", bmin), ind + v3("BoxMax", bmax), ind + v3("BoxCenter", cen),
            ind + v3("SphereCenter", cen), ind + '<SphereRadius value="%s" />' % f(rad),
            ind + '<Margin value="0.005" />', ind + '<Volume value="%s" />' % f(vol),
            ind + '<Inertia x="1" y="1" z="1" />',
            ind + '<MaterialIndex value="0" />', ind + '<MaterialColourIndex value="0" />',
            ind + '<ProceduralID value="0" />', ind + '<RoomID value="%d" />' % extra_room,
            ind + '<PedDensity value="0" />', ind + '<UnkFlags value="0" />',
            ind + '<PolyFlags value="0" />', ind + '<UnkType value="0" />',
        ]

    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<BoundsFile>", '  <Bounds type="Composite">']
    L += common("    ")
    L.append("    <Children>")
    L.append('      <Item type="GeometryBVH">')
    L += common("        ")
    L.append('        <CompositeTransform content="raw">')
    for row in ("1 0 0 0", "0 1 0 0", "0 0 1 0", "0 0 0 1"):
        L.append("          " + row)
    L.append("        </CompositeTransform>")
    L.append("        <CompositeFlags1>%s</CompositeFlags1>" % flags1)
    L.append("        <CompositeFlags2>%s</CompositeFlags2>" % flags2)
    L.append("        " + v3("GeometryCenter", cen))
    L.append('        <UnkFloat1 value="0" />')
    L.append('        <UnkFloat2 value="0" />')
    L.append("        <Materials>")
    for t, room in mats:
        L += ["          <Item>",
              '            <Type value="%d" />' % t,
              '            <ProceduralID value="0" />',
              '            <RoomID value="%d" />' % room,
              '            <PedDensity value="0" />',
              "            <Flags>NONE</Flags>",
              '            <MaterialColourIndex value="0" />',
              '            <Unk value="0" />',
              "          </Item>"]
    L.append("        </Materials>")
    L.append('        <Vertices content="raw">')
    for v in verts:
        L.append("          %s, %s, %s" % (f(v[0] - cen[0]), f(v[1] - cen[1]), f(v[2] - cen[2])))
    L.append("        </Vertices>")
    L.append("        <Polygons>")
    for mi, a, b, c, d in polys:
        L.append('          <Box m="%d" v1="%d" v2="%d" v3="%d" v4="%d" />' % (mi, a, b, c, d))
    L.append("        </Polygons>")
    L.append("      </Item>")
    L.append("    </Children>")
    L.append("  </Bounds>")
    L.append("</BoundsFile>")
    with open(os.path.join(outdir, name + ".ybn.xml"), "w") as fh:
        fh.write("\n".join(L) + "\n")


def quat_z(deg, invert=False):
    r = math.radians(deg) / 2
    s, c = math.sin(r), math.cos(r)
    if invert:
        s = -s
    return (0.0, 0.0, s, c)


def entity_xml(ind, model, pos, rot, lod=150.0, flags=1572864, guid=None, typ="CEntityDef", extra=()):
    g = guid if guid is not None else random.getrandbits(32)
    L = [
        ind + '<Item type="%s">' % typ,
        ind + "  <archetypeName>%s</archetypeName>" % model,
        ind + '  <flags value="%d" />' % flags,
        ind + '  <guid value="%d" />' % g,
        ind + "  " + v3("position", pos),
        ind + '  <rotation x="%s" y="%s" z="%s" w="%s" />' % tuple(f(v) for v in rot),
        ind + '  <scaleXY value="1" />',
        ind + '  <scaleZ value="1" />',
        ind + '  <parentIndex value="-1" />',
        ind + '  <lodDist value="%s" />' % f(lod),
        ind + '  <childLodDist value="0" />',
        ind + "  <lodLevel>LODTYPES_DEPTH_ORPHANHD</lodLevel>",
        ind + '  <numChildren value="0" />',
        ind + "  <priorityLevel>PRI_REQUIRED</priorityLevel>",
        ind + "  <extensions />",
        ind + '  <ambientOcclusionMultiplier value="255" />',
        ind + '  <artificialAmbientOcclusion value="255" />',
        ind + '  <tintValue value="0" />',
    ]
    L += [ind + "  " + e for e in extra]
    L.append(ind + "</Item>")
    return L


def archetype_xml(name, bmin, bmax, cen, rad, lod=300.0, flags=0):
    return [
        '    <Item type="CBaseArchetypeDef">',
        '      <lodDist value="%s" />' % f(lod),
        '      <flags value="%d" />' % flags,
        '      <specialAttribute value="0" />',
        "      " + v3("bbMin", bmin),
        "      " + v3("bbMax", bmax),
        "      " + v3("bsCentre", cen),
        '      <bsRadius value="%s" />' % f(rad),
        '      <hdTextureDist value="%s" />' % f(lod * 0.5),
        "      <name>%s</name>" % name,
        "      <textureDictionary />",
        "      <clipDictionary />",
        "      <drawableDictionary />",
        "      <physicsDictionary />",
        "      <assetType>ASSET_TYPE_DRAWABLE</assetType>",
        "      <assetName>%s</assetName>" % name,
        "      <extensions />",
        "    </Item>",
    ]


def ytyp_xml(outdir, arch_info):
    random.seed(1337)
    mlo_name = P + "_mlo"
    entities = []          # (model, pos, rot, room or None)
    room_objs = {r[0]: [] for r in ROOMS}
    portal_objs = {i: [] for i in range(len(PORTALS))}

    def add(model, pos, heading, room=None, portal=None, lod=150.0):
        idx = len(entities)
        entities.append((model, pos, quat_z(heading, invert=True), lod))
        if room:
            room_objs[room].append(idx)
        if portal is not None:
            portal_objs[portal].append(idx)

    for r in ROOMS:
        add(P + "_" + r[0], (0, 0, 0), 0, room=r[0], lod=300.0)
    for room, model, x, y, z, hd in PROPS:
        add(model, (x, y, z), hd, room=room)
    for pi, model, x, y, z, hd in DOORS:
        add(model, (x, y, z), hd, portal=pi)
    for model, x, y, z, hd in CELL_GATES:
        add(model, (x, y, z), hd, room="cells")

    allmin = np.array([-1.5, -3.0, -1.0])
    allmax = np.array([W + 1.5, D + 1.5, TOP])
    cen = (allmin + allmax) / 2
    rad = float(np.linalg.norm(allmax - cen))

    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<CMapTypes>", "  <extensions />", "  <archetypes>"]
    for name, (bmin, bmax, c, r) in arch_info.items():
        L += archetype_xml(name, bmin, bmax, c, r, lod=300.0 if name.endswith("ext") else 150.0)
    # MLO archetype
    L += [
        '    <Item type="CMloArchetypeDef">',
        '      <lodDist value="300" />',
        '      <flags value="0" />',
        '      <specialAttribute value="0" />',
        "      " + v3("bbMin", allmin),
        "      " + v3("bbMax", allmax),
        "      " + v3("bsCentre", cen),
        '      <bsRadius value="%s" />' % f(rad),
        '      <hdTextureDist value="150" />',
        "      <name>%s</name>" % mlo_name,
        "      <textureDictionary />",
        "      <clipDictionary />",
        "      <drawableDictionary />",
        "      <physicsDictionary />",
        "      <assetType>ASSET_TYPE_UNINITIALIZED</assetType>",
        "      <assetName>%s</assetName>" % mlo_name,
        "      <extensions />",
        '      <mloFlags value="0" />',
        "      <entities>",
    ]
    for model, pos, rot, lod in entities:
        L += entity_xml("        ", model, pos, rot, lod=lod)
    L.append("      </entities>")
    # rooms
    portal_count = {r[0]: 0 for r in ROOMS}
    portal_count["limbo"] = 0
    for a, b, *_ in PORTALS:
        portal_count[a] += 1
        portal_count[b] += 1
    L.append("      <rooms>")

    def room_xml(name, bmin, bmax, objs, pc):
        R = [
            "        <Item>",
            "          <name>%s</name>" % name,
            "          " + v3("bbMin", bmin),
            "          " + v3("bbMax", bmax),
            '          <blend value="1" />',
            "          <timecycleName />",
            "          <secondaryTimecycleName />",
            '          <flags value="%d" />' % (0 if name == "limbo" else 96),
            '          <portalCount value="%d" />' % pc,
            '          <floorId value="0" />',
            '          <exteriorVisibiltyDepth value="-1" />',
        ]
        if objs:
            R.append('          <attachedObjects content="int_array">')
            R.append("            " + " ".join(str(o) for o in objs))
            R.append("          </attachedObjects>")
        else:
            R.append('          <attachedObjects content="int_array" />')
        R.append("        </Item>")
        return R

    L += room_xml("limbo", (0, 0, 0), (0, 0, 0), [], portal_count["limbo"])
    for name, (x0, y0, x1, y1), *_ in ROOMS:
        L += room_xml(name, (x0 - 0.2, y0 - 0.2, -0.3), (x1 + 0.2, y1 + 0.2, H + 0.3),
                      room_objs[name], portal_count[name])
    L.append("      </rooms>")
    # portals
    L.append("      <portals>")
    room_ids = {"limbo": 0, **ROOM_INDEX}
    for i, (a, b, axis, c, a0, a1, h) in enumerate(PORTALS):
        if axis == "x":
            corners = [(a0, c, h), (a1, c, h), (a1, c, 0), (a0, c, 0)]
        else:
            corners = [(c, a0, h), (c, a1, h), (c, a1, 0), (c, a0, 0)]
        L += [
            "        <Item>",
            '          <roomFrom value="%d" />' % room_ids[a],
            '          <roomTo value="%d" />' % room_ids[b],
            '          <flags value="0" />',
            '          <mirrorPriority value="0" />',
            '          <opacity value="0" />',
            '          <audioOcclusion value="0" />',
            "          <corners>",
        ]
        for cc in corners:
            L.append("            <Item>%s, %s, %s</Item>" % (f(cc[0]), f(cc[1]), f(cc[2])))
        L.append("          </corners>")
        objs = portal_objs[i]
        if objs:
            L.append('          <attachedObjects content="int_array">')
            L.append("            " + " ".join(str(o) for o in objs))
            L.append("          </attachedObjects>")
        else:
            L.append('          <attachedObjects content="int_array" />')
        L.append("        </Item>")
    L.append("      </portals>")
    L += ["      <entitySets />", "      <timeCycleModifiers />", "    </Item>"]
    L += ["  </archetypes>", "  <name>%s</name>" % P, "  <dependencies />", "  <compositeEntityTypes />",
          "</CMapTypes>"]
    with open(os.path.join(outdir, P + ".ytyp.xml"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    return allmin, allmax


def ymap_xml(outdir, allmin, allmax):
    px, py, pz = CONFIG["position"]
    hd = CONFIG["heading"]
    c, s = math.cos(math.radians(hd)), math.sin(math.radians(hd))
    corners = [(x, y) for x in (allmin[0], allmax[0]) for y in (allmin[1], allmax[1])]
    wc = [(px + x * c - y * s, py + x * s + y * c) for x, y in corners]
    emin = (min(p[0] for p in wc), min(p[1] for p in wc), pz + allmin[2])
    emax = (max(p[0] for p in wc), max(p[1] for p in wc), pz + allmax[2])
    smin = (emin[0] - 300, emin[1] - 300, emin[2] - 300)
    smax = (emax[0] + 300, emax[1] + 300, emax[2] + 300)
    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<CMapData>",
         "  <name>%s</name>" % P, "  <parent />", '  <flags value="0" />', '  <contentFlags value="9" />',
         "  " + v3("streamingExtentsMin", smin), "  " + v3("streamingExtentsMax", smax),
         "  " + v3("entitiesExtentsMin", emin), "  " + v3("entitiesExtentsMax", emax),
         "  <entities>"]
    # exterior shell: normal entity -> rotation stored inverted
    L += entity_xml("    ", P + "_ext", (px, py, pz), quat_z(hd, invert=True), lod=500.0, flags=1572864,
                    guid=0x58E0A001)
    # interior: MLO instance -> rotation stored as-is
    L += entity_xml("    ", P + "_mlo", (px, py, pz), quat_z(hd, invert=False), lod=300.0, flags=1572864,
                    guid=0x58E0A002, typ="CMloInstanceDef",
                    extra=['<groupId value="0" />', '<floorId value="0" />', "<defaultEntitySets />",
                           '<numExitPortals value="2" />', '<MLOInstflags value="0" />'])
    L += ["  </entities>", "  <containerLods />", "  <boxOccluders />", "  <occludeModels />",
          "  <physicsDictionaries />",
          "  <instancedData>", "    <ImapLink />", "    <PropInstanceList />", "    <GrassInstanceList />",
          "  </instancedData>",
          "  <timeCycleModifiers />", "  <carGenerators />",
          "  <LODLightsSOA>", "    <direction />", "    <falloff />", "    <falloffExponent />",
          "    <timeAndStateFlags />", "    <hash />", "    <coneInnerAngle />",
          "    <coneOuterAngleOrCapExt />", "    <coronaIntensity />", "  </LODLightsSOA>",
          "  <DistantLODLightsSOA>", "    <position />", "    <RGBI />", '    <numStreetLights value="0" />',
          '    <category value="0" />', "  </DistantLODLightsSOA>",
          "  <block>", '    <version value="0" />', '    <flags value="0" />', "    <name>%s</name>" % P,
          "    <exportedBy>xenon_mlo-police generator</exportedBy>", "    <owner />", "    <time />",
          "  </block>", "</CMapData>"]
    with open(os.path.join(outdir, P + ".ymap.xml"), "w") as fh:
        fh.write("\n".join(L) + "\n")


# --------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_xml"))
    args = ap.parse_args()
    out = args.out
    os.makedirs(out, exist_ok=True)

    build_walls()
    build_floors_ceilings()
    build_solids()
    build_lights()
    build_exterior()

    used = {}
    for tn, fn in TEXTURES.items():
        used[tn] = write_dds(os.path.join(out, tn + ".dds"), fn())

    arch = {}
    for r in ROOMS:
        name = P + "_" + r[0]
        arch[name] = drawable_xml(name, ROOM_MESH[r[0]], LIGHTS[r[0]], out, used)
    arch[P + "_ext"] = drawable_xml(P + "_ext", EXT_MESH, [], out, used)
    bounds_xml(P + "_col", out)
    allmin, allmax = ytyp_xml(out, arch)
    ymap_xml(out, allmin, allmax)

    nverts = sum(len(v) for m in list(ROOM_MESH.values()) + [EXT_MESH] for v, _ in m.mats.values())
    print("Generated %d drawables, %d collision boxes, %d vertices -> %s" % (
        len(arch), len(COLLISION), nverts, out))


if __name__ == "__main__":
    main()
