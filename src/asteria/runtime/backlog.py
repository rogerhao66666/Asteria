"""Message log: the lines the player has read, newest last (YEP MessageBacklog)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BacklogEntry:
    speaker: str
    text: str


class MessageBacklog:
    def __init__(self, limit=100):
        self.limit = max(0, int(limit))
        self._entries = deque(maxlen=self.limit or None)

    def add(self, speaker, text):
        """Record a line (consecutive duplicates collapse). Returns True when it was added."""
        if not self.limit:
            return False
        entry = BacklogEntry(str(speaker or ""), str(text))
        if self._entries and self._entries[-1] == entry:
            return False
        self._entries.append(entry)
        return True

    def entries(self):
        return tuple(self._entries)

    def clear(self):
        self._entries.clear()

    def __len__(self):
        return len(self._entries)
