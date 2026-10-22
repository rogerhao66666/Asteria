from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg.resolved_build import ResolvedActorBuild


def _label(value, fallback):
    value = str(value).strip()
    return value or str(fallback)


@dataclass(frozen=True, slots=True)
class CharacterScreenStatView:
    stat_id: str
    label: str
    value: float
    group: str = "stats"
    priority: int = 0


@dataclass(frozen=True, slots=True)
class CharacterScreenResourceView:
    resource_id: str
    label: str
    current: float
    minimum: float
    maximum: float
    normalized: float
    presentation: str = "bar"
    group: str = "resources"
    priority: int = 0


@dataclass(frozen=True, slots=True)
class CharacterScreenEquipmentItemView:
    instance_id: str
    equipment_id: str
    label: str
    attachment_ids: tuple[str, ...] = ()
    growth_id: str | None = None


@dataclass(frozen=True, slots=True)
class CharacterScreenEquipmentSlotView:
    slot_id: str
    label: str
    capacity: int | None
    items: tuple[CharacterScreenEquipmentItemView, ...]


@dataclass(frozen=True, slots=True)
class CharacterScreenAbilityView:
    ability_id: str
    label: str
    active: bool = True
    source_labels: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CharacterScreenProgressionView:
    track_id: str
    label: str
    total: float
    rank: int


@dataclass(frozen=True, slots=True)
class CharacterScreenSection:
    section_id: str
    label: str
    kind: str
    priority: int
    count: int


@dataclass(frozen=True, slots=True)
class CharacterScreenView:
    actor_id: str
    display_name: str
    sections: tuple[CharacterScreenSection, ...]
    stats: tuple[CharacterScreenStatView, ...]
    resources: tuple[CharacterScreenResourceView, ...]
    equipment: tuple[CharacterScreenEquipmentSlotView, ...]
    abilities: tuple[CharacterScreenAbilityView, ...]
    progression: tuple[CharacterScreenProgressionView, ...]
    tags: tuple[str, ...]
    capabilities: tuple[str, ...]
    class_assignment_ids: tuple[str, ...]
    active_passives: tuple[str, ...]
    selected_section_id: str
    revision: int


@dataclass(frozen=True, slots=True)
class CharacterScreenProfile:
    """Project-owned presentation policy for the default character screen."""

    section_order: tuple[str, ...] = (
        "overview",
        "resources",
        "equipment",
        "abilities",
        "progression",
        "status",
    )
    hidden_sections: tuple[str, ...] = ()
    stat_labels: tuple[tuple[str, str], ...] = ()
    resource_labels: tuple[tuple[str, str], ...] = ()
    resource_presentations: tuple[tuple[str, str], ...] = ()
    slot_labels: tuple[tuple[str, str], ...] = ()
    equipment_labels: tuple[tuple[str, str], ...] = ()
    ability_labels: tuple[tuple[str, str], ...] = ()
    progression_labels: tuple[tuple[str, str], ...] = ()
    # stats listed first, in this order (the rest follow by name); written only when set
    stat_order: tuple[str, ...] = ()
    # resources listed first, in this order (the rest follow by name); written only when set.
    # Unset, the game's own lead resource (the one that knocks a member out: HP) is first.
    resource_order: tuple[str, ...] = ()

    SCHEMA = "asteria.character_screen_profile"
    VERSION = 1
    OPTIONAL_DATA = {"stat_order": [], "resource_order": []}

    def __init__(
        self,
        *,
        section_order=("overview", "resources", "equipment", "abilities", "progression", "status"),
        hidden_sections=(),
        stat_labels=None,
        resource_labels=None,
        resource_presentations=None,
        slot_labels=None,
        equipment_labels=None,
        ability_labels=None,
        progression_labels=None,
        stat_order=(),
        resource_order=(),
    ):
        object.__setattr__(
            self, "stat_order", tuple(dict.fromkeys(str(x).strip() for x in stat_order if x))
        )
        object.__setattr__(
            self,
            "resource_order",
            tuple(dict.fromkeys(str(x).strip() for x in resource_order if x)),
        )
        section_order = tuple(
            dict.fromkeys(str(x).strip() for x in section_order if str(x).strip())
        )
        hidden_sections = tuple(
            sorted({str(x).strip() for x in hidden_sections if str(x).strip()})
        )
        if not section_order:
            raise ValueError("character screen requires at least one section")
        object.__setattr__(self, "section_order", section_order)
        object.__setattr__(self, "hidden_sections", hidden_sections)
        for name, values in (
            ("stat_labels", stat_labels),
            ("resource_labels", resource_labels),
            ("resource_presentations", resource_presentations),
            ("slot_labels", slot_labels),
            ("equipment_labels", equipment_labels),
            ("ability_labels", ability_labels),
            ("progression_labels", progression_labels),
        ):
            pairs = tuple(sorted((str(k), str(v)) for k, v in dict(values or {}).items()))
            object.__setattr__(self, name, pairs)

    def _lookup(self, pairs, key, fallback=None):
        key = str(key)
        return dict(pairs).get(key, key if fallback is None else fallback)

    def ordered_stats(self, names):
        """``names`` with the profile's ``stat_order`` first, then the rest by name."""
        names = set(names)
        first = [x for x in self.stat_order if x in names]
        return (*first, *sorted(names - set(first)))

    def ordered_resources(self, names, lead=()):
        """``names`` with the profile's ``resource_order`` first (unset: ``lead``, the game's
        knockout resource), then the rest by name."""
        names = set(names)
        first = [x for x in (self.resource_order or tuple(lead)) if x in names]
        return (*first, *sorted(names - set(first)))

    def stat_label(self, key):
        return self._lookup(self.stat_labels, key)

    def resource_label(self, key):
        return self._lookup(self.resource_labels, key)

    def resource_presentation(self, key):
        return self._lookup(self.resource_presentations, key, "bar")

    def slot_label(self, key):
        return self._lookup(self.slot_labels, key)

    def equipment_label(self, key):
        return self._lookup(self.equipment_labels, key)

    def ability_label(self, key):
        return self._lookup(self.ability_labels, key)

    def progression_label(self, key):
        return self._lookup(self.progression_labels, key)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "section_order": list(self.section_order),
            "hidden_sections": list(self.hidden_sections),
            "stat_labels": dict(self.stat_labels),
            "resource_labels": dict(self.resource_labels),
            "resource_presentations": dict(self.resource_presentations),
            "slot_labels": dict(self.slot_labels),
            "equipment_labels": dict(self.equipment_labels),
            "ability_labels": dict(self.ability_labels),
            "progression_labels": dict(self.progression_labels),
            **({"stat_order": list(self.stat_order)} if self.stat_order else {}),
            **({"resource_order": list(self.resource_order)} if self.resource_order else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported character screen profile")
        return cls(
            section_order=data.get("section_order", ()),
            hidden_sections=data.get("hidden_sections", ()),
            stat_labels=data.get("stat_labels", {}),
            resource_labels=data.get("resource_labels", {}),
            resource_presentations=data.get("resource_presentations", {}),
            slot_labels=data.get("slot_labels", {}),
            equipment_labels=data.get("equipment_labels", {}),
            ability_labels=data.get("ability_labels", {}),
            progression_labels=data.get("progression_labels", {}),
            stat_order=data.get("stat_order", ()),
            resource_order=data.get("resource_order", ()),
        )


class CharacterScreenRuntime:
    """Read-only projection from the canonical resolved RPG build to runtime UI.

    It never equips items, spends resources, allocates progression, learns
    abilities, changes passives, or mutates the actor runtime.
    """

    SCHEMA = "asteria.character_screen_runtime"
    VERSION = 1

    def __init__(self, profile=None, *, lead_resources=()):
        self.profile = profile or CharacterScreenProfile()
        if not isinstance(self.profile, CharacterScreenProfile):
            raise TypeError("profile must be CharacterScreenProfile")
        # listed first when the profile sets no resource order (the game's knockout resource)
        self.lead_resources = tuple(str(x) for x in lead_resources if x)
        self.revision = 0
        self.selected_section_id = ""
        self._view = None

    @property
    def view(self):
        return self._view

    def project(
        self,
        resolved_build,
        *,
        display_name=None,
        loadout=None,
        progression=None,
        actor_definition=None,
    ):
        if not isinstance(resolved_build, ResolvedActorBuild):
            raise TypeError("resolved_build must be ResolvedActorBuild")

        actor_id = str(resolved_build.actor_id)
        if display_name is None and actor_definition is not None:
            display_name = getattr(actor_definition, "display_name", None)
        display_name = _label(display_name or actor_id, actor_id)

        stats = tuple(
            CharacterScreenStatView(
                stat_id=name,
                label=self.profile.stat_label(name),
                value=float(resolved_build.stats.get(name)),
            )
            for name in self.profile.ordered_stats(resolved_build.stats.names())
        )

        resources = []
        names = resolved_build.resources.names()
        for name in self.profile.ordered_resources(names, self.lead_resources):
            value = resolved_build.resources.get(name)
            resources.append(
                CharacterScreenResourceView(
                    resource_id=name,
                    label=self.profile.resource_label(name),
                    current=float(value.current),
                    minimum=float(value.minimum),
                    maximum=float(value.maximum),
                    normalized=float(value.normalized),
                    presentation=self.profile.resource_presentation(name),
                )
            )
        resources = tuple(resources)

        equipment = ()
        if loadout is not None:
            raw = loadout.to_data()
            slot_defs = {str(x["slot_id"]): x for x in raw.get("slots", ())}
            slot_views = []
            for slot_id in sorted(slot_defs):
                slot = slot_defs[slot_id]
                items = []
                for item in raw.get("equipped", {}).get(slot_id, ()):
                    equipment_id = str(item["equipment_id"])
                    attachments = tuple(
                        str(v) for _, v in sorted(dict(item.get("attachments", {})).items())
                    )
                    growth = item.get("growth")
                    growth_id = None
                    if isinstance(growth, dict):
                        growth_id = (
                            str(growth.get("growth_id") or growth.get("definition_id") or "")
                            or None
                        )
                    items.append(
                        CharacterScreenEquipmentItemView(
                            instance_id=str(item["instance_id"]),
                            equipment_id=equipment_id,
                            label=self.profile.equipment_label(equipment_id),
                            attachment_ids=attachments,
                            growth_id=growth_id,
                        )
                    )
                slot_views.append(
                    CharacterScreenEquipmentSlotView(
                        slot_id=slot_id,
                        label=self.profile.slot_label(slot_id),
                        capacity=slot.get("capacity"),
                        items=tuple(items),
                    )
                )
            equipment = tuple(slot_views)

        source_by_ability = {}
        for grant in resolved_build.ability_grants:
            source_by_ability.setdefault(str(grant.ability_id), []).append(
                f"{grant.source_kind}:{grant.source_id}"
            )
        abilities = tuple(
            CharacterScreenAbilityView(
                ability_id=ability_id,
                label=self.profile.ability_label(ability_id),
                active=True,
                source_labels=tuple(source_by_ability.get(ability_id, ())),
            )
            for ability_id in resolved_build.abilities
        )

        progression_views = ()
        if progression is not None:
            values = []
            for track_id in sorted(progression.definitions):
                values.append(
                    CharacterScreenProgressionView(
                        track_id=track_id,
                        label=self.profile.progression_label(track_id),
                        total=float(progression.total(track_id)),
                        rank=int(progression.rank(track_id)),
                    )
                )
            progression_views = tuple(values)

        counts = {
            "overview": len(stats),
            "resources": len(resources),
            "equipment": len(equipment),
            "abilities": len(abilities),
            "progression": len(progression_views),
            "status": len(tuple(resolved_build.tags.values()))
            + len(resolved_build.active_passives),
        }
        labels = {
            "overview": "Overview",
            "resources": "Resources",
            "equipment": "Equipment",
            "abilities": "Abilities",
            "progression": "Progression",
            "status": "Status",
        }
        hidden = set(self.profile.hidden_sections)
        sections = tuple(
            CharacterScreenSection(
                section_id=section_id,
                label=labels.get(section_id, section_id),
                kind=section_id,
                priority=index,
                count=int(counts.get(section_id, 0)),
            )
            for index, section_id in enumerate(self.profile.section_order)
            if section_id not in hidden
        )
        available_sections = {x.section_id for x in sections}
        if self.selected_section_id not in available_sections:
            self.selected_section_id = "" if not sections else sections[0].section_id

        self.revision += 1
        self._view = CharacterScreenView(
            actor_id=actor_id,
            display_name=display_name,
            sections=sections,
            stats=stats,
            resources=resources,
            equipment=equipment,
            abilities=abilities,
            progression=progression_views,
            tags=tuple(resolved_build.tags.values()),
            capabilities=tuple(resolved_build.capabilities),
            class_assignment_ids=tuple(resolved_build.class_assignment_ids),
            active_passives=tuple(resolved_build.active_passives),
            selected_section_id=self.selected_section_id,
            revision=self.revision,
        )
        return self._view

    def select_section(self, section_id):
        if self._view is None:
            raise RuntimeError("character screen has not been projected")
        section_id = str(section_id)
        valid = {x.section_id for x in self._view.sections}
        if section_id not in valid:
            raise KeyError(f"unknown character screen section: {section_id}")
        if section_id == self.selected_section_id:
            return self._view
        self.selected_section_id = section_id
        self.revision += 1
        raw = self.snapshot()["view"]
        raw["selected_section_id"] = section_id
        raw["revision"] = self.revision
        self._restore_view(raw)
        return self._view

    def _restore_view(self, raw):
        self._view = CharacterScreenView(
            actor_id=str(raw["actor_id"]),
            display_name=str(raw["display_name"]),
            sections=tuple(CharacterScreenSection(**x) for x in raw.get("sections", ())),
            stats=tuple(CharacterScreenStatView(**x) for x in raw.get("stats", ())),
            resources=tuple(CharacterScreenResourceView(**x) for x in raw.get("resources", ())),
            equipment=tuple(
                CharacterScreenEquipmentSlotView(
                    slot_id=x["slot_id"],
                    label=x["label"],
                    capacity=x.get("capacity"),
                    items=tuple(
                        CharacterScreenEquipmentItemView(
                            instance_id=i["instance_id"],
                            equipment_id=i["equipment_id"],
                            label=i["label"],
                            attachment_ids=tuple(i.get("attachment_ids", ())),
                            growth_id=i.get("growth_id"),
                        )
                        for i in x.get("items", ())
                    ),
                )
                for x in raw.get("equipment", ())
            ),
            abilities=tuple(
                CharacterScreenAbilityView(
                    ability_id=x["ability_id"],
                    label=x["label"],
                    active=bool(x.get("active", True)),
                    source_labels=tuple(x.get("source_labels", ())),
                )
                for x in raw.get("abilities", ())
            ),
            progression=tuple(
                CharacterScreenProgressionView(**x) for x in raw.get("progression", ())
            ),
            tags=tuple(raw.get("tags", ())),
            capabilities=tuple(raw.get("capabilities", ())),
            class_assignment_ids=tuple(raw.get("class_assignment_ids", ())),
            active_passives=tuple(raw.get("active_passives", ())),
            selected_section_id=str(raw.get("selected_section_id", "")),
            revision=int(raw["revision"]),
        )

    def snapshot(self):
        if self._view is None:
            view = None
        else:
            view = {
                "actor_id": self._view.actor_id,
                "display_name": self._view.display_name,
                "sections": [
                    x.__dict__
                    if hasattr(x, "__dict__")
                    else {
                        "section_id": x.section_id,
                        "label": x.label,
                        "kind": x.kind,
                        "priority": x.priority,
                        "count": x.count,
                    }
                    for x in self._view.sections
                ],
                "stats": [
                    {
                        "stat_id": x.stat_id,
                        "label": x.label,
                        "value": x.value,
                        "group": x.group,
                        "priority": x.priority,
                    }
                    for x in self._view.stats
                ],
                "resources": [
                    {
                        "resource_id": x.resource_id,
                        "label": x.label,
                        "current": x.current,
                        "minimum": x.minimum,
                        "maximum": x.maximum,
                        "normalized": x.normalized,
                        "presentation": x.presentation,
                        "group": x.group,
                        "priority": x.priority,
                    }
                    for x in self._view.resources
                ],
                "equipment": [
                    {
                        "slot_id": x.slot_id,
                        "label": x.label,
                        "capacity": x.capacity,
                        "items": [
                            {
                                "instance_id": i.instance_id,
                                "equipment_id": i.equipment_id,
                                "label": i.label,
                                "attachment_ids": list(i.attachment_ids),
                                "growth_id": i.growth_id,
                            }
                            for i in x.items
                        ],
                    }
                    for x in self._view.equipment
                ],
                "abilities": [
                    {
                        "ability_id": x.ability_id,
                        "label": x.label,
                        "active": x.active,
                        "source_labels": list(x.source_labels),
                    }
                    for x in self._view.abilities
                ],
                "progression": [
                    {
                        "track_id": x.track_id,
                        "label": x.label,
                        "total": x.total,
                        "rank": x.rank,
                    }
                    for x in self._view.progression
                ],
                "tags": list(self._view.tags),
                "capabilities": list(self._view.capabilities),
                "class_assignment_ids": list(self._view.class_assignment_ids),
                "active_passives": list(self._view.active_passives),
                "selected_section_id": self._view.selected_section_id,
                "revision": self._view.revision,
            }
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "revision": self.revision,
            "selected_section_id": self.selected_section_id,
            "view": view,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported character screen runtime snapshot")
        if CharacterScreenProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("character screen profile mismatch")
        self.revision = int(data["revision"])
        self.selected_section_id = str(data.get("selected_section_id", ""))
        raw = data.get("view")
        if raw is None:
            self._view = None
            return self
        self._restore_view(raw)
        self.selected_section_id = self._view.selected_section_id
        return self
