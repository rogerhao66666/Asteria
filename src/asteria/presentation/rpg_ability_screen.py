from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay.abilities import AbilityDefinition
from asteria.rpg.ability_build import ActorAbilityState, PassiveDefinition
from asteria.rpg.resolved_build import ResolvedActorBuild


@dataclass(frozen=True, slots=True)
class AbilityCollectionEntry:
    ability_id: str
    label: str
    category: str
    tags: tuple[str, ...]
    source_labels: tuple[str, ...]
    learned: bool
    resolved: bool
    selected: bool


@dataclass(frozen=True, slots=True)
class PassiveCollectionEntry:
    passive_id: str
    label: str
    category: str
    tags: tuple[str, ...]
    active: bool
    selected: bool
    granted_abilities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AbilityCollectionGroup:
    category_id: str
    label: str
    entry_ids: tuple[str, ...]
    visible_entry_ids: tuple[str, ...]
    overflow_count: int


@dataclass(frozen=True, slots=True)
class AbilityScreenView:
    abilities: tuple[AbilityCollectionEntry, ...]
    passives: tuple[PassiveCollectionEntry, ...]
    ability_groups: tuple[AbilityCollectionGroup, ...]
    passive_groups: tuple[AbilityCollectionGroup, ...]
    active_passive_ids: tuple[str, ...]
    passive_capacity: int | None
    passive_capacity_used: int
    active_tab: str
    active_category: str | None
    query: str
    selected_entry_id: str | None
    revision: int


@dataclass(frozen=True, slots=True)
class AbilityScreenProfile:
    ability_labels: tuple[tuple[str, str], ...] = ()
    passive_labels: tuple[tuple[str, str], ...] = ()
    ability_categories: tuple[tuple[str, str], ...] = ()
    passive_categories: tuple[tuple[str, str], ...] = ()
    category_labels: tuple[tuple[str, str], ...] = ()
    visible_limits: tuple[tuple[str, int], ...] = ()
    default_ability_category: str = "abilities"
    default_passive_category: str = "passives"

    SCHEMA = "asteria.ability_screen_profile"
    VERSION = 1

    def __init__(self, *, ability_labels=None, passive_labels=None,
                 ability_categories=None, passive_categories=None,
                 category_labels=None, visible_limits=None,
                 default_ability_category="abilities",
                 default_passive_category="passives"):
        for name, values in (
            ("ability_labels", ability_labels),
            ("passive_labels", passive_labels),
            ("ability_categories", ability_categories),
            ("passive_categories", passive_categories),
            ("category_labels", category_labels),
        ):
            object.__setattr__(
                self, name,
                tuple(sorted((str(k), str(v)) for k, v in dict(values or {}).items()))
            )
        limits = []
        for key, value in dict(visible_limits or {}).items():
            value = int(value)
            if value < 1:
                raise ValueError("visible limit must be >= 1")
            limits.append((str(key), value))
        object.__setattr__(self, "visible_limits", tuple(sorted(limits)))
        object.__setattr__(self, "default_ability_category", str(default_ability_category))
        object.__setattr__(self, "default_passive_category", str(default_passive_category))

    def ability_label(self, key):
        key = str(key)
        return dict(self.ability_labels).get(key, key)

    def passive_label(self, key):
        key = str(key)
        return dict(self.passive_labels).get(key, key)

    def ability_category(self, key):
        return dict(self.ability_categories).get(str(key), self.default_ability_category)

    def passive_category(self, key):
        return dict(self.passive_categories).get(str(key), self.default_passive_category)

    def category_label(self, key):
        key = str(key)
        return dict(self.category_labels).get(key, key)

    def visible_limit(self, category_id):
        return dict(self.visible_limits).get(str(category_id))

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "ability_labels": dict(self.ability_labels),
            "passive_labels": dict(self.passive_labels),
            "ability_categories": dict(self.ability_categories),
            "passive_categories": dict(self.passive_categories),
            "category_labels": dict(self.category_labels),
            "visible_limits": dict(self.visible_limits),
            "default_ability_category": self.default_ability_category,
            "default_passive_category": self.default_passive_category,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported ability screen profile")
        return cls(
            ability_labels=data.get("ability_labels", {}),
            passive_labels=data.get("passive_labels", {}),
            ability_categories=data.get("ability_categories", {}),
            passive_categories=data.get("passive_categories", {}),
            category_labels=data.get("category_labels", {}),
            visible_limits=data.get("visible_limits", {}),
            default_ability_category=data.get("default_ability_category", "abilities"),
            default_passive_category=data.get("default_passive_category", "passives"),
        )


class AbilityScreenRuntime:
    """Read-only presentation over canonical ability/passive state."""

    SCHEMA = "asteria.ability_screen_runtime"
    VERSION = 1

    def __init__(self, profile=None):
        self.profile = profile or AbilityScreenProfile()
        if not isinstance(self.profile, AbilityScreenProfile):
            raise TypeError("profile must be AbilityScreenProfile")
        self.active_tab = "abilities"
        self.active_category = None
        self.query = ""
        self.selected_entry_id = None
        self.revision = 0
        self._view = None

    @property
    def view(self):
        return self._view

    def _groups(self, entries, passive=False):
        category_ids = []
        for entry in entries:
            if entry.category not in category_ids:
                category_ids.append(entry.category)
        result = []
        for category_id in category_ids:
            ids = tuple(
                (x.passive_id if passive else x.ability_id)
                for x in entries if x.category == category_id
            )
            limit = self.profile.visible_limit(category_id)
            visible = ids if limit is None else ids[:limit]
            result.append(AbilityCollectionGroup(
                category_id=category_id,
                label=self.profile.category_label(category_id),
                entry_ids=ids,
                visible_entry_ids=tuple(visible),
                overflow_count=max(0, len(ids) - len(visible)),
            ))
        return tuple(result)

    def project(self, resolved_build, *, ability_state=None,
                ability_catalog=(), passive_catalog=(), passive_capacity=None):
        if not isinstance(resolved_build, ResolvedActorBuild):
            raise TypeError("resolved_build must be ResolvedActorBuild")
        if ability_state is not None and not isinstance(ability_state, ActorAbilityState):
            raise TypeError("ability_state must be ActorAbilityState")
        if passive_capacity is not None:
            passive_capacity = int(passive_capacity)
            if passive_capacity < 0:
                raise ValueError("passive_capacity must be >= 0 or None")

        learned = set(() if ability_state is None else ability_state.learned_abilities)
        active_passives = tuple(resolved_build.active_passives)
        grants = {}
        for grant in resolved_build.ability_grants:
            grants.setdefault(grant.ability_id, []).append(
                f"{grant.source_kind}:{grant.source_id}"
            )

        definitions = {}
        for definition in ability_catalog:
            if not isinstance(definition, AbilityDefinition):
                raise TypeError("ability_catalog must contain AbilityDefinition values")
            definitions[definition.ability_id] = definition

        query = self.query.casefold().strip()
        ids = tuple(dict.fromkeys(tuple(resolved_build.abilities) + tuple(definitions)))
        abilities = []
        for ability_id in ids:
            definition = definitions.get(ability_id)
            tags = () if definition is None else tuple(definition.tags)
            label = self.profile.ability_label(ability_id)
            category = self.profile.ability_category(ability_id)
            haystack = " ".join(
                (ability_id, label, category, *tags, *grants.get(ability_id, ()))
            ).casefold()
            if query and query not in haystack:
                continue
            abilities.append(AbilityCollectionEntry(
                ability_id=ability_id,
                label=label,
                category=category,
                tags=tags,
                source_labels=tuple(grants.get(ability_id, ())),
                learned=ability_id in learned,
                resolved=ability_id in resolved_build.abilities,
                selected=ability_id == self.selected_entry_id,
            ))

        passives = []
        for definition in passive_catalog:
            if not isinstance(definition, PassiveDefinition):
                raise TypeError("passive_catalog must contain PassiveDefinition values")
            passive_id = definition.passive_id
            label = self.profile.passive_label(passive_id)
            category = self.profile.passive_category(passive_id)
            haystack = " ".join((passive_id, label, category, *definition.tags)).casefold()
            if query and query not in haystack:
                continue
            passives.append(PassiveCollectionEntry(
                passive_id=passive_id,
                label=label,
                category=category,
                tags=tuple(definition.tags),
                active=passive_id in active_passives,
                selected=passive_id == self.selected_entry_id,
                granted_abilities=tuple(definition.granted_abilities),
            ))

        abilities = tuple(sorted(abilities, key=lambda x: (x.category, x.label.casefold(), x.ability_id)))
        passives = tuple(sorted(passives, key=lambda x: (x.category, x.label.casefold(), x.passive_id)))
        ability_groups = self._groups(abilities)
        passive_groups = self._groups(passives, passive=True)

        current = abilities if self.active_tab == "abilities" else passives
        valid_ids = {
            (x.ability_id if self.active_tab == "abilities" else x.passive_id)
            for x in current
        }
        if self.selected_entry_id not in valid_ids:
            self.selected_entry_id = None if not current else (
                current[0].ability_id if self.active_tab == "abilities"
                else current[0].passive_id
            )

        groups = ability_groups if self.active_tab == "abilities" else passive_groups
        category_ids = {x.category_id for x in groups}
        if self.active_category not in category_ids:
            self.active_category = groups[0].category_id if groups else None

        self.revision += 1
        self._view = AbilityScreenView(
            abilities=abilities,
            passives=passives,
            ability_groups=ability_groups,
            passive_groups=passive_groups,
            active_passive_ids=active_passives,
            passive_capacity=passive_capacity,
            passive_capacity_used=len(active_passives),
            active_tab=self.active_tab,
            active_category=self.active_category,
            query=self.query,
            selected_entry_id=self.selected_entry_id,
            revision=self.revision,
        )
        return self._view

    def set_tab(self, tab):
        tab = str(tab)
        if tab not in {"abilities", "passives"}:
            raise ValueError("tab must be abilities or passives")
        self.active_tab = tab
        self.active_category = None
        self.selected_entry_id = None
        return tab

    def set_category(self, category_id):
        if self._view is None:
            raise RuntimeError("ability screen has not been projected")
        groups = self._view.ability_groups if self.active_tab == "abilities" else self._view.passive_groups
        category_id = str(category_id)
        if category_id not in {x.category_id for x in groups}:
            raise KeyError(f"unknown ability screen category: {category_id}")
        self.active_category = category_id
        return category_id

    def set_query(self, query):
        self.query = str(query)
        return self.query

    def select(self, entry_id):
        if self._view is None:
            raise RuntimeError("ability screen has not been projected")
        entry_id = str(entry_id)
        known = {x.ability_id for x in self._view.abilities} | {x.passive_id for x in self._view.passives}
        if entry_id not in known:
            raise KeyError(f"unknown ability/passive entry: {entry_id}")
        self.selected_entry_id = entry_id
        return entry_id

    def snapshot(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "profile": self.profile.to_data(),
            "active_tab": self.active_tab,
            "active_category": self.active_category,
            "query": self.query,
            "selected_entry_id": self.selected_entry_id,
            "revision": self.revision,
        }

    def restore(self, data):
        if data.get("schema") != self.SCHEMA or data.get("version") != self.VERSION:
            raise ValueError("unsupported ability screen snapshot")
        if AbilityScreenProfile.from_data(data["profile"]) != self.profile:
            raise ValueError("ability screen profile mismatch")
        self.active_tab = str(data.get("active_tab", "abilities"))
        self.active_category = data.get("active_category")
        self.query = str(data.get("query", ""))
        self.selected_entry_id = data.get("selected_entry_id")
        self.revision = int(data["revision"])
        self._view = None
        return self
