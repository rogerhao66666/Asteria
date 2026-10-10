"""Editable starter policies for equipment presentation.

These are convenience presets above the generic action/attachment boundary.
They are not JRPG/ARPG engine branches: projects may copy, edit, replace, or
ignore them.  The policy only answers presentation questions: whether a visual
is persistent outside actions and what should happen after an action.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from .action_binding import ActionPresentationRequest, AfterAction, VisualResource
from .canonical import Command


class IdleVisualMode(str, Enum):
    HIDDEN = "hidden"
    PERSISTENT = "persistent"


@dataclass(frozen=True, slots=True)
class EquipmentPresentationPolicy:
    id: str
    idle_visual: IdleVisualMode
    after_action: AfterAction
    preview_on_selection: bool = False
    attachment_id: str = "active_visual"

    def validate(self) -> None:
        if not self.id or not self.attachment_id:
            raise ValueError("policy id and attachment_id required")

    def action_request(self, request: ActionPresentationRequest) -> ActionPresentationRequest:
        """Apply only presentation lifecycle defaults to an already-resolved action."""
        self.validate()
        return replace(request, attachment_id=self.attachment_id, after_action=self.after_action)

    def idle_commands(self, visual: VisualResource | None) -> tuple[Command, ...]:
        """Build initial/idle presentation commands without reading equipment state."""
        self.validate()
        if self.idle_visual is IdleVisualMode.HIDDEN:
            return (Command("attachment", "hide", {"attachment_id": self.attachment_id}),)
        if visual is None:
            return ()
        from dataclasses import asdict

        return (
            Command(
                "attachment",
                "swap_or_attach",
                {
                    "attachment_id": self.attachment_id,
                    "asset_id": visual.asset_id,
                    "socket_id": visual.socket_id,
                    "grip": asdict(visual.grip),
                    "local": asdict(visual.local),
                    "render_layer": visual.render_layer,
                    "metadata": dict(visual.metadata),
                },
            ),
        )

    def selection_preview_commands(self, visual: VisualResource | None) -> tuple[Command, ...]:
        """Optional menu/selection preview; never mutates gameplay equipment."""
        if not self.preview_on_selection or visual is None:
            return ()
        from dataclasses import asdict

        return (
            Command(
                "attachment",
                "swap_or_attach",
                {
                    "attachment_id": self.attachment_id,
                    "asset_id": visual.asset_id,
                    "socket_id": visual.socket_id,
                    "grip": asdict(visual.grip),
                    "local": asdict(visual.local),
                    "render_layer": visual.render_layer,
                    "metadata": dict(visual.metadata),
                },
            ),
        )


# Starter conveniences only. Names describe the shipped template behavior, not
# runtime modes or engine types.
ACTION_SCOPED_STARTER = EquipmentPresentationPolicy(
    id="starter.action_scoped",
    idle_visual=IdleVisualMode.HIDDEN,
    after_action=AfterAction.HIDE,
    preview_on_selection=True,
)

PERSISTENT_ACTIVE_STARTER = EquipmentPresentationPolicy(
    id="starter.persistent_active",
    idle_visual=IdleVisualMode.PERSISTENT,
    after_action=AfterAction.KEEP,
    preview_on_selection=False,
)
