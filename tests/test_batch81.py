import pytest

from asteria.presentation.property_animation import (
    Ease,
    Envelope,
    Modulation,
    Oscillator,
    PropertyAnimator,
    PropertyCurve,
    PropertyKey,
    split_channels,
)


def test_linear_curve():
    c = PropertyCurve("camera.zoom", (PropertyKey(0, 1), PropertyKey(100, 2)))
    assert c.sample(50) == pytest.approx(1.5)


def test_ease_in():
    c = PropertyCurve("x", (PropertyKey(0, 0, Ease.EASE_IN), PropertyKey(100, 1)))
    assert c.sample(50) == pytest.approx(0.25)


def test_ease_out():
    c = PropertyCurve("x", (PropertyKey(0, 0, Ease.EASE_OUT), PropertyKey(100, 1)))
    assert c.sample(50) == pytest.approx(0.75)


def test_ease_in_out_midpoint():
    c = PropertyCurve("x", (PropertyKey(0, 0, Ease.EASE_IN_OUT), PropertyKey(100, 1)))
    assert c.sample(50) == pytest.approx(0.5)


def test_step_holds_source():
    c = PropertyCurve("x", (PropertyKey(0, 2, Ease.STEP), PropertyKey(100, 9)))
    assert c.sample(99) == 2 and c.sample(100) == 9


def test_curve_clamps_ends():
    c = PropertyCurve("x", (PropertyKey(10, 2), PropertyKey(20, 4)))
    assert c.sample(0) == 2 and c.sample(999) == 4


def test_oscillator_continuous_between_sprite_frames():
    o = Oscillator(4, 10)
    assert o.sample(12.5) != o.sample(13.5)


def test_envelope_attack_and_decay():
    e = Envelope(100, 20, 1)
    assert e.sample(10) == pytest.approx(0.5)
    assert 0 < e.sample(60) < 1
    assert e.sample(100) == 0


def test_vibration_as_generic_modulation():
    a = PropertyAnimator(
        curves=(PropertyCurve("camera.x", (PropertyKey(0, 0), PropertyKey(200, 0))),),
        modulations=(Modulation("camera.x", Oscillator(5, 20), Envelope(100)),),
    )
    assert a.sample(12.5)["camera.x"] != 0


def test_layer_curve_plus_modulation():
    a = PropertyAnimator(
        curves=(PropertyCurve("actor.scale", (PropertyKey(0, 1), PropertyKey(100, 2))),),
        modulations=(Modulation("actor.scale", Oscillator(0.1, 5), Envelope(100)),),
    )
    assert a.sample(25)["actor.scale"] != pytest.approx(1.25)


def test_split_builtin_and_custom_channels():
    c = split_channels({"camera.zoom": 1.2, "material.glow": 0.8, "vfx.rate": 2, "audio.volume": 0.5, "project.foo": 7})
    assert c.camera["zoom"] == 1.2 and c.material["glow"] == 0.8
    assert c.vfx["rate"] == 2 and c.audio["volume"] == 0.5 and c.custom["project.foo"] == 7


def test_arbitrary_property_path_supported():
    a = PropertyAnimator((PropertyCurve("my_game.boss.aura.intensity", (PropertyKey(0, 0), PropertyKey(100, 1))),))
    assert a.sample(50)["my_game.boss.aura.intensity"] == pytest.approx(0.5)


def test_invalid_curves():
    with pytest.raises(ValueError):
        PropertyCurve("", (PropertyKey(0, 0),))
    with pytest.raises(ValueError):
        PropertyCurve("x", ())
    with pytest.raises(ValueError):
        PropertyCurve("x", (PropertyKey(1, 0), PropertyKey(1, 1)))
    with pytest.raises(ValueError):
        PropertyKey(-1, 0)


def test_invalid_procedural_settings():
    with pytest.raises(ValueError):
        Oscillator(1, -1)
    with pytest.raises(ValueError):
        Oscillator(1, 1, waveform="noise")
    with pytest.raises(ValueError):
        Envelope(0)
    with pytest.raises(ValueError):
        Modulation("", Oscillator(1, 1), Envelope(1))
    with pytest.raises(ValueError):
        Modulation("x", Oscillator(1, 1), Envelope(1), mode="bad")


def test_negative_runtime_time_rejected():
    with pytest.raises(ValueError):
        PropertyAnimator().sample(-1)
