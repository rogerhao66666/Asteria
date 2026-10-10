"""Renderer-facing composition contract.

Produces backend-neutral draw packets from actor + attachment presentation state.
Continuous transform modifiers are evaluated at render time so smooth camera/object
motion is not limited by authored sprite-frame rate.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from math import cos, radians, sin, tau

from .actor_attachment import ActorAttachmentFrame


@dataclass(frozen=True, slots=True)
class RenderTransform:
    x: float = 0
    y: float = 0
    rotation_deg: float = 0
    scale_x: float = 1
    scale_y: float = 1
    opacity: float = 1
    visible: bool = True
    flip_x: bool = False
    flip_y: bool = False


@dataclass(frozen=True, slots=True)
class ActorVisualLayer:
    asset_id: str
    z: float = 0
    component_id: str = "body"
    transform: RenderTransform = RenderTransform()


@dataclass(frozen=True, slots=True)
class DrawPacket:
    asset_id: str
    transform: RenderTransform
    z: float = 0
    owner_id: str | None = None
    component_id: str | None = None


@dataclass(frozen=True, slots=True)
class Vibration:
    amplitude_x: float = 0
    amplitude_y: float = 0
    rotation_amplitude_deg: float = 0
    frequency_hz: float = 20
    duration_ms: float = 100
    decay: float = 1
    phase: float = 0

    def __post_init__(self):
        if self.frequency_hz < 0 or self.duration_ms <= 0 or self.decay < 0:
            raise ValueError("invalid vibration")

    def sample(self, time_ms: float) -> RenderTransform:
        if time_ms < 0 or time_ms >= self.duration_ms:
            return RenderTransform()
        u = time_ms / self.duration_ms
        envelope = (1 - u) ** self.decay
        wave = sin(tau * (self.frequency_hz * time_ms / 1000 + self.phase))
        return RenderTransform(
            self.amplitude_x * wave * envelope,
            self.amplitude_y * wave * envelope,
            self.rotation_amplitude_deg * wave * envelope,
        )


def combine(a: RenderTransform, b: RenderTransform) -> RenderTransform:
    """Compose child ``b`` in parent ``a`` space.

    Translation is scaled, mirrored and rotated by the parent before world
    translation. Flip is retained as canonical render state rather than being
    lost at the renderer boundary.
    """
    x = b.x * a.scale_x * (-1 if a.flip_x else 1)
    y = b.y * a.scale_y * (-1 if a.flip_y else 1)
    ang = radians(a.rotation_deg)
    x, y = x * cos(ang) - y * sin(ang), x * sin(ang) + y * cos(ang)
    return RenderTransform(
        a.x + x,
        a.y + y,
        a.rotation_deg + b.rotation_deg,
        a.scale_x * b.scale_x,
        a.scale_y * b.scale_y,
        a.opacity * b.opacity,
        a.visible and b.visible,
        a.flip_x ^ b.flip_x,
        a.flip_y ^ b.flip_y,
    )


class PresentationRenderComposer:
    def actor_packets(
        self,
        frame: ActorAttachmentFrame,
        actor_asset_id: str,
        actor_transform: RenderTransform = RenderTransform(),
        modifier: Callable[[float], RenderTransform] | None = None,
        render_time_ms: float = 0,
        actor_layers: tuple[ActorVisualLayer, ...] = (),
        layer_z: dict[str, float] | None = None,
    ) -> tuple[DrawPacket, ...]:
        """Compose actor layers and generic attachments into deterministic draw order.

        ``layer_z`` names insertion bands without giving them gameplay meaning.
        A character can therefore put an attachment behind the body, between body
        and foreground hand pixels, or in front without baking the attachment.
        """
        mod = modifier(render_time_ms) if modifier else RenderTransform()
        root = combine(actor_transform, mod)
        bands = {"behind": -100.0, "attachment": 0.0, "foreground": 100.0}
        if layer_z:
            bands.update({str(k): float(v) for k, v in layer_z.items()})
        packets = [DrawPacket(actor_asset_id, root, 0, frame.actor_id, "actor")]
        # Frame-authored layers travel with ActorAttachmentFrame; explicit layers remain
        # supported for editor previews/backward compatibility.
        for layer in frame.visual_layers:
            t = layer.transform
            lt = RenderTransform(
                t.x, t.y, t.rotation_deg, t.scale_x, t.scale_y, t.opacity, t.visible, t.flip_x, t.flip_y
            )
            packets.append(
                DrawPacket(layer.asset_id, combine(root, lt), layer.z + t.z_offset, frame.actor_id, layer.component_id)
            )
        for layer in actor_layers:
            packets.append(
                DrawPacket(layer.asset_id, combine(root, layer.transform), layer.z, frame.actor_id, layer.component_id)
            )
        for a in frame.attachments:
            t = a.transform
            local = RenderTransform(
                t.x, t.y, t.rotation_deg, t.scale_x, t.scale_y, t.opacity, t.visible, t.flip_x, t.flip_y
            )
            z = bands.get(getattr(a, "render_layer", "attachment"), 0.0) + t.z_offset
            packets.append(DrawPacket(a.asset_id, combine(root, local), z, frame.actor_id, a.id))
        return tuple(
            sorted(
                (x for x in packets if x.transform.visible and x.transform.opacity > 0),
                key=lambda x: (x.z, x.component_id or ""),
            )
        )
