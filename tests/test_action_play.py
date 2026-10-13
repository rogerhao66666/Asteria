"""ASTERIA_SPEC §20 (D22 A8): action scenes in the playable runtime — keys drive the player's
abilities, enemies fight
back, the HUD draws, loot is picked up, the bag equips rolled items, the player falls and
respawns; side view jumps."""

import pytest

from asteria.core import Transform
from asteria.runtime.action_play import ARPG_ACTIONS, CombatSceneComponent, missing_action_bindings
from asteria.runtime.combat import CombatantComponent
from asteria.runtime.input_map import InputActionMap
from asteria.validation.arpg_playground import build_playground

DT = 1 / 60


def _press(rt, key, frames=2):
    pg = rt.pg
    rt._frame([pg.event.Event(pg.KEYDOWN, key=key, mod=0, unicode="", scancode=0)], DT)
    for _ in range(frames - 1):
        rt._frame([], DT)
    rt._frame([pg.event.Event(pg.KEYUP, key=key, mod=0, unicode="", scancode=0)], DT)


def _run(rt, frames):
    for _ in range(frames):
        rt._frame([], DT)


def test_project_input_maps_win_and_missing_actions_are_filled_in():
    project_map = InputActionMap.default()
    filled = missing_action_bindings(project_map)
    assert set(filled) == set(ARPG_ACTIONS) - set(project_map.actions())
    project_map.set_bindings("attack", filled["dodge"])
    assert "attack" not in missing_action_bindings(project_map)


def test_keys_fight_in_an_action_scene_with_the_hud(runtime):
    rt = runtime
    game = build_playground(rt)
    assert game.action_scene and game.combat_scene.view == "topdown"
    player = game.player
    hero_state = game.combat.state(player)
    life = player.get(CombatantComponent).life_resource
    slime = next(e for e, _ in game.scene.query(CombatantComponent) if e.name == "Slime A")
    game.set_player_position(slime.get(Transform).x - 14, slime.get(Transform).y)
    used = []
    game.action_combat.listeners.append(used.append)
    _press(rt, rt.pg.K_d, 3)  # face the slime
    _press(rt, rt.pg.K_j)
    _run(rt, 8)
    _press(rt, rt.pg.K_j)  # inside the combo window
    _run(rt, 30)
    mine = [e.kind for e in used if e.entity_id == player.id and e.kind in ("used", "combo")]
    assert mine[:2] == ["used", "combo"]
    assert (
        any(f.text for f in rt.action_hud.floats)
        or game.combat.state(slime).resources.current("hp") < 30
    )
    _press(rt, rt.pg.K_k)  # dodge
    assert any(e.ability_id == "pg_roll" and e.kind == "used" for e in used)
    _run(rt, 40)
    _press(rt, rt.pg.K_1)  # fire bolt (costs mp from the hero's build if it has some)
    _run(rt, 120)  # let the enemies fight back for two seconds
    assert hero_state.resources.current(life) < hero_state.resources.maximum(life)  # they did
    assert rt.screen.get_at((rt.width // 2, rt.height - 50)) != (0, 0, 0, 255)


def test_loot_pickup_bag_and_respawn_through_the_runtime(runtime):
    rt = runtime
    game = build_playground(rt)
    player = game.player
    x, y = player.get(Transform).x, player.get(Transform).y
    game.loot.drop(game.scene, x + 4, y, items={"pg_blade": 1}, currencies={"gold": 7}, level=5)
    gold = game.save.rpg_state.currencies.get("gold", 0)
    _run(rt, 2)
    assert game.save.rpg_state.currencies.get("gold", 0) == gold + 7  # walked over: gold
    bag = len(game.save.rpg_state.equipment_bag)
    _press(rt, rt.pg.K_f)
    assert len(game.save.rpg_state.equipment_bag) == bag + 1
    _press(rt, rt.pg.K_b)
    assert rt._ui_mode == "bag"
    rt._bag_index = len(game.save.rpg_state.equipment_bag) - 1
    _press(rt, rt.pg.K_RETURN)
    assert "Equipped" in rt.message or "Cannot equip" in rt.message
    _press(rt, rt.pg.K_b)
    assert rt._ui_mode == "field"
    state = game.combat.state(player)
    life = player.get(CombatantComponent).life_resource
    state.resources.set_current(life, 1)
    game.set_player_position(x + 40, y + 10)
    from asteria.runtime.character_control import HitEvent

    game.combat.pending.append(HitEvent("", player.id, "pg_slam", "foe"))
    _run(rt, 2)
    assert game.player_down > 0 and game.scene.get_entity(player.id) is player
    _run(rt, int(game.combat_scene.respawn_delay / DT) + 3)
    assert game.player_down == 0 and state.resources.current(life) == state.resources.maximum(life)
    assert (player.get(Transform).x, player.get(Transform).y) == pytest.approx(
        game._action_spawn[game.scene.id]
    )


def test_side_view_jumps_on_the_block_out_course(runtime):
    rt = runtime
    game = build_playground(rt, "side")
    assert game.combat_scene.view == "side" and game.combat_scene.draw_colliders
    _run(rt, 30)
    player = game.player
    from asteria.runtime.character_control import CharacterController2DComponent

    assert (
        player.get(CharacterController2DComponent).mode == "side"
        and player.get(CharacterController2DComponent).grounded
    )
    ground_y = player.get(Transform).y
    _press(rt, rt.pg.K_SPACE, 1)
    _run(rt, 8)
    assert player.get(Transform).y < ground_y - 4


def test_classic_scenes_keep_their_encounters(runtime):
    game = runtime.game
    assert not game.action_scene and game.combat_scene is None
    holder = game.scene.add_entity(type(game.player)("Settings"))
    holder.add_component(CombatSceneComponent())
    assert not game.action_scene  # combat_mode defaults to encounter
