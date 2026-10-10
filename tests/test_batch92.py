import pytest
from asteria.presentation.material_runtime import *
from asteria.presentation.property_animation import split_channels
from asteria.presentation.channel_backend import PresentationChannelExecutor


def test_material_channel_preserves_arbitrary_shader_parameters():
    m = MaterialRuntime(MaterialState("mat", "shader", {"base": 1}))
    PresentationChannelExecutor(material=m).execute(
        split_channels({"material.glow": 0.8, "material.distortion.phase": 0.25})
    )
    s = m.snapshot()
    assert s.parameters == {"base": 1, "glow": 0.8, "distortion.phase": 0.25}


def test_lighting_registry_is_generic_and_deterministic():
    l = LightingRuntime([LightState("b", "project_area"), LightState("a", "point")])
    assert [x.id for x in l.snapshot()] == ["a", "b"]


def test_light_properties_and_custom_parameters_update():
    l = LightingRuntime([LightState("key", intensity=1)])
    l.apply("key", {"intensity": 2.5, "temperature": 6500})
    s = l.snapshot()[0]
    assert s.intensity == 2.5 and s.parameters["temperature"] == 6500


def test_duplicate_light_rejected():
    l = LightingRuntime([LightState("x")])
    with pytest.raises(ValueError):
        l.add(LightState("x"))


class B:
    def __init__(self):
        self.calls = []

    def resolve_material(self, a):
        self.calls.append(("rm", a))
        return "M:" + str(a)

    def resolve_shader(self, a):
        self.calls.append(("rs", a))
        return "S:" + str(a)

    def bind_material(self, m, s, p):
        self.calls.append(("bind", m, s, p))


def test_backend_receives_stable_refs_and_uniforms():
    b = B()
    e = MaterialBackendExecutor(b)
    state = MaterialState("mat", "shader", {"u_time": 1.25, "project_param": 7})
    e.execute(state)
    assert ("bind", "M:mat", "S:shader", {"u_time": 1.25, "project_param": 7}) in b.calls


def test_backend_resource_cache_and_hot_reload_invalidation():
    b = B()
    e = MaterialBackendExecutor(b)
    s = MaterialState("mat", "shader", {})
    e.execute(s)
    e.execute(s)
    assert b.calls.count(("rm", "mat")) == 1 and b.calls.count(("rs", "shader")) == 1
    e.invalidate("shader")
    e.execute(s)
    assert b.calls.count(("rs", "shader")) == 2 and b.calls.count(("rm", "mat")) == 1


def test_lighting_clear_releases_scene_state():
    l = LightingRuntime([LightState("a"), LightState("b")])
    l.clear()
    assert l.snapshot() == ()
