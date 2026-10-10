from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg.items import EquipmentDefinition, EquipmentLoadout, EquippedItem


@dataclass(frozen=True, slots=True)
class EquipmentSocketView:
    socket_id: str
    label: str
    locked: bool
    accepted_tags: tuple[str, ...]
    attachment_id: str | None


@dataclass(frozen=True, slots=True)
class EquipmentGrowthView:
    growth_id: str
    label: str
    counters: tuple[tuple[str, float], ...]
    ranks: tuple[tuple[str, int], ...]
    evolution_equipment_id: str | None


@dataclass(frozen=True, slots=True)
class EquippedItemView:
    instance_id: str
    equipment_id: str
    label: str
    slot_id: str
    tags: tuple[str, ...]
    granted_abilities: tuple[str, ...]
    sockets: tuple[EquipmentSocketView, ...]
    growth: EquipmentGrowthView | None


@dataclass(frozen=True, slots=True)
class EquipmentSlotView:
    slot_id: str
    label: str
    accepted_tags: tuple[str, ...]
    capacity: int | None
    items: tuple[EquippedItemView, ...]


@dataclass(frozen=True, slots=True)
class EquipmentCandidateView:
    equipment_id: str
    label: str
    slot_id: str
    tags: tuple[str, ...]
    granted_abilities: tuple[str, ...]
    required_capabilities: tuple[str, ...]
    any_capabilities: tuple[str, ...]
    forbidden_capabilities: tuple[str, ...]
    socket_count: int
    growth_id: str | None
    eligible: bool | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EquipmentScreenView:
    slots: tuple[EquipmentSlotView, ...]
    candidates: tuple[EquipmentCandidateView, ...]
    selected_slot_id: str | None
    selected_equipment_id: str | None
    query: str
    revision: int


@dataclass(frozen=True, slots=True)
class EquipmentScreenProfile:
    slot_labels: tuple[tuple[str, str], ...] = ()
    equipment_labels: tuple[tuple[str, str], ...] = ()
    socket_labels: tuple[tuple[str, str], ...] = ()
    growth_labels: tuple[tuple[str, str], ...] = ()
    page_size: int = 10
    include_incompatible_candidates: bool = True

    SCHEMA = "asteria.equipment_screen_profile"
    VERSION = 1

    def __init__(
        self,
        *,
        slot_labels=None,
        equipment_labels=None,
        socket_labels=None,
        growth_labels=None,
        page_size=10,
        include_incompatible_candidates=True,
    ):
        page_size = int(page_size)
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        for name, values in (
            ("slot_labels", slot_labels),
            ("equipment_labels", equipment_labels),
            ("socket_labels", socket_labels),
            ("growth_labels", growth_labels),
        ):
            object.__setattr__(self, name, tuple(sorted((str(k), str(v)) for k, v in dict(values or {}).items())))
        object.__setattr__(self, "page_size", page_size)
        object.__setattr__(self, "include_incompatible_candidates", bool(include_incompatible_candidates))

    def _lookup(self, pairs, key):
        key = str(key)
        return dict(pairs).get(key, key)

    def slot_label(self, key):
        return self._lookup(self.slot_labels, key)

    def equipment_label(self, key):
        return self._lookup(self.equipment_labels, key)

    def socket_label(self, key):
        return self._lookup(self.socket_labels, key)

    def growth_label(self, key):
        return self._lookup(self.growth_labels, key)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "slot_labels": dict(self.slot_labels),
            "equipment_labels": dict(self.equipment_labels),
            "socket_labels": dict(self.socket_labels),
            "growth_labels": dict(self.growth_labels),
            "page_size": self.page_size,
            "include_incompatible_candidates": self.include_incompatible_candidates,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported equipment screen profile")
        return cls(
            slot_labels=data.get("slot_labels", {}),
            equipment_labels=data.get("equipment_labels", {}),
            socket_labels=data.get("socket_labels", {}),
            growth_labels=data.get("growth_labels", {}),
            page_size=data.get("page_size", 10),
            include_incompatible_candidates=data.get("include_incompatible_candidates", True),
        )


class EquipmentScreenRuntime:
    """Read-only projection of canonical EquipmentLoadout + equipment catalog.

    Eligibility/reasons may be supplied by the controller or derived using the
    existing canonical equipment definition capability rules. No equip/unequip,
    attachment mutation, growth unlock, or inventory consumption occurs here.
    """

    SCHEMA = "asteria.equipment_screen_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or EquipmentScreenProfile()
        if not isinstance(self.profile, EquipmentScreenProfile):
            raise TypeError("profile must be EquipmentScreenProfile")
        self.selected_slot_id = None
        self.selected_equipment_id = None
        self.query = ""
        self.revision = 0
        self._view = None

    @property
    def view(self):
        return self._view

    def _growth_view(self, item):
        growth = item.growth
        if growth is None:
            return None
        return EquipmentGrowthView(
            growth_id=growth.definition.growth_id,
            label=self.profile.growth_label(growth.definition.growth_id),
            counters=tuple(sorted((str(k), float(v)) for k, v in growth.counters.items())),
            ranks=tuple(sorted((str(k), int(v)) for k, v in growth.ranks.items())),
            evolution_equipment_id=item.evolution_target_id,
        )

    def _item_view(self, slot_id, item):
        definition = item.equipment
        sockets = []
        unlocked = set(item.unlocked_socket_ids())
        for socket in definition.sockets:
            attachment = item.attachments.get(socket.socket_id)
            sockets.append(
                EquipmentSocketView(
                    socket_id=socket.socket_id,
                    label=self.profile.socket_label(socket.socket_id),
                    locked=socket.socket_id not in unlocked,
                    accepted_tags=tuple(socket.accepted_tags),
                    attachment_id=None if attachment is None else attachment.attachment_id,
                )
            )
        return EquippedItemView(
            instance_id=item.instance_id,
            equipment_id=definition.equipment_id,
            label=self.profile.equipment_label(definition.equipment_id),
            slot_id=str(slot_id),
            tags=tuple(definition.tags),
            granted_abilities=tuple(item.abilities()),
            sockets=tuple(sockets),
            growth=self._growth_view(item),
        )

    def project(
        self,
        loadout,
        equipment_catalog=(),
        *,
        capabilities=(),
        eligibility_by_equipment=None,
    ):
        if not isinstance(loadout, EquipmentLoadout):
            raise TypeError("loadout must be EquipmentLoadout")

        raw = loadout.to_data()
        slots = []
        for slot in raw["slots"]:
            slot_id = str(slot["slot_id"])
            items = tuple(self._item_view(slot_id, x) for x in loadout.equipped(slot_id))
            slots.append(
                EquipmentSlotView(
                    slot_id=slot_id,
                    label=self.profile.slot_label(slot_id),
                    accepted_tags=tuple(slot.get("accepted_tags", ())),
                    capacity=slot.get("capacity"),
                    items=items,
                )
            )
        slots = tuple(slots)

        known_slots = {x.slot_id for x in slots}
        if self.selected_slot_id not in known_slots:
            self.selected_slot_id = slots[0].slot_id if slots else None

        supplied = dict(eligibility_by_equipment or {})
        query = self.query.casefold().strip()
        candidates = []
        for definition in equipment_catalog:
            if not isinstance(definition, EquipmentDefinition):
                raise TypeError("equipment_catalog must contain EquipmentDefinition values")
            if self.selected_slot_id is not None:
                slot = next(x for x in raw["slots"] if str(x["slot_id"]) == self.selected_slot_id)
                accepted = tuple(slot.get("accepted_tags", ()))
                compatible_slot = (
                    definition.slot == self.selected_slot_id
                    or not accepted
                    or any(tag in definition.tags for tag in accepted)
                )
                if not compatible_slot and not self.profile.include_incompatible_candidates:
                    continue
            else:
                compatible_slot = True

            if definition.equipment_id in supplied:
                result = supplied[definition.equipment_id]
                eligible = bool(result.allowed)
                reasons = tuple(result.reasons)
            else:
                result = definition.eligibility(capabilities)
                eligible = bool(result.allowed and compatible_slot)
                reasons = list(result.reasons)
                if not compatible_slot:
                    reasons.append("equipment is not compatible with selected slot")
                reasons = tuple(reasons)

            label = self.profile.equipment_label(definition.equipment_id)
            haystack = " ".join((definition.equipment_id, label, definition.slot, *definition.tags)).casefold()
            if query and query not in haystack:
                continue
            candidates.append(
                EquipmentCandidateView(
                    equipment_id=definition.equipment_id,
                    label=label,
                    slot_id=definition.slot,
                    tags=tuple(definition.tags),
                    granted_abilities=tuple(definition.granted_abilities),
                    required_capabilities=tuple(definition.required_capabilities),
                    any_capabilities=tuple(definition.any_capabilities),
                    forbidden_capabilities=tuple(definition.forbidden_capabilities),
                    socket_count=len(definition.sockets),
                    growth_id=definition.growth_id,
                    eligible=eligible,
                    reasons=reasons,
                )
            )
        candidates = tuple(sorted(candidates, key=lambda x: (not bool(x.eligible), x.label.casefold(), x.equipment_id)))

        if self.selected_equipment_id not in {x.equipment_id for x in candidates}:
            self.selected_equipment_id = candidates[0].equipment_id if candidates else None

        self.revision += 1
        self._view = EquipmentScreenView(
            slots=slots,
            candidates=candidates,
            selected_slot_id=self.selected_slot_id,
            selected_equipment_id=self.selected_equipment_id,
            query=self.query,
            revision=self.revision,
        )
        return self._view

    def select_slot(self, slot_id):
        if self._view is None:
            raise RuntimeError("equipment screen has not been projected")
        slot_id = str(slot_id)
        if slot_id not in {x.slot_id for x in self._view.slots}:
            raise KeyError(f"unknown equipment slot: {slot_id}")
        self.selected_slot_id = slot_id
        return slot_id

    def select_equipment(self, equipment_id):
        if self._view is None:
            raise RuntimeError("equipment screen has not been projected")
        equipment_id = str(equipment_id)
        if equipment_id not in {x.equipment_id for x in self._view.candidates}:
            raise KeyError(f"unknown equipment candidate: {equipment_id}")
        self.selected_equipment_id = equipment_id
        return equipment_id

    def set_query(self, query):
        self.query = str(query)
        return self.query

    def page(self, index=0):
        if self._view is None:
            raise RuntimeError("equipment screen has not been projected")
        index = max(0, int(index))
        start = index * self.profile.page_size
        return self._view.candidates[start : start + self.profile.page_size]

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "selected_slot_id": self.selected_slot_id,
            "selected_equipment_id": self.selected_equipment_id,
            "query": self.query,
            "revision": self.revision,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported equipment screen snapshot")
        if EquipmentScreenProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("equipment screen profile mismatch")
        self.selected_slot_id = data.get("selected_slot_id")
        self.selected_equipment_id = data.get("selected_equipment_id")
        self.query = str(data.get("query", ""))
        self.revision = int(data["revision"])
        self._view = None
        return self
