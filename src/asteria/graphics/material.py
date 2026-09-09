from dataclasses import dataclass

BLEND_ALPHA="alpha"
BLEND_ADD="add"
BLEND_MULTIPLY="multiply"
VALID_BLEND_MODES={BLEND_ALPHA,BLEND_ADD,BLEND_MULTIPLY}

@dataclass(frozen=True,slots=True)
class Material2D:
    material_id:str
    albedo_texture_id:str
    normal_texture_id:str|None=None
    emissive_texture_id:str|None=None
    blend_mode:str=BLEND_ALPHA
    receives_light:bool=True
    casts_shadow:bool=False

    def validate(self):
        if not self.material_id:
            raise ValueError("material_id required")
        if not self.albedo_texture_id:
            raise ValueError("albedo texture required")
        if self.blend_mode not in VALID_BLEND_MODES:
            raise ValueError("unsupported blend mode")
