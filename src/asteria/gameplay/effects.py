from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .formulas import FormulaContext, ValueFormula
from .stats import ResourcePool, StatBlock
from .tags import TagSet, normalize_tag


def _number(value, *, name="value"):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


class EffectOperationKind(str, Enum):
    STAT_DELTA = "stat_delta"
    RESOURCE_DELTA = "resource_delta"
    RESOURCE_SET = "resource_set"
    TAG_ADD = "tag_add"
    TAG_REMOVE = "tag_remove"


@dataclass(frozen=True, slots=True)
class EffectOperation:
    kind: EffectOperationKind
    target: str
    value: object = None

    def __init__(self, kind, target, value=None):
        kind = EffectOperationKind(kind)
        target = str(target).strip()
        if not target:
            raise ValueError("effect operation target is required")

        if kind in {
            EffectOperationKind.STAT_DELTA,
            EffectOperationKind.RESOURCE_DELTA,
            EffectOperationKind.RESOURCE_SET,
        }:
            if not isinstance(value, ValueFormula):
                value = _number(value)
        elif kind in {
            EffectOperationKind.TAG_ADD,
            EffectOperationKind.TAG_REMOVE,
        }:
            target = normalize_tag(target)
            if value is not None:
                raise ValueError("tag operations do not take a value")

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "value", value)

    def to_data(self):
        value = self.value.to_data() if isinstance(self.value, ValueFormula) else self.value
        return {
            "kind": self.kind.value,
            "target": self.target,
            "value": value,
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"kind", "target", "value"}:
            raise ValueError("invalid effect operation")
        value = data["value"]
        if isinstance(value, dict) and value.get("schema") == "asteria.value_formula":
            value = ValueFormula.from_data(value)
        return cls(data["kind"], data["target"], value)


@dataclass(frozen=True, slots=True)
class Effect:
    effect_id: str
    operations: tuple[EffectOperation, ...]
    required_tags: tuple[str, ...] = ()
    blocked_tags: tuple[str, ...] = ()

    def __init__(
        self,
        effect_id,
        operations=(),
        *,
        required_tags=(),
        blocked_tags=(),
    ):
        effect_id = str(effect_id).strip()
        if not effect_id:
            raise ValueError("effect_id is required")
        items = tuple(operations)
        if any(not isinstance(item, EffectOperation) for item in items):
            raise TypeError("operations must be EffectOperation values")
        object.__setattr__(self, "effect_id", effect_id)
        object.__setattr__(self, "operations", items)
        object.__setattr__(
            self,
            "required_tags",
            tuple(sorted({normalize_tag(x) for x in required_tags})),
        )
        object.__setattr__(
            self,
            "blocked_tags",
            tuple(sorted({normalize_tag(x) for x in blocked_tags})),
        )

    def applies(self, tags: TagSet):
        return tags.contains_all(self.required_tags) and not tags.contains_any(self.blocked_tags)

    def to_data(self):
        return {
            "schema": "asteria.effect",
            "version": 1,
            "effect_id": self.effect_id,
            "operations": [op.to_data() for op in self.operations],
            "required_tags": list(self.required_tags),
            "blocked_tags": list(self.blocked_tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "effect_id",
            "operations",
            "required_tags",
            "blocked_tags",
        }
        if set(data) != expected:
            raise ValueError("invalid effect")
        if data["schema"] != "asteria.effect" or data["version"] != 1:
            raise ValueError("unsupported effect")
        if not isinstance(data["operations"], list):
            raise TypeError("operations must be a list")
        return cls(
            data["effect_id"],
            [EffectOperation.from_data(raw) for raw in data["operations"]],
            required_tags=data["required_tags"],
            blocked_tags=data["blocked_tags"],
        )


@dataclass(frozen=True, slots=True)
class EffectApplicationResult:
    applied: bool
    effect_id: str
    changed_stats: tuple[str, ...] = ()
    changed_resources: tuple[str, ...] = ()
    added_tags: tuple[str, ...] = ()
    removed_tags: tuple[str, ...] = ()


def apply_effect(
    effect: Effect,
    stats: StatBlock,
    resources: ResourcePool,
    tags: TagSet,
    *,
    formula_context: FormulaContext | None = None,
    value_transform=None,
):
    """Apply an instantaneous effect atomically.

    ``value_transform(operation, value) -> value`` lets a caller route each
    evaluated operation value through its own rules (battle interaction
    multipliers) before it is applied.

    All operations are executed against temporary copies first. If any
    operation is invalid (for example a missing resource), the original state
    is untouched and the exception is propagated.
    """
    if not isinstance(effect, Effect):
        raise TypeError("effect must be Effect")
    if not isinstance(stats, StatBlock):
        raise TypeError("stats must be StatBlock")
    if not isinstance(resources, ResourcePool):
        raise TypeError("resources must be ResourcePool")
    if not isinstance(tags, TagSet):
        raise TypeError("tags must be TagSet")

    if not effect.applies(tags):
        return EffectApplicationResult(False, effect.effect_id)

    staged_stats = StatBlock.from_data(stats.to_data())
    staged_resources = ResourcePool.from_data(resources.to_data())
    staged_tags = TagSet.from_data(tags.to_data())

    changed_stats = set()
    changed_resources = set()
    added_tags = set()
    removed_tags = set()

    for operation in effect.operations:
        value = operation.value
        if isinstance(value, ValueFormula):
            if formula_context is None:
                raise ValueError("formula-driven effect requires formula_context")
            value = value.evaluate(formula_context)
        if value_transform is not None:
            value = value_transform(operation, value)

        if operation.kind == EffectOperationKind.STAT_DELTA:
            staged_stats.add(operation.target, value)
            changed_stats.add(operation.target)
        elif operation.kind == EffectOperationKind.RESOURCE_DELTA:
            staged_resources.change(operation.target, value)
            changed_resources.add(operation.target)
        elif operation.kind == EffectOperationKind.RESOURCE_SET:
            staged_resources.set_current(operation.target, value)
            changed_resources.add(operation.target)
        elif operation.kind == EffectOperationKind.TAG_ADD:
            if staged_tags.add(operation.target):
                added_tags.add(operation.target)
                removed_tags.discard(operation.target)
        elif operation.kind == EffectOperationKind.TAG_REMOVE:
            if staged_tags.remove(operation.target):
                removed_tags.add(operation.target)
                added_tags.discard(operation.target)

    stats._values = dict(staged_stats._values)
    resources._values = dict(staged_resources._values)
    tags._tags = set(staged_tags._tags)

    return EffectApplicationResult(
        True,
        effect.effect_id,
        changed_stats=tuple(sorted(changed_stats)),
        changed_resources=tuple(sorted(changed_resources)),
        added_tags=tuple(sorted(added_tags)),
        removed_tags=tuple(sorted(removed_tags)),
    )
