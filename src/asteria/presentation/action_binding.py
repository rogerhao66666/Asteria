"""Gameplay-action to Presentation binding.

This is an integration layer, not an equipment or combat rule engine. Gameplay
supplies an action request and resolved visual resource IDs. The binder converts
that intent into generic Presentation commands. Projects decide when to keep,
hide, or restore a temporary visual; JRPG/ARPG semantics are presets above this
boundary.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .attachments import GripTransform, Transform2D
from .canonical import Command


class AfterAction(str, Enum):
    KEEP = "keep"
    HIDE = "hide"
    RESTORE_PREVIOUS = "restore_previous"


@dataclass(frozen=True, slots=True)
class VisualResource:
    """Resolved visual resource for one generic attachment slot."""

    asset_id: str
    socket_id: str
    grip: GripTransform = GripTransform()
    local: Transform2D = Transform2D()
    render_layer: str = "attachment"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.asset_id or not self.socket_id:
            raise ValueError("asset_id and socket_id required")
        self.grip.validate()
        self.local.validate()


@dataclass(frozen=True, slots=True)
class ActionPresentationRequest:
    """Meaning-neutral presentation request emitted by gameplay/action logic."""

    action_id: str
    motion_id: str | None = None
    visual: VisualResource | None = None
    attachment_id: str = "active_visual"
    after_action: AfterAction = AfterAction.KEEP
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.action_id:
            raise ValueError("action_id required")
        if not self.attachment_id:
            raise ValueError("attachment_id required")
        if self.visual is not None:
            self.visual.validate()


@dataclass(frozen=True, slots=True)
class ActionPresentationPlan:
    begin: tuple[Command, ...]
    end: tuple[Command, ...]
    previous_visual: VisualResource | None = None


@dataclass(slots=True)
class ActionPresentationBinder:
    """Builds generic presentation commands from a resolved action request.

    ``current`` is presentation state supplied by the caller. The binder never
    reads gameplay equipment and never chooses a weapon/resource by itself.
    """

    animation_channel: str = "animation"
    attachment_channel: str = "attachment"

    def _attach_args(self, request: ActionPresentationRequest, visual: VisualResource) -> dict[str, Any]:
        from dataclasses import asdict

        return {
            "attachment_id": request.attachment_id,
            "asset_id": visual.asset_id,
            "socket_id": visual.socket_id,
            "grip": asdict(visual.grip),
            "local": asdict(visual.local),
            "render_layer": visual.render_layer,
            "metadata": dict(visual.metadata),
        }

    def plan(
        self, request: ActionPresentationRequest, *, current: VisualResource | None = None
    ) -> ActionPresentationPlan:
        request.validate()
        begin: list[Command] = []
        end: list[Command] = []

        if request.visual is not None:
            args = self._attach_args(request, request.visual)
            # ``swap_or_attach`` is an orchestration verb: the integration executor
            # resolves it against current presentation state without gameplay meaning.
            begin.append(Command(self.attachment_channel, "swap_or_attach", args))
        if request.motion_id:
            begin.append(
                Command(
                    self.animation_channel,
                    "play",
                    {
                        "animation_id": request.motion_id,
                        "action_id": request.action_id,
                    },
                )
            )

        if request.after_action is AfterAction.HIDE and request.visual is not None:
            end.append(Command(self.attachment_channel, "hide", {"attachment_id": request.attachment_id}))
        elif request.after_action is AfterAction.RESTORE_PREVIOUS:
            if current is None:
                if request.visual is not None:
                    end.append(Command(self.attachment_channel, "hide", {"attachment_id": request.attachment_id}))
            else:
                end.append(Command(self.attachment_channel, "swap_or_attach", self._attach_args(request, current)))

        return ActionPresentationPlan(tuple(begin), tuple(end), current)
