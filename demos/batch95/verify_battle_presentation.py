"""Headless Batch 95 battle-presentation reference verification."""

import json
from pathlib import Path

from asteria.gameplay import ActionCue, PresentationCue
from asteria.presentation import (
    BattlePresentationCoordinator,
    BattlePresentationRuntime,
    BattlePresentationScene,
)
from asteria.reference_data import load_animation_set, load_sprite_sheet
from asteria.runtime import Camera2D

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "reference_data"

scene = BattlePresentationScene.from_data(
    json.loads((DATA / "batch95_battle_presentation_scene.json").read_text())
)
hero_sheet = load_sprite_sheet(DATA / "hero_sheet.json")
mimic_sheet = load_sprite_sheet(DATA / "batch95_mimic_sheet.json")
hero_clips = load_animation_set(DATA / "batch95_hero_battle_animation.json")
mimic_clips = load_animation_set(DATA / "batch95_mimic_animation.json")

sheets = {
    "10000000-0000-4000-8000-000000000012": hero_sheet,
    "10000000-0000-4000-8000-000000000096": mimic_sheet,
}
clips = {
    "10000000-0000-4000-8000-000000000095": hero_clips,
    "10000000-0000-4000-8000-000000000097": mimic_clips,
}

runtime = BattlePresentationRuntime(scene, clips.get, sheets.get)
coordinator = BattlePresentationCoordinator(scene)
coordinator.consume_timeline_cues(
    (
        PresentationCue(
            "reference.slash",
            ActionCue("attack", 0.0, "animation", {"member_id": "hero", "role": "attack"}),
        ),
        PresentationCue(
            "reference.slash",
            ActionCue("hit", 0.18, "animation", {"member_id": "archive_mimic", "role": "hit"}),
        ),
    )
)
runtime.apply_events(coordinator.drain())
runtime.update(0.1)
frame = runtime.build_frame(Camera2D(width=320, height=180, zoom=2.0))
assert len(frame.combatant_draws) == 2
assert runtime.combatant("hero").role.value == "attack"
assert runtime.combatant("archive_mimic").role.value == "hit"
print("Batch 95 battle presentation reference verification: PASS")
