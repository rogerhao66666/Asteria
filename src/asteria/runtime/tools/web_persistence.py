"""Saves that survive a page reload in the browser (the web export).

A game exported with ``asteria.export_web`` runs inside the browser's in-memory file system:
everything the game writes to its ``saves/`` folder (save slots, the autosave, the player's
settings) is gone when the page is closed. ``FolderMirror`` keeps a copy of that folder in the
browser's ``localStorage``: ``restore`` writes the stored files back into the folder before the
game starts, ``sync`` (called every few frames) stores files that changed and forgets files the
game deleted. The game code itself keeps writing plain files.

The storage is anything with the Web Storage API (``getItem``, ``setItem``, ``removeItem``);
``browser_storage()`` finds the real one under pygbag, and ``DictStorage`` stands in for it in
tests and on the desktop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


class DictStorage:
    """``localStorage`` shaped storage over a dict (tests, desktop runs of the web entry)."""

    def __init__(self, items=None):
        self.items = dict(items or {})

    def getItem(self, key):  # noqa: N802 - the Web Storage API's names
        return self.items.get(key)

    def setItem(self, key, value):  # noqa: N802
        self.items[key] = str(value)

    def removeItem(self, key):  # noqa: N802
        self.items.pop(key, None)


def browser_storage():
    """The page's ``localStorage`` when running in the browser (pygbag), else None."""
    if sys.platform != "emscripten":
        return None
    try:
        import platform

        window = getattr(platform, "window", None)
        storage = None if window is None else getattr(window, "localStorage", None)
    except Exception:  # noqa: BLE001 - no bridge to the page: play without persistence
        return None
    return storage if storage is not None and hasattr(storage, "setItem") else None


class FolderMirror:
    """Keeps the text files of ``folder`` (one level, ``*.json``) in a Web Storage object.

    Keys are ``<prefix><file name>``; ``<prefix>index`` lists the stored names (Web Storage
    enumerates keys poorly across bridges, so the index is kept explicitly). ``sync`` compares
    size and modification time with what it last stored, so an unchanged folder costs a
    directory listing.
    """

    SUFFIXES = (".json",)

    def __init__(self, folder, storage, prefix="asteria.saves."):
        self.folder = Path(folder)
        self.storage = storage
        self.prefix = str(prefix)
        self._seen = {}  # name -> (size, mtime_ns) as last stored
        self.stored = 0  # files written to the storage so far
        self.restored = 0  # files written back to the folder by restore()

    # -- storage side -------------------------------------------------------------------
    @property
    def index_key(self):
        return self.prefix + "index"

    def names(self):
        """File names the storage holds."""
        raw = self.storage.getItem(self.index_key)
        try:
            names = json.loads(raw) if raw else []
        except (TypeError, ValueError):
            names = []
        return [str(n) for n in names if isinstance(n, str)]

    def _write_index(self, names):
        self.storage.setItem(self.index_key, json.dumps(sorted(set(names))))

    # -- folder side --------------------------------------------------------------------
    def _files(self):
        if not self.folder.is_dir():
            return {}
        out = {}
        for path in sorted(self.folder.iterdir()):
            if path.is_file() and path.suffix in self.SUFFIXES:
                stat = path.stat()
                out[path.name] = (stat.st_size, stat.st_mtime_ns)
        return out

    def restore(self):
        """Write every stored file into the folder (files already there win); returns the
        number of files restored."""
        self.folder.mkdir(parents=True, exist_ok=True)
        count = 0
        for name in self.names():
            target = self.folder / name
            if target.exists() or "/" in name or "\\" in name or name.startswith("."):
                continue
            text = self.storage.getItem(self.prefix + name)
            if text is None:
                continue
            target.write_text(str(text), encoding="utf-8")
            count += 1
        self.restored += count
        self._seen = self._files()
        return count

    def sync(self):
        """Store files that changed since the last call, forget files that are gone; returns
        the number of files stored or removed."""
        current = self._files()
        changed = [n for n, sig in current.items() if self._seen.get(n) != sig]
        gone = [n for n in self._seen if n not in current]
        if not changed and not gone:
            return 0
        names = set(self.names())
        for name in changed:
            try:
                text = (self.folder / name).read_text(encoding="utf-8")
            except OSError:
                continue
            self.storage.setItem(self.prefix + name, text)
            names.add(name)
            self._seen[name] = current[name]
            self.stored += 1
        for name in gone:
            self.storage.removeItem(self.prefix + name)
            names.discard(name)
            self._seen.pop(name, None)
        self._write_index(names)
        return len(changed) + len(gone)
