"""Interfaces game-specific authoritative rules plug into."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AdapterUpdate:
    """Authoritative state and events produced by a game adapter update."""

    state: Mapping[str, Any] | None = None
    events: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.state is not None and not isinstance(self.state, Mapping):
            raise TypeError("state must be a mapping or None")
        if any(not isinstance(event, Mapping) for event in self.events):
            raise TypeError("events must contain mappings")


class GameNetworkAdapter(Protocol):
    """Server-side game rules; the transport never decides game outcomes.

    Implement ``handle_command`` to validate and apply a game-specific command. The returned
    update is broadcast by the server as authoritative state and events.
    """

    def initial_state(self) -> Mapping[str, Any] | None:
        """Return the initial serializable state for a joining participant."""
        ...

    def on_player_joined(self, player_id: str, display_name: str) -> AdapterUpdate | None:
        """Apply game-specific join behavior and return any resulting state/events."""
        ...

    def handle_command(
        self, player_id: str, command: str, payload: Mapping[str, Any]
    ) -> AdapterUpdate:
        """Validate/apply one command, raising ``ValueError`` to reject it."""
        ...

    def on_player_left(self, player_id: str) -> AdapterUpdate | None:
        """Apply game-specific leave behavior."""
        ...


class TickableGameNetworkAdapter(GameNetworkAdapter, Protocol):
    """Optional extension for real-time games that advance on the authoritative server."""

    network_tick_interval: float

    def network_tick(self, dt: float) -> AdapterUpdate | None:
        """Advance one fixed server step and return state/events to publish, if any."""
        ...


class InputGameNetworkAdapter(GameNetworkAdapter, Protocol):
    """Optional extension for adapters that consume real-time per-player input state.

    The server calls handle_input with the latest held buttons or axes from one participant.
    Adapters usually store that input and consume it from network_tick.
    """

    def handle_input(self, player_id: str, input_state: Mapping[str, Any]) -> AdapterUpdate | None:
        """Validate and store a participant's latest input state."""
        ...
