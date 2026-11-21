"""Writers for CodeWalker XML formats (ydr / ybn / ytd / ytyp / ymap).

The XML is compiled to binary RAGE resources by tools/cwconv (CodeWalker.Core).
"""
import math
from xml.sax.saxutils import escape

import materials as M

# Parameter lists copied from Sollumz/szio Shaders.xml (order matters).
SHADER_PARAMS = {
    "default": [("DiffuseSampler", "T"), ("matMaterialColorScale", (1, 0, 0, 1)), ("HardAlphaBlend", (1, 0, 0, 0)),
                ("useTessellation", (0, 0, 0, 0)), ("wetnessMultiplier", (1, 0, 0, 0)),
                ("globalAnimUV1", (0, 1, 0, 0)), ("globalAnimUV0", (1, 0, 0, 0))],
    "normal_spec": [("DiffuseSampler", "T"), ("BumpSampler", "N"), ("SpecSampler", "S"),
                    ("HardAlphaBlend", (1, 0, 0, 0)), ("useTessellation", (0, 0, 0, 0)),
                    ("wetnessMultiplier", (1, 0, 0, 0)), ("bumpiness", "bump"), ("specMapIntMask", (1, 0, 0, 0)),
                    ("specularIntensityMult", "sint"), ("specularFalloffMult", "sfall"),
                    ("specularFresnel", (0.75, 0, 0, 0))],
    "spec": [("DiffuseSampler", "T"), ("SpecSampler", "S"), ("HardAlphaBlend", (1, 0, 0, 0)),
             ("useTessellation", (0, 0, 0, 0)), ("wetnessMultiplier", (1, 0, 0, 0)), ("specMapIntMask", (1, 0, 0, 0)),
             ("specularIntensityMult", "sint"), ("specularFalloffMult", "sfall"), ("specularFresnel", (0.97, 0, 0, 0)),
             ("globalAnimUV1", (0, 1, 0, 0)), ("globalAnimUV0", (1, 0, 0, 0))],
    "emissive": [("DiffuseSampler", "T"), ("matMaterialColorScale", (1, 0, 0, 1)), ("HardAlphaBlend", (1, 0, 0, 0)),
                 ("useTessellation", (0, 0, 0, 0)), ("emissiveMultiplier", "emi"),
                 ("globalAnimUV1", (0, 1, 0, 0)), ("globalAnimUV0", (1, 0, 0, 0))],
    "glass_pv": [("DiffuseSampler", "T"), ("DecalTint", (1, 1, 1, 1)), ("CrackDecalBumpAlphaThreshold", (0, 0, 0, 0)),
                 ("CrackDecalBumpAmount", (0, 0, 0, 0)), ("CrackEdgeBumpAmount", (0, 0, 0, 0)),
                 ("CrackDecalBumpTileScale", (1, 1, 0, 0)), ("CrackEdgeBumpTileScale", (1, 1, 0, 0)),
                 ("BrokenSpecularColor", (0.46, 0.611765, 0.611765, 1)),
                 ("BrokenDiffuseColor", (0.46, 0.611765, 0.611765, 0.568627)), ("useTessellation", (0, 0, 0, 0)),
                 ("specularIntensityMult", (1, 0, 0, 0)), ("specularFalloffMult", (512, 0, 0, 0)),
                 ("specularFresnel", (0.97, 0, 0, 0))],
}
SHADER_FILE = {"default": ("default.sps", 0), "normal_spec": ("normal_spec.sps", 0), "spec": ("spec.sps", 0),
               "emissive": ("emissive.sps", 0), "glass_pv": ("glass_pv.sps", 1)}
LAYOUT = {
    "default": ["Position", "Normal", "Colour0", "TexCoord0"],
    "spec": ["Position", "Normal", "Colour0", "TexCoord0"],
    "emissive": ["Position", "Normal", "Colour0", "TexCoord0"],
    "normal_spec": ["Position", "Normal", "Colour0", "TexCoord0", "Tangent"],
    "glass_pv": ["Position", "Normal", "Colour0", "TexCoord0", "Tangent"],
}
MAX_VERTS = 32000


def f(v):
    s = f"{v:.5f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def v3(tag, p, ind):
    return f'{ind}<{tag} x="{f(p[0])}" y="{f(p[1])}" z="{f(p[2])}" />\n'


# ------------------------------------------------------------------ YTD
def ytd_xml(tex_info):
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n<TextureDictionary>\n']
    for name, (w, h, fmt, mips) in sorted(tex_info.items()):
        out.append(f""" <Item>
  <Name>{name}</Name>
  <Unk32 value="0" />
  <Usage>DEFAULT</Usage>
  <UsageFlags>0</UsageFlags>
  <ExtraFlags value="0" />
  <Width value="{w}" />
  <Height value="{h}" />
  <MipLevels value="{mips}" />
  <Format>D3DFMT_{fmt}</Format>
  <FileName>{name}.dds</FileName>
 </Item>
""")
    out.append("</TextureDictionary>\n")
    return "".join(out)


# ------------------------------------------------------------------ YDR
def shader_xml(mat):
    m = M.get(mat)
    fn, bucket = SHADER_FILE[m.shader]
    lines = [f"   <Item>\n    <Name>{m.shader}</Name>\n    <FileName>{fn}</FileName>\n    <RenderBucket value=\"{bucket}\" />\n    <Parameters>\n"]
    for pname, val in SHADER_PARAMS[m.shader]:
        if isinstance(val, str) and val in ("T", "N", "S"):
            tex = {"T": m.diffuse, "N": m.normal, "S": m.spec}[val]
            if tex is None:
                tex = {"N": "lspd_flat_n", "S": "lspd_spec_lo"}.get(val, m.diffuse)
            lines.append(f'     <Item name="{pname}" type="Texture">\n      <Name>{tex}</Name>\n      <Unk32 value="0" />\n     </Item>\n')
            continue
        if isinstance(val, str):
            x = {"bump": m.bump, "sint": m.spec_int, "sfall": m.spec_fall, "emi": m.emissive}[val]
            val = (x, 0, 0, 0)
        lines.append(f'     <Item name="{pname}" type="Vector" x="{f(val[0])}" y="{f(val[1])}" z="{f(val[2])}" w="{f(val[3])}" />\n')
    lines.append("    </Parameters>\n   </Item>\n")
    return "".join(lines)


def light_xml(l):
    c = l["colour"]
    p = l["pos"]
    d = l["direction"]
    e = l["extent"]
    return f"""   <Item>
    <Position x="{f(p[0])}" y="{f(p[1])}" z="{f(p[2])}" />
    <Colour r="{c[0]}" g="{c[1]}" b="{c[2]}" />
    <Flashiness value="0" />
    <Intensity value="{f(l['intensity'])}" />
    <Flags value="0" />
    <BoneId value="0" />
    <Type>{l['kind']}</Type>
    <GroupId value="0" />
    <TimeFlags value="16777215" />
    <Falloff value="{f(l['falloff'])}" />
    <FalloffExponent value="{f(l['exponent'])}" />
    <CullingPlaneNormal x="0" y="0" z="-1" />
    <CullingPlaneOffset value="0" />
    <Unknown45 value="0" />
    <Unknown46 value="0" />
    <VolumeIntensity value="1" />
    <VolumeSizeScale value="1" />
    <VolumeOuterColour r="255" g="255" b="255" />
    <LightHash value="0" />
    <VolumeOuterIntensity value="1" />
    <CoronaSize value="{f(l['corona'])}" />
    <VolumeOuterExponent value="1" />
    <LightFadeDistance value="0" />
    <ShadowFadeDistance value="0" />
    <SpecularFadeDistance value="0" />
    <VolumetricFadeDistance value="0" />
    <ShadowNearClip value="0.01" />
    <CoronaIntensity value="1" />
    <CoronaZBias value="0.1" />
    <Direction x="{f(d[0])}" y="{f(d[1])}" z="{f(d[2])}" />
    <Tangent x="1" y="0" z="0" />
    <ConeInnerAngle value="{f(l['cone_in'])}" />
    <ConeOuterAngle value="{f(l['cone_out'])}" />
    <Extent x="{f(e[0])}" y="{f(e[1])}" z="{f(e[2])}" />
    <ProjectedTextureHash />
   </Item>
"""


def ydr_xml(name, mesh, lod_dist=9998):
    mats = [m for m in mesh.parts if mesh.parts[m][1]]
    bmin, bmax = mesh.bounds()
    c = tuple((bmin[i] + bmax[i]) / 2 for i in range(3))
    r = math.sqrt(sum((bmax[i] - c[i]) ** 2 for i in range(3)))
    out = [f"""<?xml version="1.0" encoding="UTF-8"?>
<Drawable>
 <Name>{name}</Name>
""", v3("BoundingSphereCenter", c, " "), f' <BoundingSphereRadius value="{f(r)}" />\n',
           v3("BoundingBoxMin", bmin, " "), v3("BoundingBoxMax", bmax, " "),
           f""" <LodDistHigh value="{lod_dist}" />
 <LodDistMed value="{lod_dist}" />
 <LodDistLow value="{lod_dist}" />
 <LodDistVlow value="{lod_dist}" />
 <FlagsHigh value="1" />
 <FlagsMed value="0" />
 <FlagsLow value="0" />
 <FlagsVlow value="0" />
 <ShaderGroup>
  <Unknown30 value="8" />
  <Shaders>
"""]
    for m in mats:
        out.append(shader_xml(m))
    out.append("  </Shaders>\n </ShaderGroup>\n <DrawableModelsHigh>\n  <Item>\n   <RenderMask value=\"255\" />\n   <Flags value=\"0\" />\n   <HasSkin value=\"0\" />\n   <BoneIndex value=\"0\" />\n   <Unknown1 value=\"0\" />\n   <Geometries>\n")
    for si, m in enumerate(mats):
        verts, idx = mesh.parts[m]
        shader = M.get(m).shader
        layout = LAYOUT[shader]
        # split into chunks of whole triangles
        tris = [idx[i:i + 3] for i in range(0, len(idx), 3)]
        chunk = []
        remap = {}

        def flush(chunk, remap):
            if not chunk:
                return
            vlist = [None] * len(remap)
            for old, new in remap.items():
                vlist[new] = verts[old]
            mn = [min(v[k] for v in vlist) for k in range(3)]
            mx = [max(v[k] for v in vlist) for k in range(3)]
            out.append(f"    <Item>\n     <ShaderIndex value=\"{si}\" />\n")
            out.append(v3("BoundingBoxMin", mn, "     "))
            out.append(v3("BoundingBoxMax", mx, "     "))
            out.append("     <VertexBuffer>\n      <Flags value=\"0\" />\n      <Layout type=\"GTAV1\">\n")
            for s in layout:
                out.append(f"       <{s} />\n")
            out.append("      </Layout>\n      <Data>\n")
            for v in vlist:
                col = v[12]
                s = f"       {f(v[0])} {f(v[1])} {f(v[2])}   {f(v[3])} {f(v[4])} {f(v[5])}   {col[0]} {col[1]} {col[2]} {col[3]}   {f(v[6])} {f(v[7])}"
                if "Tangent" in layout:
                    s += f"   {f(v[8])} {f(v[9])} {f(v[10])} {f(v[11])}"
                out.append(s + "\n")
            out.append("      </Data>\n     </VertexBuffer>\n     <IndexBuffer>\n      <Data>\n")
            flat = [remap[i] for t in chunk for i in t]
            for i in range(0, len(flat), 24):
                out.append("       " + " ".join(str(x) for x in flat[i:i + 24]) + "\n")
            out.append("      </Data>\n     </IndexBuffer>\n    </Item>\n")

        for t in tris:
            if len(remap) + 3 > MAX_VERTS:
                flush(chunk, remap)
                chunk, remap = [], {}
            for i in t:
                if i not in remap:
                    remap[i] = len(remap)
            chunk.append(t)
        flush(chunk, remap)
    out.append("   </Geometries>\n  </Item>\n </DrawableModelsHigh>\n")
    if mesh.lights:
        out.append(" <Lights>\n")
        for l in mesh.lights:
            out.append(light_xml(l))
        out.append(" </Lights>\n")
    out.append("</Drawable>\n")
    return "".join(out)


# ------------------------------------------------------------------ YBN
FLAGS1 = "MAP_WEAPON, MAP_DYNAMIC, MAP_ANIMAL, MAP_COVER, MAP_VEHICLE"
FLAGS2 = ("VEHICLE_NOT_BVH, VEHICLE_BVH, PED, RAGDOLL, ANIMAL, ANIMAL_RAGDOLL, OBJECT, PLANT, PROJECTILE, "
          "EXPLOSION, FORKLIFT_FORKS, TEST_WEAPON, TEST_CAMERA, TEST_AI, TEST_SCRIPT, TEST_VEHICLE_WHEEL, GLASS")


def _bounds_base(ind, mn, mx, composite_child=False):
    c = tuple((mn[i] + mx[i]) / 2 for i in range(3))
    r = math.sqrt(sum((mx[i] - c[i]) ** 2 for i in range(3)))
    s = (v3("BoxMin", mn, ind) + v3("BoxMax", mx, ind) + v3("BoxCenter", c, ind) + v3("SphereCenter", c, ind)
         + f'{ind}<SphereRadius value="{f(r)}" />\n{ind}<Margin value="0.04" />\n{ind}<Volume value="1" />\n'
         + f'{ind}<Inertia x="1" y="1" z="1" />\n{ind}<MaterialIndex value="0" />\n{ind}<MaterialColourIndex value="0" />\n'
         + f'{ind}<ProceduralID value="0" />\n{ind}<RoomID value="0" />\n{ind}<PedDensity value="0" />\n'
         + f'{ind}<UnkFlags value="0" />\n{ind}<PolyFlags value="0" />\n{ind}<UnkType value="0" />\n')
    if composite_child:
        s += (f"{ind}<CompositeTransform>\n{ind} 1 0 0 0\n{ind} 0 1 0 0\n{ind} 0 0 1 0\n{ind} 0 0 0 1\n{ind}</CompositeTransform>\n"
              f"{ind}<CompositeFlags1>{FLAGS1}</CompositeFlags1>\n{ind}<CompositeFlags2>{FLAGS2}</CompositeFlags2>\n")
    return s, c


def ybn_xml(col, offset=(0, 0, 0), max_tris=20000):
    """col: mesh.Collision in local coords; offset added (world placement)."""
    ox, oy, oz = offset
    # spatially chunk triangles into children (sorted by centroid x)
    tris = [((a[0] + ox, a[1] + oy, a[2] + oz), (b[0] + ox, b[1] + oy, b[2] + oz), (c[0] + ox, c[1] + oy, c[2] + oz), k)
            for a, b, c, k in col.tris]
    tris.sort(key=lambda t: ((t[0][2] + t[1][2] + t[2][2]) // 4.2, (t[0][0] + t[1][0] + t[2][0])))
    chunks = [tris[i:i + max_tris] for i in range(0, len(tris), max_tris)]
    allmn = [min(min(p[k] for p in t[:3]) for t in tris) for k in range(3)]
    allmx = [max(max(p[k] for p in t[:3]) for t in tris) for k in range(3)]
    base, _ = _bounds_base("  ", allmn, allmx)
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n<BoundsFile>\n <Bounds type="Composite">\n', base, "  <Children>\n"]
    for ch in chunks:
        mn = [min(min(p[k] for p in t[:3]) for t in ch) for k in range(3)]
        mx = [max(max(p[k] for p in t[:3]) for t in ch) for k in range(3)]
        b, c = _bounds_base("    ", mn, mx, True)
        out.append('   <Item type="GeometryBVH">\n')
        out.append(b)
        out.append(v3("GeometryCenter", c, "    "))
        out.append('    <UnkFloat1 value="0" />\n    <UnkFloat2 value="0" />\n')
        keys = sorted({t[3] for t in ch})
        kidx = {k: i for i, k in enumerate(keys)}
        out.append("    <Materials>\n")
        for (mt, room, flags) in keys:
            out.append(f"""     <Item>
      <Type value="{mt}" />
      <ProceduralID value="0" />
      <RoomID value="{room}" />
      <PedDensity value="0" />
      <Flags>{flags}</Flags>
      <MaterialColourIndex value="0" />
      <Unk value="0" />
     </Item>
""")
        out.append("    </Materials>\n")
        vidx = {}
        vl = []
        polys = []
        for a, b2, c2, k in ch:
            ids = []
            for p in (a, b2, c2):
                q = (round(p[0], 3), round(p[1], 3), round(p[2], 3))
                if q not in vidx:
                    vidx[q] = len(vl)
                    vl.append(q)
                ids.append(vidx[q])
            if len(set(ids)) < 3:
                continue
            polys.append((kidx[k], ids))
        if len(vl) > 32000:
            raise RuntimeError("too many collision vertices in chunk")
        out.append("    <Vertices>\n")
        for q in vl:
            out.append(f"     {f(q[0] - c[0])}, {f(q[1] - c[1])}, {f(q[2] - c[2])}\n")
        out.append("    </Vertices>\n    <Polygons>\n")
        for mi, ids in polys:
            out.append(f'     <Triangle m="{mi}" v1="{ids[0]}" v2="{ids[1]}" v3="{ids[2]}" f1="0" f2="0" f3="0" />\n')
        out.append("    </Polygons>\n   </Item>\n")
    out.append("  </Children>\n </Bounds>\n</BoundsFile>\n")
    return "".join(out)


# ------------------------------------------------------------------ YTYP / YMAP
def entity_xml(ind, name, pos, rot_q, lod_dist, flags=1572864, parent=-1, lod_level="LODTYPES_DEPTH_ORPHANHD",
               num_children=0, child_lod=0, typ="CEntityDef", extra="", guid=0):
    return (f'{ind}<Item type="{typ}">\n'
            f"{ind} <archetypeName>{name}</archetypeName>\n"
            f'{ind} <flags value="{flags}" />\n'
            f'{ind} <guid value="{guid}" />\n'
            f'{ind} <position x="{f(pos[0])}" y="{f(pos[1])}" z="{f(pos[2])}" />\n'
            f'{ind} <rotation x="{f(rot_q[0])}" y="{f(rot_q[1])}" z="{f(rot_q[2])}" w="{f(rot_q[3])}" />\n'
            f'{ind} <scaleXY value="1" />\n{ind} <scaleZ value="1" />\n'
            f'{ind} <parentIndex value="{parent}" />\n'
            f'{ind} <lodDist value="{f(lod_dist)}" />\n'
            f'{ind} <childLodDist value="{f(child_lod)}" />\n'
            f"{ind} <lodLevel>{lod_level}</lodLevel>\n"
            f'{ind} <numChildren value="{num_children}" />\n'
            f"{ind} <priorityLevel>PRI_REQUIRED</priorityLevel>\n"
            f"{ind} <extensions />\n"
            f'{ind} <ambientOcclusionMultiplier value="255" />\n'
            f'{ind} <artificialAmbientOcclusion value="255" />\n'
            f'{ind} <tintValue value="0" />\n'
            f"{extra}"
            f"{ind}</Item>\n")


def yaw_quat_stored(deg):
    """Quaternion for a heading (deg, CCW around Z) in the *stored* (inverted) form used by CEntityDef."""
    a = math.radians(deg) / 2.0
    return (0.0, 0.0, -math.sin(a), math.cos(a))


def base_archetype_xml(name, bmin, bmax, lod_dist, txd, flags=0, special=0):
    c = tuple((bmin[i] + bmax[i]) / 2 for i in range(3))
    r = math.sqrt(sum((bmax[i] - c[i]) ** 2 for i in range(3)))
    return (f'  <Item type="CBaseArchetypeDef">\n'
            f'   <lodDist value="{f(lod_dist)}" />\n   <flags value="{flags}" />\n   <specialAttribute value="{special}" />\n'
            + v3("bbMin", bmin, "   ") + v3("bbMax", bmax, "   ") + v3("bsCentre", c, "   ")
            + f'   <bsRadius value="{f(r)}" />\n   <hdTextureDist value="{f(min(lod_dist, 100))}" />\n'
            f"   <name>{name}</name>\n   <textureDictionary>{txd}</textureDictionary>\n   <clipDictionary />\n"
            f"   <drawableDictionary />\n   <physicsDictionary />\n   <assetType>ASSET_TYPE_DRAWABLE</assetType>\n"
            f"   <assetName>{name}</assetName>\n   <extensions />\n  </Item>\n")


def mlo_archetype_xml(name, bmin, bmax, lod_dist, entities, rooms, portals):
    c = tuple((bmin[i] + bmax[i]) / 2 for i in range(3))
    r = math.sqrt(sum((bmax[i] - c[i]) ** 2 for i in range(3)))
    out = [f'  <Item type="CMloArchetypeDef">\n   <lodDist value="{f(lod_dist)}" />\n   <flags value="0" />\n'
           f'   <specialAttribute value="0" />\n', v3("bbMin", bmin, "   "), v3("bbMax", bmax, "   "),
           v3("bsCentre", c, "   "), f'   <bsRadius value="{f(r)}" />\n   <hdTextureDist value="100" />\n',
           f"   <name>{name}</name>\n   <textureDictionary />\n   <clipDictionary />\n   <drawableDictionary />\n"
           f"   <physicsDictionary />\n   <assetType>ASSET_TYPE_UNINITIALIZED</assetType>\n   <assetName>{name}</assetName>\n"
           f'   <extensions />\n   <mloFlags value="0" />\n   <entities>\n']
    for e in entities:
        out.append(entity_xml("    ", e["name"], e["pos"], e["rot"], e["lod"], flags=e.get("flags", 1572864)))
    out.append("   </entities>\n   <rooms>\n")
    for rm in rooms:
        out.append("    <Item>\n")
        out.append(f"     <name>{rm['name']}</name>\n")
        out.append(v3("bbMin", rm["bbMin"], "     "))
        out.append(v3("bbMax", rm["bbMax"], "     "))
        out.append(f'     <blend value="1" />\n     <timecycleName>{rm.get("tc", "")}</timecycleName>\n'
                   f"     <secondaryTimecycleName />\n     <flags value=\"{rm.get('flags', 0)}\" />\n"
                   f'     <portalCount value="{rm["portalCount"]}" />\n     <floorId value="{rm.get("floor", 0)}" />\n'
                   f'     <exteriorVisibiltyDepth value="-1" />\n')
        objs = rm["objects"]
        if objs:
            out.append("     <attachedObjects>\n")
            for i in range(0, len(objs), 16):
                out.append("      " + " ".join(str(x) for x in objs[i:i + 16]) + "\n")
            out.append("     </attachedObjects>\n")
        else:
            out.append("     <attachedObjects />\n")
        out.append("    </Item>\n")
    out.append("   </rooms>\n   <portals>\n")
    for p in portals:
        out.append(f'    <Item>\n     <roomFrom value="{p["from"]}" />\n     <roomTo value="{p["to"]}" />\n'
                   f'     <flags value="{p.get("flags", 0)}" />\n     <mirrorPriority value="0" />\n'
                   f'     <opacity value="0" />\n     <audioOcclusion value="0" />\n     <corners>\n')
        for cpt in p["corners"]:
            out.append(f'      <Item x="{f(cpt[0])}" y="{f(cpt[1])}" z="{f(cpt[2])}" />\n')
        out.append("     </corners>\n")
        if p.get("objects"):
            out.append("     <attachedObjects>" + " ".join(str(x) for x in p["objects"]) + "</attachedObjects>\n")
        else:
            out.append("     <attachedObjects />\n")
        out.append("    </Item>\n")
    out.append('   </portals>\n   <entitySets />\n   <timeCycleModifiers />\n  </Item>\n')
    return "".join(out)


def ytyp_xml(name, archetype_xml_list):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<CMapTypes>\n <extensions />\n <archetypes>\n'
            + "".join(archetype_xml_list)
            + f" </archetypes>\n <name>{name}</name>\n <dependencies />\n <compositeEntityTypes />\n</CMapTypes>\n")


YMAP_TAIL = """ <containerLods itemType="rage__fwContainerLodDef" />
 <boxOccluders itemType="BoxOccluder" />
 <occludeModels itemType="OccludeModel" />
 <physicsDictionaries />
 <instancedData>
  <ImapLink />
  <PropInstanceList itemType="rage__fwPropInstanceListDef" />
  <GrassInstanceList itemType="rage__fwGrassInstanceListDef" />
 </instancedData>
 <timeCycleModifiers itemType="CTimeCycleModifier" />
 <carGenerators itemType="CCarGen" />
 <LODLightsSOA>
  <direction itemType="FloatXYZ" />
  <falloff />
  <falloffExponent />
  <timeAndStateFlags />
  <hash />
  <coneInnerAngle />
  <coneOuterAngleOrCapExt />
  <coronaIntensity />
 </LODLightsSOA>
 <DistantLODLightsSOA>
  <position itemType="FloatXYZ" />
  <RGBI />
  <numStreetLights value="0" />
  <category value="0" />
 </DistantLODLightsSOA>
 <block>
  <version value="0" />
  <flags value="0" />
  <name>{name}</name>
  <exportedBy>XenonD3VS</exportedBy>
  <owner>XenonD3VS</owner>
  <time></time>
 </block>
</CMapData>
"""


def ymap_xml(name, parent, flags, content_flags, smin, smax, emin, emax, entities_xml):
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<CMapData>\n <name>{name}</name>\n'
            + (f" <parent>{parent}</parent>\n" if parent else " <parent />\n")
            + f' <flags value="{flags}" />\n <contentFlags value="{content_flags}" />\n'
            + v3("streamingExtentsMin", smin, " ") + v3("streamingExtentsMax", smax, " ")
            + v3("entitiesExtentsMin", emin, " ") + v3("entitiesExtentsMax", emax, " ")
            + " <entities>\n" + entities_xml + " </entities>\n" + YMAP_TAIL.replace("{name}", name))
