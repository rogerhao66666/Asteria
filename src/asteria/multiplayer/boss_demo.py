"""Server-authoritative cooperative boss encounter used to exercise real-time adapters."""

from __future__ import annotations

import math
import random
import uuid
from collections.abc import Mapping
from typing import Any

from .adapter import AdapterUpdate
from .rules import default_rules, validate_rules


class CooperativeBossAdapter:
    """Small four-player action encounter with owned inputs and authoritative combat rules."""

    network_tick_interval = 1 / 20
    player_limit = 4
    movement_speed = 4.0
    attack_range = 4.5
    revive_range = 3.0
    player_attack_damage = 12
    player_attack_interval = 0.5
    boss_max_health = 240
    boss_attack_interval_default = 1.5
    boss_damage_default = 16
    experience_per_player_default = 100
    boss_drop_table_default = ("ancient_shard",)

    def __init__(
        self,
        *,
        player_max_health: int = 100,
        boss_damage: int = boss_damage_default,
        boss_attack_interval: float = boss_attack_interval_default,
        player_spawn_spacing: float = 3.0,
        experience_per_player: int = experience_per_player_default,
        boss_drop_table: tuple[str, ...] = boss_drop_table_default,
        random_source: random.Random | None = None,
        store=None,
        rules: Mapping[str, Any] | None = None,
    ):
        if isinstance(player_max_health, bool) or not isinstance(player_max_health, int):
            raise ValueError("player_max_health must be a positive integer")
        if player_max_health <= 0:
            raise ValueError("player_max_health must be a positive integer")
        if isinstance(boss_damage, bool) or not isinstance(boss_damage, int):
            raise ValueError("boss_damage must be a positive integer")
        if boss_damage <= 0:
            raise ValueError("boss_damage must be a positive integer")
        if isinstance(boss_attack_interval, bool):
            raise ValueError("boss_attack_interval must be a positive finite number")
        try:
            boss_attack_interval = float(boss_attack_interval)
        except (TypeError, ValueError) as exc:
            raise ValueError("boss_attack_interval must be a positive finite number") from exc
        if not math.isfinite(boss_attack_interval) or boss_attack_interval <= 0:
            raise ValueError("boss_attack_interval must be a positive finite number")
        if isinstance(player_spawn_spacing, bool):
            raise ValueError("player_spawn_spacing must be a positive finite number")
        try:
            player_spawn_spacing = float(player_spawn_spacing)
        except (TypeError, ValueError) as exc:
            raise ValueError("player_spawn_spacing must be a positive finite number") from exc
        if not math.isfinite(player_spawn_spacing) or player_spawn_spacing <= 0:
            raise ValueError("player_spawn_spacing must be a positive finite number")
        if isinstance(experience_per_player, bool) or not isinstance(experience_per_player, int):
            raise ValueError("experience_per_player must be a non-negative integer")
        if experience_per_player < 0:
            raise ValueError("experience_per_player must be a non-negative integer")
        if isinstance(boss_drop_table, str) or not isinstance(boss_drop_table, tuple):
            raise ValueError("boss_drop_table must be a tuple of item IDs")
        if any(not isinstance(item_id, str) or not item_id for item_id in boss_drop_table):
            raise ValueError("boss_drop_table must contain non-empty item IDs")

        self.player_max_health = player_max_health
        self.boss_damage = boss_damage
        self.boss_attack_interval = boss_attack_interval
        self.player_spawn_spacing = player_spawn_spacing
        resolved_rules = validate_rules(default_rules() if rules is None else rules)
        boss_rules = resolved_rules["rewards"]["boss"]
        self._ground_policy = resolved_rules["world_pickup"]["policy"]
        self.reward_eligibility = boss_rules["eligibility"]
        self.drop_assignment = boss_rules["drops"]["assignment"]
        self.experience_per_player = (
            int(boss_rules["experience"]["amount"]) if rules is not None else experience_per_player
        )
        self.boss_drop_table = (
            tuple(boss_rules["drops"]["items"]) if rules is not None else boss_drop_table
        )
        self._random = random_source or random.Random()
        self.players: dict[str, dict[str, Any]] = {}
        self.inputs: dict[str, dict[str, float | bool]] = {}
        self.threat: dict[str, int] = {}
        self.damage_contribution: dict[str, int] = {}
        self._experience: dict[str, int] = {}
        self._next_attack_at: dict[str, float] = {}
        self._elapsed = 0.0
        self._boss_attack_elapsed = 0.0
        self._boss_health = self.boss_max_health
        self._phase = 1
        self._tick = 0
        self._boss_defeated = False
        self._inventory = {}
        self._kill_credit = None
        self._combat_log = []
        self._ground_drop_created = False
        self._ground_drop_id = None
        self.store = store
        self.encounter_id = uuid.uuid4().hex
        if self.store is not None:
            self.store.begin_encounter(self.encounter_id, "cooperative_boss")

    def configure_multiplayer(self, *, store=None, rules=None):
        """Attach optional persistence before participants join."""
        if self.players:
            raise RuntimeError("multiplayer persistence must be configured before players join")
        if store is not None and self.store is not store:
            self.store = store
            self.store.begin_encounter(self.encounter_id, "cooperative_boss")
        if rules is not None:
            resolved_rules = validate_rules(rules)
            boss_rules = resolved_rules["rewards"]["boss"]
            self._ground_policy = resolved_rules["world_pickup"]["policy"]
            self.reward_eligibility = boss_rules["eligibility"]
            self.experience_per_player = int(boss_rules["experience"]["amount"])
            self.drop_assignment = boss_rules["drops"]["assignment"]
            self.boss_drop_table = tuple(boss_rules["drops"]["items"])

    def _state(self) -> dict[str, Any]:
        alive = not self._boss_defeated
        return {
            "tick": self._tick,
            "phase": self._phase,
            "kill_credit": self._kill_credit,
            "combat_log": list(self._combat_log),
            "world_drops": (
                [
                    dict(
                        self.store.get_world_drop(self._ground_drop_id)
                        if self._ground_drop_created
                        else {
                            "drop_id": self._ground_drop_id,
                            "item_id": "healing_crystal",
                            "quantity": 1,
                            "claimed_by": None,
                            "claimed_by_players": [],
                            "claim_policy": self._ground_policy,
                        },
                        x=0.0,
                        y=0.0,
                    )
                ]
                if self.store is not None and self._ground_drop_id
                else []
            ),
            "boss": {
                "id": "cooperative_boss",
                "x": 0.0,
                "y": 0.0,
                "hp": self._boss_health,
                "max_hp": self.boss_max_health,
                "alive": alive,
                "target_player_id": self._target_player_id(),
            },
            "players": [
                {
                    "player_id": player_id,
                    "display_name": player["display_name"],
                    "x": round(float(player["x"]), 3),
                    "y": round(float(player["y"]), 3),
                    "hp": int(player["hp"]),
                    "max_hp": self.player_max_health,
                    "downed": bool(player["downed"]),
                    "experience": int(self._experience.get(player_id, 0)),
                    "damage_contribution": self.damage_contribution.get(player_id, 0),
                    "inventory": (
                        self.store.get_player(player_id)["inventory"]
                        if self.store is not None
                        else dict(self._inventory.get(player_id, {}))
                    ),
                }
                for player_id, player in sorted(self.players.items())
            ],
        }

    def initial_state(self) -> Mapping[str, Any]:
        return self._state()

    def on_player_joined(self, player_id: str, display_name: str) -> AdapterUpdate:
        if self._boss_defeated:
            raise ValueError("The boss encounter is complete")
        if player_id in self.players:
            raise ValueError("participant is already registered")
        if len(self.players) >= self.player_limit:
            raise ValueError("the boss demo supports up to four players")
        spacing = self.player_spawn_spacing
        spawn_positions = (
            (-spacing, 0.0),
            (spacing, 0.0),
            (0.0, -spacing),
            (0.0, spacing),
        )
        occupied = {(float(player["x"]), float(player["y"])) for player in self.players.values()}
        spawn = next((position for position in spawn_positions if position not in occupied), None)
        if spawn is None:
            raise ValueError("the boss demo has no free player spawn")
        x, y = spawn
        self.players[player_id] = {
            "display_name": str(display_name),
            "x": x,
            "y": y,
            "hp": self.player_max_health,
            "downed": False,
        }
        if self.store is not None:
            self.store.register_player(player_id, str(display_name))
            self._experience[player_id] = int(self.store.get_player(player_id)["experience"])
        self._experience.setdefault(player_id, 0)
        self.players[player_id]["experience"] = self._experience[player_id]
        if self.store is not None and self._ground_drop_id is None:
            self._ground_drop_id = f"{self.encounter_id}:ground:0"

        self.inputs[player_id] = {"move_x": 0.0, "move_y": 0.0, "attack": False}
        self.threat[player_id] = 0
        self._next_attack_at[player_id] = 0.0
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_joined", "player_id": player_id},),
        )

    def handle_input(self, player_id: str, input_state: Mapping[str, Any]) -> AdapterUpdate | None:
        if player_id not in self.players:
            raise ValueError("participant is not registered with the game adapter")
        if self.players[player_id]["downed"]:
            raise ValueError("downed players cannot send actions")
        unexpected = set(input_state) - {"move_x", "move_y", "attack"}
        if unexpected:
            raise ValueError("boss demo input supports move_x, move_y, and attack")
        axes = []
        for name in ("move_x", "move_y"):
            value = input_state.get(name, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number from -1 to 1")
            axis = float(value)
            if not math.isfinite(axis) or not -1 <= axis <= 1:
                raise ValueError(f"{name} must be a finite number from -1 to 1")
            axes.append(axis)
        attack = input_state.get("attack", False)
        if not isinstance(attack, bool):
            raise ValueError("attack must be a boolean")
        move_x, move_y = axes
        length = math.hypot(move_x, move_y)
        if length > 1:
            move_x, move_y = move_x / length, move_y / length
        self.inputs[player_id] = {
            "move_x": move_x,
            "move_y": move_y,
            "attack": attack,
        }
        return None

    def handle_command(
        self, player_id: str, command: str, payload: Mapping[str, Any]
    ) -> AdapterUpdate:
        player = self.players.get(player_id)
        if player is None:
            raise ValueError("participant is not registered with the game adapter")
        if player["downed"]:
            raise ValueError("downed players cannot issue commands")
        if command == "pickup":
            if self.store is None or not self._ground_drop_id:
                raise ValueError("no ground drop is available")
            if self._distance(player, {"x": 0.0, "y": 0.0}) > self.revive_range:
                raise ValueError("drop is too far away")
            operation_id = payload.get("operation_id")
            if not isinstance(operation_id, str) or not operation_id or len(operation_id) > 160:
                raise ValueError("operation_id is required")
            if not self._ground_drop_created:
                eligible = sorted(self.players)
                self.store.create_world_drop(
                    self._ground_drop_id,
                    self.encounter_id,
                    "healing_crystal",
                    1,
                    policy=self._ground_policy,
                    eligible_player_ids=eligible,
                    owner_player_id=eligible[0] if self._ground_policy == "owner_only" else None,
                )
                self._ground_drop_created = True
            claimed = self.store.claim_world_drop(
                self._ground_drop_id, player_id, f"{player_id}:{operation_id}"
            )
            return AdapterUpdate(
                state=self._state(),
                events=(
                    {
                        "type": "pickup_result",
                        "player_id": player_id,
                        "accepted": claimed,
                        "drop_id": self._ground_drop_id,
                    },
                ),
            )
        if command != "revive":
            raise ValueError("supported boss demo command: revive")
        target_id = payload.get("target_player_id")
        if not isinstance(target_id, str) or not target_id:
            raise ValueError("target_player_id is required")
        target = self.players.get(target_id)
        if target is None or target_id == player_id:
            raise ValueError("target must be another participant")
        if not target["downed"]:
            raise ValueError("target player is not downed")
        if self._distance(player, target) > self.revive_range:
            raise ValueError("target player is too far away to revive")
        target["hp"] = max(1, math.ceil(self.player_max_health * 0.4))
        target["downed"] = False
        self.inputs[target_id] = {"move_x": 0.0, "move_y": 0.0, "attack": False}
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_revived", "player_id": target_id, "by": player_id},),
        )

    def on_player_left(self, player_id: str) -> AdapterUpdate:
        self.players.pop(player_id, None)
        self.inputs.pop(player_id, None)
        self.threat.pop(player_id, None)
        self._next_attack_at.pop(player_id, None)
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_left", "player_id": player_id},),
        )

    @staticmethod
    def _distance(first: Mapping[str, Any], second: Mapping[str, Any]) -> float:
        return math.hypot(
            float(first["x"]) - float(second["x"]), float(first["y"]) - float(second["y"])
        )

    def _target_player_id(self) -> str | None:
        living = [player_id for player_id, player in self.players.items() if not player["downed"]]
        if not living:
            return None
        return min(
            living,
            key=lambda player_id: (
                -self.threat.get(player_id, 0),
                self._distance(self.players[player_id], {"x": 0.0, "y": 0.0}),
                player_id,
            ),
        )

    def _apply_player_attack(self, player_id: str, events: list[dict[str, Any]]) -> None:
        player = self.players[player_id]
        if player["downed"] or self._distance(player, {"x": 0.0, "y": 0.0}) > self.attack_range:
            return
        if self._elapsed < self._next_attack_at[player_id]:
            return
        self._next_attack_at[player_id] = self._elapsed + self.player_attack_interval
        self._boss_health = max(0, self._boss_health - self.player_attack_damage)
        self._combat_log.append(
            {
                "order": len(self._combat_log) + 1,
                "tick": self._tick,
                "player_id": player_id,
                "boss_hp": self._boss_health,
            }
        )
        self.threat[player_id] += self.player_attack_damage
        self.damage_contribution[player_id] = (
            self.damage_contribution.get(player_id, 0) + self.player_attack_damage
        )
        if self.store is not None:
            self.store.record_damage(
                self.encounter_id,
                player_id,
                self.player_attack_damage,
                f"{self.encounter_id}:hit:{self._tick}:{player_id}",
            )
        events.append(
            {
                "type": "boss_hit",
                "player_id": player_id,
                "damage": self.player_attack_damage,
                "boss_hp": self._boss_health,
            }
        )
        new_phase = (
            3
            if self._boss_health <= self.boss_max_health / 3
            else (2 if self._boss_health <= self.boss_max_health * 2 / 3 else 1)
        )
        if new_phase > self._phase:
            self._phase = new_phase
            events.append({"type": "boss_phase", "phase": self._phase})
        if self._boss_health == 0:
            self._kill_credit = player_id
            self._boss_defeated = True
            events.append({"type": "boss_defeated", "boss_id": "cooperative_boss"})
            if self.reward_eligibility == "any_session_participant":
                eligible_players = sorted(self.players)
            else:
                eligible_players = sorted(
                    player_id
                    for player_id, damage in self.damage_contribution.items()
                    if damage > 0
                )
            item_grants = []
            for drop_index, item_id in enumerate(self.boss_drop_table):
                if not eligible_players:
                    break
                if self.drop_assignment == "random_eligible_player":
                    recipients = [self._random.choice(eligible_players)]
                elif self.drop_assignment == "highest_damage_player":
                    recipient = max(
                        eligible_players,
                        key=lambda key: (self.damage_contribution.get(key, 0), key),
                    )
                    recipients = [recipient]
                else:
                    recipients = eligible_players
                for recipient_id in recipients:
                    item_grants.append(
                        {
                            "drop_id": (
                                f"{self.encounter_id}:drop:{drop_index}:{recipient_id}"
                                if len(recipients) > 1
                                else f"{self.encounter_id}:drop:{drop_index}"
                            ),
                            "player_id": recipient_id,
                            "item_id": item_id,
                            "quantity": 1,
                        }
                    )
            if self.store is not None:
                self.store.complete_encounter(
                    self.encounter_id,
                    experience_by_player={
                        player_id: self.experience_per_player for player_id in eligible_players
                    },
                    item_grants=item_grants,
                    result={
                        "boss_id": "cooperative_boss",
                        "status": "defeated",
                        "kill_credit": player_id,
                        "combat_log": list(self._combat_log),
                    },
                )
            for reward_id in eligible_players:
                self._experience[reward_id] = (
                    self._experience.get(reward_id, 0) + self.experience_per_player
                )
                reward_player = self.players.get(reward_id)
                if reward_player is not None:
                    reward_player["experience"] = self._experience[reward_id]
                events.append(
                    {
                        "type": "experience_awarded",
                        "player_id": reward_id,
                        "amount": self.experience_per_player,
                    }
                )
            for grant in item_grants:
                inventory = self._inventory.setdefault(grant["player_id"], {})
                inventory[grant["item_id"]] = (
                    inventory.get(grant["item_id"], 0) + grant["quantity"]
                )
                events.append(
                    {
                        "type": "loot_awarded",
                        "player_id": grant["player_id"],
                        "item_id": grant["item_id"],
                        "quantity": grant["quantity"],
                        "drop_id": grant["drop_id"],
                    }
                )

    def _apply_boss_attack(self, events: list[dict[str, Any]]) -> None:
        if self._boss_defeated or self._boss_attack_elapsed < self.boss_attack_interval:
            return
        self._boss_attack_elapsed = 0.0
        target_id = self._target_player_id()
        if target_id is None:
            return
        if self._phase >= 3:
            targets = [
                player_id
                for player_id, player in sorted(self.players.items())
                if not player["downed"] and self._distance(player, {"x": 0.0, "y": 0.0}) <= 6.0
            ]
        else:
            targets = [target_id]
        for player_id in targets:
            player = self.players[player_id]
            player["hp"] = max(0, int(player["hp"]) - self.boss_damage)
            self.threat[player_id] += 1
            events.append(
                {
                    "type": "boss_attack",
                    "target_player_id": player_id,
                    "damage": self.boss_damage,
                    "phase": self._phase,
                }
            )
            if player["hp"] == 0:
                player["downed"] = True
                self.inputs[player_id] = {
                    "move_x": 0.0,
                    "move_y": 0.0,
                    "attack": False,
                }
                events.append({"type": "player_downed", "player_id": player_id})

    def network_tick(self, dt: float) -> AdapterUpdate:
        if isinstance(dt, bool) or not isinstance(dt, (int, float)):
            raise ValueError("dt must be a positive finite number")
        dt = float(dt)
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be a positive finite number")
        self._tick += 1
        self._elapsed += dt
        self._boss_attack_elapsed += dt
        for player_id, input_state in self.inputs.items():
            player = self.players.get(player_id)
            if player is None or player["downed"]:
                continue
            x = float(input_state["move_x"])
            y = float(input_state["move_y"])
            player["x"] = max(-20.0, min(20.0, float(player["x"]) + x * self.movement_speed * dt))
            player["y"] = max(-20.0, min(20.0, float(player["y"]) + y * self.movement_speed * dt))
        events: list[dict[str, Any]] = []
        for player_id, input_state in self.inputs.items():
            if input_state["attack"] and not self._boss_defeated:
                self._apply_player_attack(player_id, events)
        self._apply_boss_attack(events)
        return AdapterUpdate(state=self._state(), events=tuple(events))


def build_boss_adapter(*, store=None, rules=None) -> CooperativeBossAdapter:
    """Factory spec for the editor: ``asteria.multiplayer.boss_demo:build_boss_adapter``."""
    return CooperativeBossAdapter(store=store, rules=rules)
