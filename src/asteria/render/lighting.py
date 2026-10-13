from dataclasses import dataclass

from asteria.graphics import Light2D

from .commands import LightCommand, ShadowCasterCommand


@dataclass(frozen=True, slots=True)
class ShadowCaster2D:
    caster_id: str
    points: tuple[tuple[float, float], ...]
    layer: int = 0
    depth: float = 0.0

    def validate(self):
        if not self.caster_id:
            raise ValueError("caster_id required")
        if len(self.points) < 3:
            raise ValueError("shadow caster requires polygon")


def build_light_command(light: Light2D, camera):
    light.validate()
    sx, sy = camera.world_to_screen(light.x, light.y)
    return LightCommand(
        light_id=light.light_id,
        kind=light.kind,
        screen_x=sx,
        screen_y=sy,
        radius=light.radius * camera.zoom,
        intensity=light.intensity,
        color=light.color,
        casts_shadow=light.casts_shadow,
        layer_mask=light.layer_mask,
    )


def build_shadow_command(caster: ShadowCaster2D, camera):
    caster.validate()
    pts = tuple(camera.world_to_screen(x, y) for x, y in caster.points)
    return ShadowCasterCommand(
        caster_id=caster.caster_id, polygon=pts, layer=caster.layer, depth=caster.depth
    )


def validate_material_table(materials):
    seen = set()
    for material in materials:
        material.validate()
        if material.material_id in seen:
            raise ValueError(f"duplicate material id: {material.material_id}")
        seen.add(material.material_id)
    return True
