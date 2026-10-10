"""Adapter seam between an existing actor animator and generic attachments.

The engine does not replace the actor animator. Any animator capable of exposing
clip/frame/subframe state can drive the same SocketRig/AttachmentRuntime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .actor_visual_layers import ActorVisualLayerTrack, ResolvedVisualLayer
from .attachment_runtime import AttachmentRuntime, ResolvedAttachment


@dataclass(frozen=True, slots=True)
class ActorAnimationPose:
    clip_id: str
    frame: int
    subframe: float = 0.0
    facing_x: int = 1
    visible: bool = True

    def __post_init__(self):
        if self.frame < 0:
            raise ValueError("frame must be >= 0")
        if not 0 <= self.subframe <= 1:
            raise ValueError("subframe must be in [0,1]")
        if self.facing_x not in (-1, 1):
            raise ValueError("facing_x must be -1 or 1")


class ActorAnimatorSource(Protocol):
    def presentation_pose(self) -> ActorAnimationPose: ...


@dataclass(frozen=True, slots=True)
class ActorAttachmentFrame:
    actor_id: str
    pose: ActorAnimationPose
    attachments: tuple[ResolvedAttachment, ...]
    visual_layers: tuple[ResolvedVisualLayer, ...] = ()


class ActorAttachmentBinding:
    def __init__(
        self,
        actor_id: str,
        animator: ActorAnimatorSource,
        runtime: AttachmentRuntime,
        visual_layers: ActorVisualLayerTrack | None = None,
        *,
        mirror_axis_x: float = 0.0,
    ):
        if not actor_id:
            raise ValueError("actor_id required")
        self.actor_id = actor_id
        self.animator = animator
        self.runtime = runtime
        self.visual_layers = visual_layers
        self.mirror_axis_x = float(mirror_axis_x)

    def resolve(self) -> ActorAttachmentFrame:
        pose = self.animator.presentation_pose()
        if not isinstance(pose, ActorAnimationPose):
            raise TypeError("animator must return ActorAnimationPose")
        if not pose.visible:
            return ActorAttachmentFrame(self.actor_id, pose, (), ())
        # Facing is resolved at the socket target, not by naively mirroring the
        # already-placed asset origin.  Otherwise non-zero grip pivots drift away
        # from the hand after a horizontal flip.
        if pose.facing_x == -1:
            resolved = tuple(
                _resolve_mirrored(self.runtime, x, pose.frame, pose.subframe, self.mirror_axis_x)
                for x in self.runtime.instances.values()
                if x.state.value != "detached"
            )
        else:
            resolved = self.runtime.resolve_all(pose.frame, pose.subframe)
        layers = self.visual_layers.resolve(pose.clip_id, pose.frame) if self.visual_layers else ()
        if pose.facing_x == -1:
            layers = tuple(_mirror_layer(x, self.mirror_axis_x) for x in layers)
        return ActorAttachmentFrame(self.actor_id, pose, resolved, layers)


def _mirror_transform(t, axis_x: float):
    from .attachments import Transform2D

    return Transform2D(
        x=2.0 * axis_x - t.x,
        y=t.y,
        rotation_deg=-t.rotation_deg,
        scale_x=t.scale_x,
        scale_y=t.scale_y,
        flip_x=not t.flip_x,
        flip_y=t.flip_y,
        opacity=t.opacity,
        visible=t.visible,
        z_offset=t.z_offset,
    )


def _resolve_mirrored(runtime, instance, frame: int, subframe: float, axis_x: float) -> ResolvedAttachment:
    # Re-resolve from a mirrored socket target so GripTransform remains exact.
    from .attachment_runtime import AttachmentState, _combine, _place_asset_at_grip

    spec = instance.spec
    target = runtime.socket_world_transform(spec.socket_id, frame, subframe)
    target = _mirror_transform(target, axis_x)
    target = _combine(
        target,
        spec.local,
        inherit_position=spec.inherit_position,
        inherit_rotation=spec.inherit_rotation,
        inherit_scale=spec.inherit_scale,
        inherit_opacity=spec.inherit_opacity,
    )
    world = _place_asset_at_grip(target, spec.grip)
    if instance.state == AttachmentState.HIDDEN:
        from .attachments import Transform2D

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


def _mirror_layer(layer: ResolvedVisualLayer, axis_x: float) -> ResolvedVisualLayer:
    return ResolvedVisualLayer(layer.asset_id, layer.component_id, layer.z, _mirror_transform(layer.transform, axis_x))
