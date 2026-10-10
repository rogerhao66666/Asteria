import pytest
from asteria.presentation.property_animation import *
from asteria.presentation.production_preview import *
from asteria.presentation.audio_runtime import AudioCue, AudioRuntime


def session():
    a = PropertyAnimator(
        (
            PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(100, 2))),
            PropertyCurve("material.glow", (PropertyKey(0, 0), PropertyKey(100, 1))),
            PropertyCurve("vfx.intensity", (PropertyKey(0, 1), PropertyKey(100, 3))),
            PropertyCurve("audio.volume", (PropertyKey(0, 1), PropertyKey(100, 0.5))),
        )
    )
    return ProductionPreviewSession(a, audio=AudioRuntime([AudioCue("hit", "sfx", 50)]))


def test_preview_uses_same_runtime_channels():
    s = session()
    f = s.sample(25)
    assert f.camera.zoom == pytest.approx(1.25)
    assert f.material.parameters["glow"] == pytest.approx(0.25)
    assert f.vfx.properties["intensity"] == pytest.approx(1.5)
    assert s.audio.properties["volume"] == pytest.approx(0.875)


def test_preview_audio_uses_same_timeline_clock():
    s = session()
    assert s.sample(49).audio == ()
    assert [c.cue.id for c in s.sample(51).audio] == ["hit"]


def test_scrub_back_then_forward_replays_cue():
    s = session()
    s.sample(60)
    s.sample(20)
    assert [c.cue.id for c in s.sample(60).audio] == ["hit"]


def test_fractional_scrub_is_smooth():
    s = session()
    assert s.sample(10.1).camera.zoom != s.sample(10.2).camera.zoom


def test_negative_preview_time_rejected():
    with pytest.raises(ValueError):
        session().sample(-0.1)


def test_unknown_custom_property_remains_in_preview_values():
    a = PropertyAnimator((PropertyCurve("plugin.custom", (PropertyKey(0, 7),)),))
    assert ProductionPreviewSession(a).sample(0).properties["plugin.custom"] == 7
