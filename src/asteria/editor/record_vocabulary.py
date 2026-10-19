"""What a record field can hold, read from the project: the records a field refers to (with names
and icons), the stats, resources and tags in use, and the values other records already give a
field. The record form turns these into drop-downs so an author picks instead of typing.

Nothing here is per-game: the vocabulary is read from whatever the project contains, and the
key conventions (``ability_id``, ``granted_tags``, ``stat_bonuses``...) are the engine's.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# -- what a field refers to -------------------------------------------------------------------
REFERENCES = {  # field name -> vocabulary source
    "ability_id": "abilities",
    "abilities": "abilities",
    "granted_abilities": "abilities",
    "ability_ids": "abilities",
    "unlocked_abilities": "abilities",
    "skill_id": "abilities",
    "follow_up": "abilities",
    "state": "states",
    "state_id": "states",
    "states": "states",
    "blocking_states": "states",
    "cures": "states",
    "immune_states": "states",
    "class_id": "classes",
    "classes": "classes",
    "unlock_classes": "classes",
    "class_ids": "classes",
    "actor_id": "actors",
    "actors": "actors",
    "actor_ids": "actors",
    "members": "actors",
    "item_id": "items_and_equipment",
    "items": "items",
    "item_ids": "items",
    "ingredients": "items",
    "equipment_id": "equipment",
    "equipment_ids": "equipment",
    "attachment_id": "attachments",
    "attachments": "attachments",
    "enemy_id": "enemies",
    "enemies": "enemies",
    "encounter_id": "encounters",
    "encounters": "encounters",
    "passive_id": "passives",
    "passives": "passives",
    "unlocked_passives": "passives",
    "graph_id": "graphs",
    "graph_ids": "graphs",
    "track_id": "tracks",
    "progression_track_ids": "tracks",
    "resource": "resources",
    "resource_id": "resources",
    "shield_resource_id": "resources",
    "boost_resource_id": "resources",
    "damage_resource": "resources",
    "knockout_resource_id": "resources",
    "check_id": "checks",
    "checks": "checks",
    "check_ids": "checks",
    "rarity": "rarities",
    "rarity_id": "rarities",
    "drop_table_id": "drop_tables",
    "growth_id": "growth",
    "scene_id": "scenes",
    "scene": "scenes",
    "target_scene": "scenes",
    "stat": "stats",
    "stat_id": "stats",
    "initiative_stat": "stats",
    "source_stat": "stats",
    "opponent_stat": "stats",
    "lifesteal_stat": "stats",
    "slot": "slots",
    "slot_id": "slots",
    "composition_id": "gauges",
    "rules_id": None,  # a record's own id
}
# a formula term's ``key`` reads a stat or a resource, picked by its ``source``
TERM_KEY_SOURCES = {
    "source_stat": "stats",
    "target_stat": "stats",
    "source_resource_current": "resources",
    "source_resource_max": "resources",
    "target_resource_current": "resources",
    "target_resource_max": "resources",
}

# -- dictionaries of numbers: what their keys are ---------------------------------------------
STAT_MAPS = (
    "stats",
    "base_stats",
    "stat_bonuses",
    "level_growth",
    "stat_growth",
    "growth",
    "terms",
    "source_stat_terms",
    "target_stat_terms",
    "multiplier_source_terms",
    "multiplier_target_terms",
)
RESOURCE_MAPS = (
    "resources",
    "resource_bonuses",
    "resource_growth",
    "resource_costs",
    "battle_costs",
    "costs",
    "starting",
)


def map_source(key):
    """The vocabulary the keys of a ``{name: number}`` field come from (stats / resources)."""
    key = str(key)
    if key in RESOURCE_MAPS or "resource" in key or key.endswith("_costs"):
        return "resources"
    if key in STAT_MAPS or "stat" in key:
        return "stats"
    if key in ("currencies", "currency_costs", "price", "prices"):
        return "currencies"
    if key in ("item_costs", "requires_items", "ingredients", "inputs", "outputs"):
        return "items"
    return None


def is_tag_field(key):
    key = str(key)
    return key == "tags" or key.endswith("_tags") or key.endswith("_tags_all") or (
        key.endswith("_tags_any")
    )


def is_chance_field(key):
    """0..1 shares shown as percentages."""
    key = str(key)
    return key in ("chance", "base_chance", "minimum_chance", "maximum_chance") or key.endswith(
        "_chance"
    )


# -- technical fields: filled in automatically, shown under Advanced --------------------------
TECHNICAL = {
    "effect_id",
    "modifier_id",
    "assignment_id",
    "impact_id",
    "threshold_id",
    "priority",
    "importer_version",
    "growth_mode",
    "growth_cap",
    "role",
    "required_tags",
    "blocked_tags",
}


# -- the names and help shown beside fields ---------------------------------------------------
LABELS = {
    "display_name": "Name",
    "class_assignments": "Jobs",
    "base_stats": "Base Stats",
    "base_resources": "Health, SP and other resources",
    "granted_tags": "Tags it gives",
    "granted_abilities": "Skills it gives",
    "stat_bonuses": "Stat bonuses",
    "resource_bonuses": "Resource bonuses",
    "level_growth": "Growth per level",
    "resource_growth": "Resource growth per level",
    "unlock_level": "Unlocks at level",
    "unlock_classes": "Needs these jobs first",
    "icon_id": "Icon",
    "apply_states": "States it applies",
    "hits": "Hits",
    "costs": "Costs",
    "battle_costs": "Battle costs",
    "cooldown_turns": "Cooldown (turns)",
    "maximum_targets": "Most targets",
    "minimum_targets": "Fewest targets",
    "allow_self": "Can target itself",
    "modifiers": "Stat changes",
    "sockets": "Sockets",
    "required_capabilities": "Needs (capabilities)",
    "any_capabilities": "Needs one of (capabilities)",
    "forbidden_capabilities": "Not with (capabilities)",
    "rarity": "Rarity",
    "stack_limit": "Most in one stack",
    "reward": "Reward",
    "drop_table_id": "Drop table",
    "multiplier": "Multiplier",
    "flat_delta": "Adds",
    "outcome_tags": "Tags on the result",
    "success_tags": "Tags when it succeeds",
    "failure_tags": "Tags when it fails",
    "source_tags_all": "Attacker needs all of",
    "source_tags_any": "Attacker needs one of",
    "target_tags_all": "Target needs all of",
    "target_tags_any": "Target needs one of",
    "blocked_source_tags": "Not when the attacker has",
    "blocked_target_tags": "Not when the target has",
    "required_source_tags": "Attacker needs",
    "required_target_tags": "Target needs",
    "base_chance": "Chance",
    "minimum_chance": "Never below",
    "maximum_chance": "Never above",
    "source_stat_terms": "Attacker stats add",
    "target_stat_terms": "Target stats add",
    "multiplier_source_terms": "Multiplier grows with attacker stats",
    "multiplier_target_terms": "Multiplier grows with target stats",
    "contributed_tags": "Tags while active",
    "duration": "Lasts (turns)",
    "periodic": "Every turn",
    "on_apply": "When applied",
    "on_remove": "When removed",
    "on_expire": "When it runs out",
    "max_stacks": "Most stacks",
    "terms": "Read from (stat: coefficient)",
    "coefficient": "Times",
    "key": "Stat / resource",
    "source": "Reads",
    "operations": "What it does",
    "operation": "How",
    "target": "Changes",
    "value": "Amount",
}
HELP = {
    "display_name": "What players see.",
    "icon_id": "The picture in menus and lists. Pick one, or Browse for your own file.",
    "class_assignments": "The jobs this character has; the first is the main job.",
    "base_stats": "Starting numbers before jobs, levels, gear and points.",
    "base_resources": "Health (vitality), SP (technique) and other pools at the start.",
    "tags": "Short labels other rules look for (weak.fire, boss, trait.guard...).",
    "abilities": "Skills this one starts with.",
    "granted_abilities": "Skills anyone with this gets.",
    "granted_tags": "Labels anyone with this gets (weapon kinds it may use...).",
    "stat_bonuses": "Added to the stats once.",
    "level_growth": "Added to the stat for every level above 1.",
    "resource_growth": "Added to the resource's maximum for every level above 1.",
    "resource_bonuses": "Added to the resource's maximum once.",
    "unlock_level": "The level a character needs before taking this job (0 = any).",
    "apply_states": "States the skill puts on its targets or its user.",
    "hits": "Each hit lands on its own: its damage types, power and chance checks.",
    "checks": "Chance checks rolled on this hit (crit, land, block...).",
    "power": "This hit's share of the skill's damage (1 = full).",
    "costs": "What using it spends.",
    "cooldown_turns": "Turns before it can be used again (0 = every turn).",
    "modifiers": "Stat changes while this is worn or active.",
    "sockets": "Holes for gems, cards and charms.",
    "rarity": "Its colour and rank name in the bag.",
    "multiplier": "Damage is multiplied by this (1 = unchanged, 2 = double).",
    "flat_delta": "Added to the damage before the multiplier.",
    "base_chance": "How often it happens before stats (100% = always).",
    "chance": "How often it happens (100% = always).",
    "duration": "How many turns it lasts.",
    "max_stacks": "How many times it can pile up.",
    "terms": "Each stat times its number is added up.",
    "contributed_tags": "Labels the holder has while this lasts.",
    "description": "Shown to players in menus.",
    "stack_limit": "How many fit in one bag slot.",
    "minimum": "The value never goes below this.",
    "maximum": "The value never goes above this (0 = no cap where noted).",
    "order": "Lower numbers run first.",
    "applies_to": "Who uses it: the party (actors), foes (enemies) or everyone.",
    "speed": "Acts sooner and more often.",
    "outcome_tags": "Labels this result carries (WEAK shows on screen for outcome.weak).",
}

CATEGORY_HELP = {
    "actors": "The heroes the player controls: their jobs, starting stats and skills.",
    "classes": "Jobs: what they give, how they grow, what they need.",
    "abilities": "Skills and attacks: targets, costs, hits and what they do.",
    "states": "Statuses and buffs: how long they last and what they change.",
    "passives": "Always-on effects learned from trees or gear.",
    "graphs": "Skill trees: nodes, costs and what each rank gives.",
    "items": "Things in the bag: potions, materials, keys.",
    "equipment": "Weapons, armour and accessories.",
    "attachments": "Gems, cards and charms that go into sockets.",
    "enemies": "Foes: stats, skills, weaknesses and rewards.",
    "encounters": "Which foes fight together, and where.",
    "interactions": "Damage rules: weaknesses, resistances, crits.",
    "outcome_checks": "Chance rolls: landing a hit, criticals, blocks.",
    "gauges": "Shields and gauges that break or fill during battle.",
}


# -- the vocabulary of one project ------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Choice:
    value: str
    label: str
    icon: str = ""  # a project path or forged:<kind>; empty = none


class ProjectVocabulary:
    """Read once per form build; cheap enough to rebuild after every edit."""

    def __init__(self, project):
        self.project = project
        self._cache = {}
        self._values = None

    # -- records --------------------------------------------------------------------------------
    def choices(self, source):
        if source not in self._cache:
            self._cache[source] = tuple(self._choices(source))
        return self._cache[source]

    def _choices(self, source):
        project = self.project
        if project is None:
            return ()
        db = project.rpg_database
        library = project.gameplay_library

        def records(mapping, name_key="display_name"):
            for key in sorted(mapping):
                value = mapping[key]
                label = getattr(value, name_key, "") or key
                yield Choice(str(key), str(label), str(getattr(value, "icon_id", "") or ""))

        if source == "abilities":
            ids = library.abilities.ids()
            for key in sorted(ids):
                value = library.abilities.get(key)
                label = getattr(value, "display_name", "") or key.replace("_", " ").title()
                yield Choice(key, label, getattr(value, "icon_id", "") or "")
        elif source == "states":
            for key in sorted(library.states._definitions):
                yield Choice(key, key.replace("_", " ").title())
        elif source == "items_and_equipment":
            yield from self.choices("items")
            yield from self.choices("equipment")
        elif source in ("classes", "actors", "items", "equipment", "attachments", "enemies",
                        "passives", "encounters"):  # fmt: skip
            yield from records(getattr(db, source))
        elif source == "graphs":
            yield from records(db.progression_graphs)
        elif source == "tracks":
            yield from records(db.progression_tracks)
        elif source == "resources":
            names = set(db.battle_resources)
            for actor in db.actors.values():
                names.update(actor.base_resources)
            for enemy in db.enemies.values():
                names.update(enemy.resources)
            for name in sorted(names):
                yield Choice(name, _resource_label(name))
        elif source == "stats":
            for name in sorted(self.stats()):
                yield Choice(name, _stat_label(name))
        elif source == "checks":
            for key in sorted(db.outcome_checks):
                yield Choice(key, key.replace("_", " ").title())
        elif source == "rarities":
            for rarity in sorted(db.loot_rarities().values(), key=lambda r: r.order):
                yield Choice(rarity.rarity_id, rarity.display_name or rarity.rarity_id)
        elif source == "drop_tables":
            for key in sorted(db.drop_tables):
                yield Choice(key, key.replace("_", " ").title())
        elif source == "growth":
            for key in sorted(db.equipment_growth):
                yield Choice(key, key.replace("_", " ").title())
        elif source == "gauges":
            for key in sorted(db.gauge_compositions):
                yield Choice(key, key.replace("_", " ").title())
        elif source == "scenes":
            for scene in project.scenes():
                yield Choice(scene.id, getattr(scene, "name", "") or scene.id)
        elif source == "slots":
            slots = {e.slot for e in db.equipment.values()}
            for name in sorted(slots):
                yield Choice(name, name.replace("_", " ").title())
        elif source == "currencies":
            names = set(getattr(project.game_start, "currencies", {}) or {}) | {"gold"}
            for name in sorted(names):
                yield Choice(name, name.title())

    def stats(self):
        if "__stats" in self._cache:
            return self._cache["__stats"]
        project, names = self.project, set()
        if project is not None:
            db = project.rpg_database
            for actor in db.actors.values():
                names.update(actor.base_stats)
            for enemy in db.enemies.values():
                names.update(enemy.stats)
            for job in db.classes.values():
                names.update(job.stat_bonuses)
                names.update(job.level_growth)
            names.update(getattr(db, "derived_stats", {}))
            for record in (*db.equipment.values(), *db.attachments.values()):
                names.update(m.stat for m in record.modifiers)
        names.discard("")
        self._cache["__stats"] = names
        return names

    # -- values already used --------------------------------------------------------------------
    def values_for(self, key):
        """Distinct string values other records give ``key`` (a drop-down of what is used)."""
        if self._values is None:
            self._values = {}
            if self.project is not None:
                _collect(self.project.rpg_database.to_data(), self._values)
                _collect(self.project.gameplay_library.to_data(), self._values)
        return tuple(sorted(self._values.get(str(key), ())))

    def tags(self):
        """Every tag the project uses anywhere (suggestions for tag fields)."""
        if "__tags" not in self._cache:
            values = set()
            if self.values_for("tags") is not None:
                for key, found in self._values.items():
                    if is_tag_field(key):
                        values.update(found)
            if self.project is not None:
                for value in self.project.gameplay_library.abilities.ids():
                    definition = self.project.gameplay_library.abilities.get(value)
                    values.update(getattr(definition, "tags", ()))
            self._cache["__tags"] = tuple(sorted(v for v in values if v))
        return self._cache["__tags"]


def _collect(data, out, key=None):
    if isinstance(data, dict):
        for k, v in data.items():
            _collect(v, out, k)
    elif isinstance(data, list):
        for v in data:
            _collect(v, out, key)
    elif isinstance(data, str) and key is not None and len(data) <= 64:
        out.setdefault(str(key), set()).add(data)


_STAT_NAMES = {
    "str": "STR", "dex": "DEX", "int": "INT", "luk": "LUK", "power": "Physical Attack",
    "magic": "Magic Attack", "defense": "Physical Defence", "magic_defense": "Magic Defence",
    "accuracy": "Accuracy", "evade": "Evasion", "crit": "Critical Rate",
    "crit_damage": "Critical Damage %", "speed": "Speed", "lifesteal": "Lifesteal",
}  # fmt: skip
_RESOURCE_NAMES = {"vitality": "HP (vitality)", "technique": "SP (technique)"}


def _stat_label(name):
    if name in _STAT_NAMES:
        return _STAT_NAMES[name]
    if name.endswith("_attack") or name.endswith("_resist"):
        element, kind = name.rsplit("_", 1)
        return f"{element.title()} {kind.title()} %"
    return name.replace("_", " ").title()


def _resource_label(name):
    return _RESOURCE_NAMES.get(name, name.replace("_", " ").title())


def label_for(key):
    """The name a field shows: ours, else its key in words without a trailing "ID" for a
    reference (``growth_id`` -> "Growth", it is a drop-down of names)."""
    from .authoring_hub_widget import field_label

    key = str(key)
    if key in LABELS:
        return LABELS[key]
    if key.endswith("_id") and REFERENCES.get(key):
        return field_label(key[:-3])
    return field_label(key)


# -- fields with a fixed set of values, read from the engine ----------------------------------
_ENGINE_ENUMS = None


def engine_enums():
    """``{field: (values...)}`` for every record field the engine checks against a fixed set:
    ``if field not in SOME_VALUES`` or ``object.__setattr__(self, "field", SomeEnum(field))``
    in the rpg / gameplay / presentation modules. A field several records share gets every
    value any of them allows (the record's own check still decides)."""
    global _ENGINE_ENUMS
    if _ENGINE_ENUMS is not None:
        return _ENGINE_ENUMS
    import enum
    import importlib
    import pkgutil
    import re


    found = {}  # field -> {frozenset of allowed values, ...}
    tuple_check = re.compile(r"if\s+(\w+)\s+not\s+in\s+([A-Z][A-Z0-9_]+)\s*:")
    enum_set = re.compile(r'__setattr__\(\s*self,\s*"(\w+)",\s*([A-Z]\w+)\(\s*\1\s*\)')
    enum_local = re.compile(r"\b(\w+)\s*=\s*([A-Z]\w+)\(\s*\1\s*\)")
    enum_data = re.compile(r'([A-Z]\w+)\(\s*data(?:\.get\(|\[)\s*"(\w+)"')
    for package in ("rpg", "gameplay", "presentation"):
        base = importlib.import_module(f"asteria.{package}")
        for info in pkgutil.iter_modules(base.__path__):
            name = f"asteria.{package}.{info.name}"
            try:
                module = importlib.import_module(name)
                source = Path(module.__file__).read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001 - a module that cannot load offers nothing
                continue
            for field, constant in tuple_check.findall(source):
                values = getattr(module, constant, None)
                if isinstance(values, (tuple, frozenset, set, list)) and all(
                    isinstance(v, str) for v in values
                ):
                    found.setdefault(field, set()).add(frozenset(v for v in values if v))
            pairs = enum_set.findall(source) + enum_local.findall(source)
            pairs += [(field, kind) for kind, field in enum_data.findall(source)]
            for field, enum_name in pairs:
                kind = getattr(module, enum_name, None)
                if isinstance(kind, type) and issubclass(kind, enum.Enum):
                    found.setdefault(field, set()).add(frozenset(str(m.value) for m in kind))
    # a name whose records disagree (``kind``, ``mode``...) is left to the values in use
    _ENGINE_ENUMS = {
        field: tuple(sorted(next(iter(sets))))
        for field, sets in found.items()
        if len(sets) == 1 and next(iter(sets))
    }
    return _ENGINE_ENUMS
