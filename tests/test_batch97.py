import pytest, json
from asteria.presentation.production_state import *


def sample():
    return ProductionState(
        123.5,
        CameraState(1, 2, 1.4, 3, 4, 5, {"lens": 0.7}),
        MaterialState("mat", "shader", {"glow": 0.8}),
        (LightState("key", "project_area", 3, 4, 2, 100, 12, {"temp": 6500}),),
        (AudioCue("hit", "sfx", 88.25, "fx", 0.7, 1.1, False, {"filter": 0.2}),),
        {"intensity": 2},
        {"volume": 0.9},
        {"project": "demo"},
    )


def test_round_trip_preserves_production_state():
    s = sample()
    r = ProductionStateCodec.loads(ProductionStateCodec.dumps(s))
    assert r == s


def test_stable_asset_refs_survive_roundtrip():
    r = ProductionStateCodec.loads(ProductionStateCodec.dumps(sample()))
    assert r.material.material_asset_id == "mat" and r.material.shader_asset_id == "shader"
    assert r.audio_cues[0].asset_id == "sfx"


def test_float_timing_and_custom_parameters_survive():
    r = ProductionStateCodec.loads(ProductionStateCodec.dumps(sample()))
    assert r.playhead_ms == 123.5 and r.audio_cues[0].start_ms == 88.25
    assert r.camera.parameters["lens"] == 0.7 and r.lights[0].parameters["temp"] == 6500


def test_schema_version_is_explicit_and_rejects_unknown():
    raw = ProductionStateCodec.encode(sample())
    assert raw["schema_version"] == 1
    raw["schema_version"] = 99
    with pytest.raises(ValueError):
        ProductionStateCodec.decode(raw)


def test_deterministic_serialization():
    s = sample()
    assert ProductionStateCodec.dumps(s) == ProductionStateCodec.dumps(s)


def test_duplicate_ids_rejected():
    with pytest.raises(ValueError):
        ProductionState(lights=(LightState("x"), LightState("x")))
    with pytest.raises(ValueError):
        ProductionState(audio_cues=(AudioCue("x", "a", 0), AudioCue("x", "b", 1)))


def test_negative_playhead_rejected():
    with pytest.raises(ValueError):
        ProductionState(playhead_ms=-1)
