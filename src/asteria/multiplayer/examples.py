"""Small adapters that demonstrate the game-authoritative multiplayer API."""

from __future__ import annotations

import math
from collections.abc import Mapping

from .adapter import AdapterUpdate


class SharedCounterAdapter:
    """A tiny shared game state for trying commands from multiple clients."""

    def __init__(self):
        self.counter = 0
        self.players: dict[str, str] = {}

    def _state(self):
        return {
            "counter": self.counter,
            "players": [
                {"player_id": player_id, "display_name": name}
                for player_id, name in sorted(self.players.items())
            ],
        }

    def initial_state(self) -> Mapping[str, object]:
        return self._state()

    def on_player_joined(self, player_id: str, display_name: str) -> AdapterUpdate:
        self.players[player_id] = display_name
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_joined", "player_id": player_id},),
        )

    def handle_command(
        self, player_id: str, command: str, payload: Mapping[str, object]
    ) -> AdapterUpdate:
        if player_id not in self.players:
            raise ValueError("participant is not registered with the game adapter")
        if command != "increment":
            raise ValueError("supported command: increment")
        amount = payload.get("amount", 1)
        if not isinstance(amount, int) or isinstance(amount, bool) or not 1 <= amount <= 1000:
            raise ValueError("increment amount must be an integer from 1 to 1000")
        self.counter += amount
        return AdapterUpdate(
            state=self._state(),
            events=(
                {
                    "type": "counter_incremented",
                    "player_id": player_id,
                    "amount": amount,
                    "value": self.counter,
                },
            ),
        )

    def on_player_left(self, player_id: str) -> AdapterUpdate:
        self.players.pop(player_id, None)
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_left", "player_id": player_id},),
        )


def build_counter_adapter() -> SharedCounterAdapter:
    """Factory spec for the editor: ``asteria.multiplayer.examples:build_counter_adapter``."""
    return SharedCounterAdapter()


class CooperativeMovementAdapter:
    """Small authoritative movement example for multiple real-time clients."""

    network_tick_interval = 1 / 20
    movement_speed = 5.0

    def __init__(self):
        self.players: dict[str, dict[str, object]] = {}
        self.inputs: dict[str, tuple[float, float]] = {}
        self.tick = 0

    def _state(self):
        return {
            "tick": self.tick,
            "players": [
                {
                    "player_id": player_id,
                    "display_name": player["display_name"],
                    "x": round(float(player["x"]), 3),
                    "y": round(float(player["y"]), 3),
                }
                for player_id, player in sorted(self.players.items())
            ],
        }

    def initial_state(self) -> Mapping[str, object]:
        return self._state()

    def on_player_joined(self, player_id: str, display_name: str) -> AdapterUpdate:
        if player_id in self.players:
            raise ValueError("participant is already registered")
        occupied = {(float(player["x"]), float(player["y"])) for player in self.players.values()}
        slot = next(
            (
                index
                for index in range(64)
                if (
                    ((index % 8) - 3.5) * 3.0,
                    (index // 8) * 3.0,
                )
                not in occupied
            ),
            None,
        )
        if slot is None:
            raise ValueError("movement demo supports up to 64 participants")
        self.players[player_id] = {
            "display_name": display_name,
            "x": ((slot % 8) - 3.5) * 3.0,
            "y": (slot // 8) * 3.0,
        }
        self.inputs[player_id] = (0.0, 0.0)
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_joined", "player_id": player_id},),
        )

    def handle_command(
        self, player_id: str, command: str, payload: Mapping[str, object]
    ) -> AdapterUpdate:
        raise ValueError("The movement demo uses input state, not game commands")

    def handle_input(
        self, player_id: str, input_state: Mapping[str, object]
    ) -> AdapterUpdate | None:
        if player_id not in self.players:
            raise ValueError("participant is not registered with the game adapter")
        unexpected = set(input_state) - {"move_x", "move_y"}
        if unexpected:
            raise ValueError("movement input supports only move_x and move_y")

        axes = []
        for name in ("move_x", "move_y"):
            value = input_state.get(name, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be a finite number from -1 to 1")
            axis = float(value)
            if not math.isfinite(axis) or not -1 <= axis <= 1:
                raise ValueError(f"{name} must be a finite number from -1 to 1")
            axes.append(axis)
        x, y = axes
        length = math.hypot(x, y)
        if length > 1:
            x, y = x / length, y / length
        self.inputs[player_id] = (x, y)
        return None

    def on_player_left(self, player_id: str) -> AdapterUpdate:
        self.players.pop(player_id, None)
        self.inputs.pop(player_id, None)
        return AdapterUpdate(
            state=self._state(),
            events=({"type": "player_left", "player_id": player_id},),
        )

    def network_tick(self, dt: float) -> AdapterUpdate | None:
        moved = False
        for player_id, (axis_x, axis_y) in self.inputs.items():
            if not axis_x and not axis_y:
                continue
            player = self.players.get(player_id)
            if player is None:
                continue
            player["x"] = float(player["x"]) + axis_x * self.movement_speed * dt
            player["y"] = float(player["y"]) + axis_y * self.movement_speed * dt
            moved = True
        if not moved:
            return None
        self.tick += 1
        return AdapterUpdate(state=self._state())


def build_movement_adapter() -> CooperativeMovementAdapter:
    """Factory spec for the editor's real-time co-op movement demo."""
    return CooperativeMovementAdapter()
