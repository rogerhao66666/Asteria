"""Real-window tour of the Boss Trial's menus (macOS, real window): the screens a player uses to
prepare - status, items, equipment, skills, skill tree, crafting, shop, bag - each photographed.

    python scripts/boss_trial_menu_tour.py OUTPUT_DIR

The hero is left partly built (a few tree nodes, some points to spend) so the screens show choices.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import boss_trial_live_check as live  # noqa: E402


def main(argv=None):
    import pygame
    import run_trial_smoke as smoke

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.bag_screen import BagScreen
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from asteria.runtime.skill_tree_screen import SkillTreeScreen

    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0] if argv else REPO / "docs" / "audits" / "evidence" / "boss_trial")
    out.mkdir(parents=True, exist_ok=True)
    helper = live._helpers()
    pump, key = helper._pump, helper._key
    project = Project.load_json(
        live.DEMO / "project.asteria.json", EditorDocument().component_registry
    )
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), live.DEMO, width=1280, height=720
    )
    runtime.open()
    game, shots = runtime.game, []

    def shot(name, seconds=0.35):
        pump(runtime, seconds)
        pygame.image.save(runtime.capture(), str(out / name))
        shots.append(name)

    def press(k):
        key(k)
        pump(runtime, 0.05)
        key(k, up=True)
        pump(runtime, 0.15)

    # a hero partway through: some tree ranks, gear on, a bag to craft and shop with
    allocation = game.save.rpg_state.progression_allocations[smoke.HERO]
    for graph_id, nodes in (
        ("knight_tree", ("k_footing", "k_footing", "k_bash", "k_cleave")),
        ("weapon_master_tree", ("weapon_master_core", "weapon_master_arsenal_barrage")),
        ("attributes", ("attr_str", "attr_str", "attr_vit", "attr_dex")),
    ):
        for node in nodes:
            try:
                allocation.allocate(graph_id, node)
            except ValueError:
                pass
    smoke.world(game, "SET_CLASSES", actor_id=smoke.HERO, class_ids="knight,weapon_master")
    smoke.world(game, "REFINE_EQUIPMENT", actor_id=smoke.HERO, instance_id=smoke.SW)
    smoke.world(
        game,
        "SOCKET_ITEM",
        actor_id=smoke.HERO,
        instance_id=smoke.SW,
        socket_id="s1",
        item_id="ruby_item",
    )
    runtime._ui_mode = "field"
    shot("tour_field.png", 0.6)

    runtime.open_status_menu(back="field")
    for tab in ("status", "items", "equipment", "skills"):
        shot(f"tour_status_{tab}.png")
        press(pygame.K_TAB)
    runtime._ui_mode = "field"

    runtime._skill_tree = SkillTreeScreen(runtime)
    runtime._ui_mode = "skills"
    shot("tour_skill_tree.png", 0.5)
    for index in range(3):
        press(pygame.K_o)
        shot(f"tour_skill_tree_{index + 2}.png", 0.3)
    runtime._ui_mode = "field"

    runtime._bag_screen = BagScreen(runtime)
    runtime._ui_mode = "bag"
    shot("tour_bag.png", 0.5)
    runtime._ui_mode = "field"

    runtime._open_crafting("alchemy", back="field")
    shot("tour_crafting.png", 0.5)
    runtime._ui_mode = "field"

    game.open_shop("trial_shop")
    runtime._ui_mode = "shop"
    shot("tour_shop.png", 0.5)
    runtime.close()
    report = {"screens": shots, "facts": dict(Counter())}
    (out / "tour_results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
