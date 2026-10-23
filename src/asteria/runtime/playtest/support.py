"""Module-level helpers of the playtest runtime: walking rows, frame sizes, the manifest."""

from __future__ import annotations

import json
from pathlib import Path

WALK_ROW_BY_FACING = {"down": 0, "left": 1, "right": 2, "up": 3}
WALK_PATTERN_SEQUENCE = (0, 1, 2, 1)
# enemy tag kinds the bestiary groups by (``weak.fire``): the word drawn for each is a built-in
# text (``bestiary.tag.<kind>``); any other kind shows as written
BESTIARY_TAG_KINDS = ("weak", "resist", "immune", "absorb", "reflect", "trait")


def walking_row_index(facing: str) -> int:
    return WALK_ROW_BY_FACING.get(facing, 0)


def walking_pattern_index(field_step: int) -> int:
    """Use MV's 0-1-2-1 walk loop; never jump directly from stride to stride."""
    return WALK_PATTERN_SEQUENCE[(max(0, int(field_step)) // 8) % len(WALK_PATTERN_SEQUENCE)]


FIELD_BODY_HEIGHT = 24.0  # world units a field character stands tall (VFX anchors)


def field_player_render_size(frame_size, render_width=64) -> tuple[int, int]:
    """Scale field sprites to ``render_width`` while preserving each source frame's ratio."""
    frame_w, frame_h = (int(frame_size[0]), int(frame_size[1]))
    if frame_w <= 0 or frame_h <= 0:
        raise ValueError("player frame dimensions must be positive")
    render_w = int(render_width)
    render_h = max(1, round(frame_h * render_w / frame_w))
    return render_w, render_h


def _load_manifest(resource_root):
    path = Path(resource_root) / "playable_test_manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != "asteria.playable_test_content" or data.get("version") != 1:
        raise ValueError("unsupported playable test manifest")
    return data
