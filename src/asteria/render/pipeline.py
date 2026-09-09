from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameRenderPlan:
    opaque_draws: tuple = ()
    shadow_casters: tuple = ()
    lights: tuple = ()
    translucent_draws: tuple = ()
    particle_emitters: tuple = ()
    ambient: object | None = None
    fog: object | None = None
    post_effects: tuple = ()


def build_frame_plan(*, draws=(), shadow_casters=(), lights=(), environment=None):
    key = lambda d: (d.layer, d.depth, d.screen_y)
    opaque = tuple(sorted((d for d in draws if d.opacity >= 1.0), key=key))
    trans = tuple(sorted((d for d in draws if d.opacity < 1.0), key=key))
    if environment is None:
        return FrameRenderPlan(opaque, tuple(shadow_casters), tuple(lights), trans)
    return FrameRenderPlan(
        opaque,
        tuple(sorted(shadow_casters, key=lambda s: (s.layer, s.depth))),
        tuple(lights),
        trans,
        environment.particle_emitters,
        environment.ambient,
        environment.fog,
        environment.post_effects,
    )
