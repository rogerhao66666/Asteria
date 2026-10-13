from __future__ import annotations

from dataclasses import dataclass

from .battle_action_menu import (
    BattleActionEntry,
    BattleActionMenuPolicy,
    BattleActionMenuRuntime,
)
from .battle_action_workflow import (
    BattleActionWorkflowRuntime,
)


def _id(value, name):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleInteractionLayer:
    layer_id: str
    label: str
    role: str
    contextual: bool = False
    visible: bool = True
    order: int = 0

    def __init__(
        self, layer_id, label=None, *, role="action", contextual=False, visible=True, order=0
    ):
        object.__setattr__(self, "layer_id", _id(layer_id, "layer_id"))
        object.__setattr__(self, "label", _id(label if label is not None else layer_id, "label"))
        object.__setattr__(self, "role", _id(role, "role"))
        object.__setattr__(self, "contextual", bool(contextual))
        object.__setattr__(self, "visible", bool(visible))
        object.__setattr__(self, "order", int(order))


@dataclass(frozen=True, slots=True)
class BattleInteractionProfile:
    layers: tuple[BattleInteractionLayer, ...]
    page_size: int = 8
    max_primary_layers: int = 6

    def __init__(self, layers=(), *, page_size=8, max_primary_layers=6):
        layers = tuple(
            x if isinstance(x, BattleInteractionLayer) else BattleInteractionLayer(**x)
            for x in layers
        )
        if len({x.layer_id for x in layers}) != len(layers):
            raise ValueError("duplicate interaction layer_id")
        if int(page_size) < 1:
            raise ValueError("page_size must be >= 1")
        if int(max_primary_layers) < 1:
            raise ValueError("max_primary_layers must be >= 1")
        object.__setattr__(self, "layers", layers)
        object.__setattr__(self, "page_size", int(page_size))
        object.__setattr__(self, "max_primary_layers", int(max_primary_layers))


@dataclass(frozen=True, slots=True)
class BattleInteractionContext:
    action_id: str | None = None
    actor_id: str | None = None
    target_ids: tuple[str, ...] = ()
    modifier_ids: tuple[str, ...] = ()
    workflow_payload: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class BattleInteractionView:
    stage: str
    primary_layers: tuple[BattleInteractionLayer, ...]
    overflow_layers: tuple[BattleInteractionLayer, ...]
    menu_view: object | None
    workflow_view: object | None
    contextual_entries: tuple[BattleActionEntry, ...]
    selected_action_id: str | None
    target_ids: tuple[str, ...]
    modifier_ids: tuple[str, ...]
    can_confirm: bool
    revision: int


class BattleInteractionRuntime:
    """Presentation-only router for complex battle input.

    It composes existing action-menu and workflow runtimes into a layered
    interaction grammar. Project data decides category names and which
    contextual controls exist. Gameplay controllers own legality, costs,
    targets and final execution.
    """

    STAGES = ("root", "action", "workflow", "modifier", "target", "confirm")

    def __init__(self, profile=None):
        self.profile = profile or BattleInteractionProfile()
        if not isinstance(self.profile, BattleInteractionProfile):
            raise TypeError("profile must be BattleInteractionProfile")
        self.menu = BattleActionMenuRuntime(
            BattleActionMenuPolicy(page_size=self.profile.page_size)
        )
        self.workflow = BattleActionWorkflowRuntime()
        self._entries = ()
        self._contextual = ()
        self.stage = "root"
        self.context = BattleInteractionContext()
        self.revision = 0

    def _visible_layers(self):
        values = tuple(
            sorted(
                (x for x in self.profile.layers if x.visible and not x.contextual),
                key=lambda x: (x.order, x.label.casefold(), x.layer_id),
            )
        )
        return (
            values[: self.profile.max_primary_layers],
            values[self.profile.max_primary_layers :],
        )

    def set_actions(self, entries):
        self._entries = tuple(
            x if isinstance(x, BattleActionEntry) else BattleActionEntry.from_data(x)
            for x in entries
        )
        self.menu.set_entries(self._entries)
        self.revision += 1
        return self.view

    def open_layer(self, layer_id):
        layer_id = _id(layer_id, "layer_id")
        layer = next((x for x in self.profile.layers if x.layer_id == layer_id), None)
        if layer is None or not layer.visible:
            raise KeyError(layer_id)
        self.menu.set_category(layer_id)
        self.stage = "action"
        self.context = BattleInteractionContext()
        self.revision += 1
        return self.view

    def choose_action(self, action_id=None):
        action_id = action_id or self.menu.selected_action_id()
        action_id = _id(action_id, "action_id")
        entry = next((x for x in self._entries if x.action_id == action_id), None)
        if entry is None:
            raise KeyError(action_id)
        if not entry.enabled:
            return self.view
        self.context = BattleInteractionContext(action_id=action_id)
        self.stage = "action"
        self.revision += 1
        return self.view

    def begin_workflow(self, definition, options=()):
        if self.context.action_id is None:
            raise RuntimeError("choose an action before workflow")
        self.workflow.begin(definition, options)
        self.stage = "workflow"
        self.revision += 1
        return self.view

    def set_contextual_entries(self, entries):
        self._contextual = tuple(
            x if isinstance(x, BattleActionEntry) else BattleActionEntry.from_data(x)
            for x in entries
        )
        self.revision += 1
        return self.view

    def begin_modifiers(self):
        if self.context.action_id is None:
            raise RuntimeError("choose an action before modifiers")
        self.stage = "modifier"
        self.revision += 1
        return self.view

    def choose_modifier(self, modifier_id):
        modifier_id = _id(modifier_id, "modifier_id")
        entry = next((x for x in self._contextual if x.action_id == modifier_id), None)
        if entry is None:
            raise KeyError(modifier_id)
        if not entry.enabled:
            return self.view
        current = list(self.context.modifier_ids)
        if modifier_id in current:
            current.remove(modifier_id)
        else:
            current.append(modifier_id)
        self.context = BattleInteractionContext(
            self.context.action_id,
            self.context.actor_id,
            self.context.target_ids,
            tuple(current),
            self.context.workflow_payload,
        )
        self.revision += 1
        return self.view

    def begin_targeting(self, actor_id=None):
        if self.context.action_id is None:
            raise RuntimeError("choose an action before targeting")
        self.context = BattleInteractionContext(
            self.context.action_id,
            None if actor_id is None else _id(actor_id, "actor_id"),
            (),
            self.context.modifier_ids,
            self._workflow_payload(),
        )
        self.stage = "target"
        self.revision += 1
        return self.view

    def set_targets(self, target_ids):
        if self.stage != "target":
            raise RuntimeError("interaction is not targeting")
        targets = tuple(_id(x, "target_id") for x in target_ids)
        self.context = BattleInteractionContext(
            self.context.action_id,
            self.context.actor_id,
            targets,
            self.context.modifier_ids,
            self.context.workflow_payload,
        )
        self.stage = "confirm" if targets else "target"
        self.revision += 1
        return self.view

    def _workflow_payload(self):
        if not self.workflow.active:
            return ()
        return tuple((x.step_id, tuple(x.option_ids)) for x in self.workflow.view.selections)

    def reset(self):
        self.workflow.cancel() if self.workflow.active else None
        self.stage = "root"
        self.context = BattleInteractionContext()
        self._contextual = ()
        self.revision += 1
        return self.view

    @property
    def view(self):
        primary, overflow = self._visible_layers()
        return BattleInteractionView(
            self.stage,
            primary,
            overflow,
            self.menu.view if self.stage in {"action", "root"} else None,
            self.workflow.view if self.stage == "workflow" else None,
            self._contextual if self.stage == "modifier" else (),
            self.context.action_id,
            self.context.target_ids,
            self.context.modifier_ids,
            self.stage == "confirm"
            and self.context.action_id is not None
            and bool(self.context.target_ids),
            self.revision,
        )

    def snapshot(self):
        return {
            "schema": "asteria.battle_interaction_runtime",
            "version": 1,
            "stage": self.stage,
            "context": {
                "action_id": self.context.action_id,
                "actor_id": self.context.actor_id,
                "target_ids": list(self.context.target_ids),
                "modifier_ids": list(self.context.modifier_ids),
                "workflow_payload": [[a, list(b)] for a, b in self.context.workflow_payload],
            },
            "revision": self.revision,
        }
