"""Authoring API for shops, quests, factions, achievements, equipment sets and capture rules
(CB10h).

The Python API (:class:`GameSystemsAuthoringController`) and the Qt editor
(:mod:`asteria.editor.game_systems_widget`) share these canonical
definitions: every change is a canonical ``*Definition`` validated against the
whole RPG database and applied through the document's undoable command
stack. :data:`FORMS` describes each kind's fields for form-based editors; it
has no Qt dependency.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from asteria.rpg import (
    AchievementDefinition,
    CaptureRule,
    EquipmentSetDefinition,
    PetSpeciesDefinition,
    FactionDefinition,
    QuestDefinition,
    QuestObjective,
    ShopDefinition,
)
from asteria.rpg.drop_tables import RARITIES, DropTable
from asteria.rpg.items import INVENTORY_OVERFLOW, InventoryRules
from asteria.rpg.quests import OBJECTIVE_KINDS
from asteria.rpg.world_interactions import OPERATORS, VERBS, WorldInteraction
from asteria.rpg.world_record import ACHIEVEMENT_KINDS


class GameSystemsAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _MapCommand:
    mapping: dict
    key: str
    new_value: object | None
    old_value: object | None
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        if self.new_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.new_value

    def undo(self):
        if self.old_value is None:
            self.mapping.pop(self.key, None)
        else:
            self.mapping[self.key] = self.old_value


# --- form description (Qt-free) ------------------------------------------------


@dataclass(frozen=True, slots=True)
class FormField:
    """One editable field of a record.

    kinds: ``id``, ``text``, ``multiline``, ``int``, ``float``, ``bool``,
    ``choice`` (``choices``), ``ref`` / ``ref_list`` (``source`` names a
    reference list, see :meth:`GameSystemsAuthoringController.references`),
    ``optional_ref`` (may be empty), ``optional_int`` (None allowed),
    ``string_list``, ``amounts`` (``{key: number}``, keys from ``source`` when
    given), ``group`` (nested ``fields``), ``table`` (list of nested
    ``fields`` records), ``pairs`` (list of ``[number, text]``).
    """

    key: str
    label: str
    kind: str
    source: str = ""
    choices: tuple = ()
    fields: tuple = ()
    default: object = None


def F(key, label, kind, **values):  # noqa: N802 - short spec constructor
    return FormField(key, label, kind, **values)


_MODIFIER = (
    F("modifier_id", "Modifier ID", "text", default="bonus"),
    F("stat", "Stat", "text", default="power"),
    F("operation", "Operation", "choice", choices=("add", "multiply", "override"), default="add"),
    F("value", "Value", "float", default=0.0),
    F("priority", "Priority", "int", default=0),
    F("required_tags", "Required Tags", "string_list", default=()),
    F("blocked_tags", "Blocked Tags", "string_list", default=()),
)
_LOOT = (
    F("item_id", "Item", "ref", source="items"),
    F("chance", "Chance (0–1)", "float", default=1.0),
    F("minimum", "Minimum", "int", default=1),
    F("maximum", "Maximum", "int", default=1),
    F("required_switch", "Required Switch", "text", default=""),
    F("luck_bonus", "Luck Bonus", "float", default=0.0),
)
_REWARD = (
    F("currencies", "Currencies", "amounts", default={}),
    F("experience", "Experience", "amounts", source="progression_tracks", default={}),
    F("loot", "Loot", "table", fields=_LOOT, default=()),
)

_REQUIREMENT = (
    F("source", "Source", "choice", choices=("switch", "variable"), default="switch"),
    F("name", "Name", "text", default=""),
    F("operator", "Operator", "choice", choices=OPERATORS, default="=="),
    F("value", "Value", "text", default="true"),
)

_DROP = (
    F("item_id", "Item", "ref", source="items"),
    F("weight", "Weight", "float", default=1.0),
    F("minimum", "Minimum", "int", default=1),
    F("maximum", "Maximum", "int", default=1),
    F("rarity", "Rarity", "choice", choices=RARITIES, default="common"),
    F("required_switch", "Required Switch", "text", default=""),
)

FORMS = {
    "pet_species": (
        F("species_id", "Species ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("icon_id", "Icon", "text", default=""),
        F("stats", "Stats At Level 1 (read in formulas as pet_<stat>)", "amounts", default={}),
        F("growth", "Stat Growth Per Level", "amounts", default={}),
        F("max_level", "Highest Level", "int", default=50),
        F("exp_base", "Experience To Level Up = this x level", "float", default=40.0),
        F(
            "exp_per_battle",
            "Experience After A Won Battle It Was Sent Out In",
            "float",
            default=30.0,
        ),
        F("tags", "Tags", "string_list", default=()),
    ),
    "inventory_rules": (
        F("rules_id", "Rules ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("stack_limits", "Items Stack Up to Their Stack Limit", "bool", default=True),
        F(
            "max_kinds",
            "Most Different Items Carried (empty = no limit)",
            "optional_int",
            default=None,
        ),
        F(
            "exempt_tags",
            "Tags That Never Take a Place (key items)",
            "string_list",
            default=("item.key",),
        ),
        F(
            "overflow",
            "When Items Do Not Fit",
            "choice",
            choices=INVENTORY_OVERFLOW,
            default="fill",
        ),
    ),
    "drop_tables": (
        F("table_id", "Table ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("rolls", "Weighted Picks per Kill", "int", default=1),
        F("nothing_weight", "Weight of No Drop", "float", default=0.0),
        F("entries", "Weighted Entries", "table", fields=_DROP, default=()),
        F("guaranteed", "Always Drops", "table", fields=_DROP, default=()),
        F(
            "pity",
            "Pity (guarantee after misses)",
            "table",
            fields=(
                F("item_id", "Item", "ref", source="items"),
                F("after_misses", "After Misses", "int", default=10),
            ),
            default=(),
        ),
        F("luck_weight_bonus", "Luck Bonus to Rare Weights", "float", default=0.0),
    ),
    "world_interactions": (
        F("interaction_id", "Interaction ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("verb", "Verb", "choice", choices=VERBS, default="talk"),
        F("target_type", "Target Type", "text", default=""),
        F("actor_tag", "Needs Party Member Tag", "text", default=""),
        F("required_item", "Needs Item", "optional_ref", source="items", default=""),
        F("requirements", "Requirements", "table", fields=_REQUIREMENT, default=()),
        F("cost_items", "Cost: Items", "amounts", source="items", default={}),
        F("cost_currencies", "Cost: Currencies", "amounts", default={}),
        F("check_stat", "Check Stat (empty = always succeeds)", "text", default=""),
        F("difficulty", "Difficulty", "float", default=0.0),
        F("base_chance", "Base Chance (0–1)", "float", default=0.5),
        F("chance_per_point", "Chance per Stat Point", "float", default=0.05),
        F("success_items", "Success: Items", "amounts", source="items", default={}),
        F("success_currencies", "Success: Currencies", "amounts", default={}),
        F("success_switch", "Success: Set Switch", "text", default=""),
        F(
            "success_event",
            "Success: Follow-up Event",
            "optional_ref",
            source="event_programs",
            default="",
        ),
        F("failure_switch", "Failure: Set Switch", "text", default=""),
        F(
            "failure_event",
            "Failure: Follow-up Event",
            "optional_ref",
            source="event_programs",
            default="",
        ),
        F("reputation", "Consequence: Reputation", "amounts", source="factions", default={}),
        F("repeatable", "Repeatable", "bool", default=True),
    ),
    "shops": (
        F("shop_id", "Shop ID", "id"),
        F("display_name", "Name", "text"),
        F(
            "entries",
            "Stock",
            "table",
            default=(),
            fields=(
                F("item_id", "Item", "ref", source="items"),
                F("buy_prices", "Buy Price", "amounts", default={}),
                F("sell_prices", "Sell Price", "amounts", default={}),
                F("stock", "Limited Stock", "optional_int", default=None),
            ),
        ),
    ),
    "quests": (
        F("quest_id", "Quest ID", "id"),
        F("display_name", "Name", "text"),
        F("description", "Description", "multiline", default=""),
        F(
            "objectives",
            "Objectives",
            "table",
            default=(),
            fields=(
                F("objective_id", "Objective ID", "text", default="objective"),
                F("kind", "Kind", "choice", choices=OBJECTIVE_KINDS, default="counter"),
                F("target", "Target (item / enemy / switch)", "text", default=""),
                F("required", "Required", "int", default=1),
                F("description", "Description", "text", default=""),
            ),
        ),
        F("prerequisites", "Prerequisite Quests", "ref_list", source="quests", default=()),
        F("next_quest_ids", "Next Quests (chain)", "ref_list", source="quests", default=()),
        F("auto_complete", "Complete Automatically", "bool", default=True),
        F("reward", "Reward", "group", fields=_REWARD),
    ),
    "factions": (
        F("faction_id", "Faction ID", "id"),
        F("display_name", "Name", "text"),
        F("minimum", "Minimum", "float", default=-100.0),
        F("maximum", "Maximum", "float", default=100.0),
        F("initial", "Initial", "float", default=0.0),
        F("ranks", "Ranks (threshold → name)", "pairs", default=()),
    ),
    "achievements": (
        F("achievement_id", "Achievement ID", "id"),
        F("display_name", "Name", "text"),
        F("description", "Description", "multiline", default=""),
        F("kind", "Condition", "choice", choices=ACHIEVEMENT_KINDS, default="switch"),
        F("target", "Target", "text"),
        F("value", "Value", "float", default=1.0),
        F("hidden", "Hidden Until Unlocked", "bool", default=False),
    ),
    "equipment_sets": (
        F("set_id", "Set ID", "id"),
        F("display_name", "Name", "text"),
        F("equipment_ids", "Equipment", "ref_list", source="equipment", default=()),
        F(
            "bonuses",
            "Bonuses",
            "table",
            default=(),
            fields=(
                F("pieces", "Pieces Equipped", "int", default=2),
                F("modifiers", "Stat Modifiers", "table", fields=_MODIFIER, default=()),
                F("tags", "Granted Tags", "string_list", default=()),
                F(
                    "granted_abilities",
                    "Granted Abilities",
                    "ref_list",
                    source="abilities",
                    default=(),
                ),
            ),
        ),
    ),
    "capture_rules": (
        F("enemy_id", "Enemy", "id", source="enemies"),
        F("actor_id", "Joins As Actor", "optional_ref", source="actors", default=""),
        F("pet_item_id", "Becomes Pet Item", "optional_ref", source="items", default=""),
        F(
            "pet_species_id",
            "Becomes Owned Pet (species)",
            "optional_ref",
            source="pet_species",
            default="",
        ),
        F("pet_level", "Pet Starts At Level", "int", default=1),
        F("base_chance", "Base Chance (0–1)", "float", default=0.25),
        F("low_health_bonus", "Low-Health Bonus", "float", default=0.5),
        F("item_id", "Consumed Item", "optional_ref", source="items", default=""),
    ),
}


@dataclass(frozen=True, slots=True)
class _Kind:
    kind_id: str
    label: str
    store: str
    key: str
    cls: type
    template: object = field(default=None)


def _templates():
    return {
        "shops": lambda key, c: ShopDefinition(key, key),
        "quests": lambda key, c: QuestDefinition(
            key, key, objectives=[QuestObjective("objective")]
        ),
        "factions": lambda key, c: FactionDefinition(key, key),
        "achievements": lambda key, c: AchievementDefinition(key, key, target="switch.name"),
        "equipment_sets": lambda key, c: EquipmentSetDefinition(key, key),
        "capture_rules": lambda key, c: CaptureRule(
            key, next(iter(sorted(c.database.actors)), "actor")
        ),
        "pet_species": lambda key, c: PetSpeciesDefinition(
            key, key, stats={"power": 10}, growth={"power": 2}
        ),
        "world_interactions": lambda key, c: WorldInteraction(key, key),
        "drop_tables": lambda key, c: DropTable(key, key),
        "inventory_rules": lambda key, c: InventoryRules(key, key),
    }


KINDS = (
    _Kind("shops", "Shops", "shops", "shop_id", ShopDefinition),
    _Kind("quests", "Quests", "quests", "quest_id", QuestDefinition),
    _Kind("factions", "Factions", "factions", "faction_id", FactionDefinition),
    _Kind("achievements", "Achievements", "achievements", "achievement_id", AchievementDefinition),
    _Kind("equipment_sets", "Equipment Sets", "equipment_sets", "set_id", EquipmentSetDefinition),
    _Kind("capture_rules", "Capture Rules", "capture_rules", "enemy_id", CaptureRule),
    _Kind("pet_species", "Pet Species", "pet_species", "species_id", PetSpeciesDefinition),
    _Kind(
        "world_interactions",
        "World Interactions",
        "world_interactions",
        "interaction_id",
        WorldInteraction,
    ),
    _Kind("drop_tables", "Drop Tables", "drop_tables", "table_id", DropTable),
    _Kind("inventory_rules", "Inventory Rules", "inventory_rules", "rules_id", InventoryRules),
)
_BY_ID = {k.kind_id: k for k in KINDS}


# Fields whose canonical data omits defaults (LootEntry) — fill them for forms.
def _with_defaults(spec, data):
    data = copy.deepcopy(data)
    for f in spec:
        if f.kind in ("group",):
            data[f.key] = _with_defaults(f.fields, data.get(f.key, {}))
        elif f.kind == "table":
            data[f.key] = [_with_defaults(f.fields, row) for row in data.get(f.key, [])]
        elif f.key not in data:
            data[f.key] = copy.deepcopy(
                list(f.default) if isinstance(f.default, tuple) else f.default
            )
    return data


def new_row(fields):
    """Default record for a ``table`` row with these fields."""
    row = {}
    for f in fields:
        if f.kind == "group":
            row[f.key] = new_row(f.fields)
        elif f.kind in ("table", "ref_list", "string_list", "pairs"):
            row[f.key] = []
        elif f.kind == "amounts":
            row[f.key] = {}
        else:
            row[f.key] = (
                copy.deepcopy(f.default)
                if f.default is not None
                else ("" if f.kind != "optional_int" else None)
            )
    return row


class GameSystemsAuthoringController:
    """Undoable create / edit / duplicate / delete for the CB11 game-system definitions."""

    kinds = KINDS
    forms = FORMS

    def __init__(self, document):
        self.document = document

    @property
    def project(self):
        if self.document.project is None:
            raise GameSystemsAuthoringError("project required")
        return self.document.project

    @property
    def database(self):
        return self.project.rpg_database

    def kind(self, kind_id):
        try:
            return _BY_ID[str(kind_id)]
        except KeyError:
            raise GameSystemsAuthoringError(f"unknown kind: {kind_id}") from None

    def store(self, kind_id):
        return getattr(self.database, self.kind(kind_id).store)

    def ids(self, kind_id):
        return tuple(sorted(self.store(kind_id)))

    def get(self, kind_id, key):
        value = self.store(kind_id).get(str(key))
        if value is None:
            raise GameSystemsAuthoringError(f"unknown {kind_id}: {key}")
        return value

    def form_data(self, kind_id, key):
        """Canonical data of a record with every form field present."""
        return _with_defaults(FORMS[kind_id], self.get(kind_id, key).to_data())

    def decode(self, kind_id, data):
        try:
            return self.kind(kind_id).cls.from_data(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise GameSystemsAuthoringError(f"invalid {kind_id} record: {exc}") from exc

    def references(self, source):
        """Choices for ``ref`` / ``ref_list`` form fields."""
        db = self.database
        if source == "abilities":
            return tuple(sorted(self.project.gameplay_library.abilities.ids()))
        if source == "event_programs":
            return tuple(sorted(self.project.event_programs.ids()))
        stores = {
            "items": db.items,
            "enemies": db.enemies,
            "actors": db.actors,
            "equipment": db.equipment,
            "quests": db.quests,
            "factions": db.factions,
            "progression_tracks": db.progression_tracks,
            "pet_species": db.pet_species,
        }
        return tuple(sorted(stores.get(source, {})))

    def where_used(self, kind_id, key):
        """Other records that refer to ``key`` (deleting it would break them)."""
        key = str(key)
        db = self.database
        users = []
        if kind_id == "quests":
            users += [
                f"quest {q.quest_id}"
                for q in db.quests.values()
                if q.quest_id != key and key in q.prerequisites + q.next_quest_ids
            ]
            users += [
                f"achievement {a.achievement_id}"
                for a in db.achievements.values()
                if a.kind == "quest" and a.target == key
            ]
        if kind_id == "factions":
            users += [
                f"achievement {a.achievement_id}"
                for a in db.achievements.values()
                if a.kind == "reputation" and a.target == key
            ]
        return tuple(users)

    def _coerce(self, kind_id, value):
        cls = self.kind(kind_id).cls
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return self.decode(kind_id, value)
        raise TypeError(f"value must be {cls.__name__} or data")

    def _validated(self, kind_id, key, value):
        """Check the whole database with ``value`` in place, then restore it."""
        store = self.store(kind_id)
        missing = object()
        old = store.get(key, missing)
        store[key] = value
        try:
            self.database.validate()
        except ValueError as exc:
            raise GameSystemsAuthoringError(str(exc)) from exc
        finally:
            if old is missing:
                store.pop(key, None)
            else:
                store[key] = old

    def create(self, kind_id, value):
        kind = self.kind(kind_id)
        value = self._coerce(kind_id, value)
        key = getattr(value, kind.key)
        if key in self.store(kind_id):
            raise GameSystemsAuthoringError(f"duplicate {kind_id}: {key}")
        self._validated(kind_id, key, value)
        self.document.execute(
            _MapCommand(self.store(kind_id), key, value, None, f"Add {kind.label[:-1]} {key}")
        )
        return value

    def create_new(self, kind_id, key):
        """Create a minimal valid record with id ``key`` (the editor's New button)."""
        return self.create(kind_id, _templates()[kind_id](str(key).strip(), self))

    def edit(self, kind_id, key, value):
        kind = self.kind(kind_id)
        key = str(key)
        old = self.get(kind_id, key)
        value = self._coerce(kind_id, value)
        if getattr(value, kind.key) != key:
            raise GameSystemsAuthoringError(f"{kind.key} cannot change during edit")
        self._validated(kind_id, key, value)
        self.document.execute(
            _MapCommand(self.store(kind_id), key, value, old, f"Edit {kind.label[:-1]} {key}")
        )
        return value

    def duplicate(self, kind_id, key, new_key):
        data = self.get(kind_id, key).to_data()
        data[self.kind(kind_id).key] = str(new_key)
        return self.create(kind_id, data)

    def delete(self, kind_id, key):
        kind = self.kind(kind_id)
        key = str(key)
        old = self.get(kind_id, key)
        users = self.where_used(kind_id, key)
        if users:
            raise GameSystemsAuthoringError(f"{key} is used by " + ", ".join(users))
        self.document.execute(
            _MapCommand(self.store(kind_id), key, None, old, f"Delete {kind.label[:-1]} {key}")
        )
        return old


__all__ = [
    "FORMS",
    "FormField",
    "GameSystemsAuthoringController",
    "GameSystemsAuthoringError",
    "KINDS",
    "new_row",
]
