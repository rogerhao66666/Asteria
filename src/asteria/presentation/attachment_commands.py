"""Presentation command executor for generic visual attachments.

The executor deliberately exposes presentation verbs only. It does not know whether
an attached visual is a weapon, hat, aura, prop, VFX, UI marker, or project-defined
asset. Commands operate on stable attachment IDs and generic asset/socket IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .attachment_runtime import AttachmentRuntime
from .attachments import Attachment, GripTransform, Transform2D
from .bridge import ExecutorSignal
from .canonical import Command


def _transform(raw: dict[str, Any] | None) -> Transform2D:
    raw = raw or {}
    return Transform2D(
        x=float(raw.get("x", 0.0)),
        y=float(raw.get("y", 0.0)),
        rotation_deg=float(raw.get("rotation_deg", 0.0)),
        scale_x=float(raw.get("scale_x", 1.0)),
        scale_y=float(raw.get("scale_y", 1.0)),
        flip_x=bool(raw.get("flip_x", False)),
        flip_y=bool(raw.get("flip_y", False)),
        opacity=float(raw.get("opacity", 1.0)),
        visible=bool(raw.get("visible", True)),
        z_offset=float(raw.get("z_offset", 0.0)),
    )


def attachment_from_args(args: dict[str, Any], *, forced_id: str | None = None) -> Attachment:
    aid = forced_id or str(args.get("attachment_id", ""))
    asset_id = str(args.get("asset_id", ""))
    socket_id = str(args.get("socket_id", ""))
    if not aid:
        raise ValueError("attachment_id required")
    if not asset_id:
        raise ValueError("asset_id required")
    if not socket_id:
        raise ValueError("socket_id required")
    return Attachment(
        id=aid,
        asset_id=asset_id,
        socket_id=socket_id,
        local=_transform(args.get("local")),
        inherit_position=bool(args.get("inherit_position", True)),
        inherit_rotation=bool(args.get("inherit_rotation", True)),
        inherit_scale=bool(args.get("inherit_scale", True)),
        inherit_opacity=bool(args.get("inherit_opacity", True)),
        metadata=dict(args.get("metadata", {})),
        grip=GripTransform(**dict(args.get("grip", {}))),
        render_layer=str(args.get("render_layer", "attachment")),
    )


@dataclass(slots=True)
class AttachmentCommandExecutor:
    """ExecutorRegistry-compatible adapter for the ``attachment`` channel."""

    runtime: AttachmentRuntime
    received: list[tuple[str, Command]] = field(default_factory=list)

    def dispatch(self, node_id: str, command: Command) -> tuple[ExecutorSignal, ...]:
        self.received.append((node_id, command))
        a = command.args
        action = command.action
        if action == "attach":
            self.runtime.attach(attachment_from_args(a), replace=bool(a.get("replace", False)))
        elif action == "swap_or_attach":
            spec = attachment_from_args(a)
            old = self.runtime.instances.get(spec.id)
            if old is None or old.state.value == "detached":
                self.runtime.attach(spec)
            else:
                self.runtime.swap(spec.id, spec)
        elif action == "detach":
            self.runtime.detach(str(a["attachment_id"]))
        elif action == "swap":
            aid = str(a["attachment_id"])
            self.runtime.swap(aid, attachment_from_args(a, forced_id=aid))
        elif action == "show":
            self.runtime.set_visible(str(a["attachment_id"]), True)
        elif action == "hide":
            self.runtime.set_visible(str(a["attachment_id"]), False)
        else:
            raise ValueError(f"unsupported attachment presentation action: {action!r}")
        # Attachment mutations are synchronous. Blocking is accepted for canonical
        # command compatibility and completes immediately after mutation.
        return (ExecutorSignal(f"command.completed:{node_id}"),) if command.blocking else ()

    def update(self, dt_ms: float) -> tuple[ExecutorSignal, ...]:
        if dt_ms < 0:
            raise ValueError("negative dt")
        return ()

    def cancel(self, node_id: str) -> None:
        # Mutations are instantaneous; there is no in-flight operation to cancel.
        return None
