from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .effects import Effect, apply_effect
from .modifiers import ModifierSet, StatModifier
from .stats import ResourcePool, StatBlock
from .tags import TagSet


def _duration(value):
    value = float(value)
    if not isfinite(value) or value < 0.0:
        raise ValueError("duration must be finite and >= 0")
    return value


class StackingPolicy(str, Enum):
    REPLACE = "replace"
    REFRESH = "refresh"
    STACK = "stack"


@dataclass(frozen=True, slots=True)
class PeriodicEffect:
    interval: float
    effect: Effect

    def __init__(self, interval, effect):
        interval = float(interval)
        if not isfinite(interval) or interval <= 0.0:
            raise ValueError("periodic interval must be finite and > 0")
        if not isinstance(effect, Effect):
            raise TypeError("effect must be Effect")
        object.__setattr__(self, "interval", interval)
        object.__setattr__(self, "effect", effect)

    def to_data(self):
        return {"interval": self.interval, "effect": self.effect.to_data()}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"interval", "effect"}:
            raise ValueError("invalid periodic effect")
        return cls(data["interval"], Effect.from_data(data["effect"]))


@dataclass(frozen=True, slots=True)
class StateDefinition:
    state_id: str
    duration: float
    stacking: StackingPolicy = StackingPolicy.REFRESH
    max_stacks: int = 1
    modifiers: tuple[StatModifier, ...] = ()
    on_apply: tuple[Effect, ...] = ()
    periodic: tuple[PeriodicEffect, ...] = ()
    on_remove: tuple[Effect, ...] = ()
    contributed_tags: tuple[str, ...] = ()

    def __init__(
        self,
        state_id,
        duration,
        *,
        stacking=StackingPolicy.REFRESH,
        max_stacks=1,
        modifiers=(),
        on_apply=(),
        periodic=(),
        on_remove=(),
        contributed_tags=(),
    ):
        state_id = str(state_id).strip()
        if not state_id:
            raise ValueError("state_id is required")
        stacking = StackingPolicy(stacking)
        max_stacks = int(max_stacks)
        if max_stacks < 1:
            raise ValueError("max_stacks must be >= 1")
        if stacking != StackingPolicy.STACK and max_stacks != 1:
            raise ValueError("max_stacks > 1 requires STACK policy")
        modifiers = tuple(modifiers)
        on_apply = tuple(on_apply)
        periodic = tuple(periodic)
        on_remove = tuple(on_remove)
        contributed_tags = tuple(
            sorted({str(x).strip().lower() for x in contributed_tags})
        )
        if any(not x or any(ch.isspace() for ch in x) for x in contributed_tags):
            raise ValueError(
                "contributed_tags must be non-empty tags without whitespace"
            )
        if any(not isinstance(x, StatModifier) for x in modifiers):
            raise TypeError("modifiers must be StatModifier values")
        if any(not isinstance(x, Effect) for x in (*on_apply, *on_remove)):
            raise TypeError("on_apply/on_remove must be Effect values")
        if any(not isinstance(x, PeriodicEffect) for x in periodic):
            raise TypeError("periodic must be PeriodicEffect values")

        object.__setattr__(self, "state_id", state_id)
        object.__setattr__(self, "duration", _duration(duration))
        object.__setattr__(self, "stacking", stacking)
        object.__setattr__(self, "max_stacks", max_stacks)
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(self, "on_apply", on_apply)
        object.__setattr__(self, "periodic", periodic)
        object.__setattr__(self, "on_remove", on_remove)
        object.__setattr__(self, "contributed_tags", contributed_tags)

    def to_data(self):
        return {
            "schema": "asteria.state_definition",
            "version": 2,
            "state_id": self.state_id,
            "duration": self.duration,
            "stacking": self.stacking.value,
            "max_stacks": self.max_stacks,
            "modifiers": [x.to_data() for x in self.modifiers],
            "on_apply": [x.to_data() for x in self.on_apply],
            "periodic": [x.to_data() for x in self.periodic],
            "on_remove": [x.to_data() for x in self.on_remove],
            "contributed_tags": list(self.contributed_tags),
        }

    @classmethod
    def from_data(cls, data):
        base = {
            "schema",
            "version",
            "state_id",
            "duration",
            "stacking",
            "max_stacks",
            "modifiers",
            "on_apply",
            "periodic",
            "on_remove",
        }
        version = data.get("version")
        expected = base if version == 1 else base | {"contributed_tags"}
        if set(data) != expected:
            raise ValueError("invalid state definition")
        if data["schema"] != "asteria.state_definition" or version not in {1, 2}:
            raise ValueError("unsupported state definition")
        return cls(
            data["state_id"],
            data["duration"],
            stacking=data["stacking"],
            max_stacks=data["max_stacks"],
            modifiers=[StatModifier.from_data(x) for x in data["modifiers"]],
            on_apply=[Effect.from_data(x) for x in data["on_apply"]],
            periodic=[PeriodicEffect.from_data(x) for x in data["periodic"]],
            on_remove=[Effect.from_data(x) for x in data["on_remove"]],
            contributed_tags=data.get("contributed_tags", ()),
        )


class StateRegistry:
    def __init__(self, definitions=()):
        self._definitions = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition):
        if not isinstance(definition, StateDefinition):
            raise TypeError("definition must be StateDefinition")
        if definition.state_id in self._definitions:
            raise ValueError(f"duplicate state: {definition.state_id}")
        self._definitions[definition.state_id] = definition
        return definition

    def get(self, state_id):
        return self._definitions.get(str(state_id))

    def require(self, state_id):
        try:
            return self._definitions[str(state_id)]
        except KeyError as exc:
            raise KeyError(f"unknown state: {state_id}") from exc

    def ids(self):
        return tuple(sorted(self._definitions))


@dataclass(slots=True)
class ActiveState:
    state_id: str
    remaining: float
    stacks: int = 1
    periodic_elapsed: list[float] | None = None

    def __post_init__(self):
        self.state_id = str(self.state_id)
        self.remaining = _duration(self.remaining)
        self.stacks = int(self.stacks)
        if self.stacks < 1:
            raise ValueError("active state stacks must be >= 1")
        if self.periodic_elapsed is None:
            self.periodic_elapsed = []
        else:
            self.periodic_elapsed = [float(x) for x in self.periodic_elapsed]

    def to_data(self):
        return {
            "state_id": self.state_id,
            "remaining": self.remaining,
            "stacks": self.stacks,
            "periodic_elapsed": list(self.periodic_elapsed),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"state_id", "remaining", "stacks", "periodic_elapsed"}:
            raise ValueError("invalid active state")
        return cls(
            data["state_id"],
            data["remaining"],
            data["stacks"],
            data["periodic_elapsed"],
        )


class StateRuntime:
    """Deterministic state lifecycle bound to one gameplay subject."""

    def __init__(
        self,
        registry: StateRegistry,
        stats: StatBlock,
        resources: ResourcePool,
        tags: TagSet,
    ):
        if not isinstance(registry, StateRegistry):
            raise TypeError("registry must be StateRegistry")
        self.registry = registry
        self.stats = stats
        self.resources = resources
        self.tags = tags
        self._active = {}
        self._tag_contributions = {}

    def active_states(self):
        return tuple(self._active[key] for key in sorted(self._active))

    def get(self, state_id):
        return self._active.get(str(state_id))

    def apply(self, state_id):
        definition = self.registry.require(state_id)
        active = self._active.get(definition.state_id)

        if active is None or definition.stacking == StackingPolicy.REPLACE:
            active = ActiveState(
                definition.state_id,
                definition.duration,
                1,
                [0.0] * len(definition.periodic),
            )
            self._active[definition.state_id] = active
            for tag in definition.contributed_tags:
                owners = self._tag_contributions.setdefault(tag, set())
                if not owners:
                    # Record whether the tag existed independently before the
                    # first state contribution so removal never steals it.
                    owners.add("__base__") if self.tags.contains(tag) else None
                    self.tags.add(tag)
                owners.add(definition.state_id)
        elif definition.stacking == StackingPolicy.REFRESH:
            active.remaining = definition.duration
            active.periodic_elapsed = [0.0] * len(definition.periodic)
        else:
            active.stacks = min(definition.max_stacks, active.stacks + 1)
            active.remaining = definition.duration
            active.periodic_elapsed = [0.0] * len(definition.periodic)

        # on_apply describes this application event, not all stacks that
        # already existed. Replaying prior stacks would compound mutations.
        for effect in definition.on_apply:
            apply_effect(effect, self.stats, self.resources, self.tags)
        return active

    def remove(self, state_id, *, run_remove_effects=True):
        state_id = str(state_id)
        active = self._active.pop(state_id, None)
        if active is None:
            return False
        definition = self.registry.require(state_id)
        for tag in definition.contributed_tags:
            owners = self._tag_contributions.get(tag)
            if owners is None:
                continue
            owners.discard(state_id)
            if owners == set():
                self.tags.remove(tag)
                del self._tag_contributions[tag]
            elif owners == {"__base__"}:
                # Base ownership remains; contribution bookkeeping is no
                # longer needed but the tag itself must remain.
                del self._tag_contributions[tag]
        if run_remove_effects:
            for effect in definition.on_remove:
                apply_effect(effect, self.stats, self.resources, self.tags)
        return True

    def update(self, dt):
        dt = float(dt)
        if not isfinite(dt) or dt < 0.0:
            raise ValueError("dt must be finite and >= 0")

        expired = []
        for state_id in sorted(self._active):
            active = self._active[state_id]
            definition = self.registry.require(state_id)

            # A state may only tick while it is alive. If dt crosses the
            # expiry boundary, discard the post-expiry portion of dt.
            active_dt = min(dt, active.remaining)
            active.remaining = max(0.0, active.remaining - dt)
            for index, periodic in enumerate(definition.periodic):
                active.periodic_elapsed[index] += active_dt
                while active.periodic_elapsed[index] >= periodic.interval:
                    active.periodic_elapsed[index] -= periodic.interval
                    repeat = (
                        active.stacks
                        if definition.stacking == StackingPolicy.STACK
                        else 1
                    )
                    for _ in range(repeat):
                        apply_effect(
                            periodic.effect, self.stats, self.resources, self.tags
                        )

            if active.remaining <= 0.0:
                expired.append(state_id)

        for state_id in expired:
            self.remove(state_id, run_remove_effects=True)
        return tuple(expired)

    def modifiers(self):
        result = ModifierSet()
        for state_id in sorted(self._active):
            active = self._active[state_id]
            definition = self.registry.require(state_id)
            repeat = active.stacks if definition.stacking == StackingPolicy.STACK else 1
            for stack_index in range(repeat):
                for modifier in definition.modifiers:
                    result.add(
                        StatModifier(
                            f"{state_id}:{stack_index}:{modifier.modifier_id}",
                            modifier.stat,
                            modifier.operation,
                            modifier.value,
                            priority=modifier.priority,
                            required_tags=modifier.required_tags,
                            blocked_tags=modifier.blocked_tags,
                        )
                    )
        return result

    def snapshot(self):
        return {
            "schema": "asteria.state_runtime",
            "version": 1,
            "active": [x.to_data() for x in self.active_states()],
        }

    def restore(self, data):
        if set(data) != {"schema", "version", "active"}:
            raise ValueError("invalid state runtime snapshot")
        if data["schema"] != "asteria.state_runtime" or data["version"] != 1:
            raise ValueError("unsupported state runtime snapshot")
        restored = {}
        for raw in data["active"]:
            active = ActiveState.from_data(raw)
            definition = self.registry.require(active.state_id)
            if active.stacks > definition.max_stacks:
                raise ValueError("snapshot exceeds state max_stacks")
            if len(active.periodic_elapsed) != len(definition.periodic):
                raise ValueError("snapshot periodic state mismatch")
            restored[active.state_id] = active
        self._active = restored
        self._tag_contributions = {}
        for state_id in sorted(restored):
            definition = self.registry.require(state_id)
            for tag in definition.contributed_tags:
                owners = self._tag_contributions.setdefault(tag, set())
                if not owners:
                    owners.add("__base__") if self.tags.contains(tag) else None
                    self.tags.add(tag)
                owners.add(state_id)
