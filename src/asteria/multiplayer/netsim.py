"""A frame-aware TCP proxy that makes a link behave badly: delay, jitter, loss, bandwidth.

It sits between a client and a server and forwards whole JSON-line frames. Because it understands
frames, "loss" drops a whole message (as an unreliable link would) instead of corrupting the byte
stream, and order is kept for the frames that survive. Used to check that clients and servers stay
consistent under latency, and to measure what the protocol costs.
"""

from __future__ import annotations

import random
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LinkProfile:
    """One direction of a link. ``delay_ms`` plus up to ``jitter_ms`` of random extra time;
    ``loss`` drops that fraction of frames (never the handshake); ``bytes_per_second``
    caps throughput (0 = unlimited)."""

    delay_ms: float = 0.0
    jitter_ms: float = 0.0
    loss: float = 0.0
    bytes_per_second: float = 0.0

    def __post_init__(self):
        if min(self.delay_ms, self.jitter_ms, self.bytes_per_second) < 0:
            raise ValueError("delay, jitter and bandwidth must be >= 0")
        if not 0.0 <= self.loss < 1.0:
            raise ValueError("loss must be in [0, 1)")


HANDSHAKE_TYPES = (b'"hello"', b'"welcome"', b'"server_error"')


class _Pipe(threading.Thread):
    def __init__(self, source, sink, profile, rng, stats, name):
        super().__init__(name=name, daemon=True)
        self.source, self.sink, self.profile, self.rng, self.stats = (
            source,
            sink,
            profile,
            rng,
            stats,
        )
        self._queue = deque()
        self._cond = threading.Condition()
        self._stopped = False
        self._free_at = 0.0
        self._writer = threading.Thread(target=self._write_loop, daemon=True)

    def run(self):
        self._writer.start()
        reader = self.source.makefile("rb")
        try:
            while True:
                frame = reader.readline(1 << 20)
                if not frame:
                    break
                self.stats["frames"] += 1
                self.stats["bytes"] += len(frame)
                if (
                    self.profile.loss
                    and not any(tag in frame[:80] for tag in HANDSHAKE_TYPES)
                    and self.rng.random() < self.profile.loss
                ):
                    self.stats["dropped"] += 1
                    continue
                self._schedule(frame)
        except OSError:
            pass
        finally:
            with self._cond:
                self._stopped = True
                self._cond.notify_all()

    def _schedule(self, frame):
        now = time.monotonic()
        delay = (self.profile.delay_ms + self.rng.uniform(0, self.profile.jitter_ms)) / 1000.0
        due = now + delay
        if self.profile.bytes_per_second:
            start = max(now, self._free_at)
            self._free_at = start + len(frame) / self.profile.bytes_per_second
            due = max(due, self._free_at)
        with self._cond:
            # keep order: a frame never overtakes the one before it
            if self._queue:
                due = max(due, self._queue[-1][0])
            self._queue.append((due, frame))
            self._cond.notify()

    def _write_loop(self):
        while True:
            with self._cond:
                while not self._queue and not self._stopped:
                    self._cond.wait()
                if not self._queue:
                    break
                due, frame = self._queue[0]
                wait = due - time.monotonic()
                if wait > 0:
                    self._cond.wait(wait)
                    continue
                self._queue.popleft()
            try:
                self.sink.sendall(frame)
            except OSError:
                break
        try:
            self.sink.shutdown(socket.SHUT_WR)
        except OSError:
            pass


class LinkSimulator:
    """Listens on a local port and relays every connection to ``target`` through the profiles."""

    def __init__(self, target, *, upstream=None, downstream=None, host="127.0.0.1", seed=0):
        self.target = (str(target[0]), int(target[1]))
        self.upstream = upstream or LinkProfile()  # client -> server
        self.downstream = downstream or LinkProfile()  # server -> client
        self._listener = socket.create_server((host, 0))
        self._listener.settimeout(0.2)
        self.address = self._listener.getsockname()[:2]
        self._rng = random.Random(seed)
        self._stop = threading.Event()
        self._sockets = []
        self.stats = {
            "up": {"frames": 0, "bytes": 0, "dropped": 0},
            "down": {"frames": 0, "bytes": 0, "dropped": 0},
        }
        self._thread = threading.Thread(
            target=self._accept_loop, name="LinkSimulator", daemon=True
        )

    def start(self):
        self._thread.start()
        return self

    def _accept_loop(self):
        while not self._stop.is_set():
            try:
                client, _ = self._listener.accept()
            except (TimeoutError, OSError):
                continue
            try:
                server = socket.create_connection(self.target, timeout=3.0)
            except OSError:
                client.close()
                continue
            server.settimeout(None)
            client.settimeout(None)
            self._sockets += [client, server]
            seed = self._rng.random()
            _Pipe(
                client, server, self.upstream, random.Random(seed), self.stats["up"], "netsim-up"
            ).start()
            _Pipe(
                server,
                client,
                self.downstream,
                random.Random(seed + 1),
                self.stats["down"],
                "netsim-down",
            ).start()

    def close(self):
        self._stop.set()
        try:
            self._listener.close()
        except OSError:
            pass
        for item in self._sockets:
            try:
                item.close()
            except OSError:
                pass
        self._thread.join(timeout=1.0)

    def __enter__(self):
        return self.start()

    def __exit__(self, *_):
        self.close()
