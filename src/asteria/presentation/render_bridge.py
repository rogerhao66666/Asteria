"""Backend-neutral bridge from Presentation layers to render submissions."""

from dataclasses import dataclass, field
from typing import Any, Protocol
from .gap_hardening import SubmissionKey, Submission, stable_submission_batches


@dataclass(frozen=True, slots=True)
class Transform2D:
    x: float = 0.0
    y: float = 0.0
    rotation_deg: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0


@dataclass(frozen=True, slots=True)
class RenderMaterial:
    id: str | None = None
    parameters: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RenderItem:
    asset_id: str
    z: int
    transform: Transform2D = Transform2D()
    opacity: float = 1.0
    blend_mode: str = "alpha"
    material: RenderMaterial = RenderMaterial()
    visible: bool = True

    def __post_init__(self):
        if not 0 <= self.opacity <= 1:
            raise ValueError("opacity")


@dataclass(frozen=True, slots=True)
class RenderBatch:
    key: SubmissionKey
    items: tuple[RenderItem, ...]


class RenderBackend(Protocol):
    def begin_frame(self, camera: Any = None) -> None: ...
    def submit(self, batch: RenderBatch) -> None: ...
    def end_frame(self) -> None: ...


class RenderQueue:
    def __init__(self):
        self._items = []
        self._seq = 0

    def add(self, item: RenderItem):
        if item.visible:
            self._items.append((item.z, self._seq, item))
            self._seq += 1

    def clear(self):
        self._items.clear()
        self._seq = 0

    def ordered(self):
        return tuple(x[2] for x in sorted(self._items, key=lambda x: (x[0], x[1])))

    def batches(self):
        ordered = self.ordered()
        submissions = tuple(Submission(SubmissionKey(i.asset_id, i.blend_mode, i.material.id), i.z, i) for i in ordered)
        return tuple(RenderBatch(k, tuple(s.payload for s in xs)) for k, xs in stable_submission_batches(submissions))


class PresentationRenderer:
    def __init__(self, backend: RenderBackend):
        self.backend = backend

    def render(self, queue: RenderQueue, camera=None):
        self.backend.begin_frame(camera)
        for b in queue.batches():
            self.backend.submit(b)
        self.backend.end_frame()


class RecordingBackend:
    """Deterministic test/backend adapter; not the final GPU renderer."""

    def __init__(self):
        self.frames = []
        self.current = None

    def begin_frame(self, camera=None):
        self.current = {"camera": camera, "batches": []}

    def submit(self, batch):
        self.current["batches"].append(batch)

    def end_frame(self):
        self.frames.append(self.current)
        self.current = None
