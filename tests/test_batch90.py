import pytest
from asteria.presentation.property_animation import *
from asteria.presentation.channel_backend import *


class S:
    def __init__(self):
        self.calls = []

    def apply_properties(self, v):
        self.calls.append(dict(v))


def test_routes():
    ss = {k: S() for k in ("camera", "material", "vfx", "audio", "custom")}
    c = split_channels(
        {"camera.zoom": 1.2, "material.glow": 0.4, "vfx.intensity": 2, "audio.volume": 0.8, "project.wind": 3}
    )
    st = PresentationChannelExecutor(**ss).execute(c)
    assert ss["camera"].calls == [{"zoom": 1.2}]
    assert ss["custom"].calls == [{"project.wind": 3}]
    assert st.camera == 1 and st.custom == 1


def test_optional():
    assert PresentationChannelExecutor().execute(split_channels({"camera.zoom": 2})).camera == 0


def test_multiply_identity():
    a = PropertyAnimator(
        (PropertyCurve("camera.zoom", (PropertyKey(0, 2),)),),
        (Modulation("camera.zoom", Oscillator(0.2, 1), Envelope(1000), mode="multiply"),),
    )
    assert a.sample(0)["camera.zoom"] == pytest.approx(2)


def test_multiply_about_base():
    a = PropertyAnimator(
        (PropertyCurve("x", (PropertyKey(0, 2),)),),
        (Modulation("x", Oscillator(0.25, 1, waveform="cosine"), Envelope(1000, decay_power=0), mode="multiply"),),
    )
    assert a.sample(0)["x"] == pytest.approx(2.5)
