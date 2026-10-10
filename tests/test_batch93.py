import pytest

from asteria.presentation.camera_runtime import CameraModulation, CameraRuntime, CameraState
from asteria.presentation.channel_backend import PresentationChannelExecutor
from asteria.presentation.property_animation import split_channels


def test_camera_channel_drives_zoom_pan_rotation():
    c = CameraRuntime()
    PresentationChannelExecutor(camera=c).execute(
        split_channels({"camera.x": 10, "camera.y": -4, "camera.zoom": 1.5, "camera.rotation_deg": 12})
    )
    s = c.sample(0)
    assert (s.x, s.y, s.zoom, s.rotation_deg) == pytest.approx((10, -4, 1.5, 12))


def test_camera_accepts_project_defined_properties():
    c = CameraRuntime()
    c.apply_properties({"lens.custom": 0.7})
    assert c.sample(0).parameters["lens.custom"] == pytest.approx(0.7)


def test_vibration_is_continuous_and_layerable():
    c = CameraRuntime()
    c.add_modulation(CameraModulation("x", 10, 10, 1000))
    c.add_modulation(CameraModulation("rotation_deg", 2, 20, 1000, 0.25))
    a, b = c.sample(12.0), c.sample(12.5)
    assert a.x != b.x and a.rotation_deg != b.rotation_deg


def test_modulation_adds_to_authored_base():
    c = CameraRuntime(CameraState(x=100))
    c.add_modulation(CameraModulation("x", 10, 0, 1000, phase=0.25, decay_power=0))
    assert c.sample(0).x == pytest.approx(110)


def test_modulation_can_target_custom_camera_parameter():
    c = CameraRuntime()
    c.add_modulation(CameraModulation("project_lens", 4, 0, 100, 0.25, 0))
    assert c.sample(0).parameters["project_lens"] == pytest.approx(4)


def test_modulation_ends_without_changing_base():
    c = CameraRuntime(CameraState(zoom=2))
    c.add_modulation(CameraModulation("zoom", 0.5, 1, 10))
    assert c.sample(10).zoom == pytest.approx(2)


def test_prune_releases_finished_modulations():
    c = CameraRuntime()
    c.add_modulation(CameraModulation("x", 1, 1, 10))
    c.prune(10)
    assert c._mods == []


def test_invalid_modulation_rejected():
    c = CameraRuntime()
    with pytest.raises(ValueError):
        c.add_modulation(CameraModulation("x", 1, -1, 10))
