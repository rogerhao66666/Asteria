"""Pictures loaded ahead of the moment they are first drawn.

Starting a battle used to decode every battle sheet (combatants, effects, background) inside the
frame that opened the fight: a long stall on a lightweight computer. The preloader decodes the
pictures a fight is likely to show while the player is still in the field: the PNG decoding runs
on a worker thread (pygame lets go of the interpreter while it decodes), and the main thread only
converts finished pictures to the screen's pixel format, a little each frame. The pictures are the
same ones ``load_image`` would have produced: ``pygame.image.load(path).convert_alpha()``.
"""

from __future__ import annotations

import sys
import time


class ImagePreloader:
    """Keeps a bounded set of ready pictures, filled in the background.

    ``want(rels)`` names the pictures to hold, most wanted first; ``step()`` (once a frame on the
    main thread) collects what the worker decoded; ``take(rel)`` hands one over (or None).
    Loading stops once ``budget_bytes`` of decoded pixels are held; pictures in ``loaded`` (the
    host's own cache) are never loaded twice.
    ``threads`` (default: everywhere but the browser, which has none) decodes on a worker
    thread; without threads each ``step`` decodes one picture on the main thread, which still
    spreads a fight's pictures over the field's frames.
    """

    def __init__(
        self, pg, path, loaded=(), *, budget_bytes=64 << 20, step_seconds=0.001, threads=None
    ):
        self.pg = pg
        self.threads = (sys.platform != "emscripten") if threads is None else bool(threads)
        self.path = path
        self.loaded = loaded
        self.budget_bytes = int(budget_bytes)
        self.step_seconds = float(step_seconds)
        self._wanted = ()
        self._ready = {}  # rel -> converted Surface
        self._pending = None  # (rel, Future) being decoded
        self._failed = set()
        self._executor = None

    @property
    def held_bytes(self):
        return sum(_bytes(image) for image in self._ready.values())

    def ready(self, rel):
        return str(rel) in self._ready

    def want(self, rels):
        """Hold these pictures (most wanted first); pictures no longer wanted are let go."""
        self._wanted = tuple(dict.fromkeys(str(rel) for rel in rels))
        keep = set(self._wanted)
        for rel in [rel for rel in self._ready if rel not in keep]:
            del self._ready[rel]

    def take(self, rel):
        """The ready picture for ``rel`` (no longer held here), or None."""
        rel = str(rel)
        image = self._ready.pop(rel, None)
        if image is None and self._pending is not None and self._pending[0] == rel:
            future = self._pending[1]
            if future.done():
                self._pending = None
                image = self._converted(rel, future)
        return image

    def keep(self, rel, image):
        """Hold a picture that was loaded elsewhere again (released by its owner) when it is
        wanted and fits."""
        rel = str(rel)
        if rel in self._wanted and self.held_bytes + _bytes(image) <= self.budget_bytes:
            self._ready[rel] = image
            return True
        return False

    def step(self):
        """Collect decoded pictures and start the next decode (main thread, ``step_seconds``)."""
        deadline = time.perf_counter() + self.step_seconds
        while True:
            if self._pending is not None:
                rel, future = self._pending
                if not future.done():
                    return
                self._pending = None
                image = self._converted(rel, future)
                if image is not None and rel in self._wanted and rel not in self.loaded:
                    self._ready[rel] = image
            if not self._start_next() or time.perf_counter() >= deadline:
                return

    def close(self):
        if self._executor is not None:
            self._executor.shutdown(wait=True, cancel_futures=True)  # at most one decode
            self._executor = None
        self._pending = None
        self._ready.clear()

    def _start_next(self):
        if self.held_bytes >= self.budget_bytes:
            return False
        for rel in self._wanted:
            if rel not in self._ready and rel not in self._failed and rel not in self.loaded:
                break
        else:
            return False
        if not self.threads:
            self._pending = (rel, _Loaded(self.pg.image.load, self.path(rel)))
            return True
        if self._executor is None:
            from concurrent.futures import ThreadPoolExecutor

            self._executor = ThreadPoolExecutor(1, thread_name_prefix="asteria-preload")
        self._pending = (rel, self._executor.submit(self.pg.image.load, self.path(rel)))
        return True

    def _converted(self, rel, future):
        try:
            return future.result().convert_alpha()
        except Exception:  # noqa: BLE001 - a missing / unreadable picture: loaded (and reported)
            self._failed.add(rel)  # when it is drawn
            return None


class _Loaded:
    """A picture decoded right away, shaped like the Future a worker thread would give."""

    __slots__ = ("_result", "_error")

    def __init__(self, load, path):
        self._result = self._error = None
        try:
            self._result = load(path)
        except Exception as exc:  # noqa: BLE001 - reported by result(), like a Future
            self._error = exc

    def done(self):
        return True

    def result(self):
        if self._error is not None:
            raise self._error
        return self._result


def _bytes(image):
    return image.get_width() * image.get_height() * image.get_bytesize()
