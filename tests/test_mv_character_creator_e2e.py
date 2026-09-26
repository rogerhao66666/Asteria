import json
from pathlib import Path

import pytest
from PIL import Image

from scripts.validate_mv_character_creator import run_validation


@pytest.mark.filterwarnings("error::DeprecationWarning")
def test_real_mv_character_creator_editor_and_runtime_are_bounded(tmp_path):
    output = tmp_path / "captures"

    result = run_validation(output, max_frames=3, show_windows=False)

    assert result["frames_rendered"] == 3
    assert result["actor_registered"] is True
    assert result["map_id"] > 0
    assert result["standard_character"]["standing_y"] == result["standard_character"]["rect_bottom"]
    assert result["large_character"]["standing_y"] == result["large_character"]["rect_bottom"]
    assert result["large_character"]["frame_size"][1] > 48
    assert result["editor_platform"] == "cocoa"
    for name in ("editor-walking.png", "editor-face.png", "editor-side-view.png", "runtime-map.png"):
        path = output / name
        assert path.is_file()
        with Image.open(path) as image:
            assert image.width > 0 and image.height > 0
    saved = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert saved == result
