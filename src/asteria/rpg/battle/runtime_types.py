"""The battle runtime's value types: a party and its members, the turn queue, an action,
its result and preview, and the battle's outcome (``BattleRuntime`` in ``core`` uses them)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from asteria.core.lifecycle import emit_hook
from asteria.core.values import finite, required_id
from asteria.gameplay import GameplaySubject
from asteria.gameplay.expressions import SubjectView, evaluate


@dataclass(frozen=True, slots=True)
class PartyMember:
    member_id: str
    side: str
    subject: GameplaySubject
    ability_ids: tuple[str, ...] = ()
    initiative: float = 0.0
    initiative_stat: str = ""
    initiative_expression: str = ""

    def __init__(
        self,
        member_id,
        side,
        subject,
        *,
        ability_ids=(),
        initiative=0.0,
        initiative_stat="",
        initiative_expression="",
    ):
        if not isinstance(subject, GameplaySubject):
            raise TypeError("subject must be GameplaySubject")
        object.__setattr__(self, "member_id", required_id(member_id, "member_id"))
        object.__setattr__(self, "side", required_id(side, "side"))
        object.__setattr__(self, "subject", subject)
        object.__setattr__(
            self,
            "ability_ids",
            tuple(dict.fromkeys(required_id(x, "ability_id") for x in ability_ids)),
        )
        object.__setattr__(self, "initiative", finite(initiative, "initiative"))
        object.__setattr__(self, "initiative_stat", str(initiative_stat or ""))
        object.__setattr__(self, "initiative_expression", str(initiative_expression or ""))

    @property
    def current_initiative(self):
        """Initiative now: the ``initiative_stat`` of the subject when named (so speed changes in
        battle -
        haste, slow - move later turns), else the fixed ``initiative``; an
        ``initiative_expression`` (of ``self``) wins over both."""
        if self.initiative_expression:
            return evaluate(self.initiative_expression, {"self": SubjectView(self.subject)})
        stats = self.subject.stats
        if self.initiative_stat and stats.contains(self.initiative_stat):
            return float(stats.get(self.initiative_stat))
        return self.initiative


class TurnOrderPolicy(str, Enum):
    FIXED_INITIATIVE = "fixed_initiative"


@dataclass(slots=True)
class Party:
    side: str
    members: list[PartyMember] = field(default_factory=list)
    hooks: object = None

    def __init__(self, side, members=(), *, hooks=None):
        self.side = required_id(side, "side")
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
        emit_hook(self.hooks, "rpg.party.after_add", source=self.side, data={"member": member})
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

    def register_member(self, member, *, join_current_round=False):
        if any(x.member_id == member.member_id for x in self._source):
            raise ValueError(f"duplicate turn queue member: {member.member_id}")
        self._source = (*self._source, member)
        if join_current_round:
            self._pending.append(TurnEntry(member.member_id, member.side, member.initiative))
            self._pending.sort(key=lambda x: (-x.initiative, x.member_id))

    def replace_member(self, member):
        found = False
        source = []
        for current in self._source:
            if current.member_id == member.member_id:
                source.append(member)
                found = True
            else:
                source.append(current)
        if not found:
            raise KeyError(member.member_id)
        self._source = tuple(source)
        self._pending = [
            TurnEntry(x.member_id, x.side, member.initiative)
            if x.member_id == member.member_id
            else x
            for x in self._pending
        ]

    def remove_pending(self, member_id):
        member_id = str(member_id)
        self._pending = [x for x in self._pending if x.member_id != member_id]

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
            TurnEntry(x["member_id"], x["side"], x["initiative"]) for x in data["pending"]
        ]
        return result


@dataclass(frozen=True, slots=True)
class BattleAction:
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]
    forced: bool = False  # the targets were set by a state, not chosen: no targeting rules

    def __init__(self, actor_id, ability_id, target_ids, forced=False):
        object.__setattr__(self, "forced", bool(forced))
        object.__setattr__(self, "actor_id", required_id(actor_id, "actor_id"))
        object.__setattr__(self, "ability_id", required_id(ability_id, "ability_id"))
        object.__setattr__(
            self, "target_ids", tuple(required_id(x, "target_id") for x in target_ids)
        )


@dataclass(frozen=True, slots=True)
class BattleActionResult:
    action: BattleAction
    execution_result: object
    # (target_id, resource_id, ValueResolutionResult) for every harmful resource
    # delta the project's interaction rules resolved during this action.
    interactions: tuple = ()


@dataclass(frozen=True, slots=True)
class BattleActionPreview:
    """Predicted result of an action, computed by the same pipeline as execute.

    ``resource_deltas`` maps member id -> {resource id: change}; nothing in the
    battle is mutated.
    """

    action: BattleAction
    executable: bool
    errors: tuple[str, ...]
    resource_deltas: dict
    interactions: tuple = ()


@dataclass(frozen=True, slots=True)
class BattleOutcome:
    finished: bool
    winning_sides: tuple[str, ...] = ()
    defeated_sides: tuple[str, ...] = ()
    escaped_sides: tuple[str, ...] = ()
    objective_ids: tuple[str, ...] = ()
