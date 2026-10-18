from __future__ import annotations

from dataclasses import dataclass


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleWorkflowOption:
    option_id: str
    label: str
    enabled: bool = True
    disabled_reason: str = ""
    detail: str = ""
    icon_asset_id: str | None = None
    tags: tuple[str, ...] = ()
    payload: tuple[tuple[str, object], ...] = ()

    def __init__(
        self,
        option_id,
        label=None,
        *,
        enabled=True,
        disabled_reason="",
        detail="",
        icon_asset_id=None,
        tags=(),
        payload=None,
    ):
        option_id = _id(option_id, "option_id")
        label = option_id if label is None else _id(label, "label")
        object.__setattr__(self, "option_id", option_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "enabled", bool(enabled))
        object.__setattr__(self, "disabled_reason", str(disabled_reason))
        object.__setattr__(self, "detail", str(detail))
        object.__setattr__(
            self,
            "icon_asset_id",
            None if icon_asset_id is None else _id(icon_asset_id, "icon_asset_id"),
        )
        object.__setattr__(
            self, "tags", tuple(dict.fromkeys(str(x).strip() for x in tags if str(x).strip()))
        )
        payload = dict(payload or {})
        object.__setattr__(
            self, "payload", tuple(sorted(payload.items(), key=lambda x: str(x[0])))
        )

    def to_data(self):
        return {
            "option_id": self.option_id,
            "label": self.label,
            "enabled": self.enabled,
            "disabled_reason": self.disabled_reason,
            "detail": self.detail,
            "icon_asset_id": self.icon_asset_id,
            "tags": list(self.tags),
            "payload": {str(k): v for k, v in self.payload},
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleWorkflowStep:
    step_id: str
    label: str
    selection_mode: str = "single"
    minimum_selections: int = 1
    maximum_selections: int = 1
    optional: bool = False
    allow_back: bool = True
    # the choices the step offers when the project authors them (an ability's Command Input
    # Steps); a controller may also supply its own at run time
    options: tuple = ()

    def __post_init__(self):
        _id(self.step_id, "step_id")
        options = tuple(
            x if isinstance(x, BattleWorkflowOption) else BattleWorkflowOption.from_data(x)
            for x in self.options
        )
        if len({x.option_id for x in options}) != len(options):
            raise ValueError("duplicate workflow option_id")
        object.__setattr__(self, "options", options)
        _id(self.label, "label")
        if self.selection_mode not in {"single", "multiple"}:
            raise ValueError("unsupported workflow selection_mode")
        if self.minimum_selections < 0:
            raise ValueError("minimum_selections must be >= 0")
        if self.maximum_selections < self.minimum_selections:
            raise ValueError("maximum_selections must be >= minimum_selections")
        if self.selection_mode == "single" and self.maximum_selections > 1:
            raise ValueError("single step cannot select more than one option")

    def to_data(self):
        return {
            "step_id": self.step_id,
            "label": self.label,
            "selection_mode": self.selection_mode,
            "minimum_selections": self.minimum_selections,
            "maximum_selections": self.maximum_selections,
            "optional": self.optional,
            "allow_back": self.allow_back,
            **({"options": [x.to_data() for x in self.options]} if self.options else {}),
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class BattleActionWorkflowDefinition:
    workflow_id: str
    label: str
    steps: tuple[BattleWorkflowStep, ...]
    confirmation_label: str = "Confirm"

    SCHEMA = "asteria.battle_action_workflow_definition"
    VERSION = 1

    def __init__(self, workflow_id, label=None, steps=(), *, confirmation_label="Confirm"):
        workflow_id = _id(workflow_id, "workflow_id")
        label = workflow_id if label is None else _id(label, "label")
        steps = tuple(
            x if isinstance(x, BattleWorkflowStep) else BattleWorkflowStep.from_data(x)
            for x in steps
        )
        if not steps:
            raise ValueError("workflow requires at least one step")
        if len({x.step_id for x in steps}) != len(steps):
            raise ValueError("duplicate workflow step_id")
        object.__setattr__(self, "workflow_id", workflow_id)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "steps", steps)
        object.__setattr__(
            self, "confirmation_label", _id(confirmation_label, "confirmation_label")
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "workflow_id": self.workflow_id,
            "label": self.label,
            "steps": [x.to_data() for x in self.steps],
            "confirmation_label": self.confirmation_label,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle action workflow definition")
        return cls(
            data["workflow_id"],
            data["label"],
            data["steps"],
            confirmation_label=data["confirmation_label"],
        )


@dataclass(frozen=True, slots=True)
class BattleWorkflowSelection:
    step_id: str
    option_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BattleActionWorkflowView:
    workflow_id: str
    label: str
    step_index: int
    step_count: int
    step: BattleWorkflowStep | None
    options: tuple[BattleWorkflowOption, ...]
    selections: tuple[BattleWorkflowSelection, ...]
    can_back: bool
    can_advance: bool
    complete: bool
    revision: int


class BattleActionWorkflowRuntime:
    """Presentation/controller workflow state for multi-step battle input.

    The runtime never evaluates recipes, consumes materials, validates gameplay
    targets, or resolves an action result. Option lists arrive from the canonical
    controller already filtered/annotated for the current workflow step.
    """

    SCHEMA = "asteria.battle_action_workflow_runtime"
    VERSION = 1

    def __init__(self):
        self.definition = None
        self.step_index = 0
        self._options: tuple[BattleWorkflowOption, ...] = ()
        self._selections: dict[str, tuple[str, ...]] = {}
        self.revision = 0

    @property
    def active(self):
        return self.definition is not None

    @property
    def view(self):
        if self.definition is None:
            return None
        complete = self.step_index >= len(self.definition.steps)
        step = None if complete else self.definition.steps[self.step_index]
        selected = tuple(
            BattleWorkflowSelection(s.step_id, self._selections.get(s.step_id, ()))
            for s in self.definition.steps
            if s.step_id in self._selections
        )
        can_advance = complete or self._step_complete(step)
        can_back = self.step_index > 0 and (
            complete or self.definition.steps[self.step_index].allow_back
        )
        return BattleActionWorkflowView(
            self.definition.workflow_id,
            self.definition.label,
            self.step_index,
            len(self.definition.steps),
            step,
            self._options if not complete else (),
            selected,
            can_back,
            can_advance,
            complete,
            self.revision,
        )

    def begin(self, definition, options=()):
        if not isinstance(definition, BattleActionWorkflowDefinition):
            definition = BattleActionWorkflowDefinition.from_data(definition)
        self.definition = definition
        self.step_index = 0
        self._selections = {}
        self.set_options(options)
        return self.view

    def cancel(self):
        self.definition = None
        self.step_index = 0
        self._options = ()
        self._selections = {}
        self.revision += 1
        return None

    def set_options(self, options):
        if self.definition is None:
            raise RuntimeError("no active workflow")
        values = tuple(
            x if isinstance(x, BattleWorkflowOption) else BattleWorkflowOption.from_data(x)
            for x in options
        )
        if len({x.option_id for x in values}) != len(values):
            raise ValueError("duplicate workflow option_id")
        self._options = values
        self.revision += 1
        return self.view

    def _step_complete(self, step):
        if step is None:
            return True
        selected = self._selections.get(step.step_id, ())
        required = 0 if step.optional else step.minimum_selections
        return required <= len(selected) <= step.maximum_selections

    def select(self, option_id):
        if self.definition is None or self.step_index >= len(self.definition.steps):
            raise RuntimeError("workflow is not awaiting a selection")
        option_id = _id(option_id, "option_id")
        option = next((x for x in self._options if x.option_id == option_id), None)
        if option is None:
            raise KeyError(option_id)
        if not option.enabled:
            return self.view
        step = self.definition.steps[self.step_index]
        current = list(self._selections.get(step.step_id, ()))
        if step.selection_mode == "single":
            current = [option_id]
        else:
            if option_id in current:
                current.remove(option_id)
            elif len(current) < step.maximum_selections:
                current.append(option_id)
        self._selections[step.step_id] = tuple(current)
        self.revision += 1
        return self.view

    def advance(self, next_options=()):
        if self.definition is None:
            raise RuntimeError("no active workflow")
        if self.step_index >= len(self.definition.steps):
            return self.view
        step = self.definition.steps[self.step_index]
        if not self._step_complete(step):
            raise ValueError("workflow step is incomplete")
        self.step_index += 1
        self._options = ()
        if self.step_index < len(self.definition.steps):
            self.set_options(next_options)
        else:
            self.revision += 1
        return self.view

    def back(self, options=()):
        if self.definition is None or self.step_index <= 0:
            return self.view
        if (
            self.step_index < len(self.definition.steps)
            and not self.definition.steps[self.step_index].allow_back
        ):
            return self.view
        self.step_index -= 1
        self._options = ()
        self.set_options(options)
        return self.view

    def selection_payload(self):
        if self.definition is None:
            return None
        return {
            "workflow_id": self.definition.workflow_id,
            "selections": {
                step.step_id: list(self._selections.get(step.step_id, ()))
                for step in self.definition.steps
            },
        }

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "definition": None if self.definition is None else self.definition.to_data(),
            "step_index": self.step_index,
            "options": [x.to_data() for x in self._options],
            "selections": {k: list(v) for k, v in sorted(self._selections.items())},
            "revision": self.revision,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported battle action workflow runtime snapshot")
        raw = data.get("definition")
        self.definition = None if raw is None else BattleActionWorkflowDefinition.from_data(raw)
        self.step_index = int(data.get("step_index", 0))
        self._options = tuple(BattleWorkflowOption.from_data(x) for x in data.get("options", ()))
        self._selections = {
            str(k): tuple(str(x) for x in v) for k, v in dict(data.get("selections", {})).items()
        }
        self.revision = int(data.get("revision", 0))
        return self
