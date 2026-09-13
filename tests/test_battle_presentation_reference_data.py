import json
from pathlib import Path

from asteria.presentation import BattlePresentationRuntime, BattlePresentationScene
from asteria.reference_data import load_animation_set, load_sprite_sheet
from asteria.runtime import Camera2D

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "reference_data"


def test_batch95_reference_scene_and_original_asteria_assets_are_runtime_valid():
    scene = BattlePresentationScene.from_data(
        json.loads((DATA / "batch95_battle_presentation_scene.json").read_text(encoding="utf-8"))
    )
    sheets = {
        "10000000-0000-4000-8000-000000000012": load_sprite_sheet(DATA / "hero_sheet.json"),
        "10000000-0000-4000-8000-000000000096": load_sprite_sheet(DATA / "batch95_mimic_sheet.json"),
    }
    clips = {
        "10000000-0000-4000-8000-000000000095": load_animation_set(DATA / "batch95_hero_battle_animation.json"),
        "10000000-0000-4000-8000-000000000097": load_animation_set(DATA / "batch95_mimic_animation.json"),
    }
    runtime = BattlePresentationRuntime(scene, clips.get, sheets.get)
    frame = runtime.build_frame(Camera2D(width=320, height=180, zoom=2.0))
    assert scene.visual_for("hero").clip_for("attack") == "battle_attack"
    assert scene.visual_for("archive_mimic").clip_for("ko") == "ko"
    assert [d.texture_asset_id for d in frame.combatant_draws] == [
        "10000000-0000-4000-8000-000000000002",
        "10000000-0000-4000-8000-000000000003",
    ]
