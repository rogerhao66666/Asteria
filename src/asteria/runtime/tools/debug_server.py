"""Debug channel between a running game and the editor's Debugger panel (EDT-10).

The game hosts ``DebugServer`` on 127.0.0.1 only and polls it once per frame
(non-blocking, so the game loop never waits). Every request must carry the
token the editor passed on the command line. Protocol: one JSON object per
line — request ``{"id": n, "token": t, "command": c, "args": {...}}``,
response ``{"id": n, "ok": bool, "result" | "error": ...}``.
``DebugClient`` is the editor side.
"""

from __future__ import annotations

import json
import secrets
import selectors
import socket
import time

MAX_LINE = 1 << 20


class DebugServer:
    def __init__(self, debugger, *, port=0, token=None, host="127.0.0.1"):
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("the debug server only listens on the loopback interface")
        self.debugger = debugger
        self.token = token or secrets.token_hex(16)
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._listener.bind((host, int(port)))
        self._listener.listen(4)
        self._listener.setblocking(False)
        self.port = self._listener.getsockname()[1]
        self._selector = selectors.DefaultSelector()
        self._selector.register(self._listener, selectors.EVENT_READ, None)
        self._buffers = {}
        self.handled = 0

    def poll(self):
        """Accept connections and answer complete requests; never blocks."""
        for key, _ in self._selector.select(timeout=0):
            if key.data is None:
                conn, _ = self._listener.accept()
                conn.setblocking(False)
                self._selector.register(conn, selectors.EVENT_READ, "client")
                self._buffers[conn] = b""
                continue
            conn = key.fileobj
            try:
                chunk = conn.recv(65536)
            except (BlockingIOError, InterruptedError):
                continue
            except OSError:
                chunk = b""
            if not chunk:
                self._drop(conn)
                continue
            buffer = self._buffers[conn] + chunk
            if len(buffer) > MAX_LINE:
                self._drop(conn)
                continue
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                self._answer(conn, line)
            self._buffers[conn] = buffer

    def _answer(self, conn, line):
        try:
            request = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response = {"id": None, "ok": False, "error": "invalid JSON"}
        else:
            if not secrets.compare_digest(str(request.get("token", "")), self.token):
                response = {"id": request.get("id"), "ok": False, "error": "invalid token"}
            else:
                try:
                    result = self.debugger.execute(
                        str(request.get("command", "")), request.get("args") or {}
                    )
                    response = {"id": request.get("id"), "ok": True, "result": result}
                except Exception as exc:  # noqa: BLE001 - reported to the editor, never crashes the game
                    response = {"id": request.get("id"), "ok": False, "error": str(exc)}
        self.handled += 1
        try:
            conn.sendall((json.dumps(response, default=str) + "\n").encode("utf-8"))
        except OSError:
            self._drop(conn)

    def _drop(self, conn):
        try:
            self._selector.unregister(conn)
        except (KeyError, ValueError):
            pass
        self._buffers.pop(conn, None)
        conn.close()

    def close(self):
        for conn in list(self._buffers):
            self._drop(conn)
        try:
            self._selector.unregister(self._listener)
        except (KeyError, ValueError):
            pass
        self._listener.close()
        self._selector.close()


class DebugClientError(RuntimeError):
    pass


class DebugClient:
    """Editor side. ``pump`` (optional) is called while waiting, e.g. to let an in-process game
    poll."""

    def __init__(self, port, token, *, host="127.0.0.1", timeout=2.0, pump=None):
        self.port, self.token, self.host, self.timeout, self.pump = (
            int(port),
            str(token),
            host,
            float(timeout),
            pump,
        )
        self._sock = None
        self._buffer = b""
        self._next = 0

    @property
    def connected(self):
        return self._sock is not None

    def connect(self, retries=20, delay=0.1):
        last = None
        for _ in range(int(retries)):
            try:
                self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
                self._sock.setblocking(False)
                return True
            except OSError as exc:
                last = exc
                time.sleep(delay)
        raise DebugClientError(f"cannot reach the game debugger on port {self.port}: {last}")

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def request(self, command, **args):
        if self._sock is None:
            raise DebugClientError("not connected")
        self._next += 1
        payload = {"id": self._next, "token": self.token, "command": command, "args": args}
        self._sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.pump is not None:
                self.pump()
            try:
                chunk = self._sock.recv(65536)
                if not chunk:
                    self.close()
                    raise DebugClientError("the game closed the debug connection")
                self._buffer += chunk
            except (BlockingIOError, InterruptedError):
                time.sleep(0.005)
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                response = json.loads(line.decode("utf-8"))
                if response.get("id") == self._next:
                    if not response.get("ok"):
                        raise DebugClientError(response.get("error", "debug command failed"))
                    return response.get("result")
        raise DebugClientError(f"{command}: no answer from the game")
