"""The project adapter runs authored combat once and isolates participant RPG state."""

import random
from pathlib import Path

import pytest

from asteria.core import Transform
from asteria.multiplayer.persistence import SQLiteMultiplayerStore
from asteria.multiplayer.project_demo import build_project_adapter
from asteria.multiplayer.project_snapshot import unpack_scene_data
from asteria.multiplayer.protocol import encode_frame, message
from asteria.multiplayer.rules import default_rules
from asteria.runtime.character_control import HitEvent
from asteria.runtime.combat import CombatantComponent
from asteria.runtime.loot import LootComponent

PROJECT = (
    Path(__file__).resolve().parents[1]
    / "reference_projects/arpg_multiplayer_demo/project.asteria.json"
)


def adapter(tmp_path, *, fields=False):
    rules = default_rules()
    rules["rewards"]["monster"] = rules["rewards"]["boss"]
    if fields:
        rules["project_runtime"] = {
            "start_scene": "Greenvale Fields",
            "start_position": [232, 300],
        }
    store = SQLiteMultiplayerStore(tmp_path / "world.sqlite3")
    return build_project_adapter(
        store=store, project_path=PROJECT, rules=rules, random_source=random.Random(17)
    )


def test_four_authored_players_move_independently_and_fit_wire_limit(tmp_path):
    game = adapter(tmp_path)
    try:
        for pid in ("one", "two", "three", "four"):
            game.on_player_joined(pid, pid)
        assert len({id(s.save.rpg_state) for s in game.players.values()}) == 4
        assert len({s.player.id for s in game.players.values()}) == 4
        before = {pid: s.player.get(Transform).x for pid, s in game.players.items()}
        game.handle_input("one", {"actions": {"move_left": 1}})
        game.network_tick(1 / 30)
        assert game.players["one"].player.get(Transform).x < before["one"]
        assert game.players["two"].player.get(Transform).x == before["two"]
        one = game.players["one"]
        one.combat.state(one.player).resources.set_current("hp", 37)
        state = game.initial_state()
        for row in state["players"]:
            session = game.players[row["player_id"]]
            transform = session.player.get(Transform)
            pool = session.combat.state(session.player).resources
            assert (row["x"], row["y"]) == (transform.x, transform.y)
            assert row["hp"] == pool.current("hp")
            assert row["max_hp"] == pool.maximum("hp")
        assert state["players"][0]["hp"] == 37
        assert len(encode_frame(message("game_update", state=state))) < 65536
        scenes = [unpack_scene_data(s) for s in state["scenes"]]
        assert {s["name"] for s in scenes} == {"Hollowbrook", "Greenvale Fields", "Rustdeep Mine"}
    finally:
        game.store.close()


def test_original_punch_timeline_hits_original_slime(tmp_path):
    game = adapter(tmp_path, fields=True)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        slime = next(e for e, c in session.scene.query(CombatantComponent) if e.name == "Slime 1")
        before = session.combat.state(slime).resources.current("hp")
        game.handle_input("one", {"attack": 1})
        events = []
        for _ in range(12):
            events.extend(game.network_tick(1 / 30).events)
        assert session.combat.state(slime).resources.current("hp") < before
        assert any(e["kind"] == "damage" and e["target_id"] == slime.id for e in events)
        assert game.store.get_encounter_contributors(game._encounter(slime.id))["one"] > 0
    finally:
        game.store.close()


def test_two_damagers_each_get_full_xp_and_one_claims_original_loot(tmp_path):
    game = adapter(tmp_path, fields=True)
    try:
        for pid in ("one", "two"):
            game.on_player_joined(pid, pid)
        first = game.players["one"]
        slime = next(
            e for e, c in first.scene.query(CombatantComponent) if e.name == "Gorgoth the Cyclops"
        )
        combat = first.combat
        # Inject landed engine hits: reward eligibility is derived from actual CombatSystem events.
        for pid in ("one", "two"):
            combat.pending.append(HitEvent(game.players[pid].player.id, slime.id, "punch", "hero"))
            game.network_tick(1 / 30)
        combat.state(slime).resources.set_current("hp", 1)
        combat.pending.append(HitEvent(first.player.id, slime.id, "punch", "hero"))
        game.network_tick(1 / 30)
        assert all(game.store.get_player(p)["experience"] == 100 for p in ("one", "two"))
        assert all(
            s.save.rpg_state.actor_progression["hero"].experience == 100
            for s in game.players.values()
        )
        encounter = game.store.get_encounter(game._encounter(slime.id))
        assert encounter["status"] == "completed"
        assert encounter["result"]["kill_credit"] == "one"
        assert [hit["order"] for hit in encounter["result"]["combat_log"]] == [1, 2, 3]
        assert [hit["player_id"] for hit in encounter["result"]["combat_log"]] == [
            "one",
            "two",
            "one",
        ]
        loot = [(e, c) for e, c in first.scene.query(LootComponent) if e.id in game._drop_owners]
        assert loot
        entity, spec = loot[0]
        owner = game._drop_owners[entity.id]
        other = "two" if owner == "one" else "one"
        for pid in (owner, other):
            game.players[pid].set_player_position(entity.get(Transform).x, entity.get(Transform).y)
        with pytest.raises(ValueError, match="cannot be picked"):
            game.handle_command(other, "pickup", {"loot_id": entity.id})
        game.handle_command(owner, "pickup", {"loot_id": entity.id})
        assert game.store.get_world_drop(entity.id)["claimed_by"] == owner
        assert game.store.get_player(owner)["game_state"][game.SAVE_NAMESPACE]["save"]
        game.network_tick(1 / 30)
        assert all(game.store.get_player(p)["experience"] == 100 for p in ("one", "two"))
    finally:
        game.store.close()


def test_save_rejoin_keeps_individual_class_equipment_and_resources(tmp_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        game.on_player_joined("two", "two")
        one, two = game.players["one"], game.players["two"]
        one.set_classes("hero", ["warrior"])
        one.grant_actor_points("hero", ap=5)
        game.handle_command("one", "allocate", {"graph_id": "warrior_tree", "node_id": "w_might"})
        assert (
            one.resolve_actor_build("hero").stats.to_data()
            != two.resolve_actor_build("hero").stats.to_data()
        )
        one.combat.state(one.player).resources.set_current("hp", 25)
        game.handle_command("one", "save", {})
        game.on_player_left("one")
        game.on_player_joined("one", "one")
        restored = game.players["one"]
        assert restored.save.rpg_state.actor_progression["hero"].active_class_ids == ("warrior",)
        assert restored.combat.state(restored.player).resources.current("hp") == 25
        assert game.players["two"].save.rpg_state.actor_progression["hero"].active_class_ids == (
            "adventurer",
        )
    finally:
        game.store.close()


def test_input_validation_and_unreachable_loot_cannot_mutate_state(tmp_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        with pytest.raises(ValueError):
            game.handle_input("one", {"move_x": float("nan")})
        with pytest.raises(ValueError):
            game.handle_input("one", {"attack": 2})
        with pytest.raises(ValueError):
            game.handle_command("one", "transfer", {"scene_id": "arbitrary"})
        with pytest.raises(ValueError):
            game.handle_command("one", "equip", {"index": 99})
        assert game.players["one"].save.scene_id == game._template_scene.id
    finally:
        game.store.close()


def test_original_trainers_and_merchant_run_on_server_for_one_player_only(tmp_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        game.on_player_joined("two", "two")
        one, two = game.players["one"], game.players["two"]
        one.set_player_position(248, 280)
        one.set_player_facing("up")
        state = game.handle_command("one", "interact", {}).state
        assert state["players"][0]["pending_dialogue"]["schema"] == "asteria.dialogue_request"
        while one.pending_dialogue:
            game.handle_command("one", "dialogue_ack", {})
        assert one.save.rpg_state.actor_progression["hero"].active_class_ids == ("warrior",)
        assert two.save.rpg_state.actor_progression["hero"].active_class_ids == ("adventurer",)
        one.interaction.reset()
        one.set_player_position(232, 142)
        one.set_player_facing("up")
        game.handle_command("one", "interact", {})
        while one.pending_dialogue:
            game.handle_command("one", "dialogue_ack", {})
        assert one.open_shop_id == "merchant"
        assert two.open_shop_id is None
        before = one.save.rpg_state.inventory.count("potion")
        game.handle_command("one", "buy", {"item_id": "potion", "quantity": 1})
        assert one.save.rpg_state.inventory.count("potion") == before + 1
        assert two.save.rpg_state.inventory.count("potion") == 3
        with pytest.raises(ValueError, match="not open"):
            game.handle_command("two", "buy", {"shop_id": "merchant", "item_id": "potion"})
        game.handle_command("one", "close_shop", {})
        assert one.open_shop_id is None
    finally:
        game.store.close()


def test_equipment_and_character_survive_a_fresh_server_process(tmp_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        game.on_player_joined("two", "two")
        one, two = game.players["one"], game.players["two"]
        other_stats = two.resolve_actor_build("hero").stats.to_data()
        base_power = one.resolve_actor_build("hero").stats.get("power")
        # A server fixture seeds an authored item, exactly as NPC GIVE_ITEM / drops do.
        one.save.rpg_state.inventory.add("short_sword")
        game.handle_command("one", "equip", {"equipment_id": "short_sword"})
        assert one.resolve_actor_build("hero").stats.get("power") == base_power + 4
        assert two.resolve_actor_build("hero").stats.to_data() == other_stats
        game.handle_command("one", "unequip", {"slot_id": "weapon"})
        assert one.resolve_actor_build("hero").stats.get("power") == base_power
        assert len(one.save.rpg_state.equipment_bag) == 1
        game.handle_command("one", "equip", {"index": 0})
        one.combat.state(one.player).resources.set_current("hp", 21)
        game.handle_command("one", "save", {})
        game.store.close()
        game = adapter(tmp_path)
        game.on_player_joined("one", "one")
        game.on_player_joined("two", "two")
        restored = game.players["one"]
        assert restored.resolve_actor_build("hero").stats.get("power") == base_power + 4
        assert (
            restored.save.rpg_state.loadouts["hero"].equipped("weapon")[0].equipment.equipment_id
            == "short_sword"
        )
        assert restored.combat.state(restored.player).resources.current("hp") == 21
        assert game.players["two"].resolve_actor_build("hero").stats.to_data() == other_stats
    finally:
        game.store.close()


def test_rejected_sqlite_claim_rolls_back_character_inventory(tmp_path, monkeypatch):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        p = session.player.get(Transform)
        entity = session.loot.drop(session.scene, p.x, p.y, items={"potion": 1})[0]
        entity.get(Transform).x, entity.get(Transform).y = p.x, p.y
        game.store.begin_encounter("fixture", "fixture")
        game.store.create_world_drop(
            entity.id, "fixture", "potion", 1, owner_player_id="one", policy="owner_only"
        )
        game._drop_owners[entity.id] = "one"
        before = session.save.rpg_state.to_data()
        monkeypatch.setattr(game.store, "claim_world_drop", lambda *args, **kwargs: False)
        for _ in range(2):
            with pytest.raises(ValueError, match="cannot be picked"):
                game.handle_command("one", "pickup", {"loot_id": entity.id})
            assert session.save.rpg_state.to_data() == before
            assert session.scene.get_entity(entity.id) is entity
    finally:
        game.store.close()


def test_original_smith_crafts_and_potion_heals_authoritative_resources(tmp_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        session.set_player_position(376, 142)
        session.set_player_facing("up")
        game.handle_command("one", "interact", {})
        while session.pending_dialogue:
            game.handle_command("one", "dialogue_ack", {})
        assert session.open_crafting_station == "smith"
        session.save.rpg_state.inventory.add("slime_gel", 3)
        before = session.save.rpg_state.inventory.count("potion")
        game.handle_command(
            "one",
            "craft",
            {"payload": {f"brew_gel.{i}": ["slime_gel"] for i in range(3)}, "station": "smith"},
        )
        assert session.save.rpg_state.inventory.count("potion") == before + 1
        assert session.save.rpg_state.inventory.count("slime_gel") == 0
        game.handle_command("one", "close_crafting", {})
        resources = session.combat.state(session.player).resources
        resources.set_current("hp", 1)
        game.handle_command("one", "use_item", {"item_id": "potion"})
        for _ in range(30):
            state = game.network_tick(1 / 30).state
        assert resources.current("hp") > 1
        assert (
            state["players"][0]["game_save"]["rpg_state"]["actor_snapshots"]["hero"]["resources"]
            == resources.to_data()
        )
        with pytest.raises(ValueError, match="not open"):
            game.handle_command("one", "craft", {"payload": {}, "station": "smith"})
    finally:
        game.store.close()


def test_atomic_owned_rolled_equipment_claim_survives_reopen(tmp_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        p = session.player.get(Transform)
        entity = session.loot.drop(session.scene, p.x, p.y, items={"short_sword": 1}, level=5)[0]
        entity.get(Transform).x, entity.get(Transform).y = p.x, p.y
        game.store.begin_encounter("atomic_fixture", "fixture")
        game.store.create_world_drop(
            entity.id,
            "atomic_fixture",
            "short_sword",
            1,
            owner_player_id="one",
            policy="owner_only",
        )
        game._drop_owners[entity.id] = "one"
        game.handle_command("one", "pickup", {"loot_id": entity.id})
        rolled = session.save.rpg_state.equipment_bag[-1].to_data()
        drop_id = entity.id
        game.store.close()
        game = adapter(tmp_path)
        assert game.store.get_world_drop(drop_id)["claimed_by"] == "one"
        game.on_player_joined("one", "one")
        assert game.players["one"].save.rpg_state.equipment_bag[-1].to_data() == rolled
    finally:
        game.store.close()


def test_atomic_profile_failure_leaves_owned_loot_unclaimed(tmp_path):
    import sqlite3

    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        p = session.player.get(Transform)
        entity = session.loot.drop(session.scene, p.x, p.y, items={"potion": 1})[0]
        entity.get(Transform).x, entity.get(Transform).y = p.x, p.y
        game.store.begin_encounter("atomic_fixture", "fixture")
        game.store.create_world_drop(
            entity.id, "atomic_fixture", "potion", 1, owner_player_id="one", policy="owner_only"
        )
        game._drop_owners[entity.id] = "one"
        before = session.save.rpg_state.to_data()
        with sqlite3.connect(game.store.path) as connection:
            connection.execute(
                "CREATE TRIGGER reject_profile BEFORE INSERT ON player_state "
                "BEGIN SELECT RAISE(ABORT, 'fixture profile failure'); END"
            )
        with pytest.raises(sqlite3.IntegrityError, match="fixture profile failure"):
            game.handle_command("one", "pickup", {"loot_id": entity.id})
        assert session.save.rpg_state.to_data() == before
        assert game.store.get_world_drop(entity.id)["claimed_by"] is None
        assert game.store.get_player("one")["inventory"].get("potion", 0) == 0
    finally:
        game.store.close()


@pytest.mark.parametrize(
    "assignment", ["random_eligible_player", "highest_damage_player", "every_eligible_player"]
)
def test_original_boss_drop_assignment_policies(tmp_path, assignment):
    game = adapter(tmp_path, fields=True)
    try:
        game.rules["rewards"]["boss"]["drops"]["assignment"] = assignment
        for pid in ("one", "two"):
            game.on_player_joined(pid, pid)
        session = game.players["one"]
        boss = next(
            e
            for e, c in session.scene.query(CombatantComponent)
            if e.name == "Gorgoth the Cyclops"
        )
        for pid in ("one", "two"):
            session.combat.pending.append(
                HitEvent(game.players[pid].player.id, boss.id, "punch", "hero")
            )
            game.network_tick(1 / 30)
        session.combat.state(boss).resources.set_current("hp", 1)
        session.combat.pending.append(HitEvent(session.player.id, boss.id, "punch", "hero"))
        game.network_tick(1 / 30)
        owned = {
            pid: [eid for eid, owner in game._drop_owners.items() if owner == pid]
            for pid in ("one", "two")
        }
        if assignment == "highest_damage_player":
            assert owned["one"] and not owned["two"]
        elif assignment == "every_eligible_player":
            assert len(owned["one"]) == len(owned["two"]) > 0
        else:
            assert owned["one"] and owned["two"]
        assert all(
            game.store.get_world_drop(eid)["owner_player_id"] == owner
            for eid, owner in game._drop_owners.items()
        )
    finally:
        game.store.close()


@pytest.mark.parametrize(
    "claim_policy",
    ["first_valid_claim", "owner_only", "personal", "round_robin", "random_eligible_player"],
)
def test_configured_monster_drop_source_and_world_claim_policy(tmp_path, claim_policy):
    rules = default_rules()
    rules["project_runtime"] = {"start_scene": "Greenvale Fields", "start_position": [232, 300]}
    rules["rewards"]["monster"] = {
        **rules["rewards"]["boss"],
        "drops": {
            "source": "configured",
            "assignment": "random_eligible_player",
            "items": ["potion"],
        },
    }
    rules["world_pickup"]["policy"] = claim_policy
    game = build_project_adapter(
        store=SQLiteMultiplayerStore(tmp_path / "world.sqlite3"), project_path=PROJECT, rules=rules
    )
    try:
        for pid in ("one", "two"):
            game.on_player_joined(pid, pid)
        session = game.players["one"]
        slime = next(e for e, c in session.scene.query(CombatantComponent) if e.name == "Slime 1")
        for pid in ("one", "two"):
            session.combat.pending.append(
                HitEvent(game.players[pid].player.id, slime.id, "punch", "hero")
            )
            game.network_tick(1 / 30)
        session.combat.state(slime).resources.set_current("hp", 1)
        session.combat.pending.append(HitEvent(session.player.id, slime.id, "punch", "hero"))
        game.network_tick(1 / 30)
        drops = [game.store.get_world_drop(eid) for eid in game._drop_owners]
        assert len(drops) == (2 if claim_policy == "personal" else 1)
        assert all(d["item_id"] == "potion" and d["claim_policy"] == claim_policy for d in drops)
        if claim_policy == "first_valid_claim":
            assert all(owner is None for owner in game._drop_owners.values())
        elif claim_policy == "personal":
            assert set(game._drop_owners.values()) == {"one", "two"}
        else:
            assert set(game._drop_owners.values()) <= {"one", "two"}
    finally:
        game.store.close()


def test_configured_drop_source_rejects_unknown_database_items(tmp_path):
    rules = default_rules()
    rules["rewards"]["boss"]["drops"]["source"] = "configured"
    store = SQLiteMultiplayerStore(tmp_path / "world.sqlite3")
    try:
        with pytest.raises(ValueError, match="configured drop item does not exist"):
            build_project_adapter(store=store, project_path=PROJECT, rules=rules)
    finally:
        store.close()


@pytest.mark.parametrize("interaction_path", ["input", "command"])
def test_rapid_turn_uses_current_controller_facing_for_npc_interaction(tmp_path, interaction_path):
    game = adapter(tmp_path)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        session.set_player_position(248, 280)
        session.set_player_facing("down")
        game.handle_input("one", {"move_y": -1})
        game.network_tick(1 / 30)
        from asteria.runtime.character_control import CharacterController2DComponent

        assert session.player.get(CharacterController2DComponent).facing == "up"
        if interaction_path == "command":
            game.handle_command("one", "interact", {})
        else:
            game.handle_input("one", {"interact": 1})
            game.network_tick(1 / 30)
        assert session.pending_dialogue is not None
        assert session.pending_dialogue.line.speaker == "Warrior Trainer"
    finally:
        game.store.close()


def test_authored_mine_door_prepares_side_controller_and_jump(tmp_path):
    from asteria.runtime.character_control import CharacterController2DComponent

    game = adapter(tmp_path, fields=True)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        actor_context = session.save.rpg_state
        controller = session.player.get(CharacterController2DComponent)
        assert controller.mode == "topdown"
        controller.velocity_y = 123
        controller.jump_held = True
        controller.buffer_left = 1
        session.set_player_position(1088, 512)  # Original Mine Gate touch trigger.
        game.network_tick(1 / 30)
        assert session.scene.name == "Rustdeep Mine"
        assert controller.mode == "side"
        assert controller.velocity_y < 123
        assert controller.buffer_left == 0
        assert session.save.rpg_state is actor_context
        assert session.scene.id in session._action_spawn
        for _ in range(30):
            game.network_tick(1 / 30)
        assert controller.grounded
        before = session.player.get(Transform).y
        game.handle_input("one", {"jump": 1})
        game.network_tick(1 / 30)
        assert controller.velocity_y < 0
        assert session.player.get(Transform).y < before
        game.handle_input("one", {})
        session.set_player_position(45, 262)  # Original Mine Exit touch trigger.
        game.network_tick(1 / 30)
        assert session.scene.name == "Greenvale Fields"
        assert controller.mode == "topdown"
        assert controller.velocity_y == 0
    finally:
        game.store.close()


def test_real_death_respawns_at_authoritative_scene_entry(tmp_path):
    game = adapter(tmp_path, fields=True)
    try:
        game.on_player_joined("one", "one")
        session = game.players["one"]
        spawn = session._action_spawn[session.scene.id]
        assert spawn == (232, 300)
        slime = next(e for e, c in session.scene.query(CombatantComponent) if e.name == "Slime 1")
        session.set_player_position(100, 100)
        session.combat.state(session.player).resources.set_current("hp", 1)
        session.combat.pending.append(HitEvent(slime.id, session.player.id, "slime_bite", "enemy"))
        game.network_tick(1 / 30)
        assert session.combat.state(session.player).dead
        assert session.player_down > 0
        for _ in range(80):
            game.network_tick(1 / 30)
        assert not session.combat.state(session.player).dead
        position = session.player.get(Transform)
        assert (position.x, position.y) == spawn
        assert session.combat.state(session.player).resources.current("hp") > 1
    finally:
        game.store.close()
