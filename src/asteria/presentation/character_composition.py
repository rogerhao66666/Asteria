"""Layered character composition (CMP-01, CMP-02, CMP-04) resolved to draw parts.

A body sprite sheet's metadata may carry ``socket_rig``, ``attachments`` and
``visual_layers`` (authored in the editor's Character Composition tab). This
module turns them into the parts drawn with a body frame:

* sockets are points in body-frame source pixels, relative to the frame pivot
  (x right, y down), optionally keyed per sheet frame;
* an attachment draws one frame of another sprite sheet with its grip on the
  socket, inheriting the socket's rotation and scale;
* a visual layer draws the *same* frame index of another sheet over / under the
  body (a cape, a front hand), offset by its transform.

``z`` below zero draws behind the body, otherwise in front. Nothing here has
gameplay meaning; equipment or scripts decide *what* is attached.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .actor_visual_layers import ActorVisualLayerTrack
from .attachment_runtime import AttachmentRuntime
from .attachments import Attachment, GripTransform, SocketRig, Transform2D


def attachment_from_data(data):
    data = dict(data)
    data["local"] = Transform2D(**data.get("local", {}))
    data["grip"] = GripTransform(**data.get("grip", {}))
    return Attachment(**data)


def attachment_to_data(attachment):
    return asdict(attachment)


def composition_of(meta):
    """``(SocketRig, (Attachment, ...), ActorVisualLayerTrack)`` from sheet metadata."""
    rig = SocketRig.from_dict(meta["socket_rig"]) if meta.get("socket_rig") else SocketRig()
    attachments = tuple(attachment_from_data(x) for x in meta.get("attachments", ()))
    layers = ActorVisualLayerTrack.from_dict(meta.get("visual_layers") or {"layers": []})
    return rig, attachments, layers


@dataclass(frozen=True, slots=True)
class CompositionPart:
    """One sprite drawn with the body, in body source pixels.

    ``x, y`` is the part's top-left (before rotation): measured from the body pivot
    for an attachment, from the body frame's top-left for a layer.
    """

    kind: str  # "attachment" | "layer"
    id: str
    asset_id: str
    frame_index: int
    x: float
    y: float
    rotation_deg: float
    scale_x: float
    scale_y: float
    opacity: float
    z: float

    @property
    def behind(self):
        return self.z < 0


class CharacterComposition:
    def __init__(self, rig, attachments=(), layers=None):
        self.rig = rig
        self.layers = layers or ActorVisualLayerTrack()
        self.runtime = AttachmentRuntime(rig, Transform2D())
        self.runtime.attach_many(attachments)

    @classmethod
    def from_meta(cls, meta):
        """The sheet's composition, or ``None`` when it has no attachments or layers."""
        if not meta.get("attachments") and not (meta.get("visual_layers") or {}).get("layers"):
            return None
        return cls(*composition_of(meta))

    def parts(self, clip_id, frame_index):
        """Visible parts for a body frame, back to front."""
        parts = []
        for resolved in self.runtime.resolve_all(frame_index):
            t = resolved.transform
            if not t.visible:
                continue
            parts.append(
                CompositionPart(
                    "attachment",
                    resolved.id,
                    resolved.asset_id,
                    int(resolved.metadata.get("frame", 0)),
                    t.x,
                    t.y,
                    t.rotation_deg,
                    t.scale_x,
                    t.scale_y,
                    t.opacity,
                    float(t.z_offset),
                )
            )
        for layer in self.layers.resolve(clip_id, frame_index):
            t = layer.transform
            if not t.visible:
                continue
            parts.append(
                CompositionPart(
                    "layer",
                    layer.component_id,
                    layer.asset_id,
                    frame_index,
                    t.x,
                    t.y,
                    t.rotation_deg,
                    t.scale_x,
                    t.scale_y,
                    t.opacity,
                    float(layer.z),
                )
            )
        return sorted(parts, key=lambda p: p.z)
