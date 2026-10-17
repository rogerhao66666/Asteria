"""The battle presentation of the complex reference project that is not art: the effect sheets,
the motion sequences of its few skills and the side-view layout and HUD.

    python scripts/build_reference_presentation.py [PROJECT_DIR]

Run on a freshly built ``complex_reference_rpg`` (after ``build_project.py``) and before the
Lucifer reskin (``scripts/reskin_reference_projects.py``), which adds the characters. Only the
canonical presentation sections of ``project.asteria.json`` are rewritten.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from asteria.assets.canonical import AssetSource, CanonicalAsset  # noqa: E402
from asteria.editor import EditorDocument  # noqa: E402
from asteria.presentation.battle_hud import BattleHudProfile, BattleHudResourceStyle  # noqa: E402
from asteria.presentation.battle_motion_sequence import (  # noqa: E402
    BattleMotionBeat,
    BattleMotionSequence,
)
from asteria.project import Project  # noqa: E402

FX = ("slash", "flame", "explosion")  # the strips themselves come with the reskin
SOURCE = (("license", "CC0 1.0"), ("source", "Foozle Pixel Magic Effects"))


def _beat(beat_id, at, channel, cue, member, **payload):
    return BattleMotionBeat(beat_id, at, channel, cue, member_id=member, payload=payload or None)


def motion_sequences():
    def offensive(sequence_id, fx, hit_at, duration, shake, flash=None):
        beats = [
            _beat("swing", 0.0, "animation", "attack", "@source"),
            _beat("fx", round(hit_at - 0.12, 3), "vfx", fx, "@target"),
            _beat("impact", hit_at, "animation", "hit", "@target"),
            _beat("sound", hit_at, "audio", "hit", "@target"),
            _beat("shake", hit_at, "camera", "shake", "@target", amplitude=shake, duration=0.18),
        ]
        if flash:
            beats.append(
                _beat("flash", hit_at, "screen_fx", "flash", "@target", alpha=flash, duration=0.08)
            )
        return BattleMotionSequence(sequence_id, duration, beats)

    return (
        offensive("default_action", "battle.fx.slash", 0.24, 0.7, 4),
        offensive("strike", "battle.fx.slash", 0.24, 0.7, 4),
        offensive("fire_arc", "battle.fx.flame", 0.32, 0.9, 5, flash=40),
        offensive("meteor", "battle.fx.explosion", 0.45, 1.1, 9, flash=80),
        BattleMotionSequence(
            "heal",
            0.8,
            (
                _beat("raise", 0.0, "animation", "attack", "@source"),
                _beat("fx", 0.12, "vfx", "battle.fx.heal", "@target"),
                _beat("sound", 0.12, "audio", "heal", "@target"),
            ),
        ),
    )


def build(folder):
    folder = Path(folder)
    path = folder / "project.asteria.json"
    project = Project.load_json(path, EditorDocument().component_registry)
    library = project.battle_presentation_library
    for key in FX:  # placeholders: the reskin draws them (same ids, so skills keep their effect)
        project.assets.register(
            CanonicalAsset(
                f"battle.fx.{key}",
                "sprite_sheet",
                AssetSource(f"playable_assets/battle/{key}.png", "project", SOURCE),
                tags=frozenset({"battle", "vfx"}),
                metadata=(
                    ("clips", {"play": {"frames": [0], "frame_duration": 0.06, "loop": False}}),
                    ("frame_size", [128, 128]),
                    ("pivot", [0.5, 0.5]),
                ),
            ),
            replace=True,
        )
    project.assets.register(
        CanonicalAsset(
            "battle.fx.heal",
            "sprite_sheet",
            AssetSource("playable_assets/fx_heal.png", "project", (("license", "repository"),)),
            tags=frozenset({"battle", "vfx"}),
            metadata=(
                (
                    "clips",
                    {"play": {"frames": list(range(16)), "frame_duration": 0.04, "loop": False}},
                ),
                ("frame_size", [64, 64]),
                ("pivot", [0.5, 0.5]),
            ),
        ),
        replace=True,
    )
    for sequence in motion_sequences():
        library.set("motion_sequences", sequence.sequence_id, sequence)
    layout = library.require("ui_layout", "adaptive")
    library.set(
        "ui_layout",
        "adaptive",
        replace(
            layout,
            party_hud="bottom_row",
            overhead_zones=("left",),
            action_menu_placement="actor",
            stage_top=0.44,
        ),
    )
    library.set(
        "hud",
        "adaptive",
        BattleHudProfile(
            resources=[
                BattleHudResourceStyle("vitality", "HP", order=0, priority=10),
                BattleHudResourceStyle("technique", "SP", order=1, priority=5),
            ],
            show_unmapped_resources=True,
        ),
    )
    project.save_json(path)


if __name__ == "__main__":
    build(
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else REPO / "reference_projects/complex_reference_rpg"
    )
