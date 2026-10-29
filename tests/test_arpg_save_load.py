"""D23: the ARPG demo survives a real save and load - class, skill ranks and points, level,
rolled equipment (rarity and affixes) in the bag and worn, items, gold, the scene and where the
player stands - and play continues with the same build."""

from pathlib import Path

import pytest

from asteria.core import Transform

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_demo"


def _open(monkeypatch, save=None):
    pytest.importorskip("pygame")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    state = save or project.game_start.instantiate(project)
    rt = PlayableTestRuntime(project, state, ROOT, width=960, height=540)
    rt.open()
    rt._ui_mode = "field"
    return rt, project


def _frames(rt, count):
    for _ in range(count):
        rt._frame([], 1 / 60)


def _snapshot(game):
    state = game.save.rpg_state
    progress = state.actor_progression["hero"]
    build = game.resolve_actor_build("hero")
    return {
        "scene": game.scene.name,
        "classes": progress.active_class_ids,
        "unlocked": progress.unlocked_class_ids,
        "level": progress.level,
        "experience": progress.experience,
        "points": dict(progress.points),
        "ap": state.progression_allocations["hero"].balance("ap"),
        "ranks": {
            graph: dict(ranks)
            for graph, ranks in state.progression_allocations["hero"].allocations.items()
        },
        "gold": state.currencies.get("gold"),
        "potions": state.inventory.count("potion"),
        "bag": [
            (i.equipment.equipment_id, i.rarity, i.item_level, i.rolled_affixes)
            for i in state.equipment_bag
        ],
        "worn": sorted(
            (i.equipment.equipment_id, i.rarity, i.rolled_affixes)
            for i in state.loadouts["hero"].equipped()
        ),
        "abilities": sorted(build.abilities),
        "stats": {name: build.stats.get(name) for name in sorted(build.stats.names())},
    }


def test_a_played_session_comes_back_exactly_after_save_and_load(monkeypatch, tmp_path):
    from asteria.runtime.game_save import GameRuntimeSave

    rt, project = _open(monkeypatch)
    game = rt.game
    game.set_classes("", ["warrior"])
    game.grant_actor_experience("hero", 3200, **game.action_progression)
    for node in ("w_rend", "w_whirl", "w_might", "w_might"):
        game.allocate_progression("hero", "warrior_tree", node)
    game.allocate_progression("hero", "attributes", "a_str")
    # loot: a rolled drop is picked up, one piece is worn, the potion count changes
    from asteria.rpg.loot import roll_equipment

    db = project.rpg_database
    import random

    rng = random.Random(3)
    for item_id, rarity in (("war_axe", "rare"), ("iron_helm", "magic"), ("cyclops_eye", None)):
        game.save.rpg_state.equipment_bag.append(
            roll_equipment(
                db.equipment[item_id],
                rng,
                item_level=7,
                rarity_id=rarity,
                rarities=db.loot_rarities(),
                affixes=db.affixes,
                instance_id=f"test:{item_id}",
            )
        )
    game.equip_from_bag("hero", 0)
    game.save.rpg_state.inventory.add("potion", 4)
    game.save.rpg_state.currencies["gold"] = 321
    field = next(s for s in project.scenes() if s.name.startswith("Greenvale"))
    game.transfer_player(field.id, 20 * 16, 25 * 16, facing="left")
    _frames(rt, 30)
    before = _snapshot(game)
    position = game.player.get(Transform)
    where = (round(position.x, 3), round(position.y, 3))
    assert before["scene"] == "Greenvale Fields" and before["classes"] == ("warrior",)
    assert before["worn"] and before["bag"]

    path = tmp_path / "slot1.asteria-save.json"
    game.sync_world_state()
    game.save.save_json(path)
    rt.close()

    loaded = GameRuntimeSave.load_json(path, project)
    rt2, _ = _open(monkeypatch, loaded)
    game2 = rt2.game
    _frames(rt2, 30)
    after = _snapshot(game2)
    assert after == before
    t2 = game2.player.get(Transform)
    assert (round(t2.x, 3), round(t2.y, 3)) == where
    assert game2.facing == "left"
    # play goes on: the learned skill works, the worn weapon still counts, stairs back to town
    game2.combat.state(game2.player).resources.set_current("mp", 80)
    assert game2.action_combat.use(game2.player, "w_whirl") == "used"
    town = next(s for s in project.scenes() if s.name == "Hollowbrook")
    game2.transfer_player(town.id, 300, 200, facing="down")
    _frames(rt2, 10)
    assert game2.scene.name == "Hollowbrook"
    rt2.close()


def test_a_save_made_in_a_side_view_scene_loads_back_into_it(monkeypatch, tmp_path):
    from asteria.runtime.character_control import CharacterController2DComponent
    from asteria.runtime.game_save import GameRuntimeSave

    rt, project = _open(monkeypatch)
    game = rt.game
    mine = next(s for s in project.scenes() if s.name.startswith("Rustdeep"))
    game.transfer_player(mine.id, 6 * 18, 10 * 18, facing="right")
    _frames(rt, 60)
    path = tmp_path / "mine.asteria-save.json"
    game.sync_world_state()
    game.save.save_json(path)
    x = game.player.get(Transform).x
    rt.close()
    rt2, _ = _open(monkeypatch, GameRuntimeSave.load_json(path, project))
    _frames(rt2, 60)
    controller = rt2.game.player.get(CharacterController2DComponent)
    assert rt2.game.scene.name == "Rustdeep Mine" and controller.mode == "side"
    assert controller.grounded and abs(rt2.game.player.get(Transform).x - x) < 4
    rt2.close()


def test_a_defeated_boss_stays_dead_after_save_and_load(monkeypatch, tmp_path):
    from asteria.runtime.combat import CombatantComponent
    from asteria.runtime.game_save import GameRuntimeSave

    rt, project = _open(monkeypatch)
    game = rt.game
    field = next(s for s in project.scenes() if s.name.startswith("Greenvale"))
    game.transfer_player(field.id, 20 * 16, 25 * 16, facing="right")
    _frames(rt, 5)

    def alive(game):
        return [
            e.name
            for e, c in game.scene.query(CombatantComponent)
            if c.defeat_switch and e.name.startswith("Gorgoth")
        ]

    assert alive(game) == ["Gorgoth the Cyclops"]
    boss = next(e for e in game.scene.entities() if e.name.startswith("Gorgoth"))
    # defeat it the way play does: a hit that kills goes through the combat system
    from asteria.gameplay.attacks import AttackDefinition
    from asteria.gameplay.formulas import ValueFormula
    from asteria.runtime.character_control import HitEvent

    game.project.gameplay_library.attacks["_kill"] = AttackDefinition(
        "_kill", damage=ValueFormula.constant(1e9)
    )
    combat = game.combat
    combat.attacks["_kill"] = game.project.gameplay_library.attacks["_kill"]
    combat.pending.append(HitEvent(game.player.id, boss.id, "_kill", "hero"))
    _frames(rt, 5)
    assert not alive(game)
    assert game.save.event_context.get_switch("defeated.gorgoth")
    path = tmp_path / "boss.asteria-save.json"
    game.sync_world_state()
    game.save.save_json(path)
    rt.close()
    rt2, _ = _open(monkeypatch, GameRuntimeSave.load_json(path, project))
    _frames(rt2, 5)
    assert alive(rt2.game) == []  # the boss is gone from the loaded game
    others = [e.name for e, c in rt2.game.scene.query(CombatantComponent) if "Slime" in e.name]
    assert others  # everything else is back
    rt2.close()
