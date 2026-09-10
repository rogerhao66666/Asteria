from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import AbilityRuntime, AbilityTarget, GameplaySubject


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class PartyMember:
    member_id: str
    side: str
    subject: GameplaySubject
    ability_ids: tuple[str, ...] = ()
    initiative: float = 0.0

    def __init__(self, member_id, side, subject, *, ability_ids=(), initiative=0.0):
        if not isinstance(subject, GameplaySubject):
            raise TypeError("subject must be GameplaySubject")
        object.__setattr__(self, "member_id", _id(member_id, "member_id"))
        object.__setattr__(self, "side", _id(side, "side"))
        object.__setattr__(self, "subject", subject)
        object.__setattr__(
            self,
            "ability_ids",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in ability_ids)),
        )
        object.__setattr__(self, "initiative", _number(initiative, "initiative"))


class TurnOrderPolicy(str, Enum):
    FIXED_INITIATIVE = "fixed_initiative"


@dataclass(slots=True)
class Party:
    side: str
    members: list[PartyMember] = field(default_factory=list)
    hooks: object = None

    def __init__(self, side, members=(), *, hooks=None):
        self.side = _id(side, "side")
        self.members = []
        self.hooks = hooks
        for member in members:
            self.add(member)

    def add(self, member):
        if not isinstance(member, PartyMember):
            raise TypeError("member must be PartyMember")
        if member.side != self.side:
            raise ValueError("party member side mismatch")
        if any(x.member_id == member.member_id for x in self.members):
            raise ValueError(f"duplicate party member: {member.member_id}")
        emit_hook(
            self.hooks,
            "rpg.party.before_add",
            source=self.side,
            data={"member": member},
        )
        self.members.append(member)
        emit_hook(
            self.hooks, "rpg.party.after_add", source=self.side, data={"member": member}
        )
        return member

    def remove(self, member_id):
        member_id = str(member_id)
        for i, m in enumerate(self.members):
            if m.member_id == member_id:
                emit_hook(
                    self.hooks,
                    "rpg.party.before_remove",
                    source=self.side,
                    data={"member": m},
                )
                removed = self.members.pop(i)
                emit_hook(
                    self.hooks,
                    "rpg.party.after_remove",
                    source=self.side,
                    data={"member": removed},
                )
                return removed
        raise KeyError(member_id)

    def ids(self):
        return tuple(x.member_id for x in self.members)


@dataclass(frozen=True, slots=True)
class TurnEntry:
    member_id: str
    side: str
    initiative: float


class TurnQueue:
    """Deterministic round queue. Higher initiative acts first; ID breaks ties."""

    def __init__(self, members=(), policy=TurnOrderPolicy.FIXED_INITIATIVE):
        self.policy = TurnOrderPolicy(policy)
        self._source = tuple(members)
        self._round = 0
        self._pending = []
        self.start_round()

    @property
    def round_index(self):
        return self._round

    def start_round(self):
        self._round += 1
        self._pending = [
            TurnEntry(m.member_id, m.side, m.initiative)
            for m in sorted(self._source, key=lambda x: (-x.initiative, x.member_id))
        ]
        return tuple(self._pending)

    def peek(self):
        return self._pending[0] if self._pending else None

    def pop(self):
        return self._pending.pop(0) if self._pending else None

    def pending(self):
        return tuple(self._pending)

    def exhausted(self):
        return not self._pending

    def to_data(self):
        return {
            "schema": "asteria.rpg.turn_queue",
            "version": 1,
            "policy": self.policy.value,
            "round_index": self._round,
            "pending": [
                {"member_id": x.member_id, "side": x.side, "initiative": x.initiative}
                for x in self._pending
            ],
        }

    @classmethod
    def from_data(cls, data, members):
        if data.get("schema") != "asteria.rpg.turn_queue" or data.get("version") != 1:
            raise ValueError("unsupported turn queue")
        result = cls.__new__(cls)
        result.policy = TurnOrderPolicy(data["policy"])
        result._source = tuple(members)
        result._round = int(data["round_index"])
        result._pending = [
            TurnEntry(x["member_id"], x["side"], x["initiative"])
            for x in data["pending"]
        ]
        return result


@dataclass(frozen=True, slots=True)
class BattleAction:
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]

    def __init__(self, actor_id, ability_id, target_ids):
        object.__setattr__(self, "actor_id", _id(actor_id, "actor_id"))
        object.__setattr__(self, "ability_id", _id(ability_id, "ability_id"))
        object.__setattr__(
            self, "target_ids", tuple(_id(x, "target_id") for x in target_ids)
        )


@dataclass(frozen=True, slots=True)
class BattleActionResult:
    action: BattleAction
    execution_result: object


@dataclass(frozen=True, slots=True)
class BattleOutcome:
    finished: bool
    winning_sides: tuple[str, ...] = ()
    defeated_sides: tuple[str, ...] = ()


class BattleRuntime:
    """Thin RPG coordinator over Phase 6 AbilityRuntime plus lifecycle hooks.

    Outcome semantics are injected through `is_active`; BattleRuntime never
    assumes HP, death tags, or any specific defeat rule.
    """

    def __init__(
        self,
        parties,
        ability_runtime,
        *,
        turn_policy=TurnOrderPolicy.FIXED_INITIATIVE,
        hooks=None,
        is_active: Callable[[PartyMember], bool] | None = None,
    ):
        parties = tuple(parties)
        if not parties:
            raise ValueError("battle requires at least one party")
        if any(not isinstance(x, Party) for x in parties):
            raise TypeError("parties must be Party values")
        if not isinstance(ability_runtime, AbilityRuntime):
            raise TypeError("ability_runtime must be AbilityRuntime")
        if is_active is not None and not callable(is_active):
            raise TypeError("is_active must be callable")
        self.hooks = hooks
        self.is_active = is_active or (lambda member: True)
        self.parties = {p.side: p for p in parties}
        if len(self.parties) != len(parties):
            raise ValueError("duplicate party side")
        members = []
        for p in parties:
            members.extend(p.members)
        if len({m.member_id for m in members}) != len(members):
            raise ValueError("duplicate battle member id")
        self.members = {m.member_id: m for m in members}
        self.ability_runtime = ability_runtime
        self.turn_queue = TurnQueue(members, turn_policy)
        emit_hook(self.hooks, "rpg.battle.started", data={"battle": self})
        emit_hook(
            self.hooks,
            "rpg.battle.round_started",
            data={"round_index": self.turn_queue.round_index},
        )

    def member(self, member_id):
        return self.members[str(member_id)]

    def execute(self, action):
        if not isinstance(action, BattleAction):
            raise TypeError("action must be BattleAction")
        actor = self.member(action.actor_id)
        if action.ability_id not in actor.ability_ids:
            raise ValueError("actor does not know ability")
        targets = [self.member(x) for x in action.target_ids]
        emit_hook(
            self.hooks,
            "rpg.battle.before_action",
            source=actor.member_id,
            data={"action": action, "actor": actor, "targets": tuple(targets)},
        )
        source = AbilityTarget(actor.member_id, actor.subject)
        target_values = tuple(AbilityTarget(x.member_id, x.subject) for x in targets)
        result = self.ability_runtime.execute(action.ability_id, source, target_values)
        wrapped = BattleActionResult(action, result)
        emit_hook(
            self.hooks,
            "rpg.battle.after_action",
            source=actor.member_id,
            data={"result": wrapped, "actor": actor, "targets": tuple(targets)},
        )
        return wrapped

    def next_actor(self):
        entry = self.turn_queue.peek()
        if entry is None:
            return None
        actor = self.member(entry.member_id)
        emit_hook(
            self.hooks,
            "rpg.battle.turn_ready",
            source=actor.member_id,
            data={"actor": actor, "round_index": self.turn_queue.round_index},
        )
        return actor

    def advance_turn(self):
        entry = self.turn_queue.pop()
        if entry is not None:
            emit_hook(
                self.hooks,
                "rpg.battle.turn_ended",
                source=entry.member_id,
                data={"entry": entry, "round_index": self.turn_queue.round_index},
            )
        return entry

    def start_next_round(self):
        emit_hook(
            self.hooks,
            "rpg.battle.round_ended",
            data={"round_index": self.turn_queue.round_index},
        )
        entries = self.turn_queue.start_round()
        emit_hook(
            self.hooks,
            "rpg.battle.round_started",
            data={"round_index": self.turn_queue.round_index},
        )
        return entries

    def resolve_outcome(self):
        active_sides = []
        defeated = []
        for side, party in self.parties.items():
            if any(self.is_active(member) for member in party.members):
                active_sides.append(side)
            else:
                defeated.append(side)
        finished = len(active_sides) <= 1
        outcome = BattleOutcome(
            finished,
            tuple(sorted(active_sides)) if finished else (),
            tuple(sorted(defeated)),
        )
        emit_hook(self.hooks, "rpg.battle.outcome_resolved", data={"outcome": outcome})
        if finished:
            emit_hook(self.hooks, "rpg.battle.finished", data={"outcome": outcome})
        return outcome
