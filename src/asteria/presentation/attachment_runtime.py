"""Runtime materialization and lifecycle for generic visual attachments.

This module deliberately knows nothing about weapons, equipment, battle, skills,
or any other gameplay vocabulary. It resolves a SocketRig into world-space
attachment poses and manages attachment instances by stable project IDs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from math import cos, radians, sin
from typing import Any, Callable, Iterable

from .attachments import Attachment, GripTransform, SocketRig, Transform2D, validate_attachments


class AttachmentState(str, Enum):
    ACTIVE = "active"
    HIDDEN = "hidden"
    DETACHED = "detached"


@dataclass(frozen=True, slots=True)
class ResolvedAttachment:
    id: str
    asset_id: str
    socket_id: str
    transform: Transform2D
    state: AttachmentState
    metadata: dict[str, Any] = field(default_factory=dict)
    render_layer: str = "attachment"


@dataclass(slots=True)
class AttachmentInstance:
    spec: Attachment
    state: AttachmentState = AttachmentState.ACTIVE
    runtime_data: dict[str, Any] = field(default_factory=dict)

    def set_visible(self, visible: bool) -> None:
        if self.state == AttachmentState.DETACHED:
            raise RuntimeError("cannot change visibility of detached attachment")
        self.state = AttachmentState.ACTIVE if visible else AttachmentState.HIDDEN


def _combine(
    parent: Transform2D,
    child: Transform2D,
    *,
    inherit_position: bool = True,
    inherit_rotation: bool = True,
    inherit_scale: bool = True,
    inherit_opacity: bool = True,
) -> Transform2D:
    """Compose child into parent in 2D while honoring inheritance policy."""
    px, py = child.x, child.y
    if inherit_scale:
        px *= parent.scale_x
        py *= parent.scale_y
    if inherit_rotation:
        a = radians(parent.rotation_deg)
        px, py = px * cos(a) - py * sin(a), px * sin(a) + py * cos(a)
    x = (parent.x + px) if inherit_position else child.x
    y = (parent.y + py) if inherit_position else child.y
    return Transform2D(
        x=x,
        y=y,
        rotation_deg=(parent.rotation_deg + child.rotation_deg) if inherit_rotation else child.rotation_deg,
        scale_x=(parent.scale_x * child.scale_x) if inherit_scale else child.scale_x,
        scale_y=(parent.scale_y * child.scale_y) if inherit_scale else child.scale_y,
        flip_x=parent.flip_x ^ child.flip_x if inherit_scale else child.flip_x,
        flip_y=parent.flip_y ^ child.flip_y if inherit_scale else child.flip_y,
        opacity=(parent.opacity * child.opacity) if inherit_opacity else child.opacity,
        visible=parent.visible and child.visible,
        z_offset=parent.z_offset + child.z_offset,
    )


def _place_asset_at_grip(target: Transform2D, grip: GripTransform) -> Transform2D:
    """Return the asset transform whose authored grip coincides with ``target``.

    This solves the production problem that point attachment alone does not place
    a sprite correctly when its visual origin is not the hand/grip point.
    """
    grip.validate()
    sx = target.scale_x / grip.scale_x
    sy = target.scale_y / grip.scale_y
    rotation = target.rotation_deg - grip.rotation_deg
    a = radians(rotation)
    # Flip changes the local grip direction around the asset origin.  Account for
    # it before rotation so a mirrored attachment still lands its authored grip
    # exactly on the socket target.
    dx = grip.x * sx * (-1.0 if target.flip_x else 1.0)
    dy = grip.y * sy * (-1.0 if target.flip_y else 1.0)
    rx, ry = dx * cos(a) - dy * sin(a), dx * sin(a) + dy * cos(a)
    return Transform2D(
        x=target.x - rx,
        y=target.y - ry,
        rotation_deg=rotation,
        scale_x=sx,
        scale_y=sy,
        flip_x=target.flip_x,
        flip_y=target.flip_y,
        opacity=target.opacity,
        visible=target.visible,
        z_offset=target.z_offset,
    )


def _apply_pivot(t: Transform2D, pivot_x: float, pivot_y: float) -> Transform2D:
    """Apply socket pivot before a child attachment is composed."""
    if pivot_x == 0 and pivot_y == 0:
        return t
    a = radians(t.rotation_deg)
    dx = pivot_x * t.scale_x
    dy = pivot_y * t.scale_y
    rx, ry = dx * cos(a) - dy * sin(a), dx * sin(a) + dy * cos(a)
    return Transform2D(
        t.x + rx,
        t.y + ry,
        t.rotation_deg,
        t.scale_x,
        t.scale_y,
        t.flip_x,
        t.flip_y,
        t.opacity,
        t.visible,
        t.z_offset,
    )


@dataclass(slots=True)
class AttachmentRuntime:
    rig: SocketRig
    root_transform: Transform2D = Transform2D()
    instances: dict[str, AttachmentInstance] = field(default_factory=dict)
    _on_attach: list[Callable[[AttachmentInstance], None]] = field(default_factory=list, repr=False)
    _on_detach: list[Callable[[AttachmentInstance], None]] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.rig.validate()
        self.root_transform.validate()

    def on_attach(self, callback: Callable[[AttachmentInstance], None]) -> None:
        self._on_attach.append(callback)

    def on_detach(self, callback: Callable[[AttachmentInstance], None]) -> None:
        self._on_detach.append(callback)

    def attach(self, spec: Attachment, *, replace: bool = False) -> AttachmentInstance:
        validate_attachments(self.rig, (spec,))
        existing = self.instances.get(spec.id)
        if existing is not None and existing.state != AttachmentState.DETACHED and not replace:
            raise ValueError(f"attachment already active: {spec.id}")
        if existing is not None and existing.state != AttachmentState.DETACHED:
            self.detach(spec.id)
        instance = AttachmentInstance(spec)
        self.instances[spec.id] = instance
        for cb in tuple(self._on_attach):
            cb(instance)
        return instance

    def attach_many(self, specs: Iterable[Attachment]) -> tuple[AttachmentInstance, ...]:
        specs = validate_attachments(self.rig, specs)
        # Transactional preflight: do not partially mutate on duplicate active IDs.
        for spec in specs:
            old = self.instances.get(spec.id)
            if old is not None and old.state != AttachmentState.DETACHED:
                raise ValueError(f"attachment already active: {spec.id}")
        return tuple(self.attach(spec) for spec in specs)

    def detach(self, attachment_id: str) -> AttachmentInstance:
        instance = self.instances.get(attachment_id)
        if instance is None or instance.state == AttachmentState.DETACHED:
            raise KeyError(f"attachment not active: {attachment_id}")
        instance.state = AttachmentState.DETACHED
        for cb in tuple(self._on_detach):
            cb(instance)
        return instance

    def swap(self, attachment_id: str, replacement: Attachment) -> AttachmentInstance:
        """Atomically replace an active attachment while preserving stable slot intent."""
        if attachment_id not in self.instances or self.instances[attachment_id].state == AttachmentState.DETACHED:
            raise KeyError(f"attachment not active: {attachment_id}")
        validate_attachments(self.rig, (replacement,))
        if replacement.id != attachment_id:
            raise ValueError("swap replacement must preserve attachment id")
        self.detach(attachment_id)
        return self.attach(replacement)

    def set_visible(self, attachment_id: str, visible: bool) -> None:
        self._active(attachment_id).set_visible(visible)

    def _active(self, attachment_id: str) -> AttachmentInstance:
        instance = self.instances.get(attachment_id)
        if instance is None or instance.state == AttachmentState.DETACHED:
            raise KeyError(f"attachment not active: {attachment_id}")
        return instance

    def socket_world_transform(self, socket_id: str, frame: int, subframe: float = 0.0) -> Transform2D:
        if socket_id not in self.rig.sockets:
            raise KeyError(f"unknown socket: {socket_id}")
        chain = []
        current = self.rig.sockets[socket_id]
        while current is not None:
            chain.append(current)
            current = self.rig.sockets[current.parent] if current.parent else None
        world = self.root_transform
        for socket in reversed(chain):
            sampled = socket.sample(frame, subframe)
            world = _combine(world, sampled)
            world = _apply_pivot(world, socket.pivot_x, socket.pivot_y)
        return world

    def resolve(self, attachment_id: str, frame: int, subframe: float = 0.0) -> ResolvedAttachment:
        instance = self._active(attachment_id)
        spec = instance.spec
        socket_world = self.socket_world_transform(spec.socket_id, frame, subframe)
        world = _combine(
            socket_world,
            spec.local,
            inherit_position=spec.inherit_position,
            inherit_rotation=spec.inherit_rotation,
            inherit_scale=spec.inherit_scale,
            inherit_opacity=spec.inherit_opacity,
        )
        world = _place_asset_at_grip(world, spec.grip)
        if instance.state == AttachmentState.HIDDEN:
            world = Transform2D(
                world.x,
                world.y,
                world.rotation_deg,
                world.scale_x,
                world.scale_y,
                world.flip_x,
                world.flip_y,
                world.opacity,
                False,
                world.z_offset,
            )
        return ResolvedAttachment(
            spec.id, spec.asset_id, spec.socket_id, world, instance.state, dict(spec.metadata), spec.render_layer
        )

    def resolve_all(self, frame: int, subframe: float = 0.0) -> tuple[ResolvedAttachment, ...]:
        resolved = [
            self.resolve(k, frame, subframe) for k, v in self.instances.items() if v.state != AttachmentState.DETACHED
        ]
        return tuple(sorted(resolved, key=lambda r: (r.transform.z_offset, r.id)))

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": 1,
            "instances": [
                {"id": i.spec.id, "state": i.state.value, "runtime_data": dict(i.runtime_data)}
                for i in self.instances.values()
                if i.state != AttachmentState.DETACHED
            ],
        }

    def restore_runtime_state(self, snapshot: dict[str, Any]) -> None:
        states = {raw["id"]: raw for raw in snapshot.get("instances", [])}
        for aid, instance in self.instances.items():
            raw = states.get(aid)
            if raw is None:
                continue
            instance.state = AttachmentState(raw.get("state", AttachmentState.ACTIVE.value))
            instance.runtime_data = dict(raw.get("runtime_data", {}))
