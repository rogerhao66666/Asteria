"""Transactional SQLite persistence for game-owned multiplayer state and rewards."""

from __future__ import annotations

import json
import random
import sqlite3
import threading
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_SCHEMA_VERSION = 2


class SQLiteMultiplayerStore:
    """Persist player, encounter, inventory, and reward state on the game server.

    Game adapters choose the rules and pass their resolved awards to this store. The store
    provides atomic writes and operation IDs so a repeated network event cannot grant twice.
    """

    def __init__(self, path: str | Path, *, random_source: random.Random | None = None):
        self.path = Path(path).expanduser().resolve()
        if str(path) == ":memory:":
            raise ValueError("SQLiteMultiplayerStore requires a persistent database path")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._closed = False
        self._random = random_source or random.Random()
        self._initialize()

    def _connect(self):
        if self._closed:
            raise RuntimeError("multiplayer store is closed")
        connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    @contextmanager
    def _transaction(self):
        with self._lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _initialize(self):
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=15, isolation_level=None)
            try:
                connection.execute("PRAGMA journal_mode = WAL")
                version = int(connection.execute("PRAGMA user_version").fetchone()[0])
                if version > _SCHEMA_VERSION:
                    raise ValueError("multiplayer database schema is newer than this Asteria")
                connection.executescript(
                    """
                    BEGIN IMMEDIATE;
                    CREATE TABLE IF NOT EXISTS players (
                        player_id TEXT PRIMARY KEY,
                        display_name TEXT NOT NULL,
                        experience INTEGER NOT NULL DEFAULT 0 CHECK (experience >= 0)
                    );
                    CREATE TABLE IF NOT EXISTS player_state (
                        player_id TEXT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
                        namespace TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        PRIMARY KEY (player_id, namespace)
                    );
                    CREATE TABLE IF NOT EXISTS inventory (
                        player_id TEXT NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
                        item_id TEXT NOT NULL,
                        quantity INTEGER NOT NULL CHECK (quantity > 0),
                        PRIMARY KEY (player_id, item_id)
                    );
                    CREATE TABLE IF NOT EXISTS encounters (
                        encounter_id TEXT PRIMARY KEY,
                        encounter_type TEXT NOT NULL,
                        status TEXT NOT NULL CHECK (status IN ('active', 'completed')),
                        result_json TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE TABLE IF NOT EXISTS encounter_state (
                        encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
                        namespace TEXT NOT NULL,
                        state_json TEXT NOT NULL,
                        PRIMARY KEY (encounter_id, namespace)
                    );
                    CREATE TABLE IF NOT EXISTS contributions (
                        encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
                        player_id TEXT NOT NULL REFERENCES players(player_id),
                        damage INTEGER NOT NULL CHECK (damage >= 0),
                        first_event_id TEXT NOT NULL,
                        last_event_id TEXT NOT NULL,
                        PRIMARY KEY (encounter_id, player_id)
                    );
                    CREATE TABLE IF NOT EXISTS reward_grants (
                        reward_id TEXT PRIMARY KEY,
                        encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
                        player_id TEXT NOT NULL REFERENCES players(player_id),
                        reward_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS world_drops (
                        drop_id TEXT PRIMARY KEY,
                        encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
                        item_id TEXT NOT NULL,
                        quantity INTEGER NOT NULL CHECK (quantity > 0),
                        owner_player_id TEXT REFERENCES players(player_id),
                        claimed_by TEXT REFERENCES players(player_id),
                        claim_operation_id TEXT UNIQUE,
                        claim_policy TEXT NOT NULL DEFAULT 'first_valid_claim'
                    );
                    CREATE TABLE IF NOT EXISTS world_drop_eligible (
                        drop_id TEXT NOT NULL REFERENCES world_drops(drop_id) ON DELETE CASCADE,
                        player_id TEXT NOT NULL REFERENCES players(player_id),
                        PRIMARY KEY (drop_id, player_id)
                    );
                    CREATE TABLE IF NOT EXISTS world_drop_claims (
                        drop_id TEXT NOT NULL REFERENCES world_drops(drop_id) ON DELETE CASCADE,
                        player_id TEXT NOT NULL REFERENCES players(player_id),
                        operation_id TEXT NOT NULL UNIQUE,
                        PRIMARY KEY (drop_id, player_id)
                    );
                    CREATE TABLE IF NOT EXISTS processed_operations (
                        operation_id TEXT PRIMARY KEY,
                        operation_type TEXT NOT NULL
                    );
                    PRAGMA user_version = 2;
                    COMMIT;
                    """
                )
                drop_columns = {
                    row[1] for row in connection.execute("PRAGMA table_info(world_drops)")
                }
                if "claim_policy" not in drop_columns:
                    connection.execute(
                        "ALTER TABLE world_drops ADD COLUMN claim_policy TEXT NOT NULL "
                        "DEFAULT 'first_valid_claim'"
                    )
                connection.execute("PRAGMA user_version = 2")
            except Exception:
                if connection.in_transaction:
                    connection.rollback()
                raise
            finally:
                connection.close()

    @staticmethod
    def _required_text(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 160:
            raise ValueError(f"{label} must be non-empty text up to 160 characters")
        return value.strip()

    @staticmethod
    def _json(value: Any) -> str:
        try:
            return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"value must be strict JSON: {exc}") from exc

    @staticmethod
    def _amount(value: int, label: str, *, allow_zero=False) -> int:
        minimum = 0 if allow_zero else 1
        if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
            qualifier = "non-negative" if allow_zero else "positive"
            raise ValueError(f"{label} must be a {qualifier} integer")
        return value

    @staticmethod
    def _record_operation(connection, operation_id: str, operation_type: str) -> bool:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO processed_operations(operation_id, operation_type) "
            "VALUES (?, ?)",
            (operation_id, operation_type),
        )
        return cursor.rowcount == 1

    @staticmethod
    def _require_player(connection, player_id: str):
        if (
            connection.execute(
                "SELECT 1 FROM players WHERE player_id = ?", (player_id,)
            ).fetchone()
            is None
        ):
            raise ValueError(f"player {player_id!r} is not registered")

    def register_player(self, player_id: str, display_name: str) -> None:
        player_id = self._required_text(player_id, "player_id")
        display_name = self._required_text(display_name, "display_name")[:64]
        with self._transaction() as connection:
            connection.execute(
                "INSERT INTO players(player_id, display_name) VALUES (?, ?) "
                "ON CONFLICT(player_id) DO UPDATE SET display_name = excluded.display_name",
                (player_id, display_name),
            )

    def get_player(self, player_id: str) -> dict[str, Any]:
        player_id = self._required_text(player_id, "player_id")
        connection = self._connect()
        try:
            player = connection.execute(
                "SELECT player_id, display_name, experience FROM players WHERE player_id = ?",
                (player_id,),
            ).fetchone()
            if player is None:
                raise KeyError(player_id)
            states = connection.execute(
                "SELECT namespace, state_json FROM player_state WHERE player_id = ?",
                (player_id,),
            ).fetchall()
            inventory = connection.execute(
                "SELECT item_id, quantity FROM inventory WHERE player_id = ? ORDER BY item_id",
                (player_id,),
            ).fetchall()
            return {
                "player_id": player["player_id"],
                "display_name": player["display_name"],
                "experience": int(player["experience"]),
                "game_state": {row["namespace"]: json.loads(row["state_json"]) for row in states},
                "inventory": {row["item_id"]: int(row["quantity"]) for row in inventory},
            }
        finally:
            connection.close()

    def save_player_state(
        self, player_id: str, namespace: str, state: Mapping[str, Any], operation_id: str
    ) -> bool:
        player_id = self._required_text(player_id, "player_id")
        namespace = self._required_text(namespace, "namespace")
        operation_id = self._required_text(operation_id, "operation_id")
        if not isinstance(state, Mapping):
            raise ValueError("player state must be a JSON object")
        encoded = self._json(dict(state))
        with self._transaction() as connection:
            self._require_player(connection, player_id)
            if not self._record_operation(connection, operation_id, "save_player_state"):
                return False
            connection.execute(
                "INSERT INTO player_state(player_id, namespace, state_json) VALUES (?, ?, ?) "
                "ON CONFLICT(player_id, namespace) DO UPDATE SET state_json = excluded.state_json",
                (player_id, namespace, encoded),
            )
            return True

    def award_experience(self, player_id: str, amount: int, operation_id: str) -> bool:
        player_id = self._required_text(player_id, "player_id")
        amount = self._amount(amount, "amount", allow_zero=True)
        operation_id = self._required_text(operation_id, "operation_id")
        with self._transaction() as connection:
            self._require_player(connection, player_id)
            if not self._record_operation(connection, operation_id, "award_experience"):
                return False
            connection.execute(
                "UPDATE players SET experience = experience + ? WHERE player_id = ?",
                (amount, player_id),
            )
            return True

    def begin_encounter(self, encounter_id: str, encounter_type: str) -> bool:
        encounter_id = self._required_text(encounter_id, "encounter_id")
        encounter_type = self._required_text(encounter_type, "encounter_type")
        with self._transaction() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO encounters(encounter_id, encounter_type, status) "
                "VALUES (?, ?, 'active')",
                (encounter_id, encounter_type),
            )
            if cursor.rowcount == 0:
                row = connection.execute(
                    "SELECT encounter_type, status FROM encounters WHERE encounter_id = ?",
                    (encounter_id,),
                ).fetchone()
                if row["encounter_type"] != encounter_type:
                    raise ValueError("encounter_id is already used by another encounter")
            return cursor.rowcount == 1

    def get_encounter(self, encounter_id: str) -> dict[str, Any]:
        encounter_id = self._required_text(encounter_id, "encounter_id")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT encounter_id, encounter_type, status, result_json "
                "FROM encounters WHERE encounter_id = ?",
                (encounter_id,),
            ).fetchone()
            if row is None:
                raise KeyError(encounter_id)
            state_rows = connection.execute(
                "SELECT namespace, state_json FROM encounter_state WHERE encounter_id = ?",
                (encounter_id,),
            ).fetchall()
            return {
                "encounter_id": row["encounter_id"],
                "encounter_type": row["encounter_type"],
                "status": row["status"],
                "result": json.loads(row["result_json"]),
                "game_state": {
                    item["namespace"]: json.loads(item["state_json"]) for item in state_rows
                },
            }
        finally:
            connection.close()

    def save_encounter_state(
        self, encounter_id: str, namespace: str, state: Mapping[str, Any], operation_id: str
    ) -> bool:
        encounter_id = self._required_text(encounter_id, "encounter_id")
        namespace = self._required_text(namespace, "namespace")
        operation_id = self._required_text(operation_id, "operation_id")
        if not isinstance(state, Mapping):
            raise ValueError("encounter state must be a JSON object")
        encoded = self._json(dict(state))
        with self._transaction() as connection:
            encounter = connection.execute(
                "SELECT status FROM encounters WHERE encounter_id = ?", (encounter_id,)
            ).fetchone()
            if encounter is None:
                raise ValueError("encounter is not registered")
            if encounter["status"] != "active":
                raise ValueError("encounter is already completed")
            if not self._record_operation(connection, operation_id, "save_encounter_state"):
                return False
            connection.execute(
                "INSERT INTO encounter_state(encounter_id, namespace, state_json) "
                "VALUES (?, ?, ?) ON CONFLICT(encounter_id, namespace) "
                "DO UPDATE SET state_json = excluded.state_json",
                (encounter_id, namespace, encoded),
            )
            return True

    def record_damage(
        self, encounter_id: str, player_id: str, amount: int, operation_id: str
    ) -> bool:
        encounter_id = self._required_text(encounter_id, "encounter_id")
        player_id = self._required_text(player_id, "player_id")
        amount = self._amount(amount, "amount")
        operation_id = self._required_text(operation_id, "operation_id")
        with self._transaction() as connection:
            self._require_player(connection, player_id)
            encounter = connection.execute(
                "SELECT status FROM encounters WHERE encounter_id = ?", (encounter_id,)
            ).fetchone()
            if encounter is None or encounter["status"] != "active":
                raise ValueError("encounter is not active")
            if not self._record_operation(connection, operation_id, "record_damage"):
                return False
            connection.execute(
                "INSERT INTO contributions(encounter_id, player_id, damage, "
                "first_event_id, last_event_id) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(encounter_id, player_id) DO UPDATE SET "
                "damage = damage + excluded.damage, last_event_id = excluded.last_event_id",
                (encounter_id, player_id, amount, operation_id, operation_id),
            )
            return True

    def get_encounter_contributors(self, encounter_id: str) -> dict[str, int]:
        encounter_id = self._required_text(encounter_id, "encounter_id")
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT player_id, damage FROM contributions WHERE encounter_id = ? "
                "AND damage > 0 ORDER BY player_id",
                (encounter_id,),
            ).fetchall()
            return {row["player_id"]: int(row["damage"]) for row in rows}
        finally:
            connection.close()

    def complete_encounter(
        self,
        encounter_id: str,
        *,
        experience_by_player: Mapping[str, int],
        item_grants: Sequence[Mapping[str, Any]],
        result: Mapping[str, Any] | None = None,
    ) -> bool:
        encounter_id = self._required_text(encounter_id, "encounter_id")
        if not isinstance(experience_by_player, Mapping):
            raise ValueError("experience_by_player must be a mapping")
        if not isinstance(item_grants, Sequence) or isinstance(item_grants, (str, bytes)):
            raise ValueError("item_grants must be a sequence")
        experience = {
            self._required_text(player_id, "player_id"): self._amount(
                amount, "experience", allow_zero=True
            )
            for player_id, amount in experience_by_player.items()
        }
        grants: list[dict[str, Any]] = []
        seen_drop_ids = set()
        for grant in item_grants:
            if not isinstance(grant, Mapping):
                raise ValueError("each item grant must be an object")
            drop_id = self._required_text(grant.get("drop_id"), "drop_id")
            player_id = self._required_text(grant.get("player_id"), "player_id")
            item_id = self._required_text(grant.get("item_id"), "item_id")
            quantity = self._amount(grant.get("quantity"), "quantity")
            if drop_id in seen_drop_ids:
                raise ValueError("item grant drop IDs must be unique")
            seen_drop_ids.add(drop_id)
            grants.append(
                {
                    "drop_id": drop_id,
                    "player_id": player_id,
                    "item_id": item_id,
                    "quantity": quantity,
                }
            )
        result_json = self._json(dict(result or {}))
        with self._transaction() as connection:
            encounter = connection.execute(
                "SELECT status FROM encounters WHERE encounter_id = ?", (encounter_id,)
            ).fetchone()
            if encounter is None:
                raise ValueError("encounter is not registered")
            if encounter["status"] == "completed":
                return False
            for player_id in set(experience) | {item["player_id"] for item in grants}:
                self._require_player(connection, player_id)
            connection.execute(
                "UPDATE encounters SET status = 'completed', result_json = ? "
                "WHERE encounter_id = ? AND status = 'active'",
                (result_json, encounter_id),
            )
            for player_id, amount in experience.items():
                connection.execute(
                    "UPDATE players SET experience = experience + ? WHERE player_id = ?",
                    (amount, player_id),
                )
                reward_id = f"{encounter_id}:xp:{player_id}"
                connection.execute(
                    "INSERT INTO reward_grants "
                    "(reward_id, encounter_id, player_id, reward_type, payload_json) "
                    "VALUES (?, ?, ?, 'experience', ?)",
                    (reward_id, encounter_id, player_id, self._json({"amount": amount})),
                )
            for grant in grants:
                connection.execute(
                    "INSERT INTO inventory(player_id, item_id, quantity) VALUES (?, ?, ?) "
                    "ON CONFLICT(player_id, item_id) DO UPDATE "
                    "SET quantity = quantity + excluded.quantity",
                    (grant["player_id"], grant["item_id"], grant["quantity"]),
                )
                connection.execute(
                    "INSERT INTO reward_grants "
                    "(reward_id, encounter_id, player_id, reward_type, payload_json) "
                    "VALUES (?, ?, ?, 'item', ?)",
                    (
                        grant["drop_id"],
                        encounter_id,
                        grant["player_id"],
                        self._json({"item_id": grant["item_id"], "quantity": grant["quantity"]}),
                    ),
                )
            return True

    def create_world_drop(
        self,
        drop_id: str,
        encounter_id: str,
        item_id: str,
        quantity: int,
        *,
        owner_player_id: str | None = None,
        policy: str = "first_valid_claim",
        eligible_player_ids: Sequence[str] = (),
    ) -> None:
        drop_id = self._required_text(drop_id, "drop_id")
        encounter_id = self._required_text(encounter_id, "encounter_id")
        item_id = self._required_text(item_id, "item_id")
        quantity = self._amount(quantity, "quantity")
        if owner_player_id is not None:
            owner_player_id = self._required_text(owner_player_id, "owner_player_id")
        if not isinstance(policy, str) or policy not in {
            "first_valid_claim",
            "owner_only",
            "personal",
            "round_robin",
            "random_eligible_player",
        }:
            raise ValueError("unsupported world drop claim policy")
        if isinstance(eligible_player_ids, (str, bytes)) or not isinstance(
            eligible_player_ids, Sequence
        ):
            raise ValueError("eligible_player_ids must be a sequence")
        eligible = tuple(
            dict.fromkeys(
                self._required_text(value, "eligible_player_id") for value in eligible_player_ids
            )
        )
        if policy in {"personal", "round_robin", "random_eligible_player"} and not eligible:
            raise ValueError(f"{policy} drops require eligible players")
        if policy == "owner_only" and owner_player_id is None:
            raise ValueError("owner_only drops require an owner_player_id")
        if policy == "personal" and owner_player_id is not None:
            raise ValueError("personal drops do not have a single owner")
        with self._transaction() as connection:
            for player_id in eligible:
                self._require_player(connection, player_id)
            if policy in {"round_robin", "random_eligible_player"}:
                if owner_player_id is not None and owner_player_id not in eligible:
                    raise ValueError("assigned drop owner must be eligible")
                if owner_player_id is None and policy == "random_eligible_player":
                    owner_player_id = self._random.choice(eligible)
                elif owner_player_id is None:
                    index = int(
                        connection.execute(
                            "SELECT COUNT(*) FROM world_drops WHERE encounter_id = ? "
                            "AND claim_policy = 'round_robin'",
                            (encounter_id,),
                        ).fetchone()[0]
                    )
                    owner_player_id = eligible[index % len(eligible)]
            if owner_player_id is not None:
                self._require_player(connection, owner_player_id)
                if eligible and owner_player_id not in eligible:
                    raise ValueError("drop owner must be an eligible player")
            connection.execute(
                "INSERT INTO world_drops(drop_id, encounter_id, item_id, quantity, "
                "owner_player_id, claim_policy) VALUES (?, ?, ?, ?, ?, ?)",
                (drop_id, encounter_id, item_id, quantity, owner_player_id, policy),
            )
            connection.executemany(
                "INSERT INTO world_drop_eligible(drop_id, player_id) VALUES (?, ?)",
                ((drop_id, player_id) for player_id in eligible),
            )

    def claim_world_drop(
        self,
        drop_id: str,
        player_id: str,
        operation_id: str,
        *,
        state_namespace: str | None = None,
        player_state: Mapping[str, Any] | None = None,
    ) -> bool:
        drop_id = self._required_text(drop_id, "drop_id")
        player_id = self._required_text(player_id, "player_id")
        operation_id = self._required_text(operation_id, "operation_id")
        state_json = None
        if (state_namespace is None) != (player_state is None):
            raise ValueError("claim state requires both namespace and player state")
        if player_state is not None:
            state_namespace = self._required_text(state_namespace, "state_namespace")
            if not isinstance(player_state, Mapping):
                raise ValueError("claim player state must be an object")
            state_json = self._json(dict(player_state))
        with self._transaction() as connection:

            def save_claim_state():
                if state_json is not None:
                    connection.execute(
                        "INSERT INTO player_state(player_id, namespace, state_json) "
                        "VALUES (?, ?, ?) ON CONFLICT(player_id, namespace) "
                        "DO UPDATE SET state_json = excluded.state_json",
                        (player_id, state_namespace, state_json),
                    )

            self._require_player(connection, player_id)
            drop = connection.execute(
                "SELECT item_id, quantity, owner_player_id, claimed_by, claim_policy "
                "FROM world_drops WHERE drop_id = ?",
                (drop_id,),
            ).fetchone()
            if drop is None:
                raise KeyError(drop_id)
            if drop["claimed_by"] is not None:
                return False
            if drop["owner_player_id"] not in (None, player_id):
                return False
            eligibility = connection.execute(
                "SELECT 1 FROM world_drop_eligible WHERE drop_id = ? AND player_id = ?",
                (drop_id, player_id),
            ).fetchone()
            has_eligibility_list = connection.execute(
                "SELECT 1 FROM world_drop_eligible WHERE drop_id = ? LIMIT 1", (drop_id,)
            ).fetchone()
            if has_eligibility_list is not None and eligibility is None:
                return False
            if drop["claim_policy"] == "personal":
                already_claimed = connection.execute(
                    "SELECT 1 FROM world_drop_claims WHERE drop_id = ? AND player_id = ?",
                    (drop_id, player_id),
                ).fetchone()
                if already_claimed is not None:
                    return False
            if not self._record_operation(connection, operation_id, "claim_world_drop"):
                return False
            if drop["claim_policy"] == "personal":
                connection.execute(
                    "INSERT INTO world_drop_claims(drop_id, player_id, operation_id) "
                    "VALUES (?, ?, ?)",
                    (drop_id, player_id, operation_id),
                )
                connection.execute(
                    "INSERT INTO inventory(player_id, item_id, quantity) VALUES (?, ?, ?) "
                    "ON CONFLICT(player_id, item_id) DO UPDATE "
                    "SET quantity = quantity + excluded.quantity",
                    (player_id, drop["item_id"], drop["quantity"]),
                )
                connection.execute(
                    "INSERT INTO reward_grants "
                    "(reward_id, encounter_id, player_id, reward_type, payload_json) "
                    "VALUES (?, (SELECT encounter_id FROM world_drops WHERE drop_id = ?), "
                    "?, 'world_drop', ?)",
                    (
                        operation_id,
                        drop_id,
                        player_id,
                        self._json({"item_id": drop["item_id"], "quantity": drop["quantity"]}),
                    ),
                )
                save_claim_state()
                return True
            cursor = connection.execute(
                "UPDATE world_drops SET claimed_by = ?, claim_operation_id = ? "
                "WHERE drop_id = ? AND claimed_by IS NULL "
                "AND (owner_player_id IS NULL OR owner_player_id = ?)",
                (player_id, operation_id, drop_id, player_id),
            )
            if cursor.rowcount != 1:
                return False
            connection.execute(
                "INSERT INTO inventory(player_id, item_id, quantity) VALUES (?, ?, ?) "
                "ON CONFLICT(player_id, item_id) DO UPDATE "
                "SET quantity = quantity + excluded.quantity",
                (player_id, drop["item_id"], drop["quantity"]),
            )
            connection.execute(
                "INSERT INTO reward_grants "
                "(reward_id, encounter_id, player_id, reward_type, payload_json) "
                "SELECT ?, encounter_id, ?, 'world_drop', ? FROM world_drops WHERE drop_id = ?",
                (
                    operation_id,
                    player_id,
                    self._json({"item_id": drop["item_id"], "quantity": drop["quantity"]}),
                    drop_id,
                ),
            )
            save_claim_state()
            return True

    def get_world_drop(self, drop_id: str) -> dict[str, Any]:
        drop_id = self._required_text(drop_id, "drop_id")
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT drop_id, encounter_id, item_id, quantity, owner_player_id, claimed_by, "
                "claim_policy "
                "FROM world_drops WHERE drop_id = ?",
                (drop_id,),
            ).fetchone()
            if row is None:
                raise KeyError(drop_id)
            drop = dict(row)
            drop["claimed_by_players"] = [
                item[0]
                for item in connection.execute(
                    "SELECT player_id FROM world_drop_claims WHERE drop_id = ? ORDER BY player_id",
                    (drop_id,),
                )
            ]
            return drop
        finally:
            connection.close()

    def close(self):
        with self._lock:
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
