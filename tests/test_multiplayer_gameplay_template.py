"""The loadable sample exposes server-owned rewards, claims and kill attribution."""

import random

from asteria.multiplayer.boss_demo import CooperativeBossAdapter
from asteria.multiplayer.persistence import SQLiteMultiplayerStore
from asteria.multiplayer.rules import default_rules


def test_four_player_template_publishes_inventory_kill_credit_and_ordered_hits(tmp_path):
    path = tmp_path / "server.sqlite3"
    store = SQLiteMultiplayerStore(path)
    adapter = CooperativeBossAdapter(store=store, random_source=random.Random(7))
    ids = ["one", "two", "three", "four"]
    try:
        for player_id in ids:
            adapter.on_player_joined(player_id, player_id)
            adapter.handle_input(player_id, {"attack": True})
        for _ in range(80):
            state = adapter.network_tick(0.05).state
            if not state["boss"]["alive"]:
                break
        assert not state["boss"]["alive"]
        assert all(p["experience"] == 100 for p in state["players"])
        assert state["kill_credit"] in ids
        assert [hit["order"] for hit in state["combat_log"]] == list(
            range(1, len(state["combat_log"]) + 1)
        )
        assert state["combat_log"][-1]["player_id"] == state["kill_credit"]
        inventories = {p["player_id"]: p["inventory"] for p in state["players"]}
        assert sum(bag.get("ancient_shard", 0) for bag in inventories.values()) == 1
        assert all(p["damage_contribution"] > 0 for p in state["players"])
        results = [
            adapter.handle_command(p, "pickup", {"operation_id": p}).events[0]["accepted"]
            for p in ids
        ]
        assert results == [True, False, False, False]
        assert not adapter.handle_command("one", "pickup", {"operation_id": "one"}).events[0][
            "accepted"
        ]
        assert store.get_player("one")["inventory"]["healing_crystal"] == 1
    finally:
        store.close()
    with SQLiteMultiplayerStore(path) as reopened:
        assert all(reopened.get_player(p)["experience"] == 100 for p in ids)
        assert reopened.get_player("one")["inventory"]["healing_crystal"] == 1


def test_project_template_can_give_personal_treasure_and_boss_items_to_every_contributor(tmp_path):
    rules = default_rules()
    rules["world_pickup"]["policy"] = "personal"
    rules["rewards"]["boss"]["drops"]["assignment"] = "every_eligible_player"
    rules["rewards"]["boss"]["experience"]["amount"] = 250
    with SQLiteMultiplayerStore(tmp_path / "server.sqlite3") as store:
        adapter = CooperativeBossAdapter(store=store, rules=rules)
        for p in ["one", "two"]:
            adapter.on_player_joined(p, p)
        for p in ["one", "two"]:
            assert adapter.handle_command(p, "pickup", {"operation_id": p}).events[0]["accepted"]
            adapter.handle_input(p, {"attack": True})
        for _ in range(150):
            state = adapter.network_tick(0.05).state
            if not state["boss"]["alive"]:
                break
        assert all(p["experience"] == 250 for p in state["players"])
        assert all(
            p["inventory"] == {"ancient_shard": 1, "healing_crystal": 1} for p in state["players"]
        )
