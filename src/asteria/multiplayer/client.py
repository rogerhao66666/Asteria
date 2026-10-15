"""Small threaded client for Asteria's versioned JSON-line multiplayer protocol."""

from __future__ import annotations

import copy
import socket
import ssl
import threading
import time
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from .delta import DeltaError
from .delta import apply as apply_delta
from .protocol import (
    MAX_FRAME_BYTES,
    ProtocolError,
    clean_guest_id,
    decode_frame,
    encode_frame,
    message,
)


class MultiplayerClientError(ConnectionError):
    """A server could not be reached or rejected the requested session operation."""


class MultiplayerClient:
    """Join a session and receive server messages on a background thread.

    Callbacks run on the receive thread. GUI clients should forward callback data through their
    GUI framework's queued signals. Commands are only accepted when the server has a game adapter.
    """

    def __init__(
        self,
        *,
        on_message: Callable[[dict[str, Any]], None] | None = None,
        on_disconnect: Callable[[str], None] | None = None,
    ):
        self._on_message = on_message
        self._on_disconnect = on_disconnect
        self._socket: socket.socket | None = None
        self._reader = None
        self._receive_thread: threading.Thread | None = None
        self._send_lock = threading.Lock()
        self._command_lock = threading.Lock()
        self._input_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._closing = False
        self._connected = False
        self.player_id: str | None = None
        self.session_id: str | None = None
        self.session_name: str | None = None
        self.max_players = 0
        self.revision = 0
        self._players: dict[str, dict[str, str]] = {}
        self._next_sequence = 0
        self._next_input_sequence = 0
        self.gaps = 0  # times a missed update was noticed (and a resync asked for)
        self.delta_misses = 0  # deltas that did not fit the state held (a resync was asked for)
        self._state = None  # the last full state, which deltas are applied to
        self._state_revision = -1
        self._want_resync = False
        self._heartbeat = None

    @property
    def connected(self):
        with self._state_lock:
            return self._connected

    @property
    def players(self):
        with self._state_lock:
            return tuple(dict(item) for item in self._players.values())

    def connect(
        self,
        host: str,
        port: int,
        display_name="Player",
        *,
        guest_id=None,
        timeout=4.0,
        token=None,
        tls=None,
        cafile=None,
        server_hostname=None,
        heartbeat=None,
        delta=True,
    ):
        """Join a session.

        ``token``: a signed player token, when the server requires one. ``tls``: ``True`` (verify
        the server's certificate, trusting ``cafile`` if given) or a ready ``ssl.SSLContext``; the
        server name checked is ``server_hostname`` or ``host``. ``heartbeat``: seconds between
        pings, which also notice a missed final update (the pong carries the server's revision).
        """
        with self._state_lock:
            if self._connected or self._socket is not None:
                raise MultiplayerClientError("client is already connected")
            self._closing = False
        try:
            connection = socket.create_connection((str(host), int(port)), timeout=float(timeout))
            connection.settimeout(float(timeout))
            if tls:
                from .security import client_context

                context = tls if isinstance(tls, ssl.SSLContext) else client_context(cafile)
                connection = context.wrap_socket(
                    connection, server_hostname=str(server_hostname or host)
                )
            reader = connection.makefile("rb")
            hello = message("hello", display_name=str(display_name))
            if delta:
                hello["features"] = ["delta"]  # state updates may arrive as deltas
            if guest_id is not None:
                hello["guest_id"] = clean_guest_id(guest_id)
            if token is not None:
                hello["token"] = str(token)
            connection.sendall(encode_frame(hello))
            welcome = self._read_message(reader)
            if welcome.get("type") == "server_error":
                raise MultiplayerClientError(str(welcome.get("message", "join rejected")))
            if welcome.get("type") != "welcome":
                raise MultiplayerClientError("server did not send a welcome message")
        except (OSError, ProtocolError, ValueError, ssl.SSLError) as exc:
            try:
                if "reader" in locals():
                    reader.close()
            except OSError:
                pass
            try:
                if "connection" in locals():
                    connection.close()
            except OSError:
                pass
            if isinstance(exc, MultiplayerClientError):
                raise
            raise MultiplayerClientError(str(exc)) from exc
        with self._state_lock:
            self._socket = connection
            self._reader = reader
            self._connected = True
            self.player_id = str(welcome.get("player_id", "")) or None
            self.session_id = str(welcome.get("session_id", "")) or None
            self.session_name = str(welcome.get("session_name", "")) or None
            self.max_players = int(welcome.get("max_players", 0))
            self.revision = int(welcome.get("revision", 0))
            state = welcome.get("state")
            self._state = copy.deepcopy(state) if isinstance(state, dict) else None
            self._state_revision = self.revision
            players = welcome.get("players", ())
            self._players = {
                str(item.get("player_id")): {
                    "player_id": str(item.get("player_id", "")),
                    "display_name": str(item.get("display_name", "Player")),
                }
                for item in players
                if isinstance(item, Mapping) and item.get("player_id")
            }
        connection.settimeout(None)
        self._receive_thread = threading.Thread(
            target=self._receive_loop,
            name=f"AsteriaNetworkClient-{self.player_id or 'peer'}",
            daemon=True,
        )
        self._receive_thread.start()
        if heartbeat:
            self._heartbeat = threading.Thread(
                target=self._heartbeat_loop,
                args=(float(heartbeat),),
                name=f"AsteriaNetworkHeartbeat-{self.player_id or 'peer'}",
                daemon=True,
            )
            self._heartbeat.start()
        return dict(welcome)

    def _heartbeat_loop(self, interval):
        while self.connected:
            time.sleep(interval)
            try:
                self.send_ping()
            except MultiplayerClientError:
                return

    def send_ping(self):
        return self._send(message("ping", client_time=time.monotonic()))

    def send_command(self, command: str, payload: Mapping[str, Any] | None = None):
        command = str(command).strip()
        if not command:
            raise ValueError("command is required")
        command_id = uuid.uuid4().hex
        with self._command_lock:
            with self._state_lock:
                self._next_sequence += 1
                sequence = self._next_sequence
            self._send(
                message(
                    "command",
                    command_id=command_id,
                    sequence=sequence,
                    command=command,
                    payload=dict(payload or {}),
                )
            )
        return command_id

    def send_input(self, input_state: Mapping[str, Any]) -> int:
        """Send the latest held input state; real-time adapters can consume it on server ticks."""
        if not isinstance(input_state, Mapping):
            raise TypeError("input_state must be a mapping")
        with self._input_lock:
            with self._state_lock:
                self._next_input_sequence += 1
                sequence = self._next_input_sequence
            self._send(
                message(
                    "input",
                    sequence=sequence,
                    input_state=dict(input_state),
                )
            )
        return sequence

    def close(self):
        with self._state_lock:
            self._closing = True
            self._connected = False
            connection, reader = self._socket, self._reader
            self._socket = None
            self._reader = None
        if connection is not None:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                connection.close()
            except OSError:
                pass
        if reader is not None:
            try:
                reader.close()
            except OSError:
                pass
        thread = self._receive_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._receive_thread = None

    def _send(self, value):
        frame = encode_frame(value)
        with self._send_lock:
            with self._state_lock:
                connection = self._socket
                connected = self._connected
            if not connected or connection is None:
                raise MultiplayerClientError("client is not connected")
            try:
                connection.sendall(frame)
            except OSError as exc:
                raise MultiplayerClientError(str(exc)) from exc
        return True

    def _receive_loop(self):
        reason = "Connection closed"
        try:
            while True:
                with self._state_lock:
                    reader = self._reader
                    if self._closing:
                        return
                if reader is None:
                    return
                value = self._read_message(reader)
                if self._update_membership(value):
                    self._notify(self._on_message, value)
                self._send_resync_if_needed()
        except (OSError, ProtocolError, MultiplayerClientError) as exc:
            reason = str(exc) or reason
        finally:
            with self._state_lock:
                intentional = self._closing
                self._connected = False
                connection, reader = self._socket, self._reader
                self._socket = None
                self._reader = None
            if connection is not None:
                try:
                    connection.close()
                except OSError:
                    pass
            if reader is not None:
                try:
                    reader.close()
                except OSError:
                    pass
            if not intentional:
                self._notify(self._on_disconnect, reason)

    @staticmethod
    def _read_message(reader):
        frame = reader.readline(MAX_FRAME_BYTES + 2)
        if not frame:
            raise MultiplayerClientError("server closed the connection")
        if len(frame) > MAX_FRAME_BYTES + 1 or not frame.endswith(b"\n"):
            raise ProtocolError(f"message exceeds {MAX_FRAME_BYTES} bytes")
        return decode_frame(frame)

    def _update_membership(self, value):
        kind = value.get("type")
        with self._state_lock:
            if kind == "peer_joined":
                player = value.get("player")
                if isinstance(player, Mapping) and player.get("player_id"):
                    player_id = str(player["player_id"])
                    self._players[player_id] = {
                        "player_id": player_id,
                        "display_name": str(player.get("display_name", "Player")),
                    }
            elif kind == "peer_left":
                self._players.pop(str(value.get("player_id", "")), None)
            elif kind == "pong":
                revision = value.get("revision")
                if isinstance(revision, int) and not isinstance(revision, bool):
                    if revision > self.revision:
                        self._want_resync = True  # the server is ahead: an update never arrived
            elif kind == "game_update":
                revision = value.get("revision")
                if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
                    raise ProtocolError("game update revision must be a non-negative integer")
                if value.get("resync"):  # the server's answer to a resync request
                    self.revision = max(self.revision, revision)
                    self._remember_state(value, revision)
                    return True
                if revision <= self.revision:
                    return False
                if revision > self.revision + 1:
                    self.gaps += 1
                    self._want_resync = True
                self.revision = revision
                if "state_delta" in value and not self._apply_state_delta(value, revision):
                    return False  # it did not fit what we hold: wait for the full state
                self._remember_state(value, revision)
        return True

    def _remember_state(self, value, revision):
        state = value.get("state")
        if isinstance(state, dict):
            self._state, self._state_revision = copy.deepcopy(state), revision

    def _apply_state_delta(self, value, revision):
        """Rebuild the full ``state`` from a delta (so callers never see one); False when the
        delta's base is not the state held here."""
        delta = value.pop("state_delta")
        base = value.pop("base_revision", None)
        if self._state is None or base != self._state_revision:
            self.delta_misses += 1
            self._want_resync = True
            return False
        try:
            value["state"] = apply_delta(self._state, delta)
        except DeltaError:
            self.delta_misses += 1
            self._want_resync = True
            return False
        value["delta"] = True
        return True

    def _send_resync_if_needed(self):
        with self._state_lock:
            wanted, self._want_resync = self._want_resync, False
        if wanted:
            try:
                self._send(message("resync_request"))
            except MultiplayerClientError:
                pass

    @staticmethod
    def _notify(callback, value):
        if callback is None:
            return
        try:
            callback(value)
        except Exception:
            # A UI callback must not terminate the network receive loop.
            return

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
