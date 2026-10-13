from __future__ import annotations

from dataclasses import dataclass


def _id(v, label):
    v = str(v).strip()
    if not v:
        raise ValueError(f"{label} is required")
    return v


@dataclass(frozen=True, slots=True)
class PartyPlacementDefinition:
    actor_id: str
    slot_id: str

    def __init__(self, actor_id, slot_id):
        object.__setattr__(self, "actor_id", _id(actor_id, "actor_id"))
        object.__setattr__(self, "slot_id", _id(slot_id, "slot_id"))

    def to_data(self):
        return {"actor_id": self.actor_id, "slot_id": self.slot_id}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"actor_id", "slot_id"}:
            raise ValueError("invalid party placement")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class PartySetupDefinition:
    party_id: str
    display_name: str
    roster_actor_ids: tuple[str, ...]
    active_actor_ids: tuple[str, ...]
    active_capacity: int
    formation_id: str | None
    placements: tuple[PartyPlacementDefinition, ...]
    allow_reserve: bool
    allow_swap: bool
    allow_reorder: bool
    tags: tuple[str, ...]

    def __init__(
        self,
        party_id,
        display_name=None,
        *,
        roster_actor_ids=(),
        active_actor_ids=(),
        active_capacity=4,
        formation_id=None,
        placements=(),
        allow_reserve=True,
        allow_swap=True,
        allow_reorder=True,
        tags=(),
    ):
        roster = tuple(dict.fromkeys(_id(x, "actor_id") for x in roster_actor_ids))
        active = tuple(_id(x, "actor_id") for x in active_actor_ids)
        if len(active) != len(set(active)):
            raise ValueError("active actor ids must be unique")
        unknown = set(active) - set(roster)
        if unknown:
            raise ValueError("active actors must belong to roster")
        active_capacity = int(active_capacity)
        if active_capacity < 1:
            raise ValueError("active_capacity must be >= 1")
        if len(active) > active_capacity:
            raise ValueError("active actor count exceeds active_capacity")
        placements = tuple(
            x if isinstance(x, PartyPlacementDefinition) else PartyPlacementDefinition.from_data(x)
            for x in placements
        )
        if len({x.actor_id for x in placements}) != len(placements):
            raise ValueError("actor cannot occupy multiple formation slots")
        if len({x.slot_id for x in placements}) != len(placements):
            raise ValueError("formation slot cannot contain multiple actors")
        if set(x.actor_id for x in placements) - set(active):
            raise ValueError("only active actors can have formation placements")
        if placements and formation_id is None:
            raise ValueError("placements require formation_id")
        object.__setattr__(self, "party_id", _id(party_id, "party_id"))
        object.__setattr__(self, "display_name", str(display_name or party_id))
        object.__setattr__(self, "roster_actor_ids", roster)
        object.__setattr__(self, "active_actor_ids", active)
        object.__setattr__(self, "active_capacity", active_capacity)
        object.__setattr__(
            self,
            "formation_id",
            None if formation_id is None else _id(formation_id, "formation_id"),
        )
        object.__setattr__(self, "placements", placements)
        object.__setattr__(self, "allow_reserve", bool(allow_reserve))
        object.__setattr__(self, "allow_swap", bool(allow_swap))
        object.__setattr__(self, "allow_reorder", bool(allow_reorder))
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags})))

    @property
    def reserve_actor_ids(self):
        active = set(self.active_actor_ids)
        return tuple(x for x in self.roster_actor_ids if x not in active)

    def to_data(self):
        return {
            "schema": "asteria.rpg.party_setup",
            "version": 1,
            "party_id": self.party_id,
            "display_name": self.display_name,
            "roster_actor_ids": list(self.roster_actor_ids),
            "active_actor_ids": list(self.active_actor_ids),
            "active_capacity": self.active_capacity,
            "formation_id": self.formation_id,
            "placements": [x.to_data() for x in self.placements],
            "allow_reserve": self.allow_reserve,
            "allow_swap": self.allow_swap,
            "allow_reorder": self.allow_reorder,
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.party_setup" or data.get("version") != 1:
            raise ValueError("unsupported party setup")
        return cls(
            data["party_id"],
            data["display_name"],
            roster_actor_ids=data["roster_actor_ids"],
            active_actor_ids=data["active_actor_ids"],
            active_capacity=data["active_capacity"],
            formation_id=data["formation_id"],
            placements=[PartyPlacementDefinition.from_data(x) for x in data["placements"]],
            allow_reserve=data["allow_reserve"],
            allow_swap=data["allow_swap"],
            allow_reorder=data["allow_reorder"],
            tags=data["tags"],
        )


@dataclass(frozen=True, slots=True)
class PartyPresentationPolicyDefinition:
    profile_id: str
    group_order: tuple[str, ...]
    group_labels: tuple[tuple[str, str], ...]
    member_labels: tuple[tuple[str, str], ...]
    slot_labels: tuple[tuple[str, str], ...]
    visible_limits: tuple[tuple[str, int], ...]

    def __init__(
        self,
        profile_id,
        *,
        group_order=("active", "reserve"),
        group_labels=None,
        member_labels=None,
        slot_labels=None,
        visible_limits=None,
    ):
        order = tuple(dict.fromkeys(_id(x, "group_id") for x in group_order))
        if not order:
            raise ValueError("party presentation requires a group")
        limits = []
        for k, v in dict(visible_limits or {}).items():
            v = int(v)
            if v < 1:
                raise ValueError("visible limit must be >= 1")
            limits.append((_id(k, "group_id"), v))
        object.__setattr__(self, "profile_id", _id(profile_id, "profile_id"))
        object.__setattr__(self, "group_order", order)
        object.__setattr__(
            self,
            "group_labels",
            tuple(sorted((str(k), str(v)) for k, v in dict(group_labels or {}).items())),
        )
        object.__setattr__(
            self,
            "member_labels",
            tuple(sorted((str(k), str(v)) for k, v in dict(member_labels or {}).items())),
        )
        object.__setattr__(
            self,
            "slot_labels",
            tuple(sorted((str(k), str(v)) for k, v in dict(slot_labels or {}).items())),
        )
        object.__setattr__(self, "visible_limits", tuple(sorted(limits)))

    def to_data(self):
        return {
            "schema": "asteria.rpg.party_presentation_policy",
            "version": 1,
            "profile_id": self.profile_id,
            "group_order": list(self.group_order),
            "group_labels": dict(self.group_labels),
            "member_labels": dict(self.member_labels),
            "slot_labels": dict(self.slot_labels),
            "visible_limits": dict(self.visible_limits),
        }

    @classmethod
    def from_data(cls, data):
        if (
            data.get("schema") != "asteria.rpg.party_presentation_policy"
            or data.get("version") != 1
        ):
            raise ValueError("unsupported party presentation policy")
        return cls(
            data["profile_id"],
            group_order=data["group_order"],
            group_labels=data["group_labels"],
            member_labels=data["member_labels"],
            slot_labels=data["slot_labels"],
            visible_limits=data["visible_limits"],
        )
