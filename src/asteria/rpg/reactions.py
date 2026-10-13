from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import normalize_tag


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _tags(values):
    return tuple(sorted({normalize_tag(x) for x in values}))


@dataclass(frozen=True, slots=True)
class ReactionDefinition:
    """Project-authored reaction rule.

    Selector/policy names are intentionally open strings. Asteria ships useful
    built-ins, while projects/plugins may register additional resolvers without
    changing engine schemas.
    """

    reaction_id: str
    trigger: str
    reactor_selector: str
    target_selector: str = "event_source"
    ability_id: str | None = None
    priority: int = 0
    required_tags: tuple[str, ...] = ()
    blocked_tags: tuple[str, ...] = ()
    require_can_act: bool = True
    allow_self: bool = False
    max_per_chain: int = 1
    action_target_policy: str = "preserve"

    SCHEMA = "asteria.rpg.reaction_definition"
    VERSION = 1

    def __init__(
        self,
        reaction_id,
        trigger,
        reactor_selector,
        *,
        target_selector="event_source",
        ability_id=None,
        priority=0,
        required_tags=(),
        blocked_tags=(),
        require_can_act=True,
        allow_self=False,
        max_per_chain=1,
        action_target_policy="preserve",
    ):
        object.__setattr__(self, "reaction_id", _id(reaction_id, "reaction_id"))
        object.__setattr__(self, "trigger", _id(trigger, "trigger"))
        object.__setattr__(self, "reactor_selector", _id(reactor_selector, "reactor_selector"))
        object.__setattr__(self, "target_selector", _id(target_selector, "target_selector"))
        object.__setattr__(
            self, "ability_id", None if ability_id is None else _id(ability_id, "ability_id")
        )
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(self, "required_tags", _tags(required_tags))
        object.__setattr__(self, "blocked_tags", _tags(blocked_tags))
        object.__setattr__(self, "require_can_act", bool(require_can_act))
        object.__setattr__(self, "allow_self", bool(allow_self))
        count = int(max_per_chain)
        if count < 1:
            raise ValueError("max_per_chain must be >= 1")
        object.__setattr__(self, "max_per_chain", count)
        object.__setattr__(
            self, "action_target_policy", _id(action_target_policy, "action_target_policy")
        )

    def matches(self, trigger, tags):
        if self.trigger != str(trigger):
            return False
        values = set(_tags(tags))
        return set(self.required_tags).issubset(values) and not set(
            self.blocked_tags
        ).intersection(values)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "reaction_id": self.reaction_id,
            "trigger": self.trigger,
            "reactor_selector": self.reactor_selector,
            "target_selector": self.target_selector,
            "ability_id": self.ability_id,
            "priority": self.priority,
            "required_tags": list(self.required_tags),
            "blocked_tags": list(self.blocked_tags),
            "require_can_act": self.require_can_act,
            "allow_self": self.allow_self,
            "max_per_chain": self.max_per_chain,
            "action_target_policy": self.action_target_policy,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported reaction definition")
        return cls(
            data["reaction_id"],
            data["trigger"],
            data["reactor_selector"],
            target_selector=data.get("target_selector", "event_source"),
            ability_id=data.get("ability_id"),
            priority=data.get("priority", 0),
            required_tags=data.get("required_tags", ()),
            blocked_tags=data.get("blocked_tags", ()),
            require_can_act=data.get("require_can_act", True),
            allow_self=data.get("allow_self", False),
            max_per_chain=data.get("max_per_chain", 1),
            action_target_policy=data.get("action_target_policy", "preserve"),
        )


@dataclass(frozen=True, slots=True)
class ReactionEvent:
    trigger: str
    source_id: str
    target_ids: tuple[str, ...]
    tags: tuple[str, ...] = ()
    depth: int = 0


@dataclass(frozen=True, slots=True)
class ReactionRequest:
    reaction_id: str
    reactor_id: str
    ability_id: str | None
    target_ids: tuple[str, ...]
    priority: int
    depth: int
    action_target_policy: str


@dataclass(frozen=True, slots=True)
class ReactionChainResult:
    requests: tuple[ReactionRequest, ...]
    action_results: tuple[object, ...]
    suppressed: tuple[str, ...]
    final_target_ids: tuple[str, ...]


class ReactionRuntime:
    """Deterministic reaction queue with bounded recursion/chain execution."""

    def __init__(
        self,
        definitions=(),
        *,
        hooks=None,
        max_depth=16,
        max_reactions=256,
        selector_resolvers=None,
    ):
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, ReactionDefinition):
                raise TypeError("definitions must contain ReactionDefinition values")
            if definition.reaction_id in self.definitions:
                raise ValueError(f"duplicate reaction: {definition.reaction_id}")
            self.definitions[definition.reaction_id] = definition
        self.hooks = hooks
        self.max_depth = int(max_depth)
        self.max_reactions = int(max_reactions)
        if self.max_depth < 0 or self.max_reactions < 1:
            raise ValueError("invalid reaction limits")
        self.selector_resolvers = dict(selector_resolvers or {})

    def _reactors(self, battle, selector, event):
        custom = self.selector_resolvers.get(selector)
        if custom is not None:
            return tuple(custom(battle, event))
        source = battle.member(event.source_id)
        targets = [battle.member(x) for x in event.target_ids if x in battle.members]
        if selector == "event_source":
            return (source.member_id,)
        if selector == "event_targets":
            return tuple(x.member_id for x in targets)
        if selector == "allies_of_source":
            return tuple(
                sorted(x.member_id for x in battle.members.values() if x.side == source.side)
            )
        if selector == "allies_of_source_except_source":
            return tuple(
                sorted(
                    x.member_id
                    for x in battle.members.values()
                    if x.side == source.side and x.member_id != source.member_id
                )
            )
        if selector == "opponents_of_source":
            return tuple(
                sorted(x.member_id for x in battle.members.values() if x.side != source.side)
            )
        if selector == "allies_of_targets":
            sides = {x.side for x in targets}
            return tuple(sorted(x.member_id for x in battle.members.values() if x.side in sides))
        if selector == "allies_of_targets_except_targets":
            sides = {x.side for x in targets}
            target_ids = {x.member_id for x in targets}
            return tuple(
                sorted(
                    x.member_id
                    for x in battle.members.values()
                    if x.side in sides and x.member_id not in target_ids
                )
            )
        if selector == "all_present":
            return tuple(
                sorted(
                    x.member_id
                    for x in battle.members.values()
                    if battle.combatants.state(x.member_id).present
                )
            )
        raise KeyError(f"unknown reactor selector: {selector}")

    def _targets(self, battle, selector, event, reactor_id):
        custom = self.selector_resolvers.get(selector)
        if custom is not None:
            return tuple(custom(battle, event, reactor_id))
        if selector == "event_source":
            return (event.source_id,)
        if selector == "event_targets":
            return tuple(event.target_ids)
        if selector == "reactor":
            return (reactor_id,)
        if selector == "first_event_target":
            return tuple(event.target_ids[:1])
        raise KeyError(f"unknown target selector: {selector}")

    def resolve(self, battle, trigger, source_id, target_ids=(), *, tags=(), rng=None):
        from .battle import BattleAction

        event = ReactionEvent(
            _id(trigger, "trigger"),
            _id(source_id, "source_id"),
            tuple(str(x) for x in target_ids),
            _tags(tags),
            0,
        )
        queue = []
        sequence = 0
        counts = {}
        executed = []
        results = []
        suppressed = []
        final_target_ids = tuple(event.target_ids)

        def enqueue(ev):
            nonlocal sequence
            if ev.depth > self.max_depth:
                suppressed.append("max_depth")
                return
            for definition in sorted(
                self.definitions.values(), key=lambda x: (-x.priority, x.reaction_id)
            ):
                if not definition.matches(ev.trigger, ev.tags):
                    continue
                for reactor_id in self._reactors(battle, definition.reactor_selector, ev):
                    if reactor_id not in battle.members:
                        continue
                    if not definition.allow_self and reactor_id == ev.source_id:
                        continue
                    if definition.require_can_act and not battle.can_act(reactor_id):
                        continue
                    key = (definition.reaction_id, reactor_id)
                    if counts.get(key, 0) >= definition.max_per_chain:
                        continue
                    target_values = self._targets(
                        battle, definition.target_selector, ev, reactor_id
                    )
                    request = ReactionRequest(
                        definition.reaction_id,
                        reactor_id,
                        definition.ability_id,
                        target_values,
                        definition.priority,
                        ev.depth,
                        definition.action_target_policy,
                    )
                    heappush(
                        queue,
                        (
                            -definition.priority,
                            sequence,
                            definition.reaction_id,
                            reactor_id,
                            request,
                        ),
                    )
                    sequence += 1

        enqueue(event)
        while queue and len(executed) < self.max_reactions:
            _, _, _, _, request = heappop(queue)
            definition = self.definitions[request.reaction_id]
            key = (request.reaction_id, request.reactor_id)
            if counts.get(key, 0) >= definition.max_per_chain:
                continue
            if definition.require_can_act and not battle.can_act(request.reactor_id):
                suppressed.append(f"inactive:{request.reactor_id}")
                continue
            counts[key] = counts.get(key, 0) + 1
            executed.append(request)
            emit_hook(
                self.hooks,
                "rpg.battle.reaction_started",
                source=request.reactor_id,
                data={"request": request},
            )
            if request.action_target_policy == "replace_event_targets_with_reactor":
                final_target_ids = (request.reactor_id,)
            elif request.action_target_policy != "preserve":
                custom = self.selector_resolvers.get(request.action_target_policy)
                if custom is None:
                    raise KeyError(f"unknown action target policy: {request.action_target_policy}")
                final_target_ids = tuple(custom(battle, event, request.reactor_id))
            action_result = None
            if request.ability_id is not None:
                action_result = battle.execute(
                    BattleAction(request.reactor_id, request.ability_id, request.target_ids),
                    rng=rng,
                )
                results.append(action_result)
                nested = ReactionEvent(
                    "rpg.battle.after_action",
                    request.reactor_id,
                    request.target_ids,
                    _tags((*event.tags, "reaction", f"reaction.{request.reaction_id}")),
                    request.depth + 1,
                )
                enqueue(nested)
            emit_hook(
                self.hooks,
                "rpg.battle.reaction_finished",
                source=request.reactor_id,
                data={"request": request, "result": action_result},
            )
        if queue:
            suppressed.append("max_reactions")
        chain = ReactionChainResult(
            tuple(executed), tuple(results), tuple(suppressed), tuple(final_target_ids)
        )
        emit_hook(
            self.hooks,
            "rpg.battle.reaction_chain_finished",
            source=source_id,
            data={"result": chain},
        )
        return chain
