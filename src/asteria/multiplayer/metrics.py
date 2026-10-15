"""Counters for a multiplayer server: traffic per message type, tick cost and fan-out."""

from __future__ import annotations

import threading
import time
from collections import Counter


class ServerMetrics:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self.started = clock()
        self.bytes_in = 0
        self.bytes_out = 0
        self.messages_in = Counter()
        self.messages_out = Counter()
        self.tick_count = 0
        self.tick_seconds = 0.0
        self.worst_tick_seconds = 0.0
        self.rejected = Counter()  # reason -> count (rate limits, bad auth ...)
        self.peak_players = 0
        self.delta_bytes_saved = 0

    def received(self, kind, size):
        with self._lock:
            self.bytes_in += size
            self.messages_in[str(kind)[:40]] += 1

    def sent(self, kind, size):
        with self._lock:
            self.bytes_out += size
            self.messages_out[str(kind)[:40]] += 1

    def tick(self, seconds):
        with self._lock:
            self.tick_count += 1
            self.tick_seconds += seconds
            self.worst_tick_seconds = max(self.worst_tick_seconds, seconds)

    def reject(self, reason):
        with self._lock:
            self.rejected[str(reason)[:60]] += 1

    def saved(self, size):
        with self._lock:
            self.delta_bytes_saved += int(size)

    def players(self, count):
        with self._lock:
            self.peak_players = max(self.peak_players, int(count))

    def snapshot(self, *, players=0):
        """A plain dict of everything counted so far, with rates over the server's lifetime."""
        with self._lock:
            elapsed = max(1e-9, self._clock() - self.started)
            ticks = self.tick_count
            return {
                "uptime_seconds": elapsed,
                "bytes_in": self.bytes_in,
                "bytes_out": self.bytes_out,
                "bytes_out_per_second": self.bytes_out / elapsed,
                "bytes_out_per_player_second": self.bytes_out / elapsed / max(1, players),
                "messages_in": dict(self.messages_in),
                "messages_out": dict(self.messages_out),
                "ticks": ticks,
                "tick_ms_average": 1000.0 * self.tick_seconds / ticks if ticks else 0.0,
                "tick_ms_worst": 1000.0 * self.worst_tick_seconds,
                "tick_cpu_share": self.tick_seconds / elapsed,
                "rejected": dict(self.rejected),
                "peak_players": self.peak_players,
                "delta_bytes_saved": self.delta_bytes_saved,
            }
