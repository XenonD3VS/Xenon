"""Full build: textures -> XML -> binary RAGE resources -> FiveM resource folder.

Usage:
    python3 build.py --out ../../xenon_police --cwconv <path to cwconv.dll> [--origin X Y Z]
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import building as B
import cwxml as X
import furnish as F
import layout as LY
import textures as T

NAME = "xenon_police"
TXD = "xenon_police_txd"
DEFAULT_ORIGIN = (0.0, 0.0, 0.0)   # overwritten by config.json


def world_box(bmin, bmax, o):
    return (bmin[0] + o[0], bmin[1] + o[1], bmin[2] + o[2]), (bmax[0] + o[0], bmax[1] + o[1], bmax[2] + o[2])


def merge_box(a, b):
    if a is None:
        return b
    return (tuple(min(a[0][i], b[0][i]) for i in range(3)), tuple(max(a[1][i], b[1][i]) for i in range(3)))


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout, r.stderr)
        raise SystemExit(f"command failed: {' '.join(cmd)}")
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", default=None)
    ap.add_argument("--cwconv", required=True)
    ap.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.json"))
    ap.add_argument("--objectlist", default=None, help="optional ObjectList.ini to validate prop names")
    ap.add_argument("--keep-xml", default=None, help="copy generated XML sources here")
    args = ap.parse_args()

    cfg = json.load(open(args.config))
    O = tuple(cfg["origin"])
    work = args.work or os.path.join(os.path.dirname(os.path.abspath(args.out)), "_build")
    xml_dir = os.path.join(work, "xml")
    tex_dir = os.path.join(xml_dir, TXD)
    os.makedirs(xml_dir, exist_ok=True)

    errs = LY.validate()
    if errs:
        raise SystemExit("layout errors:\n" + "\n".join(errs))

    # ---------------------------------------------------------------- textures
    print("[1/6] textures")
    tex_info = T.build_all(tex_dir)
    open(os.path.join(xml_dir, TXD + ".ytd.xml"), "w").write(X.ytd_xml(tex_info))

    # ---------------------------------------------------------------- geometry
    print("[2/6] geometry")
    sh = B.build_all()
    F.furnish_all(sh)
    used_tex = set()
    import materials as M
    for mesh in list(sh.int.values()) + [sh.ext, sh.site, sh.lod]:
        for m in mesh.parts:
            mm = M.get(m)
            for t in (mm.diffuse, mm.normal, mm.spec):
                if t:
                    used_tex.add(t)
    used_tex |= {"lspd_flat_n", "lspd_spec_lo"}
    missing = used_tex - set(tex_info)
    if missing:
        raise SystemExit(f"missing textures: {missing}")

    drawables = {}
    for room, mesh in sh.int.items():
        drawables[f"{NAME}_{room}"] = (mesh, 150.0)
    drawables[f"{NAME}_ext"] = (sh.ext, 350.0)
    drawables[f"{NAME}_site"] = (sh.site, 350.0)
    drawables[f"{NAME}_ext_lod"] = (sh.lod, 2000.0)
    for name, (mesh, lod) in drawables.items():
        open(os.path.join(xml_dir, name + ".ydr.xml"), "w").write(X.ydr_xml(name, mesh))

    print("[3/6] collision")
    open(os.path.join(xml_dir, f"{NAME}_int_col.ybn.xml"), "w").write(X.ybn_xml(sh.col_int, O))
    open(os.path.join(xml_dir, f"{NAME}_ext_col.ybn.xml"), "w").write(X.ybn_xml(sh.col_ext, O))

    # ---------------------------------------------------------------- ytyp
    print("[4/6] ytyp / ymap")
    arch = []
    bounds = {}
    for name, (mesh, lod) in drawables.items():
        bmin, bmax = mesh.bounds()
        bounds[name] = (bmin, bmax)
        flags = 0
        arch.append(X.base_archetype_xml(name, bmin, bmax, lod, TXD, flags=flags))

    # MLO entities: shells first, then doors and props
    ents = []
    room_objs = {n: [] for n in B.MLO_ROOMS}
    for room in sh.int:
        ents.append(dict(name=f"{NAME}_{room}", pos=(0, 0, 0), rot=(0, 0, 0, 1), lod=150.0))
        room_objs[room].append(len(ents) - 1)
    for d in sh.doors:
        ents.append(dict(name=d["model"], pos=d["pos"], rot=X.yaw_quat_stored(d["heading"]), lod=60.0, flags=1572864))
        room_objs[d["room"].mlo_room].append(len(ents) - 1)
    for p in sh.props_int:
        ents.append(dict(name=p["model"], pos=p["pos"], rot=X.yaw_quat_stored(p["heading"]), lod=p.get("lod", 50.0),
                         flags=1572896))
        room_objs[p["mlo_room"]].append(len(ents) - 1)

    rooms_xml = []
    for i, rn in enumerate(B.MLO_ROOMS):
        if i == 0:
            bmin, bmax = (0, 0, 0), (0, 0, 0)
        else:
            bmin, bmax = bounds[f"{NAME}_{rn}"]
            bmin = (bmin[0] - 0.5, bmin[1] - 0.5, bmin[2] - 0.5)
            bmax = (bmax[0] + 0.5, bmax[1] + 0.5, bmax[2] + 0.5)
        pc = sum(1 for p in sh.portals if p["frm"] == i or p["to"] == i)
        tc = "" if i == 0 else ("int_hanger_small" if rn == "garage" else "policestation")
        rooms_xml.append(dict(name=rn, bbMin=bmin, bbMax=bmax, portalCount=pc, objects=room_objs[rn], tc=tc,
                              floor=0))
    portals_xml = [dict({"from": p["frm"], "to": p["to"], "corners": p["corners"]}) for p in sh.portals]
    mlo_box = None
    for rn in B.MLO_ROOMS[1:]:
        mlo_box = merge_box(mlo_box, bounds[f"{NAME}_{rn}"])
    arch.append(X.mlo_archetype_xml(f"{NAME}_int", mlo_box[0], mlo_box[1], 300.0, ents, rooms_xml, portals_xml))
    open(os.path.join(xml_dir, NAME + ".ytyp.xml"), "w").write(X.ytyp_xml(NAME, arch))

    # ---------------------------------------------------------------- ymaps
    lod_box = world_box(*bounds[f"{NAME}_ext_lod"], O)
    lod_ent = X.entity_xml("  ", f"{NAME}_ext_lod", O, (0, 0, 0, 1), 2000.0, flags=1572864, parent=-1,
                           lod_level="LODTYPES_DEPTH_LOD", num_children=1, child_lod=350.0, guid=4100000001)
    smin = tuple(lod_box[0][i] - 2000 for i in range(3))
    smax = tuple(lod_box[1][i] + 2000 for i in range(3))
    open(os.path.join(xml_dir, NAME + "_lod.ymap.xml"), "w").write(
        X.ymap_xml(NAME + "_lod", None, 3, 2, smin, smax, lod_box[0], lod_box[1], lod_ent))

    ents_xml = []
    ebox = None
    ents_xml.append(X.entity_xml("  ", f"{NAME}_ext", O, (0, 0, 0, 1), 350.0, flags=1572872, parent=0,
                                 lod_level="LODTYPES_DEPTH_HD", guid=4100000002))
    ebox = merge_box(ebox, world_box(*bounds[f"{NAME}_ext"], O))
    ents_xml.append(X.entity_xml("  ", f"{NAME}_site", O, (0, 0, 0, 1), 350.0, flags=1572864, parent=-1,
                                 lod_level="LODTYPES_DEPTH_ORPHANHD", guid=4100000003))
    ebox = merge_box(ebox, world_box(*bounds[f"{NAME}_site"], O))
    n_exit = sum(1 for p in sh.portals if p["to"] == 0)
    mlo_extra = ('   <groupId value="0" />\n   <floorId value="0" />\n   <defaultEntitySets />\n'
                 f'   <numExitPortals value="{n_exit}" />\n   <MLOInstflags value="0" />\n')
    ents_xml.append(X.entity_xml("  ", f"{NAME}_int", O, (0, 0, 0, 1), 300.0, flags=1572864, parent=-1,
                                 lod_level="LODTYPES_DEPTH_ORPHANHD", typ="CMloInstanceDef", extra=mlo_extra,
                                 guid=4100000004))
    ebox = merge_box(ebox, world_box(*mlo_box, O))
    for k, p in enumerate(sh.props_ext):
        pos = (p["pos"][0] + O[0], p["pos"][1] + O[1], p["pos"][2] + O[2])
        ents_xml.append(X.entity_xml("  ", p["model"], pos, X.yaw_quat_stored(p["heading"]), p.get("lod", 100),
                                     flags=1572896, guid=4100001000 + k))
    smin = tuple(ebox[0][i] - 350 for i in range(3))
    smax = tuple(ebox[1][i] + 350 for i in range(3))
    open(os.path.join(xml_dir, NAME + ".ymap.xml"), "w").write(
        X.ymap_xml(NAME, NAME + "_lod", 1, 9, smin, smax, ebox[0], ebox[1], "".join(ents_xml)))

    # ---------------------------------------------------------------- props check
    all_models = sorted({d["model"] for d in sh.doors} | {p["model"] for p in sh.props_int} | {p["model"] for p in sh.props_ext})
    if args.objectlist:
        known = {l.strip().lower() for l in open(args.objectlist, errors="ignore")}
        bad = [m for m in all_models if m.lower() not in known]
        if bad:
            raise SystemExit(f"unknown base-game models: {bad}")
        print(f"   all {len(all_models)} base-game models verified against ObjectList")

    # ---------------------------------------------------------------- compile
    print("[5/6] compiling with CodeWalker.Core")
    out = os.path.abspath(args.out)
    stream = os.path.join(out, "stream")
    if os.path.isdir(stream):
        shutil.rmtree(stream)
    os.makedirs(stream)
    jobs = [(TXD + ".ytd.xml", TXD + ".ytd", tex_dir)]
    for name in drawables:
        jobs.append((name + ".ydr.xml", name + ".ydr", None))
    jobs += [(f"{NAME}_int_col.ybn.xml", f"{NAME}_int_col.ybn", None), (f"{NAME}_ext_col.ybn.xml", f"{NAME}_ext_col.ybn", None),
             (NAME + ".ytyp.xml", NAME + ".ytyp", None), (NAME + ".ymap.xml", NAME + ".ymap", None),
             (NAME + "_lod.ymap.xml", NAME + "_lod.ymap", None)]
    for src, dst, texf in jobs:
        cmd = ["dotnet", args.cwconv, "build", os.path.join(xml_dir, src), os.path.join(stream, dst)]
        if texf:
            cmd.append(texf)
        print("  ", run(cmd).strip())

    print("[6/6] verifying binaries (re-load + export with CodeWalker)")
    vdir = os.path.join(work, "verify")
    for _, dst, _ in jobs:
        print("  ", run(["dotnet", args.cwconv, "dump", os.path.join(stream, dst), vdir]).strip())

    # keep the optional map blip in sync with the placement
    blip = os.path.join(out, "client", "blip.lua")
    if os.path.isfile(blip):
        import re
        ent = (O[0] + 28.0, O[1] - 3.0, O[2])
        txt = open(blip).read()
        txt = re.sub(r"local ENTRANCE = vector3\([^)]*\)",
                     f"local ENTRANCE = vector3({ent[0]:.2f}, {ent[1]:.2f}, {ent[2]:.2f})", txt)
        open(blip, "w").write(txt)

    if args.keep_xml:
        if os.path.isdir(args.keep_xml):
            shutil.rmtree(args.keep_xml)
        shutil.copytree(xml_dir, args.keep_xml, ignore=shutil.ignore_patterns("*.dds"))

    # summary json for docs
    summary = dict(origin=O, models=all_models, rooms=len(LY.ROOMS), doors=len(sh.doors), props_int=len(sh.props_int),
                   props_ext=len(sh.props_ext), portals=len(sh.portals),
                   tris={k: v[0].tri_count() for k, v in drawables.items()},
                   lights={k: len(v[0].lights) for k, v in drawables.items()},
                   col_tris=dict(interior=len(sh.col_int.tris), exterior=len(sh.col_ext.tris)),
                   doors_list=[dict(model=d["model"], kind=d["kind"], level=LY.LEVEL_NAMES[d["level"]],
                                    pos=[round(d["pos"][0] + O[0], 3), round(d["pos"][1] + O[1], 3), round(d["pos"][2] + O[2], 3)],
                                    heading=d["heading"], room=d["room"].title) for d in sh.doors])
    json.dump(summary, open(os.path.join(work, "summary.json"), "w"), indent=1)
    print("done ->", out)


if __name__ == "__main__":
    main()
