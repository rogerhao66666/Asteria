from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from asteria.core.lifecycle import emit_hook


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
class ProgressionMilestone:
    rank: int
    required_total: float
    stat_bonuses: dict[str, float] = field(default_factory=dict)
    granted_abilities: tuple[str, ...] = ()
    granted_tags: tuple[str, ...] = ()

    def __init__(
        self,
        rank,
        required_total,
        *,
        stat_bonuses=None,
        granted_abilities=(),
        granted_tags=(),
    ):
        rank = int(rank)
        required_total = _number(required_total, "required_total")
        if rank < 1:
            raise ValueError("rank must be >= 1")
        if required_total < 0:
            raise ValueError("required_total must be >= 0")
        bonuses = {}
        for k, v in dict(stat_bonuses or {}).items():
            bonuses[_id(k, "stat")] = _number(v, "stat bonus")
        object.__setattr__(self, "rank", rank)
        object.__setattr__(self, "required_total", required_total)
        object.__setattr__(self, "stat_bonuses", bonuses)
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in granted_abilities)),
        )
        object.__setattr__(
            self,
            "granted_tags",
            tuple(sorted({_id(x, "tag").lower() for x in granted_tags})),
        )

    def to_data(self):
        return {
            "rank": self.rank,
            "required_total": self.required_total,
            "stat_bonuses": dict(sorted(self.stat_bonuses.items())),
            "granted_abilities": list(self.granted_abilities),
            "granted_tags": list(self.granted_tags),
        }

    @classmethod
    def from_data(cls, data):
        return cls(**data)


@dataclass(frozen=True, slots=True)
class ProgressionTrackDefinition:
    track_id: str
    display_name: str
    milestones: tuple[ProgressionMilestone, ...]

    def __init__(self, track_id, display_name=None, *, milestones):
        track_id = _id(track_id, "track_id")
        milestones = tuple(milestones)
        if not milestones:
            raise ValueError("progression track requires milestones")
        if any(not isinstance(x, ProgressionMilestone) for x in milestones):
            raise TypeError("milestones must be ProgressionMilestone values")
        ranks = [x.rank for x in milestones]
        totals = [x.required_total for x in milestones]
        if ranks != sorted(ranks) or len(set(ranks)) != len(ranks):
            raise ValueError("milestone ranks must be unique and ascending")
        if totals != sorted(totals) or len(set(totals)) != len(totals):
            raise ValueError("milestone requirements must be unique and ascending")
        object.__setattr__(self, "track_id", track_id)
        object.__setattr__(self, "display_name", str(display_name or track_id))
        object.__setattr__(self, "milestones", milestones)

    def rank_for(self, total):
        total = max(0.0, _number(total, "total"))
        rank = self.milestones[0].rank
        for m in self.milestones:
            if total < m.required_total:
                break
            rank = m.rank
        return rank

    def milestone(self, rank):
        rank = int(rank)
        return next((x for x in self.milestones if x.rank == rank), None)

    def next_milestone(self, total):
        total = max(0.0, _number(total, "total"))
        return next((x for x in self.milestones if x.required_total > total), None)

    def to_data(self):
        return {
            "schema": "asteria.rpg.progression_track",
            "version": 1,
            "track_id": self.track_id,
            "display_name": self.display_name,
            "milestones": [x.to_data() for x in self.milestones],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.progression_track" or data.get("version") != 1:
            raise ValueError("unsupported progression track")
        return cls(
            data["track_id"],
            data["display_name"],
            milestones=[ProgressionMilestone.from_data(x) for x in data["milestones"]],
        )


@dataclass(frozen=True, slots=True)
class ProgressionAdvanceResult:
    track_id: str
    old_total: float
    new_total: float
    old_rank: int
    new_rank: int
    crossed: tuple[ProgressionMilestone, ...]


class ProgressionRuntime:
    """Runtime totals for arbitrary project-defined progression tracks."""

    def __init__(self, definitions=(), totals=None, *, hooks=None):
        self.hooks = hooks
        self.definitions = {}
        for definition in definitions:
            if not isinstance(definition, ProgressionTrackDefinition):
                raise TypeError("definitions must be ProgressionTrackDefinition values")
            if definition.track_id in self.definitions:
                raise ValueError(f"duplicate progression track: {definition.track_id}")
            self.definitions[definition.track_id] = definition
        self.totals = {k: 0.0 for k in self.definitions}
        for key, value in dict(totals or {}).items():
            if key not in self.definitions:
                raise KeyError(f"unknown progression track: {key}")
            value = _number(value, "progression total")
            if value < 0:
                raise ValueError("progression total must be >= 0")
            self.totals[key] = value

    def total(self, track_id):
        return self.totals[str(track_id)]

    def rank(self, track_id):
        key = str(track_id)
        return self.definitions[key].rank_for(self.totals[key])

    def add(self, track_id, amount):
        key = str(track_id)
        amount = _number(amount, "progression amount")
        emit_hook(
            self.hooks,
            "rpg.progression.before_add",
            source=key,
            data={"amount": amount},
        )
        if amount < 0:
            raise ValueError("progression amount must be >= 0")
        definition = self.definitions[key]
        old = self.totals[key]
        old_rank = definition.rank_for(old)
        new = old + amount
        self.totals[key] = new
        new_rank = definition.rank_for(new)
        crossed = tuple(m for m in definition.milestones if old < m.required_total <= new)
        result = ProgressionAdvanceResult(key, old, new, old_rank, new_rank, crossed)
        emit_hook(self.hooks, "rpg.progression.after_add", source=key, data={"result": result})
        if new_rank != old_rank:
            emit_hook(
                self.hooks,
                "rpg.progression.rank_changed",
                source=key,
                data={"result": result},
            )
        return result

    def to_data(self):
        return {
            "schema": "asteria.rpg.progression_runtime",
            "version": 1,
            "totals": {k: self.totals[k] for k in sorted(self.totals)},
        }

    @classmethod
    def from_data(cls, data, definitions):
        if data.get("schema") != "asteria.rpg.progression_runtime" or data.get("version") != 1:
            raise ValueError("unsupported progression runtime")
        return cls(definitions, data["totals"])

    def replace_from(self, other):
        if not isinstance(other, ProgressionRuntime):
            raise TypeError("other must be ProgressionRuntime")
        if set(self.definitions) != set(other.definitions):
            raise ValueError("progression definitions do not match")
        self.totals = dict(other.totals)
        return self

    def replace_from_data(self, data):
        return self.replace_from(type(self).from_data(data, self.definitions.values()))
