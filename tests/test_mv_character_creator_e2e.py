import json
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

from asteria.assets.local_reference import resolve_rpg_maker_mv_root
from scripts.validate_mv_character_creator import run_validation

REPO = Path(__file__).resolve().parents[1]


def _expected_qt_platform():
    """Return the Qt platform this run should report, or None when unknown."""
    requested = os.environ.get("QT_QPA_PLATFORM")
    if requested:
        return requested
    return "cocoa" if sys.platform == "darwin" else None


@pytest.mark.skipif(resolve_rpg_maker_mv_root(REPO) is None, reason="local RPG Maker MV reference unavailable")
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
    expected_platform = _expected_qt_platform()
    if expected_platform is not None:
        assert result["editor_platform"] == expected_platform
    assert result["families_checked"] == ["Male", "Female", "Kid"]
    assert result["hair_variation_changed_side_view"] is True
    assert result["project_reloaded"] is True
    assert result["weapon_frames_rendered"] == 6
    assert result["weapon_swapped_visual"] is True
    for family in ("female", "kid"):
        for name, size in (
            ("walking", (144, 192)),
            ("face", (144, 144)),
            ("damaged", (144, 48)),
            ("side_view", (576, 384)),
        ):
            with Image.open(output / "generated" / f"validated-{family}" / f"{name}.png") as image:
                assert image.size == size
    for name in (
        "editor-walking.png",
        "editor-face.png",
        "editor-damaged.png",
        "editor-side-view.png",
        "editor-female-side-view.png",
        "editor-kid-side-view.png",
        "runtime-map.png",
        "runtime-battle-weapons.png",
    ):
        path = output / name
        assert path.is_file()
        with Image.open(path) as image:
            assert image.width > 0 and image.height > 0
    saved = json.loads((output / "results.json").read_text(encoding="utf-8"))
    assert saved == result
