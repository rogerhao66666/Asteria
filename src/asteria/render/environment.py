from dataclasses import dataclass

from asteria.graphics import AmbientLight2D, Fog2D, ParticleEmitter2D


@dataclass(frozen=True, slots=True)
class EnvironmentCommand:
    ambient: AmbientLight2D
    fog: Fog2D | None
    particle_emitters: tuple[ParticleEmitter2D, ...]
    post_effects: tuple


def build_environment_command(*, ambient=None, fog=None, particle_emitters=(), post_stack=None):
    ambient = ambient or AmbientLight2D()
    ambient.validate()
    if fog is not None:
        fog.validate()
    emitters = tuple(particle_emitters)
    for emitter in emitters:
        emitter.validate()
    effects = () if post_stack is None else post_stack.enabled_effects()
    return EnvironmentCommand(ambient, fog, emitters, effects)
