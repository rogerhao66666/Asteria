import pytest

from asteria.presentation.channel_backend import PresentationChannelExecutor
from asteria.presentation.property_animation import split_channels
from asteria.presentation.vfx_runtime import Particle, VFXRuntime


def test_particle_motion_is_continuous_not_sprite_frame_bound():
    v = VFXRuntime([Particle("p", 0, 0, vx=100, vy=-50)])
    v.update(2.5)
    p = v.frame().particles[0]
    assert (p.x, p.y) == pytest.approx((0.25, -0.125))


def test_expired_particles_removed_deterministically():
    v = VFXRuntime([Particle("b", 0, 0, lifetime_ms=10), Particle("a", 0, 0, lifetime_ms=100)])
    v.update(10)
    assert [p.id for p in v.frame().particles] == ["a"]


def test_vfx_channel_drives_arbitrary_properties():
    v = VFXRuntime()
    c = split_channels({"vfx.emission_rate": 42, "vfx.custom_distortion": 0.75})
    PresentationChannelExecutor(vfx=v).execute(c)
    assert v.frame().properties == {"emission_rate": 42, "custom_distortion": 0.75}


def test_duplicate_particle_rejected():
    v = VFXRuntime([Particle("p", 0, 0)])
    with pytest.raises(ValueError):
        v.spawn(Particle("p", 1, 1))


def test_invalid_lifetime_rejected_at_spawn():
    v = VFXRuntime()
    with pytest.raises(ValueError):
        v.spawn(Particle("p", 0, 0, lifetime_ms=0))


def test_negative_update_rejected():
    with pytest.raises(ValueError):
        VFXRuntime().update(-1)


def test_clear_releases_transient_vfx_state():
    v = VFXRuntime([Particle("p", 0, 0)])
    v.apply_properties({"intensity": 2})
    v.clear()
    assert v.frame().particles == () and v.frame().properties == {}
