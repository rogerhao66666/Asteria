"""Generic socket/anchor model for composable visual presentation.

Sockets intentionally carry no gameplay meaning: a project may attach a weapon,
shield, hat, wing, prop, VFX, UI marker, or any other visual resource.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable
import bisect


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


@dataclass(frozen=True, slots=True)
class Transform2D:
    x: float = 0.0
    y: float = 0.0
    rotation_deg: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    flip_x: bool = False
    flip_y: bool = False
    opacity: float = 1.0
    visible: bool = True
    z_offset: int = 0

    def validate(self) -> None:
        if self.scale_x < 0 or self.scale_y < 0:
            raise ValueError("scale must be non-negative; use flip flags for mirroring")
        if not 0.0 <= self.opacity <= 1.0:
            raise ValueError("opacity must be within [0, 1]")

    @staticmethod
    def interpolate(a: "Transform2D", b: "Transform2D", t: float) -> "Transform2D":
        t = min(1.0, max(0.0, float(t)))
        # Discrete properties switch at the destination key rather than creating
        # impossible half-visible/half-flipped states.
        discrete_b = t >= 1.0
        return Transform2D(
            _lerp(a.x,b.x,t), _lerp(a.y,b.y,t), _lerp(a.rotation_deg,b.rotation_deg,t),
            _lerp(a.scale_x,b.scale_x,t), _lerp(a.scale_y,b.scale_y,t),
            b.flip_x if discrete_b else a.flip_x,
            b.flip_y if discrete_b else a.flip_y,
            _lerp(a.opacity,b.opacity,t), b.visible if discrete_b else a.visible,
            b.z_offset if discrete_b else a.z_offset,
        )


@dataclass(frozen=True, slots=True)
class SocketKey:
    frame: int
    transform: Transform2D = Transform2D()
    interpolate: bool = True

    def validate(self) -> None:
        if self.frame < 0: raise ValueError("socket key frame must be >= 0")
        self.transform.validate()


@dataclass(frozen=True, slots=True)
class Socket:
    id: str
    parent: str | None = None
    pivot_x: float = 0.0
    pivot_y: float = 0.0
    default: Transform2D = Transform2D()
    keys: tuple[SocketKey, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.id: raise ValueError("socket id required")
        self.default.validate()
        last = -1
        for key in self.keys:
            key.validate()
            if key.frame <= last: raise ValueError("socket keys must have unique ascending frames")
            last = key.frame

    def sample(self, frame: int, subframe: float = 0.0) -> Transform2D:
        if frame < 0: raise ValueError("frame must be >= 0")
        if not self.keys: return self.default
        frames = [k.frame for k in self.keys]
        pos = bisect.bisect_right(frames, frame) - 1
        if pos < 0: return self.default
        left = self.keys[pos]
        if pos + 1 >= len(self.keys): return left.transform
        right = self.keys[pos + 1]
        if not left.interpolate: return left.transform
        absolute = frame + min(0.999999, max(0.0, subframe))
        span = right.frame - left.frame
        t = (absolute - left.frame) / span
        return Transform2D.interpolate(left.transform, right.transform, t)


@dataclass(frozen=True, slots=True)
class GripTransform:
    """Asset-space grip that must land on the resolved socket target.

    Coordinates are expressed in the attachment asset's local pixel/unit space.
    This is presentation metadata only and carries no weapon semantics.
    """
    x: float = 0.0
    y: float = 0.0
    rotation_deg: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0

    def validate(self) -> None:
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise ValueError("grip scale must be > 0")


@dataclass(frozen=True, slots=True)
class Attachment:
    id: str
    asset_id: str
    socket_id: str
    local: Transform2D = Transform2D()
    inherit_position: bool = True
    inherit_rotation: bool = True
    inherit_scale: bool = True
    inherit_opacity: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    grip: GripTransform = GripTransform()
    render_layer: str = "attachment"

    def validate(self) -> None:
        if not self.id or not self.asset_id or not self.socket_id:
            raise ValueError("attachment id, asset_id and socket_id are required")
        self.local.validate()
        self.grip.validate()
        if not self.render_layer:
            raise ValueError("render_layer required")


@dataclass(slots=True)
class SocketRig:
    sockets: dict[str, Socket] = field(default_factory=dict)

    def add(self, socket: Socket) -> None:
        socket.validate()
        if socket.id in self.sockets: raise ValueError(f"duplicate socket: {socket.id}")
        if socket.parent == socket.id: raise ValueError("socket cannot parent itself")
        self.sockets[socket.id] = socket
        self.validate()

    def validate(self) -> None:
        for s in self.sockets.values():
            s.validate()
            if s.parent is not None and s.parent not in self.sockets:
                raise ValueError(f"missing parent socket: {s.parent}")
        def walk(sid: str, path: set[str]):
            if sid in path: raise ValueError("socket parent cycle")
            parent = self.sockets[sid].parent
            if parent is not None: walk(parent, path | {sid})
        for sid in self.sockets: walk(sid, set())

    def sample(self, socket_id: str, frame: int, subframe: float = 0.0) -> Transform2D:
        return self.sockets[socket_id].sample(frame, subframe)

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "sockets": [asdict(s) for s in self.sockets.values()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SocketRig":
        rig = cls()
        for raw in data.get("sockets", []):
            keys = tuple(SocketKey(int(k["frame"]), Transform2D(**k.get("transform", {})), bool(k.get("interpolate", True))) for k in raw.get("keys", []))
            rig.add(Socket(raw["id"], raw.get("parent"), float(raw.get("pivot_x",0)), float(raw.get("pivot_y",0)), Transform2D(**raw.get("default",{})), keys, dict(raw.get("metadata",{}))))
        rig.validate(); return rig


def validate_attachments(rig: SocketRig, attachments: Iterable[Attachment]) -> tuple[Attachment, ...]:
    result = tuple(attachments); seen=set()
    for a in result:
        a.validate()
        if a.id in seen: raise ValueError(f"duplicate attachment: {a.id}")
        if a.socket_id not in rig.sockets: raise ValueError(f"unknown socket: {a.socket_id}")
        seen.add(a.id)
    return result
