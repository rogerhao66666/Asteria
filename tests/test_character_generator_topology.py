import json

import pytest
from PIL import Image

from asteria.assets.character_generator import DIRECTIONS
from asteria.assets.character_generator_topology import (
    CharacterAnimationTopology,
    CharacterPartManifest,
    validate_part_manifest,
    write_authoring_template,
)


def manifest(tmp_path, topology_id="rpg_like_48_walk_v1"):
    frames = {}
    for d in DIRECTIONS:
        frames[d] = []
        for i in range(3):
            p = tmp_path / f"body_{d}_{i}.png"
            Image.new("RGBA", (48, 48), (0, 0, 0, 0)).save(p)
            im = Image.open(p)
            im.putpixel((24, 30), (220, 170, 140, 255))
            im.save(p)
            frames[d].append(p.name)
    return CharacterPartManifest("starter_body_01", "body", topology_id, frames)


def test_topology_accepts_interchangeable_part_contract(tmp_path):
    m = manifest(tmp_path)
    validate_part_manifest(m, CharacterAnimationTopology(), tmp_path)
    assert "topology:rpg_like_48_walk_v1" in m.to_part().tags


def test_topology_rejects_mismatched_authoring_template(tmp_path):
    with pytest.raises(ValueError):
        validate_part_manifest(manifest(tmp_path, "wrong"), CharacterAnimationTopology(), tmp_path)


def test_authoring_template_is_explicit_and_not_runtime_type(tmp_path):
    p = write_authoring_template(tmp_path)
    d = json.loads(p.read_text())
    assert d["frame_size"] == [48, 48]
    assert d["contract"]["parts_are_interchangeable"] is True
    assert d["contract"]["no_runtime_generator_type"] is True
