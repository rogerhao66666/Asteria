"""Scene environment, lights and shadow casters (VFX-02 / VFX-03) as canonical scene components.

* ``Environment2D`` (one per scene, usually on a "Scene Settings" entity): ambient light,
  fog, weather, bloom, colour grading, vignette and a screen shader (built-in id or a
  project ``shader`` asset).
* ``LightSource2D`` (any entity): a point light at the entity, with height for normal maps.
* ``ShadowCaster2D`` (any entity): a box that blocks shadow-casting lights.

``resolve_environment`` turns them (plus the manifest's ``render.environment`` defaults)
into one backend-neutral ``SceneEnvironment`` built from the existing graphics models
(``AmbientLight2D``, ``Fog2D``, ``Light2D``, ``PostEffect2D``). Renderers draw it; nothing
here touches pixels or game rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asteria.core import Component, Field, Transform, component_schema, world_position
from asteria.core.metadata import get_component_schema
from asteria.graphics import AmbientLight2D, Fog2D, Light2D
from asteria.render.lighting import ShadowCaster2D
from asteria.render.postprocess import PostEffect2D

BUILTIN_SCREEN_SHADERS = ("", "grayscale", "sepia", "invert", "wave", "crt", "pixelate")
WEATHER_KINDS = ("none", "rain", "snow", "leaves", "dust")


@component_schema(
    type_name="asteria.Environment2D",
    version=1,
    fields=(
        Field(
            "lighting_enabled",
            bool,
            False,
            label="Lighting",
            tooltip="Darken the world to the ambient light.",
        ),
        Field("ambient_r", float, 1.0, minimum=0.0, maximum=4.0, label="Ambient R"),
        Field("ambient_g", float, 1.0, minimum=0.0, maximum=4.0, label="Ambient G"),
        Field("ambient_b", float, 1.0, minimum=0.0, maximum=4.0, label="Ambient B"),
        Field(
            "ambient_intensity", float, 0.35, minimum=0.0, maximum=4.0, label="Ambient Intensity"
        ),
        Field("fog_density", float, 0.0, minimum=0.0, maximum=1.0, label="Fog Density"),
        Field("fog_r", float, 0.7, minimum=0.0, maximum=1.0, label="Fog R"),
        Field("fog_g", float, 0.75, minimum=0.0, maximum=1.0, label="Fog G"),
        Field("fog_b", float, 0.8, minimum=0.0, maximum=1.0, label="Fog B"),
        Field(
            "fog_drift",
            float,
            12.0,
            minimum=0.0,
            label="Fog Drift",
            tooltip="Pixels per second the fog moves.",
        ),
        Field("weather", str, "none", choices=WEATHER_KINDS, label="Weather"),
        Field(
            "weather_intensity", float, 0.5, minimum=0.0, maximum=1.0, label="Weather Intensity"
        ),
        Field("weather_wind", float, 0.0, minimum=-400.0, maximum=400.0, label="Wind"),
        Field("weather_max_particles", int, 400, minimum=0, maximum=5000, label="Max Particles"),
        Field("bloom_enabled", bool, False, label="Bloom"),
        Field("bloom_threshold", float, 0.75, minimum=0.0, maximum=1.0, label="Bloom Threshold"),
        Field("bloom_intensity", float, 0.8, minimum=0.0, maximum=4.0, label="Bloom Intensity"),
        Field("exposure", float, 1.0, minimum=0.0, maximum=4.0, label="Exposure"),
        Field("contrast", float, 1.0, minimum=0.0, maximum=3.0, label="Contrast"),
        Field("saturation", float, 1.0, minimum=0.0, maximum=3.0, label="Saturation"),
        Field("tint_r", float, 1.0, minimum=0.0, maximum=2.0, label="Tint R"),
        Field("tint_g", float, 1.0, minimum=0.0, maximum=2.0, label="Tint G"),
        Field("tint_b", float, 1.0, minimum=0.0, maximum=2.0, label="Tint B"),
        Field("vignette", float, 0.0, minimum=0.0, maximum=1.0, label="Vignette"),
        Field("screen_shader", str, "", choices=BUILTIN_SCREEN_SHADERS, label="Screen Shader"),
        Field(
            "screen_shader_asset_id",
            str,
            "",
            label="Project Shader",
            tooltip="A 'shader' asset (GLSL fragment).",
        ),
        Field(
            "screen_shader_strength", float, 1.0, minimum=0.0, maximum=1.0, label="Shader Strength"
        ),
        Field("enabled", bool, True),
    ),
)
class Environment2DComponent(Component):
    def __init__(self):
        super().__init__()
        for f in get_component_schema(type(self)).fields.values():
            setattr(self, f.name, f.default)


@component_schema(
    type_name="asteria.LightSource2D",
    version=1,
    fields=(
        Field("radius", float, 160.0, minimum=1.0, label="Radius"),
        Field("intensity", float, 1.0, minimum=0.0, maximum=8.0, label="Intensity"),
        Field("color_r", float, 1.0, minimum=0.0, maximum=1.0, label="Color R"),
        Field("color_g", float, 0.9, minimum=0.0, maximum=1.0, label="Color G"),
        Field("color_b", float, 0.7, minimum=0.0, maximum=1.0, label="Color B"),
        Field(
            "height",
            float,
            48.0,
            minimum=0.0,
            label="Height",
            tooltip="Height above the ground (normal maps).",
        ),
        Field("offset_x", float, 0.0),
        Field("offset_y", float, 0.0),
        Field("casts_shadow", bool, False, label="Casts Shadows"),
        Field("flicker", float, 0.0, minimum=0.0, maximum=1.0, label="Flicker"),
        Field("enabled", bool, True),
    ),
)
class LightSource2DComponent(Component):
    def __init__(self):
        super().__init__()
        for f in get_component_schema(type(self)).fields.values():
            setattr(self, f.name, f.default)


@component_schema(
    type_name="asteria.ShadowCaster2D",
    version=1,
    fields=(
        Field("width", float, 32.0, minimum=0.0),
        Field("height", float, 16.0, minimum=0.0),
        Field("offset_x", float, 0.0),
        Field("offset_y", float, -8.0),
        Field("enabled", bool, True),
    ),
)
class ShadowCaster2DComponent(Component):
    def __init__(self):
        super().__init__()
        for f in get_component_schema(type(self)).fields.values():
            setattr(self, f.name, f.default)


@component_schema(
    type_name="asteria.WaterRegion2D",
    version=1,
    fields=(
        Field("width", float, 96.0, minimum=1.0),
        Field("height", float, 64.0, minimum=1.0),
        Field("offset_x", float, 0.0),
        Field("offset_y", float, 0.0),
        Field(
            "amplitude",
            float,
            2.0,
            minimum=0.0,
            maximum=32.0,
            tooltip="Ripple size in world units.",
        ),
        Field(
            "wavelength", float, 24.0, minimum=1.0, tooltip="World units between ripple crests."
        ),
        Field("speed", float, 2.0, minimum=0.0, maximum=20.0),
        Field("tint_r", float, 0.35, minimum=0.0, maximum=1.0),
        Field("tint_g", float, 0.55, minimum=0.0, maximum=1.0),
        Field("tint_b", float, 0.85, minimum=0.0, maximum=1.0),
        Field("tint_strength", float, 0.25, minimum=0.0, maximum=1.0),
        Field("enabled", bool, True),
    ),
)
class WaterRegion2DComponent(Component):
    """A rectangle of water: ripples (UV distortion on the GPU, row shifts on pygame) and a tint.
    Visual only."""

    def __init__(self):
        super().__init__()
        for f in get_component_schema(type(self)).fields.values():
            setattr(self, f.name, f.default)


@component_schema(
    type_name="asteria.MotionTrail2D",
    version=1,
    fields=(
        Field("kind", str, "afterimage", choices=("afterimage", "trail")),
        Field("interval", float, 0.06, minimum=0.005, maximum=1.0),
        Field("count", int, 4, minimum=1, maximum=32),
        Field("fade", float, 0.55, minimum=0.05, maximum=0.99),
        Field("lifetime", float, 0.35, minimum=0.02, maximum=3.0),
        Field("only_while_moving", bool, True),
        Field("enabled", bool, True),
    ),
)
class MotionTrail2DComponent(Component):
    """Afterimages / a trail behind this entity's sprite while it moves (VFX-03). Visual only."""

    def __init__(self):
        super().__init__()
        for f in get_component_schema(type(self)).fields.values():
            setattr(self, f.name, f.default)


@dataclass
class SceneEnvironment:
    """Everything a renderer needs this frame, in screen pixels (lights and casters already
    projected)."""

    lighting: bool = False
    ambient: AmbientLight2D = field(default_factory=lambda: AmbientLight2D((1.0, 1.0, 1.0), 1.0))
    lights: list = field(default_factory=list)  # (Light2D in screen space, height_px)
    casters: list = field(default_factory=list)  # ShadowCaster2D with screen-space points
    fog: Fog2D | None = None
    fog_drift: float = 0.0
    weather: str = "none"
    weather_intensity: float = 0.0
    weather_wind: float = 0.0
    weather_max_particles: int = 0
    post: list = field(default_factory=list)  # PostEffect2D, in order
    shader_source: str | None = None  # project shader GLSL (resolved from the asset registry)
    shader_id: str = ""
    # (x0, y0, x1, y1, amplitude_px, wavelength_px, speed, (r, g, b), tint_strength) in screen
    # pixels
    water: list = field(default_factory=list)

    @property
    def active(self):
        return bool(self.lighting or self.fog or self.post or self.weather != "none" or self.water)

    def post_effect(self, effect_id):
        return next((e for e in self.post if e.effect_id == effect_id and e.enabled), None)


def _settings(scene, defaults):
    component = None
    if scene is not None:
        for _, c in scene.query(Environment2DComponent):
            if c.enabled:
                component = c
                break
    fields = get_component_schema(Environment2DComponent).fields.values()
    values = {f.name: f.default for f in fields}
    values.update({k: v for k, v in dict(defaults or {}).items() if k in values})
    if component is not None:
        values.update({f.name: getattr(component, f.name) for f in fields})
    return values


def resolve_environment(scene, *, defaults=None, to_screen=None, scale=1.0, read_shader=None):
    """The scene's environment for this frame.

    ``to_screen(x, y)`` projects world positions (lights, casters) to screen pixels and
    ``scale`` converts world lengths (radius, sizes) to pixels; ``read_shader(asset_id)``
    returns a project shader's GLSL source (or None).
    """
    v = _settings(scene, defaults)
    env = SceneEnvironment()
    if not v["enabled"]:
        return env
    env.lighting = bool(v["lighting_enabled"])
    env.ambient = AmbientLight2D(
        (v["ambient_r"], v["ambient_g"], v["ambient_b"]), v["ambient_intensity"]
    )
    if v["fog_density"] > 0:
        env.fog = Fog2D(v["fog_density"], (v["fog_r"], v["fog_g"], v["fog_b"]))
        env.fog_drift = float(v["fog_drift"])
    env.weather = v["weather"] if v["weather"] in WEATHER_KINDS else "none"
    env.weather_intensity = float(v["weather_intensity"])
    env.weather_wind = float(v["weather_wind"])
    env.weather_max_particles = int(v["weather_max_particles"])
    if v["bloom_enabled"]:
        env.post.append(
            PostEffect2D(
                "bloom",
                True,
                (("threshold", v["bloom_threshold"]), ("intensity", v["bloom_intensity"])),
            )
        )
    grade = {k: v[k] for k in ("exposure", "contrast", "saturation", "tint_r", "tint_g", "tint_b")}
    if any(abs(value - 1.0) > 1e-6 for value in grade.values()):
        env.post.append(PostEffect2D("grade", True, tuple(sorted(grade.items()))))
    if v["vignette"] > 0:
        env.post.append(PostEffect2D("vignette", True, (("amount", v["vignette"]),)))
    if v["screen_shader_asset_id"] and read_shader is not None:
        env.shader_source = read_shader(v["screen_shader_asset_id"])
        if env.shader_source:
            env.shader_id = f"asset:{v['screen_shader_asset_id']}"
    elif v["screen_shader"]:
        env.shader_id = v["screen_shader"]
    if env.shader_id:
        env.post.append(
            PostEffect2D("screen_shader", True, (("strength", v["screen_shader_strength"]),))
        )
    for effect in env.post:
        effect.validate()
    if scene is not None and to_screen is not None:
        for entity, water, _ in scene.query(WaterRegion2DComponent, Transform):
            if water.enabled:
                wx, wy = world_position(entity)
                x0, y0 = to_screen(
                    wx + water.offset_x - water.width / 2, wy + water.offset_y - water.height / 2
                )
                x1, y1 = to_screen(
                    wx + water.offset_x + water.width / 2, wy + water.offset_y + water.height / 2
                )
                env.water.append(
                    (
                        x0,
                        y0,
                        x1,
                        y1,
                        water.amplitude * scale,
                        water.wavelength * scale,
                        water.speed,
                        (water.tint_r, water.tint_g, water.tint_b),
                        water.tint_strength,
                    )
                )
        env.water = env.water[:8]  # the GPU pass takes up to 8 regions per frame
    if scene is not None and to_screen is not None and env.lighting:
        # lights and casters each keep scene order in their own list
        for entity, light, _ in scene.query(LightSource2DComponent, Transform):
            if light.enabled:
                wx, wy = world_position(entity)
                sx, sy = to_screen(wx + light.offset_x, wy + light.offset_y)
                env.lights.append(
                    (
                        Light2D(
                            entity.id,
                            x=sx,
                            y=sy,
                            radius=light.radius * scale,
                            intensity=light.intensity,
                            color=(light.color_r, light.color_g, light.color_b),
                            casts_shadow=light.casts_shadow,
                        ),
                        light.height * scale,
                        light.flicker,
                    )
                )
        for entity, caster, _ in scene.query(ShadowCaster2DComponent, Transform):
            if caster.enabled and caster.width > 0 and caster.height > 0:
                wx, wy = world_position(entity)
                cx, cy = wx + caster.offset_x, wy + caster.offset_y
                hw, hh = caster.width / 2, caster.height / 2
                corners = [
                    to_screen(cx + dx, cy + dy)
                    for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))
                ]
                env.casters.append(ShadowCaster2D(entity.id, tuple(corners)))
    return env


@component_schema(
    type_name="asteria.ParticleEmitter2D",
    version=1,
    fields=(
        Field(
            "effect_id",
            str,
            "",
            label="Particle Effect",
            tooltip="A particle_effect asset (VFX tool > Particle Effects).",
        ),
        Field(
            "playing",
            bool,
            True,
            label="Playing",
            tooltip="Off: stop emitting (live particles finish).",
        ),
        Field("offset_x", float, 0.0, label="Offset X"),
        Field("offset_y", float, 0.0, label="Offset Y"),
        Field(
            "scale",
            float,
            1.0,
            minimum=0.01,
            label="Scale",
            tooltip="Multiplies sizes, speeds and the shape.",
        ),
        Field("enabled", bool, True),
    ),
)
class ParticleEmitter2DComponent(Component):
    """A particle effect (VFX-01) emitting at this entity, following it."""

    def __init__(self):
        super().__init__()
        for f in get_component_schema(type(self)).fields.values():
            setattr(self, f.name, f.default)


def register_environment_components(registry):
    for component in (
        Environment2DComponent,
        LightSource2DComponent,
        ShadowCaster2DComponent,
        WaterRegion2DComponent,
        MotionTrail2DComponent,
        ParticleEmitter2DComponent,
    ):
        registry.register(component)
