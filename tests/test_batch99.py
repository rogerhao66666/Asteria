import pytest

from asteria.presentation.art_e2e import (
    ArtPresentationRuntime,
    LightingRuntime,
    PresentationBackendExecutor,
    VFXRuntime,
    apply_light_channels,
    vfx_draw_packets,
)
from asteria.presentation.audio_runtime import AudioCue, AudioRuntime
from asteria.presentation.e2e_pipeline import PresentationE2EPipeline
from asteria.presentation.material_runtime import LightState
from asteria.presentation.production_preview import ProductionPreviewSession
from asteria.presentation.property_animation import PropertyAnimator, PropertyCurve, PropertyKey
from asteria.presentation.vfx_runtime import Particle


class B:
    def __init__(self):
        self.draw = []

    def begin_frame(self, i):
        pass

    def resolve_visual(self, a):
        return "R:" + a

    def draw_visual(self, r, p):
        self.draw.append((r, p.component_id))

    def resolve_font(self, a):
        return "F:" + str(a)

    def draw_text(self, f, p):
        pass

    def end_frame(self):
        pass


def animator():
    return PropertyAnimator(
        (
            PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(100, 2))),
            PropertyCurve("material.glow", (PropertyKey(0, 0), PropertyKey(100, 1))),
            PropertyCurve("vfx.intensity", (PropertyKey(0, 1), PropertyKey(100, 2))),
            PropertyCurve("audio.volume", (PropertyKey(0, 1), PropertyKey(100, 0.5))),
            PropertyCurve("light.key.intensity", (PropertyKey(0, 1), PropertyKey(100, 3))),
        )
    )


def test_light_custom_channel_routes_generically():
    l = LightingRuntime((LightState("key"),))
    apply_light_channels(l, {"light.key.intensity": 2.5, "light.key.project_param": 7})
    s = l.snapshot()[0]
    assert s.intensity == 2.5 and s.parameters["project_param"] == 7


def test_vfx_particles_submit_as_normal_draw_packets():
    v = VFXRuntime((Particle("spark", 3, 4, scale=2, asset_id="fx.spark"),))
    p = vfx_draw_packets(v, 9)[0]
    assert (
        p.asset_id == "fx.spark"
        and p.component_id == "spark"
        and p.transform.x == 3
        and p.transform.scale_x == 2
        and p.z == 9
    )


def test_full_art_frame_routes_channels_vfx_audio_renderer():
    a = animator()
    v = VFXRuntime((Particle("spark", 1, 2, asset_id="fx.spark"),))
    audio = AudioRuntime((AudioCue("hit", "audio.hit", 50.25),))
    preview = ProductionPreviewSession(a, vfx=v, audio=audio)
    light = LightingRuntime((LightState("key"),))
    backend = B()
    rt = ArtPresentationRuntime(PresentationE2EPipeline((), a), preview, light, PresentationBackendExecutor(backend))
    f = rt.render(1, 60)
    assert f.material.parameters["glow"] == pytest.approx(0.6)
    assert f.lights[0].intensity == pytest.approx(2.2)
    assert [x.cue.id for x in f.audio] == ["hit"]
    assert ("R:fx.spark", "spark") in backend.draw
    assert f.backend_stats.visual_packets == 1


def test_subframe_art_sampling_not_sprite_fps_bound():
    a = animator()
    rt = ArtPresentationRuntime(
        PresentationE2EPipeline((), a),
        ProductionPreviewSession(a),
        LightingRuntime((LightState("key"),)),
        PresentationBackendExecutor(B()),
    )
    assert rt.render(1, 10.1).material.parameters["glow"] != rt.render(2, 10.2).material.parameters["glow"]


def test_no_gameplay_semantics_required_for_custom_light_kind():
    l = LightingRuntime((LightState("custom", "project_volumetric"),))
    apply_light_channels(l, {"light.custom.fog_density": 0.4})
    assert l.snapshot()[0].kind == "project_volumetric" and l.snapshot()[0].parameters["fog_density"] == 0.4
