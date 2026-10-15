"""Durable server-side state shared by multiplayer game adapters."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from asteria.multiplayer.persistence import SQLiteMultiplayerStore


def test_player_state_survives_store_reopen(tmp_path):
    database = tmp_path / "session.sqlite3"
    store = SQLiteMultiplayerStore(database)
    store.register_player("guest-one", "One")
    assert store.save_player_state("guest-one", "demo", {"quest": 2}, "op-state-1")
    assert store.award_experience("guest-one", 100, "op-xp-1")
    store.close()

    reopened = SQLiteMultiplayerStore(database)
    assert reopened.get_player("guest-one") == {
        "player_id": "guest-one",
        "display_name": "One",
        "experience": 100,
        "game_state": {"demo": {"quest": 2}},
        "inventory": {},
    }
    reopened.close()


def test_encounter_damage_and_awards_are_idempotent(tmp_path):
    store = SQLiteMultiplayerStore(tmp_path / "session.sqlite3")
    for player_id in ("p1", "p2", "p3"):
        store.register_player(player_id, player_id)
    store.begin_encounter("boss-1", "cooperative_boss")
    assert store.record_damage("boss-1", "p1", 12, "hit-1")
    assert store.record_damage("boss-1", "p2", 12, "hit-2")
    assert not store.record_damage("boss-1", "p1", 12, "hit-1")
    assert store.get_encounter_contributors("boss-1") == {"p1": 12, "p2": 12}

    awards = store.complete_encounter(
        "boss-1",
        experience_by_player={"p1": 100, "p2": 100},
        item_grants=[
            {
                "drop_id": "boss-1:drop:0",
                "player_id": "p2",
                "item_id": "ancient_shard",
                "quantity": 1,
            }
        ],
    )
    assert awards
    assert not store.complete_encounter(
        "boss-1",
        experience_by_player={"p1": 100, "p2": 100},
        item_grants=[
            {
                "drop_id": "boss-1:drop:0",
                "player_id": "p2",
                "item_id": "ancient_shard",
                "quantity": 1,
            }
        ],
    )
    assert store.get_player("p1")["experience"] == 100
    assert store.get_player("p2")["experience"] == 100
    assert store.get_player("p3")["experience"] == 0
    assert store.get_player("p2")["inventory"] == {"ancient_shard": 1}
    store.close()


def test_only_one_player_can_atomically_claim_a_shared_drop(tmp_path):
    store = SQLiteMultiplayerStore(tmp_path / "session.sqlite3")
    store.register_player("p1", "One")
    store.register_player("p2", "Two")
    store.begin_encounter("field-1", "slime")
    store.create_world_drop("field-1:drop:0", "field-1", "gel", 1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        claimed = list(
            pool.map(
                lambda player_id: store.claim_world_drop(
                    "field-1:drop:0", player_id, f"claim-{player_id}"
                ),
                ("p1", "p2"),
            )
        )

    assert sorted(claimed) == [False, True]
    winners = [
        player_id
        for player_id in ("p1", "p2")
        if store.get_player(player_id)["inventory"] == {"gel": 1}
    ]
    assert len(winners) == 1
    assert store.get_world_drop("field-1:drop:0")["claimed_by"] == winners[0]
    store.close()


def test_failed_reward_transaction_leaves_encounter_and_profiles_unchanged(tmp_path):
    store = SQLiteMultiplayerStore(tmp_path / "session.sqlite3")
    store.register_player("p1", "One")
    store.begin_encounter("boss-1", "cooperative_boss")

    with pytest.raises(ValueError, match="registered"):
        store.complete_encounter(
            "boss-1",
            experience_by_player={"p1": 100, "missing": 100},
            item_grants=[],
        )

    assert store.get_player("p1")["experience"] == 0
    assert store.get_encounter("boss-1")["status"] == "active"
    store.close()


def test_player_state_rejects_non_finite_json(tmp_path):
    store = SQLiteMultiplayerStore(tmp_path / "session.sqlite3")
    store.register_player("p1", "One")

    with pytest.raises(ValueError, match="JSON"):
        store.save_player_state("p1", "demo", {"value": float("nan")}, "op-nan")
    assert store.get_player("p1")["game_state"] == {}
    store.close()


def test_personal_drops_are_claimable_once_by_each_eligible_player(tmp_path):
    store = SQLiteMultiplayerStore(tmp_path / "session.sqlite3")
    for player_id in ("p1", "p2", "p3"):
        store.register_player(player_id, player_id)
    store.begin_encounter("field-2", "treasure")
    store.create_world_drop(
        "personal-1",
        "field-2",
        "potion",
        1,
        policy="personal",
        eligible_player_ids=("p1", "p2"),
    )

    assert store.claim_world_drop("personal-1", "p1", "personal-p1")
    assert not store.claim_world_drop("personal-1", "p1", "personal-p1-again")
    assert not store.claim_world_drop("personal-1", "p3", "personal-p3")
    assert store.claim_world_drop("personal-1", "p2", "personal-p2")
    assert store.get_player("p1")["inventory"] == {"potion": 1}
    assert store.get_player("p2")["inventory"] == {"potion": 1}
    assert store.get_player("p3")["inventory"] == {}
    store.close()


def test_random_and_round_robin_drops_are_assigned_by_the_server(tmp_path):
    import random

    store = SQLiteMultiplayerStore(tmp_path / "session.sqlite3", random_source=random.Random(4))
    for player_id in ("p1", "p2"):
        store.register_player(player_id, player_id)
    store.begin_encounter("field-3", "loot")
    store.create_world_drop(
        "random-1",
        "field-3",
        "coin",
        1,
        policy="random_eligible_player",
        eligible_player_ids=("p1", "p2"),
    )
    random_owner = store.get_world_drop("random-1")["owner_player_id"]
    assert random_owner in {"p1", "p2"}
    assert store.claim_world_drop("random-1", random_owner, "random-claim")

    store.create_world_drop(
        "round-1",
        "field-3",
        "coin",
        1,
        policy="round_robin",
        eligible_player_ids=("p1", "p2"),
    )
    store.create_world_drop(
        "round-2",
        "field-3",
        "coin",
        1,
        policy="round_robin",
        eligible_player_ids=("p1", "p2"),
    )
    assert store.get_world_drop("round-1")["owner_player_id"] == "p1"
    assert store.get_world_drop("round-2")["owner_player_id"] == "p2"
    assert not store.claim_world_drop("round-1", "p2", "round-wrong-player")
    store.close()


def test_owner_only_drop_requires_registered_owner_and_migrates_v1_schema(tmp_path):
    import sqlite3

    database = tmp_path / "old.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE world_drops (
            drop_id TEXT PRIMARY KEY,
            encounter_id TEXT NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            owner_player_id TEXT,
            claimed_by TEXT,
            claim_operation_id TEXT UNIQUE
        );
        PRAGMA user_version = 1;
        """
    )
    connection.close()

    store = SQLiteMultiplayerStore(database)
    store.register_player("p1", "One")
    store.register_player("p2", "Two")
    store.begin_encounter("field-4", "owner-loot")
    store.create_world_drop(
        "owner-1", "field-4", "key", 1, policy="owner_only", owner_player_id="p1"
    )
    assert not store.claim_world_drop("owner-1", "p2", "owner-wrong")
    assert store.claim_world_drop("owner-1", "p1", "owner-correct")
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 2
    connection.close()
    store.close()


def test_claim_and_character_bag_are_committed_in_one_transaction(tmp_path):
    import sqlite3

    path = tmp_path / "atomic.sqlite3"
    with SQLiteMultiplayerStore(path) as store:
        store.register_player("one", "One")
        store.begin_encounter("fight", "boss")
        store.create_world_drop("drop", "fight", "sword", 1)
        connection = sqlite3.connect(path)
        connection.execute(
            "CREATE TRIGGER reject_profile BEFORE INSERT ON player_state "
            "BEGIN SELECT RAISE(ABORT, 'profile blocked'); END"
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            store.claim_world_drop(
                "drop",
                "one",
                "operation",
                state_namespace="game",
                player_state={"bag": ["sword-instance"]},
            )
        assert store.get_world_drop("drop")["claimed_by"] is None
        assert store.get_player("one")["inventory"] == {}
        connection.execute("DROP TRIGGER reject_profile")
        connection.commit()
        connection.close()
        assert store.claim_world_drop(
            "drop",
            "one",
            "operation",
            state_namespace="game",
            player_state={"bag": ["sword-instance"]},
        )
    with SQLiteMultiplayerStore(path) as reopened:
        assert reopened.get_player("one")["game_state"]["game"]["bag"] == ["sword-instance"]
        assert reopened.get_player("one")["inventory"] == {"sword": 1}
