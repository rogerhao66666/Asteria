"""Asset Browser -> generic attachment authoring seam.

The browser supplies stable canonical asset references. This module never
duplicates AssetStore records and never assigns gameplay meaning to assets.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from asteria.editor.attachment_authoring import AttachmentAuthoringModel
from asteria.presentation.attachments import Attachment, GripTransform, Transform2D


@dataclass(frozen=True, slots=True)
class AssetDragPayload:
    asset_id: str
    asset_kind: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    grip: GripTransform = GripTransform()
    render_layer: str = "attachment"

    def __post_init__(self):
        if not self.asset_id:
            raise ValueError("asset_id required")


@dataclass(frozen=True, slots=True)
class AttachmentDropRequest:
    payload: AssetDragPayload
    socket_id: str
    attachment_id: str
    local: Transform2D = Transform2D()
    inherit_position: bool = True
    inherit_rotation: bool = True
    inherit_scale: bool = True
    inherit_opacity: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)
    grip: GripTransform | None = None
    render_layer: str | None = None


class AssetAttachmentController:
    def __init__(self, authoring: AttachmentAuthoringModel, asset_exists=None):
        self.authoring = authoring
        self.asset_exists = asset_exists

    def can_drop(self, payload: AssetDragPayload, socket_id: str) -> tuple[bool, str | None]:
        if socket_id not in self.authoring.rig.sockets:
            return False, "unknown socket"
        if self.asset_exists is not None and not self.asset_exists(payload.asset_id):
            return False, "unknown asset"
        return True, None

    def drop(self, request: AttachmentDropRequest):
        ok, reason = self.can_drop(request.payload, request.socket_id)
        if not ok:
            raise ValueError(reason)
        md = dict(request.payload.metadata)
        md.update(request.metadata)
        if request.payload.asset_kind is not None:
            md.setdefault("asset_kind", request.payload.asset_kind)
        a = Attachment(
            id=request.attachment_id,
            asset_id=request.payload.asset_id,
            socket_id=request.socket_id,
            local=request.local,
            inherit_position=request.inherit_position,
            inherit_rotation=request.inherit_rotation,
            inherit_scale=request.inherit_scale,
            inherit_opacity=request.inherit_opacity,
            metadata=md,
            grip=request.grip or request.payload.grip,
            render_layer=request.render_layer or request.payload.render_layer,
        )
        self.authoring.attach(a)
        return a

    def move_attachment(self, attachment_id: str, socket_id: str):
        if socket_id not in self.authoring.rig.sockets:
            raise ValueError("unknown socket")
        inst = self.authoring.runtime.instances.get(attachment_id)
        if inst is None or inst.state.value == "detached":
            raise KeyError(attachment_id)
        old = inst.spec
        replacement = Attachment(
            id=old.id,
            asset_id=old.asset_id,
            socket_id=socket_id,
            local=old.local,
            inherit_position=old.inherit_position,
            inherit_rotation=old.inherit_rotation,
            inherit_scale=old.inherit_scale,
            inherit_opacity=old.inherit_opacity,
            metadata=dict(old.metadata),
            grip=old.grip,
            render_layer=old.render_layer,
        )
        self.authoring._checkpoint()
        self.authoring.runtime.detach(attachment_id)
        self.authoring.runtime.attach(replacement)
        return replacement
