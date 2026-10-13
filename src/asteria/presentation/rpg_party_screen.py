from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg.targeting import BattleFormationRuntime


@dataclass(frozen=True, slots=True)
class PartyMemberPresentation:
    member_id: str
    label: str
    group: str
    active: bool
    reserve: bool
    focused: bool
    formation_slot_id: str | None = None
    formation_x: float | None = None
    formation_y: float | None = None
    formation_tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PartyFormationSlotView:
    slot_id: str
    label: str
    x: float
    y: float
    tags: tuple[str, ...]
    adjacent_to: tuple[str, ...]
    member_id: str | None


@dataclass(frozen=True, slots=True)
class PartyGroupView:
    group_id: str
    label: str
    member_ids: tuple[str, ...]
    visible_member_ids: tuple[str, ...]
    overflow_count: int


@dataclass(frozen=True, slots=True)
class PartyScreenView:
    roster: tuple[PartyMemberPresentation, ...]
    groups: tuple[PartyGroupView, ...]
    formation_id: str | None
    formation_slots: tuple[PartyFormationSlotView, ...]
    focused_member_id: str | None
    revision: int


@dataclass(frozen=True, slots=True)
class PartyScreenProfile:
    """Project-owned party/formation presentation policy.

    `visible_limits` are display limits only; they never constrain canonical
    party membership or formation placement.
    """

    group_order: tuple[str, ...] = ("active", "reserve")
    group_labels: tuple[tuple[str, str], ...] = (("active", "Active"), ("reserve", "Reserve"))
    member_labels: tuple[tuple[str, str], ...] = ()
    slot_labels: tuple[tuple[str, str], ...] = ()
    visible_limits: tuple[tuple[str, int], ...] = ()

    SCHEMA = "asteria.party_screen_profile"
    VERSION = 1

    def __init__(
        self,
        *,
        group_order=("active", "reserve"),
        group_labels=None,
        member_labels=None,
        slot_labels=None,
        visible_limits=None,
    ):
        group_order = tuple(dict.fromkeys(str(x).strip() for x in group_order if str(x).strip()))
        if not group_order:
            raise ValueError("party screen requires at least one group")
        object.__setattr__(self, "group_order", group_order)
        object.__setattr__(
            self,
            "group_labels",
            tuple(
                sorted(
                    (str(k), str(v))
                    for k, v in dict(
                        group_labels or {"active": "Active", "reserve": "Reserve"}
                    ).items()
                )
            ),
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
        limits = []
        for key, value in dict(visible_limits or {}).items():
            value = int(value)
            if value < 1:
                raise ValueError("party visible limit must be >= 1")
            limits.append((str(key), value))
        object.__setattr__(self, "visible_limits", tuple(sorted(limits)))

    def group_label(self, group_id):
        return dict(self.group_labels).get(str(group_id), str(group_id))

    def member_label(self, member_id):
        return dict(self.member_labels).get(str(member_id), str(member_id))

    def slot_label(self, slot_id):
        return dict(self.slot_labels).get(str(slot_id), str(slot_id))

    def visible_limit(self, group_id):
        return dict(self.visible_limits).get(str(group_id))

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "group_order": list(self.group_order),
            "group_labels": dict(self.group_labels),
            "member_labels": dict(self.member_labels),
            "slot_labels": dict(self.slot_labels),
            "visible_limits": dict(self.visible_limits),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported party screen profile")
        return cls(
            group_order=data.get("group_order", ()),
            group_labels=data.get("group_labels", {}),
            member_labels=data.get("member_labels", {}),
            slot_labels=data.get("slot_labels", {}),
            visible_limits=data.get("visible_limits", {}),
        )


class PartyScreenRuntime:
    """Read-only party/formation presentation projection.

    The caller supplies canonical roster membership and which members are active.
    Presentation never moves members between groups or formation slots.
    """

    SCHEMA = "asteria.party_screen_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or PartyScreenProfile()
        if not isinstance(self.profile, PartyScreenProfile):
            raise TypeError("profile must be PartyScreenProfile")
        self.focused_member_id = None
        self.revision = 0
        self._view = None

    @property
    def view(self):
        return self._view

    def project(
        self, roster_member_ids, *, active_member_ids=(), formation=None, group_by_member=None
    ):
        roster = tuple(dict.fromkeys(str(x) for x in roster_member_ids))
        if any(not x.strip() for x in roster):
            raise ValueError("party member id is required")

        active = {str(x) for x in active_member_ids}
        unknown_active = active - set(roster)
        if unknown_active:
            raise ValueError("active members must belong to roster")

        if formation is not None and not isinstance(formation, BattleFormationRuntime):
            raise TypeError("formation must be BattleFormationRuntime")
        if formation is not None:
            unknown_placements = {x.member_id for x in formation.placements()} - set(roster)
            if unknown_placements:
                raise ValueError("formation members must belong to roster")

        groups_by_member = {str(k): str(v) for k, v in dict(group_by_member or {}).items()}
        for member_id in groups_by_member:
            if member_id not in roster:
                raise ValueError("group mapping references unknown party member")

        def group_for(member_id):
            if member_id in groups_by_member:
                return groups_by_member[member_id]
            return "active" if member_id in active else "reserve"

        available_groups = []
        for group_id in self.profile.group_order:
            if any(group_for(x) == group_id for x in roster):
                available_groups.append(group_id)
        for member_id in roster:
            group_id = group_for(member_id)
            if group_id not in available_groups:
                available_groups.append(group_id)

        if self.focused_member_id not in roster:
            self.focused_member_id = roster[0] if roster else None

        slots = ()
        slot_by_member = {}
        if formation is not None:
            slots_list = []
            for slot in formation.definition.slots:
                member_id = formation.member_at(slot.slot_id)
                if member_id is not None:
                    slot_by_member[member_id] = slot
                slots_list.append(
                    PartyFormationSlotView(
                        slot_id=slot.slot_id,
                        label=self.profile.slot_label(slot.slot_id),
                        x=float(slot.x),
                        y=float(slot.y),
                        tags=tuple(slot.tags),
                        adjacent_to=tuple(slot.adjacent_to),
                        member_id=member_id,
                    )
                )
            slots = tuple(slots_list)

        members = []
        for member_id in roster:
            slot = slot_by_member.get(member_id)
            group_id = group_for(member_id)
            members.append(
                PartyMemberPresentation(
                    member_id=member_id,
                    label=self.profile.member_label(member_id),
                    group=group_id,
                    active=member_id in active,
                    reserve=member_id not in active,
                    focused=member_id == self.focused_member_id,
                    formation_slot_id=None if slot is None else slot.slot_id,
                    formation_x=None if slot is None else float(slot.x),
                    formation_y=None if slot is None else float(slot.y),
                    formation_tags=() if slot is None else tuple(slot.tags),
                )
            )

        groups = []
        for group_id in available_groups:
            ids = tuple(x.member_id for x in members if x.group == group_id)
            limit = self.profile.visible_limit(group_id)
            if limit is None or len(ids) <= limit:
                visible = ids
            else:
                visible = list(ids[:limit])
                # Focus retention is presentation-only and never changes roster order.
                if self.focused_member_id in ids and self.focused_member_id not in visible:
                    visible[-1] = self.focused_member_id
                visible = tuple(visible)
            groups.append(
                PartyGroupView(
                    group_id=group_id,
                    label=self.profile.group_label(group_id),
                    member_ids=ids,
                    visible_member_ids=tuple(visible),
                    overflow_count=max(0, len(ids) - len(visible)),
                )
            )

        self.revision += 1
        self._view = PartyScreenView(
            roster=tuple(members),
            groups=tuple(groups),
            formation_id=None if formation is None else formation.definition.formation_id,
            formation_slots=slots,
            focused_member_id=self.focused_member_id,
            revision=self.revision,
        )
        return self._view

    def focus(self, member_id):
        if self._view is None:
            raise RuntimeError("party screen has not been projected")
        member_id = str(member_id)
        if member_id not in {x.member_id for x in self._view.roster}:
            raise KeyError(f"unknown party member: {member_id}")
        if member_id == self.focused_member_id:
            return self._view
        self.focused_member_id = member_id
        self.revision += 1
        self._view = PartyScreenView(
            roster=tuple(
                PartyMemberPresentation(
                    x.member_id,
                    x.label,
                    x.group,
                    x.active,
                    x.reserve,
                    x.member_id == member_id,
                    x.formation_slot_id,
                    x.formation_x,
                    x.formation_y,
                    x.formation_tags,
                )
                for x in self._view.roster
            ),
            groups=self._view.groups,
            formation_id=self._view.formation_id,
            formation_slots=self._view.formation_slots,
            focused_member_id=member_id,
            revision=self.revision,
        )
        return self._view

    def snapshot(self):
        def member_data(x):
            return {
                "member_id": x.member_id,
                "label": x.label,
                "group": x.group,
                "active": x.active,
                "reserve": x.reserve,
                "focused": x.focused,
                "formation_slot_id": x.formation_slot_id,
                "formation_x": x.formation_x,
                "formation_y": x.formation_y,
                "formation_tags": list(x.formation_tags),
            }

        view = None
        if self._view is not None:
            view = {
                "roster": [member_data(x) for x in self._view.roster],
                "groups": [
                    {
                        "group_id": x.group_id,
                        "label": x.label,
                        "member_ids": list(x.member_ids),
                        "visible_member_ids": list(x.visible_member_ids),
                        "overflow_count": x.overflow_count,
                    }
                    for x in self._view.groups
                ],
                "formation_id": self._view.formation_id,
                "formation_slots": [
                    {
                        "slot_id": x.slot_id,
                        "label": x.label,
                        "x": x.x,
                        "y": x.y,
                        "tags": list(x.tags),
                        "adjacent_to": list(x.adjacent_to),
                        "member_id": x.member_id,
                    }
                    for x in self._view.formation_slots
                ],
                "focused_member_id": self._view.focused_member_id,
                "revision": self._view.revision,
            }
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "focused_member_id": self.focused_member_id,
            "revision": self.revision,
            "view": view,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported party screen snapshot")
        if PartyScreenProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("party screen profile mismatch")
        self.focused_member_id = data.get("focused_member_id")
        self.revision = int(data["revision"])
        raw = data.get("view")
        if raw is None:
            self._view = None
            return self
        self._view = PartyScreenView(
            roster=tuple(
                PartyMemberPresentation(
                    member_id=x["member_id"],
                    label=x["label"],
                    group=x["group"],
                    active=bool(x["active"]),
                    reserve=bool(x["reserve"]),
                    focused=bool(x["focused"]),
                    formation_slot_id=x.get("formation_slot_id"),
                    formation_x=x.get("formation_x"),
                    formation_y=x.get("formation_y"),
                    formation_tags=tuple(x.get("formation_tags", ())),
                )
                for x in raw.get("roster", ())
            ),
            groups=tuple(
                PartyGroupView(
                    group_id=x["group_id"],
                    label=x["label"],
                    member_ids=tuple(x.get("member_ids", ())),
                    visible_member_ids=tuple(x.get("visible_member_ids", ())),
                    overflow_count=int(x["overflow_count"]),
                )
                for x in raw.get("groups", ())
            ),
            formation_id=raw.get("formation_id"),
            formation_slots=tuple(
                PartyFormationSlotView(
                    slot_id=x["slot_id"],
                    label=x["label"],
                    x=float(x["x"]),
                    y=float(x["y"]),
                    tags=tuple(x.get("tags", ())),
                    adjacent_to=tuple(x.get("adjacent_to", ())),
                    member_id=x.get("member_id"),
                )
                for x in raw.get("formation_slots", ())
            ),
            focused_member_id=raw.get("focused_member_id"),
            revision=int(raw["revision"]),
        )
        return self
