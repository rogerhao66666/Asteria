from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg import (
    BattleFormationRuntime,
    BattlePlacement,
    FormationDefinition,
    FormationSlotDefinition,
    Party,
)

from .playable_battle_party import build_playable_party_scenario


@dataclass(frozen=True, slots=True)
class PartyFormationLabSnapshot:
    roster_ids: tuple[str, ...]
    active_ids: tuple[str, ...]
    reserve_ids: tuple[str, ...]
    placements: tuple[tuple[str, str], ...]


class PartyFormationLab:
    """Operable outside-battle party/formation reference controller.

    Active capacity and active/reserve grouping are project policy. Canonical
    Party owns the roster and BattleFormationRuntime owns logical placement.
    """

    def __init__(self, *, active_capacity=4):
        active_capacity = int(active_capacity)
        if active_capacity < 1:
            raise ValueError("active_capacity must be >= 1")
        source = build_playable_party_scenario()
        roster_ids = tuple(f"party_{i:02d}" for i in range(12))
        members = tuple(source.battle.member(member_id) for member_id in roster_ids)
        self.party = Party("side.alpha", members)
        self.active_capacity = active_capacity
        self._active = list(roster_ids[:active_capacity])
        self._reserve = list(roster_ids[active_capacity:])

        slots = tuple(
            FormationSlotDefinition(
                f"slot_{i}",
                x=float(i),
                y=float(i % 2),
                tags=(f"position.{i}",),
                adjacent_to=tuple(
                    x
                    for x in (
                        f"slot_{i - 1}" if i > 0 else None,
                        f"slot_{i + 1}" if i + 1 < active_capacity else None,
                    )
                    if x is not None
                ),
            )
            for i in range(active_capacity)
        )
        definition = FormationDefinition("party_lab_formation", slots)
        self.formation = BattleFormationRuntime(
            definition,
            tuple(BattlePlacement(member_id, f"slot_{i}") for i, member_id in enumerate(self._active)),
        )

    def roster_ids(self):
        return self.party.ids()

    def active_ids(self):
        return tuple(self._active)

    def reserve_ids(self):
        return tuple(self._reserve)

    def move(self, member_id, slot_id):
        member_id = str(member_id)
        if member_id not in self._active:
            raise ValueError("only active members can occupy formation slots")
        occupant = self.formation.member_at(slot_id)
        current = self.formation.slot_id_for(member_id)
        if occupant is not None and occupant != member_id:
            if current is None:
                raise ValueError("active member has no current formation slot")
            # Canonical formation.place() never overwrites an occupied slot.
            # For a project-level swap, clear both placements first, then place.
            self.formation.remove(member_id)
            self.formation.remove(occupant)
            self.formation.place(occupant, current)
            return self.formation.place(member_id, slot_id)
        return self.formation.place(member_id, slot_id)

    def swap_active_with_reserve(self, outgoing_id, incoming_id):
        outgoing_id = str(outgoing_id)
        incoming_id = str(incoming_id)
        if outgoing_id not in self._active:
            raise ValueError("outgoing member must be active")
        if incoming_id not in self._reserve:
            raise ValueError("incoming member must be reserve")
        active_index = self._active.index(outgoing_id)
        reserve_index = self._reserve.index(incoming_id)
        slot_id = self.formation.slot_id_for(outgoing_id)
        if slot_id is None:
            raise ValueError("outgoing member has no formation slot")

        self.formation.remove(outgoing_id)
        self.formation.place(incoming_id, slot_id)
        self._active[active_index] = incoming_id
        self._reserve[reserve_index] = outgoing_id
        return outgoing_id, incoming_id, slot_id

    def set_active_members(self, member_ids):
        values = tuple(str(x) for x in member_ids)
        if len(values) > self.active_capacity:
            raise ValueError("active member count exceeds project active_capacity")
        if len(values) != len(set(values)):
            raise ValueError("active member ids must be unique")
        unknown = set(values) - set(self.roster_ids())
        if unknown:
            raise KeyError(", ".join(sorted(unknown)))

        self._active = list(values)
        self._reserve = [x for x in self.roster_ids() if x not in values]
        self.formation = BattleFormationRuntime(self.formation.definition)
        for i, member_id in enumerate(values):
            self.formation.place(member_id, f"slot_{i}")
        return self.active_ids()

    def reorder_roster(self, member_ids):
        values = tuple(str(x) for x in member_ids)
        if set(values) != set(self.roster_ids()) or len(values) != len(self.roster_ids()):
            raise ValueError("reorder must contain each roster member exactly once")
        lookup = {m.member_id: m for m in self.party.members}
        self.party.members = [lookup[x] for x in values]
        self._reserve = [x for x in values if x not in self._active]
        return self.roster_ids()

    def add_member(self, member):
        added = self.party.add(member)
        self._reserve.append(added.member_id)
        return added

    def remove_member(self, member_id):
        member_id = str(member_id)
        if member_id in self._active:
            slot_id = self.formation.slot_id_for(member_id)
            if slot_id is not None:
                self.formation.remove(member_id)
            self._active.remove(member_id)
        elif member_id in self._reserve:
            self._reserve.remove(member_id)
        return self.party.remove(member_id)

    def snapshot(self):
        return PartyFormationLabSnapshot(
            self.roster_ids(),
            self.active_ids(),
            self.reserve_ids(),
            tuple((x.member_id, x.slot_id) for x in self.formation.placements()),
        )
