"""Threaded TCP session server with a server-owned lobby and optional game adapter."""

from __future__ import annotations

import argparse
import copy
import importlib
import inspect
import json
import math
import sys
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from socketserver import StreamRequestHandler, ThreadingTCPServer
from typing import Any

from .adapter import AdapterUpdate, GameNetworkAdapter
from .delta import diff
from .metrics import ServerMetrics
from .protocol import (
    MAX_COMMAND_NAME,
    MAX_FRAME_BYTES,
    ProtocolError,
    clean_display_name,
    clean_guest_id,
    decode_frame,
    encode_frame,
    message,
)
from .security import AuthError, TlsSettings, TokenAuthenticator, check_exposure, load_secret


class RoomFullError(ValueError):
    """The requested session already has its maximum number of participants."""


@dataclass(slots=True)
class _Peer:
    player_id: str
    display_name: str
    handler: _ClientHandler
    last_sequence: int = 0
    last_input_sequence: int = 0
    last_input_at: float | None = None
    last_resync_at: float | None = None
    delta: bool = False  # this peer reads state deltas
    base_state: dict | None = None  # the last state sent to this peer
    base_revision: int = -1  # revision of the message that carried base_state


class MultiplayerServer(ThreadingTCPServer):
    """Single-session TCP server; game outcomes are delegated to ``adapter``."""

    allow_reuse_address = True
    daemon_threads = True
    request_queue_size = 32
    max_connections = 64
    handshake_timeout = 5.0
    input_rate_limit = 60

    def __init__(
        self,
        server_address,
        *,
        max_players=4,
        session_name="Asteria Session",
        adapter: GameNetworkAdapter | None = None,
        store=None,
        store_path=None,
        rules=None,
        tls=None,
        authenticator=None,
        allow_insecure=False,
        metrics=None,
        delta=True,
    ):
        max_players = int(max_players)
        if not 2 <= max_players <= 64:
            raise ValueError("max_players must be between 2 and 64")
        if tls is not None and not isinstance(tls, TlsSettings):
            raise TypeError("tls must be TlsSettings")
        if authenticator is not None and not isinstance(authenticator, TokenAuthenticator):
            raise TypeError("authenticator must be TokenAuthenticator")
        check_exposure(
            server_address[0],
            tls=tls is not None,
            auth=authenticator is not None,
            allow_insecure=allow_insecure,
        )
        self.tls_context = None if tls is None else tls.server_context()
        self.authenticator = authenticator
        self.metrics = metrics or ServerMetrics()
        self.delta_enabled = bool(delta)  # peers that ask for deltas get them
        self.max_players = max_players
        self.session_name = str(session_name).strip()[:64] or "Asteria Session"
        self.session_id = uuid.uuid4().hex[:12]
        self.adapter = adapter
        self._owns_store = store is None and store_path is not None
        if self._owns_store:
            from .persistence import SQLiteMultiplayerStore

            store = SQLiteMultiplayerStore(store_path)
        self.store = store
        if self.adapter is not None:
            configure = getattr(self.adapter, "configure_multiplayer", None)
            if callable(configure):
                configure(store=store, rules=rules)
        self._connection_slots = threading.BoundedSemaphore(self.max_connections)
        tick = getattr(adapter, "network_tick", None)
        self._network_tick = tick if callable(tick) else None
        self._tick_interval = None
        if self._network_tick is not None:
            try:
                interval = float(getattr(adapter, "network_tick_interval", 1 / 20))
            except (TypeError, ValueError) as exc:
                raise ValueError("network_tick_interval must be a number from 1/120 to 1") from exc
            if not math.isfinite(interval) or not 1 / 120 <= interval <= 1:
                raise ValueError("network_tick_interval must be from 1/120 to 1 seconds")
            self._tick_interval = interval
        if adapter is not None:
            required = (
                "initial_state",
                "on_player_joined",
                "handle_command",
                "on_player_left",
            )
            missing = [name for name in required if not callable(getattr(adapter, name, None))]
            if missing:
                raise TypeError("game adapter is missing: " + ", ".join(missing))
        self._room_lock = threading.RLock()
        self._publish_lock = threading.RLock()
        self._tick_stop = threading.Event()
        self._tick_thread = None
        self._peers: dict[str, _Peer] = {}
        self._revision = 0
        super().__init__(server_address, _ClientHandler)

    def process_request(self, request, client_address):
        if not self._connection_slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self._connection_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._connection_slots.release()

    def serve_forever(self, poll_interval=0.5):
        if self._network_tick is not None and self._tick_thread is None:
            self._tick_stop.clear()
            self._tick_thread = threading.Thread(
                target=self._run_network_ticks,
                name="AsteriaNetworkSimulation",
                daemon=True,
            )
            self._tick_thread.start()
        try:
            super().serve_forever(poll_interval=poll_interval)
        finally:
            self._tick_stop.set()
            if self._tick_thread is not None:
                self._tick_thread.join(timeout=max(1.0, self._tick_interval or 0.0))
                self._tick_thread = None

    def server_close(self):
        try:
            super().server_close()
        finally:
            if self._owns_store and self.store is not None:
                self.store.close()

    def _run_network_ticks(self):
        interval = self._tick_interval
        if interval is None:
            return
        next_tick = time.monotonic()
        while not self._tick_stop.is_set():
            wait = next_tick - time.monotonic()
            if wait > 0 and self._tick_stop.wait(wait):
                return
            started = time.monotonic()
            try:
                with self._publish_lock:
                    with self._room_lock:
                        if not self._peers:
                            update = None
                        else:
                            update = self._network_tick(interval)
                            if update is not None and not isinstance(update, AdapterUpdate):
                                raise TypeError("network_tick must return AdapterUpdate or None")
                            self._validate_update(update)
                        if update is not None:
                            self._revision += 1
                            revision = self._revision
                    if update is not None:
                        self.broadcast(
                            message(
                                "game_update",
                                revision=revision,
                                origin_player_id=None,
                                command_id="",
                                state=dict(update.state) if update.state is not None else None,
                                events=[dict(event) for event in update.events],
                            )
                        )
                self.metrics.tick(time.monotonic() - started)
            except Exception as exc:
                print(f"ERROR game adapter tick failed: {exc}", file=sys.stderr, flush=True)
                with self._publish_lock:
                    self.broadcast(
                        message("server_error", message=f"game adapter tick failed: {exc}")
                    )
                return
            next_tick = started + interval

    @staticmethod
    def _validate_update(update: AdapterUpdate | None):
        if update is None:
            return
        payload = message(
            "game_update",
            revision=0,
            origin_player_id=None,
            command_id="",
            state=dict(update.state) if update.state is not None else None,
            events=[dict(event) for event in update.events],
        )
        try:
            encode_frame(payload)
        except ProtocolError as exc:
            raise ValueError(f"adapter update is not serializable: {exc}") from exc

    def metrics_snapshot(self):
        """Traffic and tick-cost counters since the server started (see ``ServerMetrics``)."""
        with self._room_lock:
            players = len(self._peers)
        return self.metrics.snapshot(players=players)

    def handle_error(self, request, client_address):
        # A failed TLS handshake or a dropped connection is routine; do not print a traceback.
        import ssl

        exc = sys.exc_info()[1]
        if isinstance(exc, ssl.SSLError | ConnectionError | TimeoutError | OSError):
            self.metrics.reject("connection")
            return
        super().handle_error(request, client_address)

    def participants(self):
        with self._room_lock:
            return tuple(self._peer_data(peer) for peer in self._peers.values())

    @staticmethod
    def _peer_data(peer: _Peer):
        return {"player_id": peer.player_id, "display_name": peer.display_name}

    def join(self, handler: _ClientHandler, display_name: str, guest_id=None, features=()):
        with self._room_lock:
            if len(self._peers) >= self.max_players:
                raise RoomFullError("This session is full")
            player_id = clean_guest_id(guest_id) if guest_id is not None else uuid.uuid4().hex[:12]
            if player_id in self._peers:
                raise ValueError("guest ID is already active in this session")
            clean_name = clean_display_name(display_name)
            if self.store is not None:
                self.store.register_player(player_id, clean_name)
            peer = _Peer(player_id, clean_name, handler)
            peer.delta = self.delta_enabled and "delta" in features
            self._peers[peer.player_id] = peer
            update = None
            try:
                if self.adapter is not None:
                    update = self.adapter.on_player_joined(peer.player_id, peer.display_name)
                    if update is not None and not isinstance(update, AdapterUpdate):
                        raise TypeError("on_player_joined must return AdapterUpdate or None")
                    self._validate_update(update)
                    state = self.adapter.initial_state()
                    if state is not None and not isinstance(state, Mapping):
                        raise TypeError("adapter initial_state must return a mapping or None")
                else:
                    state = None
                next_revision = self._revision + int(update is not None)
                if update is not None and update.state is not None:
                    state = update.state
                welcome = message(
                    "welcome",
                    player_id=peer.player_id,
                    session_id=self.session_id,
                    session_name=self.session_name,
                    max_players=self.max_players,
                    players=[self._peer_data(item) for item in self._peers.values()],
                    revision=next_revision,
                    state=dict(state) if state is not None else None,
                )
                encode_frame(welcome)
            except Exception as exc:
                self._peers.pop(peer.player_id, None)
                if self.adapter is not None:
                    try:
                        self.adapter.on_player_left(peer.player_id)
                    except Exception:
                        pass
                if isinstance(exc, ProtocolError):
                    raise ValueError(f"adapter join state is not serializable: {exc}") from exc
                raise
            self._revision = next_revision
            self._set_baseline(peer, welcome.get("state"), next_revision)
            self.metrics.players(len(self._peers))
            return peer, welcome, update

    def leave(self, player_id: str):
        with self._room_lock:
            peer = self._peers.pop(player_id, None)
            if peer is None:
                return None
            update = None
            if self.adapter is not None:
                try:
                    update = self.adapter.on_player_left(player_id)
                    if update is not None and not isinstance(update, AdapterUpdate):
                        raise TypeError("on_player_left must return AdapterUpdate or None")
                    self._validate_update(update)
                    if update is not None:
                        self._revision += 1
                except Exception as exc:
                    self._send_error(peer.handler, f"game adapter leave error: {exc}")
                    update = None
            return peer, update, self._revision

    def handle_command(self, handler: _ClientHandler, value: Mapping[str, Any]):
        with self._publish_lock:
            self._handle_command_locked(handler, value)

    def handle_input(self, handler: _ClientHandler, value: Mapping[str, Any]):
        with self._publish_lock:
            self._handle_input_locked(handler, value)

    resync_min_interval = 0.25  # seconds between one player's resync requests

    def handle_resync(self, handler: _ClientHandler):
        """A client noticed it missed updates (a revision gap): send it the current state."""
        with self._publish_lock:
            with self._room_lock:
                peer = self._peers.get(handler.player_id)
                if peer is None:
                    return
                now = time.monotonic()
                if (
                    peer.last_resync_at is not None
                    and now - peer.last_resync_at < self.resync_min_interval
                ):
                    self.metrics.reject("resync rate")
                    return
                peer.last_resync_at = now
                state = self.adapter.initial_state() if self.adapter is not None else None
                revision = self._revision
                self._set_baseline(peer, state, revision)
            handler.send(
                message(
                    "game_update",
                    revision=revision,
                    origin_player_id=None,
                    command_id="",
                    resync=True,
                    state=dict(state) if state is not None else None,
                    events=[],
                )
            )

    def _handle_input_locked(self, handler: _ClientHandler, value: Mapping[str, Any]):
        player_id = handler.player_id
        sequence = value.get("sequence")
        input_state = value.get("input_state")
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            self._send_input_ack(handler, sequence, accepted=False, reason="invalid sequence")
            return
        if not isinstance(input_state, dict):
            self._send_input_ack(
                handler, sequence, accepted=False, reason="input_state must be an object"
            )
            return
        with self._room_lock:
            peer = self._peers.get(player_id)
            if peer is None:
                self._send_input_ack(
                    handler, sequence, accepted=False, reason="participant is not in session"
                )
                return
            if sequence <= peer.last_input_sequence:
                self._send_input_ack(handler, sequence, accepted=False, reason="duplicate input")
                return
            peer.last_input_sequence = sequence
            now = time.monotonic()
            if (
                peer.last_input_at is not None
                and now - peer.last_input_at < 1 / self.input_rate_limit
            ):
                self._send_input_ack(
                    handler, sequence, accepted=False, reason="input rate exceeded"
                )
                return
            peer.last_input_at = now
            callback = getattr(self.adapter, "handle_input", None)
            if not callable(callback):
                self._send_input_ack(
                    handler,
                    sequence,
                    accepted=False,
                    reason="adapter does not accept real-time input",
                )
                return
            try:
                update = callback(player_id, dict(input_state))
                if update is not None and not isinstance(update, AdapterUpdate):
                    raise TypeError("handle_input must return AdapterUpdate or None")
                self._validate_update(update)
            except (ValueError, TypeError) as exc:
                self._send_input_ack(handler, sequence, accepted=False, reason=str(exc))
                return
            except Exception as exc:
                self._send_input_ack(
                    handler, sequence, accepted=False, reason=f"game adapter error: {exc}"
                )
                return
            self._send_input_ack(handler, sequence, accepted=True)
            if update is not None:
                self._revision += 1
                revision = self._revision
            else:
                revision = None
        if update is not None:
            self.broadcast(
                message(
                    "game_update",
                    revision=revision,
                    origin_player_id=player_id,
                    input_sequence=sequence,
                    command_id="",
                    state=dict(update.state) if update.state is not None else None,
                    events=[dict(event) for event in update.events],
                )
            )

    @staticmethod
    def _send_input_ack(handler: _ClientHandler, sequence, *, accepted, reason=None):
        handler.send(
            message(
                "input_ack",
                sequence=sequence,
                accepted=bool(accepted),
                reason=str(reason)[:160] if reason else "",
            )
        )

    def _handle_command_locked(self, handler: _ClientHandler, value: Mapping[str, Any]):
        player_id = handler.player_id
        command_id = value.get("command_id")
        command = value.get("command")
        sequence = value.get("sequence")
        payload = value.get("payload", {})
        if not isinstance(command_id, str) or not 1 <= len(command_id) <= 80:
            self._send_error(handler, "command_id must be a non-empty string up to 80 characters")
            return
        if not isinstance(command, str) or not 1 <= len(command.strip()) <= MAX_COMMAND_NAME:
            self._send_error(handler, "command must be a non-empty string up to 80 characters")
            return
        if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
            self._send_error(handler, "sequence must be a positive integer")
            return
        if not isinstance(payload, dict):
            self._send_error(handler, "command payload must be an object")
            return
        with self._room_lock:
            peer = self._peers.get(player_id)
            if peer is None:
                self._send_error(handler, "participant is no longer in this session")
                return
            if sequence <= peer.last_sequence:
                handler.send(
                    message(
                        "command_ack",
                        command_id=command_id,
                        sequence=sequence,
                        duplicate=True,
                    )
                )
                return
            if self.adapter is None:
                self._send_error(handler, "This server has no game adapter; lobby messages only")
                return
            try:
                update = self.adapter.handle_command(player_id, command.strip(), dict(payload))
                if not isinstance(update, AdapterUpdate):
                    raise TypeError("handle_command must return AdapterUpdate")
                self._validate_update(update)
            except (ValueError, TypeError) as exc:
                self._send_error(handler, str(exc))
                return
            except Exception as exc:
                self._send_error(handler, f"game adapter error: {exc}")
                return
            peer.last_sequence = sequence
            self._revision += 1
            revision = self._revision
        self.broadcast(
            message(
                "game_update",
                revision=revision,
                origin_player_id=player_id,
                command_id=command_id,
                state=dict(update.state) if update.state is not None else None,
                events=[dict(event) for event in update.events],
            )
        )

    @staticmethod
    def _set_baseline(peer: _Peer, state, revision, shared=None):
        if peer.delta and isinstance(state, dict):
            if shared is None:
                baseline = copy.deepcopy(state)
            else:
                # Baselines are only ever read (diffed against), never mutated, so the peers of
                # one broadcast can share a single copy of the state they were sent.
                entry = shared.get(("copy", id(state)))
                if entry is None or entry[0] is not state:
                    entry = shared[("copy", id(state))] = (state, copy.deepcopy(state))
                baseline = entry[1]
            peer.base_state, peer.base_revision = baseline, int(revision)

    @staticmethod
    def _send_shared(peer: _Peer, value: Mapping[str, Any], shared):
        """``peer.handler.send(value)``, encoding a message shared by several peers only once."""
        if shared is None:
            return peer.handler.send(value)
        entry = shared.get(("frame", id(value)))
        if entry is None or entry[0] is not value:
            try:
                frame = encode_frame(value)
            except ProtocolError:
                frame = None
            entry = shared[("frame", id(value))] = (value, frame)
        if entry[1] is None:
            return False
        return peer.handler.send(value, frame=entry[1])

    def _deliver(self, peer: _Peer, value: Mapping[str, Any], shared=None):
        """Send ``value`` to one peer; a state update becomes a delta when the peer reads them.

        ``shared`` (one dict per broadcast) lets peers that hold the same baseline share the
        diff, the delta message, its encoding and the new baseline copy.
        """
        state = value.get("state")
        if (
            not peer.delta
            or value.get("type") != "game_update"
            or not isinstance(state, dict)
            or value.get("resync")
        ):
            if peer.delta and value.get("type") == "game_update":
                self._set_baseline(peer, state, value.get("revision", -1), shared)
            return self._send_shared(peer, value, shared)
        revision = value.get("revision", -1)
        base_state = peer.base_state
        if base_state is None:
            self._set_baseline(peer, state, revision, shared)
            return self._send_shared(peer, value, shared)
        # Peers whose baseline is the same object at the same revision get the same message.
        key = ("delta", id(base_state), peer.base_revision)
        entry = None if shared is None else shared.get(key)
        if entry is None or entry[0] is not base_state:
            patch = diff(base_state, state)
            if isinstance(patch, dict) and set(patch) == {"$set"}:
                slim = None  # nothing smaller than the whole state
            else:
                slim = {k: v for k, v in value.items() if k != "state"}
                slim.update(
                    state_delta=patch if patch is not None else {"$del": []},
                    base_revision=peer.base_revision,
                )
            entry = (base_state, slim, [])  # [] caches the bytes saved once computed
            if shared is not None:
                shared[key] = entry
        slim = entry[1]
        if slim is None:
            self._set_baseline(peer, state, revision, shared)
            return self._send_shared(peer, value, shared)
        sent = self._send_shared(peer, slim, shared)
        if sent:
            saved = entry[2]
            if not saved:
                if shared is None:
                    before = len(json.dumps(value, separators=(",", ":"), ensure_ascii=False))
                else:
                    sizes = shared.get(("size", id(value)))
                    if sizes is None or sizes[0] is not value:
                        size = len(json.dumps(value, separators=(",", ":"), ensure_ascii=False))
                        sizes = shared[("size", id(value))] = (value, size)
                    before = sizes[1]
                after = len(json.dumps(slim, separators=(",", ":"), ensure_ascii=False))
                saved.append(max(0, before - after))
            self.metrics.saved(saved[0])
        self._set_baseline(peer, state, revision, shared)
        return sent

    def broadcast(self, value: Mapping[str, Any], *, exclude=None):
        with self._publish_lock:
            with self._room_lock:
                peers = tuple(self._peers.values())
            shared = {}
            for peer in peers:
                if peer.player_id != exclude:
                    self._deliver(peer, value, shared)

    def _send_error(self, handler: _ClientHandler, text: str):
        handler.send(message("server_error", message=str(text)[:240]))

    def broadcast_join(self, peer: _Peer, update: AdapterUpdate | None):
        with self._publish_lock:
            self.broadcast(
                message("peer_joined", player=self._peer_data(peer)),
                exclude=peer.player_id,
            )
            if update is not None:
                self.broadcast(
                    message(
                        "game_update",
                        revision=self._revision,
                        origin_player_id=peer.player_id,
                        command_id="",
                        state=dict(update.state) if update.state is not None else None,
                        events=[dict(event) for event in update.events],
                    ),
                    exclude=peer.player_id,
                )

    def broadcast_leave(self, peer: _Peer, update: AdapterUpdate | None, revision: int):
        with self._publish_lock:
            self.broadcast(message("peer_left", player_id=peer.player_id))
            if update is not None:
                self.broadcast(
                    message(
                        "game_update",
                        revision=revision,
                        origin_player_id=peer.player_id,
                        command_id="",
                        state=dict(update.state) if update.state is not None else None,
                        events=[dict(event) for event in update.events],
                    )
                )


class _ClientHandler(StreamRequestHandler):
    server: MultiplayerServer

    def setup(self):
        context = self.server.tls_context
        if context is not None:  # encrypt first: nothing is read in the clear
            self.request.settimeout(self.server.handshake_timeout)
            self.request = context.wrap_socket(self.request, server_side=True)
        super().setup()
        self.player_id = None
        self._send_lock = threading.Lock()
        self.request.settimeout(self.server.handshake_timeout)

    def handle(self):
        try:
            hello = self._read_message()
            if hello is None or hello.get("type") != "hello":
                self.server._send_error(self, "first message must be hello")
                return
            display_name = hello.get("display_name", "Player")
            if not isinstance(display_name, str):
                self.server._send_error(self, "display_name must be text")
                return
            guest_id = hello.get("guest_id")
            raw = hello.get("features", ())
            features = tuple(x for x in raw if isinstance(x, str)) if isinstance(raw, list) else ()
            authenticator = self.server.authenticator
            if authenticator is not None:
                try:
                    guest_id = authenticator.verify(hello.get("token"), guest_id)
                except AuthError as exc:
                    self.server.metrics.reject("auth")
                    self.server._send_error(self, f"authentication failed: {exc}")
                    return
            with self.server._publish_lock:
                try:
                    peer, welcome, update = self.server.join(
                        self, display_name, guest_id, features
                    )
                except RoomFullError as exc:
                    self.server._send_error(self, str(exc))
                    return
                except Exception as exc:
                    self.server._send_error(self, f"could not join session: {exc}")
                    return
                self.player_id = peer.player_id
                if not self.send(welcome):
                    return
                self.server.broadcast_join(peer, update)
                self.request.settimeout(None)
            while True:
                value = self._read_message()
                if value is None:
                    return
                kind = value["type"]
                if kind == "ping":
                    self.send(
                        message(
                            "pong",
                            client_time=value.get("client_time"),
                            revision=self.server._revision,
                        )
                    )
                elif kind == "resync_request":
                    self.server.handle_resync(self)
                elif kind == "command":
                    self.server.handle_command(self, value)
                elif kind == "input":
                    self.server.handle_input(self, value)
                else:
                    self.server._send_error(self, f"unsupported message type: {kind[:80]}")
        except ProtocolError as exc:
            self.server._send_error(self, str(exc))
        except (ConnectionError, OSError):
            return
        finally:
            if self.player_id is not None:
                with self.server._publish_lock:
                    result = self.server.leave(self.player_id)
                    if result is not None:
                        peer, update, revision = result
                        self.server.broadcast_leave(peer, update, revision)

    def _read_message(self):
        frame = self.rfile.readline(MAX_FRAME_BYTES + 2)
        if not frame:
            return None
        if len(frame) > MAX_FRAME_BYTES + 1 or not frame.endswith(b"\n"):
            raise ProtocolError(f"message exceeds {MAX_FRAME_BYTES} bytes")
        value = decode_frame(frame)
        self.server.metrics.received(value.get("type", "?"), len(frame))
        return value

    def send(self, value, frame=None):
        """Write ``value`` (already encoded as ``frame`` when given) to this client."""
        try:
            if frame is None:
                frame = encode_frame(value)
            with self._send_lock:
                self.wfile.write(frame)
                self.wfile.flush()
            self.server.metrics.sent(value.get("type", "?"), len(frame))
            return True
        except (OSError, ProtocolError):
            return False


def create_server(
    host="127.0.0.1",
    port=8765,
    *,
    max_players=4,
    session_name="Asteria Session",
    adapter: GameNetworkAdapter | None = None,
    store=None,
    store_path=None,
    rules=None,
    tls=None,
    authenticator=None,
    allow_insecure=False,
) -> MultiplayerServer:
    """Create a server without starting its accept loop."""
    return MultiplayerServer(
        (str(host), int(port)),
        max_players=max_players,
        session_name=session_name,
        adapter=adapter,
        store=store,
        store_path=store_path,
        rules=rules,
        tls=tls,
        authenticator=authenticator,
        allow_insecure=allow_insecure,
    )


def _load_adapter(
    spec: str | None, *, store=None, rules=None, project_path=None, allowed_prefixes=None
):
    if not spec:
        return None
    module_name, separator, attribute = spec.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("adapter must use the form package.module:factory")
    if allowed_prefixes is not None and not any(
        module_name == prefix or module_name.startswith(prefix.rstrip(".") + ".")
        for prefix in allowed_prefixes
    ):
        raise ValueError(
            f"adapter module {module_name!r} is not on the allow-list "
            f"({', '.join(allowed_prefixes) or 'empty'}); a server runs only the code it is "
            "told to"
        )
    factory = getattr(importlib.import_module(module_name), attribute)
    if callable(factory):
        parameters = inspect.signature(factory).parameters
        accepts_kwargs = any(
            item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters.values()
        )
        kwargs = {}
        if "store" in parameters or accepts_kwargs:
            kwargs["store"] = store
        if "rules" in parameters or accepts_kwargs:
            kwargs["rules"] = rules
        if project_path is not None and ("project_path" in parameters or accepts_kwargs):
            kwargs["project_path"] = project_path
        adapter = factory(**kwargs)
    else:
        adapter = factory
    return adapter


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an Asteria multiplayer session server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--max-players", type=int, default=4)
    parser.add_argument("--session-name", default="Asteria Session")
    parser.add_argument(
        "--adapter",
        help="server-side game adapter factory (package.module:factory)",
    )
    parser.add_argument("--database", help="server-side SQLite path for persistent player state")
    parser.add_argument("--project", help="selected project JSON for project-backed adapters")
    parser.add_argument("--rules", help="project-owned multiplayer rules JSON file")
    parser.add_argument("--tls-cert", help="PEM certificate chain: serve over TLS")
    parser.add_argument("--tls-key", help="PEM private key for --tls-cert")
    parser.add_argument(
        "--auth-secret-file",
        help="file holding the token secret (>= 16 bytes): players must present a signed token",
    )
    parser.add_argument(
        "--insecure-lan",
        action="store_true",
        help="allow listening beyond 127.0.0.1 without TLS and tokens (trusted network only)",
    )
    parser.add_argument(
        "--adapter-allow",
        action="append",
        default=None,
        metavar="PREFIX",
        help="only load adapters from modules under PREFIX (repeatable; default: any)",
    )
    parser.add_argument("--metrics-file", help="write the traffic / tick counters here on exit")
    args = parser.parse_args(argv)
    store = None
    try:
        if args.database:
            from .persistence import SQLiteMultiplayerStore

            store = SQLiteMultiplayerStore(args.database)
        rules = None
        if args.rules:
            from .rules import load_rules

            rules = load_rules(args.rules)
        adapter = _load_adapter(
            args.adapter,
            store=store,
            rules=rules,
            project_path=args.project,
            allowed_prefixes=args.adapter_allow,
        )
        tls = None
        if args.tls_cert or args.tls_key:
            if not (args.tls_cert and args.tls_key):
                raise ValueError("--tls-cert and --tls-key go together")
            tls = TlsSettings(args.tls_cert, args.tls_key)
        authenticator = (
            TokenAuthenticator(load_secret(args.auth_secret_file))
            if args.auth_secret_file
            else None
        )
        server = create_server(
            args.host,
            args.port,
            max_players=args.max_players,
            session_name=args.session_name,
            adapter=adapter,
            store=store,
            rules=rules,
            tls=tls,
            authenticator=authenticator,
            allow_insecure=args.insecure_lan,
        )
    except Exception as exc:
        if store is not None:
            store.close()
        print(f"ERROR {exc}", file=sys.stderr, flush=True)
        return 2
    address, port = server.server_address[:2]
    print(
        "READY "
        + json.dumps(
            {
                "host": address,
                "port": port,
                "session_id": server.session_id,
                "session_name": server.session_name,
                "tls": tls is not None,
                "auth": authenticator is not None,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        if args.metrics_file:
            try:
                with open(args.metrics_file, "w", encoding="utf-8") as handle:
                    json.dump(server.metrics_snapshot(), handle, indent=2, sort_keys=True)
            except OSError as exc:
                print(f"ERROR could not write metrics: {exc}", file=sys.stderr, flush=True)
        server.server_close()
        if store is not None:
            store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
