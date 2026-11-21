"""Material library: shader, textures, world UV tiling and collision material per surface."""

# collision material indices (GTA V materials.dat order)
COL = {
    "DEFAULT": 0, "CONCRETE": 1, "TARMAC": 4, "BRICK": 13, "MARBLE": 14, "PAVING_SLAB": 15, "GRASS": 47,
    "METAL_SOLID_SMALL": 55, "METAL_SOLID_MEDIUM": 56, "METAL_GRILLE": 64, "WOOD_SOLID_MEDIUM": 70,
    "WOOD_SOLID_POLISHED": 72, "CERAMIC": 81, "PLASTIC_HOLLOW": 87, "RUBBER": 93, "LINOLEUM": 95,
    "CARPET_SOLID": 97, "PLASTER_SOLID": 101, "GLASS_SHOOT_THROUGH": 112, "GLASS_BULLETPROOF": 113,
    "CONCRETE_PAVEMENT": 174,
}


class Mat:
    def __init__(self, name, shader, diffuse, tile=1.0, col="CONCRETE", normal=None, spec=None,
                 emissive=1.0, spec_int=0.4, spec_fall=60.0, bump=1.0, alpha=False, decal=False):
        self.name = name
        self.shader = shader
        self.diffuse = diffuse
        self.normal = normal
        self.spec = spec
        self.tile = tile
        self.col = col
        self.emissive = emissive
        self.spec_int = spec_int
        self.spec_fall = spec_fall
        self.bump = bump
        self.alpha = alpha
        self.decal = decal

    @property
    def needs_tangent(self):
        return self.shader in ("normal_spec", "glass_pv", "normal_spec_decal")


MATS = {}


def surf(name, tile, col, spec_int=0.4, spec_fall=60.0, bump=1.0):
    MATS[name] = Mat(name, "normal_spec", name, tile, col, name + "_n", name + "_s",
                     spec_int=spec_int, spec_fall=spec_fall, bump=bump)


surf("lspd_terrazzo", 2.0, "MARBLE", 0.7, 120)
surf("lspd_carpet_navy", 1.0, "CARPET_SOLID", 0.1, 10, 0.8)
surf("lspd_carpet_grey", 1.0, "CARPET_SOLID", 0.1, 10, 0.8)
surf("lspd_vinyl", 1.2, "LINOLEUM", 0.5, 80)
surf("lspd_epoxy", 3.0, "CONCRETE", 0.6, 90)
surf("lspd_tile_white", 1.2, "CERAMIC", 0.7, 120)
surf("lspd_tile_dark", 1.2, "CERAMIC", 0.6, 100)
surf("lspd_rubber", 1.0, "RUBBER", 0.1, 10)
surf("lspd_concrete", 3.0, "CONCRETE", 0.2, 30)
surf("lspd_concrete_dark", 3.0, "CONCRETE", 0.2, 30)
surf("lspd_wood_floor", 2.0, "WOOD_SOLID_POLISHED", 0.5, 70)
surf("lspd_wood_veneer", 1.2, "WOOD_SOLID_POLISHED", 0.5, 70)
surf("lspd_wood_light", 1.2, "WOOD_SOLID_POLISHED", 0.5, 70)
surf("lspd_paint_white", 2.0, "PLASTER_SOLID", 0.15, 20, 0.5)
surf("lspd_paint_grey", 2.0, "PLASTER_SOLID", 0.15, 20, 0.5)
surf("lspd_paint_navy", 2.0, "PLASTER_SOLID", 0.2, 25, 0.5)
surf("lspd_paint_blue", 2.0, "PLASTER_SOLID", 0.15, 20, 0.5)
surf("lspd_block", 1.2, "BRICK", 0.15, 20)
surf("lspd_acoustic", 1.2, "CARPET_SOLID", 0.05, 8)
surf("lspd_ceiling", 1.2, "PLASTER_SOLID", 0.05, 8)
surf("lspd_metal", 1.0, "METAL_SOLID_MEDIUM", 0.9, 150)
surf("lspd_metal_dark", 1.0, "METAL_SOLID_MEDIUM", 0.6, 90)
surf("lspd_metal_navy", 1.0, "METAL_SOLID_MEDIUM", 0.6, 90)
surf("lspd_laminate", 1.0, "WOOD_SOLID_MEDIUM", 0.4, 70)
surf("lspd_laminate_dark", 1.0, "WOOD_SOLID_MEDIUM", 0.4, 70)
surf("lspd_fabric", 0.5, "CARPET_SOLID", 0.05, 8)
surf("lspd_fabric_grey", 0.5, "CARPET_SOLID", 0.05, 8)
surf("lspd_ext_panel", 3.0, "CONCRETE", 0.2, 30)
surf("lspd_ext_metal", 1.0, "METAL_SOLID_MEDIUM", 0.6, 80)
surf("lspd_stone", 1.2, "MARBLE", 0.6, 90)
surf("lspd_roof", 4.0, "CONCRETE", 0.05, 10)
surf("lspd_asphalt", 4.0, "TARMAC", 0.1, 20)
surf("lspd_pavers", 1.2, "PAVING_SLAB", 0.1, 20)
surf("lspd_grass", 3.0, "GRASS", 0.02, 5)


def flat(name, tex, col="DEFAULT", shader="default", tile=1.0, **kw):
    MATS[name] = Mat(name, shader, tex, tile, col, **kw)


# unique decals / images: tile <= 0 means "UV supplied explicitly (0..1 over the face)"
flat("img_sign_main", "lspd_sign_main", "METAL_SOLID_MEDIUM", tile=0)
flat("img_wall_logo", "lspd_wall_logo", "PLASTER_SOLID", tile=0)
flat("img_signs", "lspd_signs", "PLASTIC_HOLLOW", tile=0)
flat("img_whiteboard", "lspd_whiteboard", "PLASTIC_HOLLOW", tile=0)
flat("img_corkboard", "lspd_corkboard", "WOOD_SOLID_MEDIUM", tile=0)
flat("img_height", "lspd_height", "PLASTER_SOLID", tile=0)
flat("img_mugshot", "lspd_mugshot", "PLASTER_SOLID", tile=0)
flat("img_helipad", "lspd_helipad", "CONCRETE", tile=0)
flat("img_parking", "lspd_parking", "TARMAC", tile=2.6)
flat("img_stripe", "lspd_stripe", "CONCRETE", tile=1.0)
flat("img_rug", "lspd_rug", "CARPET_SOLID", tile=0)
flat("img_merit", "lspd_merit", "WOOD_SOLID_MEDIUM", tile=0)
flat("img_wanted", "lspd_wanted", "PLASTER_SOLID", tile=0)
flat("img_infoboard", "lspd_infoboard", "PLASTIC_HOLLOW", tile=0)
flat("img_shelflabel", "lspd_shelflabel", "METAL_SOLID_SMALL", tile=0)
flat("img_cardboard", "lspd_cardboard", "PLASTIC_HOLLOW", tile=0)
flat("img_locker", "lspd_locker", "METAL_SOLID_MEDIUM", tile=0)
flat("img_rack", "lspd_rack", "METAL_SOLID_MEDIUM", tile=0)
flat("mat_red", "lspd_red", "CARPET_SOLID", tile=1.0)
flat("mat_black", "lspd_black", "PLASTIC_HOLLOW", tile=1.0)
flat("mat_white", "lspd_white", "PLASTIC_HOLLOW", tile=1.0)
flat("mirror", "lspd_mirror", "GLASS_BULLETPROOF", shader="spec", tile=0, spec="lspd_white",
     spec_int=1.0, spec_fall=300)
# emissive surfaces (screens, ceiling light panels)
flat("emi_light", "lspd_light", "PLASTIC_HOLLOW", shader="emissive", tile=0, emissive=2.0)
flat("emi_map", "lspd_scr_map", "GLASS_SHOOT_THROUGH", shader="emissive", tile=0, emissive=1.2)
flat("emi_cctv", "lspd_scr_cctv", "GLASS_SHOOT_THROUGH", shader="emissive", tile=0, emissive=1.2)
flat("emi_cad", "lspd_scr_cad", "GLASS_SHOOT_THROUGH", shader="emissive", tile=0, emissive=1.2)
flat("emi_desk", "lspd_scr_desk", "GLASS_SHOOT_THROUGH", shader="emissive", tile=0, emissive=1.0)
flat("emi_signs", "lspd_signs", "PLASTIC_HOLLOW", shader="emissive", tile=0, emissive=0.6)
flat("emi_sign_main", "lspd_sign_main", "METAL_SOLID_MEDIUM", shader="emissive", tile=0, emissive=0.8)
# glass
MATS["glass_ext"] = Mat("glass_ext", "glass_pv", "lspd_glass", 0, "GLASS_BULLETPROOF", alpha=True)
MATS["glass_int"] = Mat("glass_int", "glass_pv", "lspd_glass_int", 0, "GLASS_BULLETPROOF", alpha=True)


def get(name):
    return MATS[name]
