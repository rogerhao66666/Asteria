import base64
import zlib

import pytest

from asteria.multiplayer.project_snapshot import pack_scene_data, unpack_scene_data


def test_scene_snapshot_codec_roundtrip_large_authored_scene():
    scene = {
        "schema": "asteria.scene",
        "entities": [{"name": "monster", "x": i} for i in range(2000)],
    }
    packed = pack_scene_data(scene)
    assert len(packed["data"]) < 64 * 1024
    assert unpack_scene_data(packed) == scene
    assert unpack_scene_data(scene) == scene


def test_scene_snapshot_codec_rejects_inflated_or_truncated_data():
    for raw in [zlib.compress(b"x" * (1024 * 1024 + 1)), b"bad"]:
        with pytest.raises(ValueError):
            unpack_scene_data(
                {"encoding": "asteria.scene.zlib.v1", "data": base64.b64encode(raw).decode()}
            )
    with pytest.raises(ValueError):
        unpack_scene_data({"encoding": "asteria.scene.zlib.v1", "data": "!!bad"})
