"""Optional Multiplayer-session bridge for playable project previews.

The project-owned connection profile opts a preview into an existing session. This adapter stays
outside the game model: the server remains authoritative for its network state while ordinary
projects and projects without the opt-in flag keep their offline path.
"""

from __future__ import annotations

import json
import math
import threading
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from asteria.multiplayer.client import MultiplayerClient, MultiplayerClientError
from asteria.multiplayer.protocol import clean_guest_id
from asteria.multiplayer.smoothing import SnapshotInterpolator

PROFILE_SCHEMA = "asteria.multiplayer.profile"
PROFILE_VERSION = 1
INPUT_SEND_INTERVAL = 1 / 20
INPUT_RESEND_DELAY = 1 / 30  # longer than the server's 1 / 60 s input window


def load_runtime_multiplayer_profile(resource_root: str | Path) -> dict[str, Any] | None:
    """Load an opted-in project connection profile; absent or disabled profiles remain offline."""
    path = Path(resource_root) / ".asteria" / "multiplayer.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=lambda constant: (_ for _ in ()).throw(
                ValueError(f"non-finite JSON value: {constant}")
            ),
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"could not read multiplayer profile: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("multiplayer profile must be a JSON object")
    if value.get("schema") != PROFILE_SCHEMA or value.get("version") != PROFILE_VERSION:
        raise ValueError("unsupported multiplayer profile schema")
    enabled = value.get("connect_on_run", False)
    if not isinstance(enabled, bool):
        raise ValueError("connect_on_run must be a boolean")
    if not enabled:
        return None

    address = value.get("server_address", "127.0.0.1")
    if not isinstance(address, str) or not address.strip() or len(address) > 255:
        raise ValueError("server address must be a non-empty host name or IP address")
    port = value.get("port", 8765)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("multiplayer profile port must be an integer from 1 to 65535")
    player_name = value.get("player_name", "Player")
    if not isinstance(player_name, str) or not player_name.strip() or len(player_name) > 32:
        raise ValueError("multiplayer profile player name must contain 1 to 32 characters")
    guest_id = clean_guest_id(value.get("guest_id"))
    return {
        **value,
        "server_address": address.strip(),
        "port": port,
        "player_name": player_name.strip(),
        "guest_id": guest_id,
    }


class MultiplayerPreviewBridge:
    """Thread-safe view of an authoritative multiplayer adapter for a playable runtime."""

    def __init__(
        self,
        profile: Mapping[str, Any],
        *,
        client_factory=MultiplayerClient,
        clock=time.monotonic,
    ):
        self.profile = dict(profile)
        self._client_factory = client_factory
        self._clock = clock
        self._client: MultiplayerClient | None = None
        self._state: dict[str, Any] = {}
        self._events: tuple[dict[str, Any], ...] = ()
        self._revision = 0
        self._remote_interpolator = SnapshotInterpolator(delay=0.1, max_extrapolation=0.1)
        self._last_input_sequence = 0
        self._acked_input_sequence = 0
        self._acked_input_revision = -1
        self._lock = threading.RLock()
        self._last_input_at = 0.0
        self._last_input_state = None  # the newest input sent, for a rate-limit resend
        self._pending_commands = {}
        self._command_results = []
        self.error = ""

    @property
    def connected(self) -> bool:
        with self._lock:
            client = self._client
        return client is not None and client.connected

    @property
    def player_id(self) -> str | None:
        with self._lock:
            client = self._client
        return None if client is None else client.player_id

    @property
    def state(self) -> dict[str, Any]:
        with self._lock:
            return json.loads(json.dumps(self._state, allow_nan=False))

    def snapshot(self):
        """Read the scene, events and revision as one consistent publication."""
        with self._lock:
            return (
                json.loads(json.dumps(self._state, allow_nan=False)),
                tuple(json.loads(json.dumps(event, allow_nan=False)) for event in self._events),
                self._revision,
            )

    @property
    def events(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(json.loads(json.dumps(event, allow_nan=False)) for event in self._events)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def last_input_sequence(self) -> int:
        with self._lock:
            return self._last_input_sequence

    @property
    def acked_input_sequence(self) -> int:
        with self._lock:
            return self._acked_input_sequence

    @property
    def acked_input_revision(self) -> int:
        with self._lock:
            return self._acked_input_revision

    def remote_positions(self, *, now=None):
        """Return timestamp-interpolated player positions from the newest server snapshots."""
        with self._lock:
            return self._remote_interpolator.sample(self._clock() if now is None else now)

    def _remember_remote_positions(self, state):
        rows = state.get("players", ())
        positions = {}
        if isinstance(rows, (list, tuple)):
            for player in rows:
                if not isinstance(player, Mapping):
                    continue
                player_id = player.get("player_id")
                x, y = player.get("x"), player.get("y")
                if (
                    isinstance(player_id, str)
                    and isinstance(x, (int, float))
                    and not isinstance(x, bool)
                    and isinstance(y, (int, float))
                    and not isinstance(y, bool)
                    and math.isfinite(x)
                    and math.isfinite(y)
                ):
                    positions[player_id] = (x, y)
        self._remote_interpolator.push(self._clock(), positions)

    def _on_message(self, value: dict[str, Any]) -> None:
        kind = value.get("type")
        if kind == "input_ack":
            sequence = value.get("sequence")
            if (
                value.get("accepted") is True
                and isinstance(sequence, int)
                and not isinstance(sequence, bool)
            ):
                with self._lock:
                    self._acked_input_sequence = max(self._acked_input_sequence, sequence)
                    self._acked_input_revision = self._revision
            elif (
                value.get("accepted") is False
                and value.get("reason") == "input rate exceeded"
                and isinstance(sequence, int)
                and not isinstance(sequence, bool)
            ):
                # the server drops an input that follows another within its rate window; the
                # newest input state must still arrive, so send it again once the window passed
                timer = threading.Timer(INPUT_RESEND_DELAY, self._resend_input, args=(sequence,))
                timer.daemon = True
                timer.start()
            return
        if kind == "server_error":
            with self._lock:
                self.error = str(value.get("message", "Server rejected command"))
                self._command_results.append({"accepted": False, "reason": self.error})
            return
        if kind != "game_update":
            return
        state = value.get("state")
        events = value.get("events", ())
        if state is not None and not isinstance(state, Mapping):
            return
        if not isinstance(events, (list, tuple)):
            events = ()
        try:
            clean_state = json.loads(json.dumps(dict(state or {}), allow_nan=False))
            clean_events = tuple(
                json.loads(json.dumps(dict(event), allow_nan=False))
                for event in events
                if isinstance(event, Mapping)
            )
        except (TypeError, ValueError):
            return
        with self._lock:
            incoming_revision = value.get("revision")
            if (
                isinstance(incoming_revision, int)
                and not isinstance(incoming_revision, bool)
                and incoming_revision < self._revision
            ):
                return
            command_id = value.get("command_id")
            if command_id and value.get("origin_player_id") == self.player_id:
                self._command_results.append(
                    {
                        "accepted": True,
                        "command_id": command_id,
                        "revision": value.get("revision", 0),
                    }
                )
            self._state = clean_state
            self._events = clean_events
            self._remember_remote_positions(clean_state)
            revision = value.get("revision")
            if isinstance(revision, int) and not isinstance(revision, bool):
                self._revision = max(self._revision, revision)

    def _on_disconnect(self, reason: str) -> None:
        self.error = str(reason) or "Connection closed"

    def connect(self) -> bool:
        if self.connected:
            return True
        self.close()
        with self._lock:
            # Revisions belong to a server session; a restarted server begins at zero.
            self._revision = -1
            self._state = {}
            self._events = ()
            self._pending_commands = {}
            self._command_results = []
            self._remote_interpolator = SnapshotInterpolator(delay=0.1, max_extrapolation=0.1)
            self._last_input_sequence = 0
            self._acked_input_sequence = 0
            self._acked_input_revision = -1
        client = self._client_factory(
            on_message=self._on_message, on_disconnect=self._on_disconnect
        )
        try:
            welcome = client.connect(
                self.profile["server_address"],
                self.profile["port"],
                self.profile["player_name"],
                guest_id=self.profile["guest_id"],
            )
        except (MultiplayerClientError, OSError, TypeError, ValueError) as exc:
            client.close()
            self.error = str(exc)
            return False
        initial_state = welcome.get("state")
        with self._lock:
            self._client = client
            welcome_revision = welcome.get("revision")
            welcome_revision = (
                welcome_revision
                if isinstance(welcome_revision, int) and not isinstance(welcome_revision, bool)
                else 0
            )
            if welcome_revision >= self._revision:
                self._state = dict(initial_state) if isinstance(initial_state, Mapping) else {}
                self._revision = welcome_revision
                self._events = ()
                self._remember_remote_positions(self._state)
            self.error = ""
        return True

    def send_input(self, input_state: Mapping[str, Any], *, force=False) -> bool:
        with self._lock:
            client = self._client
            now = time.monotonic()
            if not force and now - self._last_input_at < INPUT_SEND_INTERVAL:
                return False
            self._last_input_at = now
        if client is None or not client.connected:
            return False
        try:
            sequence = client.send_input(input_state)
        except (MultiplayerClientError, TypeError, ValueError) as exc:
            self.error = str(exc)
            return False
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            with self._lock:
                self._last_input_sequence = max(self._last_input_sequence, sequence)
                self._last_input_state = dict(input_state)
        return True

    def _resend_input(self, rejected_sequence: int) -> None:
        """Send the newest input again when it was the one the server rate-limited."""
        with self._lock:
            client = self._client
            state = self._last_input_state
            newest = self._last_input_sequence
        if client is None or state is None or not client.connected:
            return
        if newest != rejected_sequence:  # a newer input already went out
            return
        try:
            sequence = client.send_input(state)
        except (MultiplayerClientError, TypeError, ValueError):
            return
        if isinstance(sequence, int) and not isinstance(sequence, bool):
            with self._lock:
                self._last_input_sequence = max(self._last_input_sequence, sequence)

    def send_command(self, command: str, payload=None):
        """Submit a game command through the connected authoritative server."""
        with self._lock:
            client = self._client
        if client is None or not client.connected:
            return None
        try:
            command_id = client.send_command(command, payload)
            with self._lock:
                self._pending_commands[command_id] = command
            return command_id
        except (MultiplayerClientError, TypeError, ValueError) as exc:
            self.error = str(exc)
            return None

    def command_results(self, applied_revision):
        """Return acknowledgements only after their state has reached the presentation."""
        ready = []
        with self._lock:
            waiting = []
            for result in self._command_results:
                if result.get("revision", 0) > applied_revision:
                    waiting.append(result)
                    continue
                result = dict(result)
                command_id = result.get("command_id")
                if command_id:
                    result["command"] = self._pending_commands.pop(command_id, "Command")
                elif self._pending_commands:
                    first = next(iter(self._pending_commands))
                    result["command"] = self._pending_commands.pop(first)
                ready.append(result)
            self._command_results = waiting
        return tuple(ready)

    def close(self) -> None:
        with self._lock:
            client, self._client = self._client, None
        if client is not None:
            client.close()


def map_network_position(
    player: Mapping[str, Any],
    boss: Mapping[str, Any] | None,
    *,
    origin: tuple[float, float],
    scale: float,
) -> tuple[float, float]:
    """Map adapter-relative coordinates around the Boss onto a game world's chosen anchor."""
    boss = boss or {"x": 0.0, "y": 0.0}
    values = (player.get("x"), player.get("y"), boss.get("x", 0), boss.get("y", 0), *origin, scale)
    try:
        x, y, boss_x, boss_y, origin_x, origin_y, world_scale = map(float, values)
    except (TypeError, ValueError) as exc:
        raise ValueError("network positions must be finite numbers") from exc
    coordinates = (x, y, boss_x, boss_y, origin_x, origin_y, world_scale)
    if any(not math.isfinite(value) for value in coordinates):
        raise ValueError("network positions must be finite numbers")
    if world_scale <= 0:
        raise ValueError("network world scale must be positive")
    return (origin_x + (x - boss_x) * world_scale, origin_y + (y - boss_y) * world_scale)


def apply_project_snapshot(runtime, state, player_id):
    """Project a server scene and the guest's save into the existing presentation session.

    Deserialization constructs detached entities. No gameplay update runs here; the
    authoritative scene carries additions, removals and resource values together.
    """
    if state.get("schema") != "asteria.multiplayer.project_state":
        return False
    from types import SimpleNamespace

    from asteria.core.serialization import deserialize_scene
    from asteria.gameplay import ResourcePool, StatBlock, TagSet
    from asteria.runtime.character_control import CharacterController2DComponent
    from asteria.runtime.combat import CombatantComponent, CombatantState
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.preview import build_preview_registry

    local = next((p for p in state.get("players", ()) if p.get("player_id") == player_id), None)
    if local is None:
        return False
    from asteria.multiplayer.project_snapshot import unpack_scene_data

    scene_data = unpack_scene_data(state["scene"])
    scene_id = local["game_save"]["scene_id"]
    if scene_data["id"] != scene_id:
        scene_data = next(
            (
                value
                for value in (unpack_scene_data(item) for item in state.get("scenes", ()))
                if value["id"] == scene_id
            ),
            scene_data,
        )
    scene = deserialize_scene(scene_data, build_preview_registry())
    player = scene.get_entity(local["entity_id"])
    if player is None:
        raise ValueError("authoritative snapshot has no local player entity")
    # A joined player's dynamic entity id is absent from the authored project.
    # Validate the underlying save against the authored player before mapping it.
    data = dict(local["game_save"])
    authored_id = runtime.project.game_start.player_entity_id
    data["player_entity_id"] = authored_id
    save = GameRuntimeSave.from_data(data, runtime.project)
    save.player_entity_id = player.id
    game = runtime.game
    # Create presentation system objects before switching to the detached scene.
    game.scene, game.player = scene, player
    game.save = runtime.save = save
    systems = game._field_systems()
    game.facing = save.player_facing
    game.mode = "field"
    game.events.context = save.event_context
    game._configure_inventory()
    game.open_shop_id = local.get("open_shop_id")
    game.open_crafting_station = local.get("open_crafting_station")
    runtime._network_event_busy = bool(local.get("event_busy", False))
    dialogue_data = local.get("pending_dialogue")
    runtime._network_dialogue = None
    if dialogue_data:
        from asteria.events.dialogue import ChoiceRequest, DialogueRequest

        request_type = (
            DialogueRequest
            if dialogue_data.get("schema") == "asteria.dialogue_request"
            else ChoiceRequest
        )
        runtime._network_dialogue = request_type.from_data(dialogue_data)
    for entity_id, values in state.get("combatants", {}).items():
        entity = scene.get_entity(entity_id)
        component = entity.try_get(CombatantComponent) if entity else None
        if component is None:
            continue
        component.state = CombatantState(
            StatBlock.from_data(values["stats"]),
            ResourcePool.from_data(values["resources"]),
            TagSet.from_data(values["tags"]),
            poise=float(values.get("poise", 0)),
            dead=bool(values.get("dead", False)),
            down_phase=str(values.get("down_phase", "")),
            down_left=float(values.get("down_left", 0)),
        )
        if values.get("states"):
            from asteria.gameplay.states import StateRuntime

            current = component.state
            current.states = StateRuntime(
                game.project.gameplay_library.states,
                current.stats,
                current.resources,
                current.tags,
            )
            current.states.restore(values["states"])
    from asteria.runtime.action_combat import ActionCombatComponent

    systems["action_combat"].cooldowns = {
        (value["entity_id"], value["ability_id"]): float(value["left"])
        for value in state.get("cooldowns", ())
    }
    for entity_id, target_id in state.get("targets", {}).items():
        entity = scene.get_entity(entity_id)
        spec = entity.try_get(ActionCombatComponent) if entity else None
        if spec is not None:
            spec.lock_target_id = target_id
    for entity_id, values in state.get("controllers", {}).items():
        entity = scene.get_entity(entity_id)
        controller = entity.try_get(CharacterController2DComponent) if entity else None
        if controller is not None:
            for name in ("facing", "intent_x", "intent_y", "velocity_x", "velocity_y"):
                if name in values:
                    setattr(controller, name, values[name])
    # Actor ids name shared definitions; each guest's classes are independent saves.
    from asteria.runtime.actor_link import ClassAppearanceComponent
    from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D

    for row in state.get("players", ()):
        entity = scene.get_entity(row.get("entity_id", ""))
        if entity is None:
            continue
        appearance = entity.try_get(ClassAppearanceComponent)
        sprite = entity.try_get(SpriteRenderer2D)
        actor_id = game._actor_of(entity)
        if appearance is None or sprite is None or actor_id is None:
            continue
        peer_data = dict(row["game_save"])
        peer_data["player_entity_id"] = authored_id
        peer_save = GameRuntimeSave.from_data(peer_data, runtime.project)
        progression = peer_save.rpg_state.actor_progression.get(actor_id)
        if progression is None:
            continue
        looks = appearance.parsed()
        chosen = next(
            (looks[c] for c in reversed(progression.active_class_ids) if c in looks), None
        )
        if chosen:
            sprite.sprite_sheet_asset_id = chosen[0]
            animator = entity.try_get(Animator2DComponent)
            if animator is not None and chosen[1]:
                animator.clip_set_id = chosen[1]
    systems["actions"].running = {
        key: SimpleNamespace(**value) for key, value in state.get("actions", {}).items()
    }
    shots = tuple(SimpleNamespace(**value) for value in state.get("projectiles", ()))
    systems["projectiles"].views = lambda: shots
    systems["combat"].events = ()
    systems["loot"].events = ()
    game.progression_events = []
    return True


def install_authoritative_commands(runtime):
    """Route existing screen actions through the server without changing offline screens."""
    import inspect

    game = runtime.game
    if getattr(game, "_network_commands_installed", False):
        return
    game._network_commands_installed = True
    commands = {
        "equip_from_bag": ("equip", {"index": "index", "slot_id": "slot_id"}),
        "unequip_to_bag": ("unequip", {"slot_id": "slot_id"}),
        "equip_from_inventory": ("equip", {"equipment_id": "equipment_id", "slot_id": "slot_id"}),
        "unequip_to_inventory": ("unequip", {"slot_id": "slot_id"}),
        "equip_definition": ("equip", {"equipment_id": "equipment_id", "slot_id": "slot_id"}),
        "allocate_progression": (
            "allocate",
            {"graph_id": "graph_id", "node_id": "node_id", "count": "count"},
        ),
        "set_active_classes": ("change_class", {"class_ids": "class_ids"}),
        "set_classes": ("change_class", {"class_ids": "class_ids"}),
        "set_passives": ("passive", {"passive_ids": "passive_ids"}),
        "equip_passive": ("equip_passive", {"passive_id": "passive_id"}),
        "use_item": ("use_item", {"item_id": "item_id"}),
        "buy": ("buy", {"item_id": "item_id", "quantity": "quantity", "shop_id": "shop_id"}),
        "sell": ("sell", {"item_id": "item_id", "quantity": "quantity", "shop_id": "shop_id"}),
        "craft": ("craft", {"payload": "payload", "station": "station"}),
        "close_shop": ("close_shop", {}),
        "acknowledge_dialogue": ("dialogue_ack", {}),
        "choose": ("choose", {"index": "index"}),
        "learn_ability": ("learn_ability", {"ability_id": "ability_id"}),
        "set_active_party": (
            "active_party",
            {"actor_ids": "actor_ids", "placements": "placements"},
        ),
    }
    for name, (command, fields) in commands.items():
        original = getattr(game, name)
        signature = inspect.signature(original)

        def invoke(
            *args,
            _original=original,
            _signature=signature,
            _command=command,
            _fields=fields,
            **kwargs,
        ):
            if not runtime._multiplayer_connected():
                if getattr(runtime, "_authoritative_project_mode", False):
                    return None
                return _original(*args, **kwargs)
            bound = _signature.bind(*args, **kwargs)
            payload = {
                target: bound.arguments[source]
                for source, target in _fields.items()
                if source in bound.arguments and bound.arguments[source] is not None
            }
            return runtime.multiplayer_bridge.send_command(_command, payload)

        setattr(game, name, invoke)
    original_secondary = game.set_secondary_class

    def secondary(actor_id, class_id):
        if not runtime._multiplayer_connected():
            if getattr(runtime, "_authoritative_project_mode", False):
                return None
            return original_secondary(actor_id, class_id)
        progression = game.ensure_actor_progression(actor_id)
        return runtime.multiplayer_bridge.send_command(
            "change_class", {"class_ids": [progression.active_class_ids[0], class_id]}
        )

    game.set_secondary_class = secondary
    original_build = game.resolve_actor_build

    def resolved_build(actor_id):
        result = original_build(actor_id)
        if runtime._multiplayer_connected() and game._actor_of(game.player) == str(actor_id):
            from dataclasses import replace

            from asteria.runtime.combat import CombatantComponent

            component = game.player.try_get(CombatantComponent)
            if component is not None and component.state is not None:
                current = component.state
                return replace(
                    result, stats=current.stats, resources=current.resources, tags=current.tags
                )
        return result

    game.resolve_actor_build = resolved_build
