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
    FactionDefinition,
    PetSpeciesDefinition,
    QuestDefinition,
    QuestObjective,
    ShopDefinition,
)
from asteria.rpg.ability_loadout import AbilityLoadoutRules
from asteria.rpg.battle_extensions import GAIN_EVENTS, BattleExtensionRules
from asteria.rpg.boards import CARD_STYLES, QuestBoardDefinition, RecruitOfficeDefinition
from asteria.rpg.derived_stats import DerivedStatRule
from asteria.rpg.disassembly import DisassemblyRecipe
from asteria.rpg.doodads import DoodadDefinition
from asteria.rpg.drop_tables import RARITIES, DropTable
from asteria.rpg.durability import ON_BREAK, DurabilityRules
from asteria.rpg.enemy_levels import EnemyLevelRules
from asteria.rpg.extras import BattleOptions, CreditsPage, MenuEntry, MusicTrack
from asteria.rpg.gacha import PRIZE_KINDS, GachaBanner, GachaRuntime
from asteria.rpg.items import (
    BATTLE_SWAPS,
    EQUIP_OFFERS,
    INVENTORY_OVERFLOW,
    SLOT_CONFLICTS,
    EquipmentSlotDefinition,
    InventoryRules,
)
from asteria.rpg.job_points import JobPointRules
from asteria.rpg.localization import LocaleTable, MessageSettings
from asteria.rpg.map_rules import MapRuleSet
from asteria.rpg.menu_pages import (
    BLOCK_KINDS,
    BLOCK_PLACES,
    MENU_ENTRY,
    PAGE_ENTRY,
    PAUSE_NEEDS,
    MenuBlock,
    MenuPage,
    default_pages,
    engine_pause_order,
    usable_pause_entries,
)
from asteria.rpg.menu_rules import (
    ITEM_DETAILS,
    NO_STAT_GRAPH,
    STAT_COLUMNS,
    STAT_FORMATS,
    MenuRules,
    menu_rules,
)
from asteria.rpg.new_game_plus import CARRY, NewGamePlusRules
from asteria.rpg.pets import EXP_SHARES, LEVEL_UP_HEALS, PetRules
from asteria.rpg.quests import OBJECTIVE_KINDS
from asteria.rpg.refine import ON_FAIL, RefineRules
from asteria.rpg.stat_definitions import SET_ON, STAT_DISPLAY, StatDefinition
from asteria.rpg.tag_definitions import TagDefinition
from asteria.rpg.workstations import WorkstationDefinition
from asteria.rpg.world_interactions import OPERATORS, VERBS, WorldInteraction
from asteria.rpg.world_record import ACHIEVEMENT_KINDS

EDITOR_ONLY = (
    "The game does not show this description: it stays in the editor (and in translation"
    " tables). For your own notes, use Note below."
)


class GameSystemsAuthoringError(RuntimeError):
    pass


@dataclass(slots=True)
class _StepsCommand:
    """Commands as one undo step: a record, its note and its Players See It."""

    steps: tuple

    @property
    def label(self):
        return self.steps[0].label

    def redo(self):
        for step in self.steps:
            step.redo()

    def undo(self):
        for step in reversed(self.steps):
            step.undo()


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
    ``icon`` (a picture id picked from the project's icons or the built-in library),
    ``choice`` (``choices``), ``ref`` / ``ref_list`` (``source`` names a
    reference list, see :meth:`GameSystemsAuthoringController.references`),
    ``pause_order`` (the pause menu top to bottom with a tick each: the order in ``key``, the
    unticked entries in ``hidden_key``; D97),
    ``row_id`` (a table row's own id: made for it, unique among its rows, never shown),
    ``rgb`` (a colour as "r, g, b" text, picked from a colour dialog),
    ``optional_point`` (``[x, y]`` or None: one switch, ``toggle_label``), ``row_pick`` (a row of
    the table field ``source``, numbered from 1, picked by its name),
    ``optional_ref`` (may be empty; ``empty_label`` names that choice), ``optional_int`` (None
    allowed). A reference list may hold ``(id, name)`` pairs: the form shows the name and keeps
    the id,
    ``string_list`` (picked from ``choices`` - values or (value, words) pairs - when it has
    them), ``amounts`` (``{key: number}``, keys from ``source`` when
    given), ``group`` (nested ``fields``), ``table`` (list of nested
    ``fields`` records), ``pairs`` (list of ``[number, text]``), ``translations`` (a locale
    table's key / text rows, listed with every built-in word of the engine).
    """

    key: str
    label: str
    kind: str
    source: str = ""
    choices: tuple = ()
    fields: tuple = ()
    default: object = None
    empty_label: str = ""
    toggle_label: str = "Limited"  # the check box of an ``optional_int``
    help: str = ""  # what the field means and how it counts: an ⓘ beside its label (D91)
    # (key, values): shown only while the record's ``key`` field holds one of ``values`` (D96)
    when: tuple = ()
    hidden_key: str = ""  # a ``pause_order``'s unticked entries (D97)
    # an ``amounts``' table of stats also lists HP, MP and the like: those it holds are kept in
    # this other ``amounts`` field, which then lists only the mechanics (a shield)
    pools_key: str = ""
    with_pools: bool = False  # an ``amounts`` of stats that offers HP, MP and the like too


def F(key, label, kind, **values):  # noqa: N802 - short spec constructor
    return FormField(key, label, kind, **values)


SPECIAL_RESOURCES = "Only the mechanics of their own, such as a shield: HP and MP are stats."
EDITOR_ONLY_DESCRIPTION = F(
    "description", "Description", "multiline", default="", help=EDITOR_ONLY
)


_ITEM_CATEGORY = (  # a tab of the Items page (D87)
    F("category_id", "Tab ID", "row_id", default="all"),
    F("display_name", "Tab Name", "text", default=""),
    F("tags", "Items With Any of These Properties (none: every item)", "string_list", default=()),
    F("icon_id", "Icon", "icon", default=""),
)
_ITEM_FILTER = (  # what the Items page's F key narrows a tab to (D87)
    F("filter_id", "Filter ID", "row_id", default="usable"),
    F("display_name", "Filter Name", "text", default=""),
    F("tags", "Items With All of These Properties", "string_list", default=()),
    F("usable", "Only Items the Menu Can Use", "bool", default=False),
)
SET_ON_WORDS = {"actors": "Actors", "classes": "Jobs (growth per level)", "enemies": "Enemies"}
STAT_COLUMN_WORDS = {
    "rank": "Rank (ranks taken / highest)",
    "total": "Total",
    "base": "Base (actor, jobs, level, passives)",
    "points": "Points (stat points spent)",
    "gear": "Gear",
    "gain": "Each + (what one more point adds)",
}
_STAT_GROUP = (  # a heading of the Status page's detail table (D89)
    F("group_id", "Group ID", "row_id", default="attack"),
    F("display_name", "Group Name", "text", default=""),
)
_STAT_LINE = (  # a stat of the Status page's detail table (D89)
    F("stat_id", "Stat", "ref", source="stats"),
    F("group", "Group ID", "text", default="", help="Empty: the Other group."),
    F(
        "format",
        "Written As",
        "choice",
        choices=STAT_FORMATS,
        default="number",
        help="Number: the stat as it is (299). Percent: with a % (12.5%). Range: the low ~ high"
        " an attack rolls, the stat less and plus Spread % (180 ~ 220). Chance: the % a battle"
        " check gives at this stat (crit 20%). Share: a 0-1 stat as a percent (0.12: 12%).",
    ),
    F(
        "spread",
        "Spread %",
        "float",
        default=0.0,
        help="Range lines only: how far either way the low and high stand from the stat, in %.",
    ),
    F("label", "Own Name", "text", default="", help="Empty: the stat's own name."),
    F(
        "check",
        "Battle Check",
        "optional_ref",
        source="outcome_checks",
        empty_label="(none)",
        default="",
        help="Chance lines only: the battle check (Battle Options ▸ Outcome Checks) whose"
        " chance the line shows, worked out from this stat.",
    ),
)
_MENU_BLOCK = (  # a block of a menu page: its kind, place and that kind's settings (D96)
    F(
        "kind",
        "Block",
        "choice",
        choices=BLOCK_KINDS,
        default="item_list",
        help="Profile: the member's name, level, jobs and resource bars. Stat Points: the"
        " stat table with a + per stat. Stat Details: the table of the other stats."
        " Item List: the bag, with tabs, filters and the chosen thing's details.",
    ),
    F("place", "Place", "choice", choices=BLOCK_PLACES, default="full"),
    F("height", "Height (0 = share the rest of its column)", "int", default=0),
    F(
        "stat_graph",
        "Stat Points Are Spent In (empty: the graph tagged attributes; - : no +)",
        "optional_ref",
        source="stat_graphs",
        empty_label="(the graph tagged attributes)",
        default="",
        when=("kind", ("stat_points",)),
    ),
    F(
        "stat_columns",
        "Stat Table Columns, in Order (none ticked: every column)",
        "ref_list",
        source="stat_columns",
        default=(),
        when=("kind", ("stat_points",)),
    ),
    F(
        "stat_rows",
        "Detail Stats of the Status Page, in Order (none ticked: every stat formula)",
        "ref_list",
        source="stats",
        default=(),
        when=("kind", ("stat_details",)),
    ),
    F(
        "stat_groups",
        "Detail Table Groups (Attack, Defence...: a heading each)",
        "table",
        fields=_STAT_GROUP,
        default=(),
        when=("kind", ("stat_details",)),
    ),
    F(
        "stat_lines",
        "Detail Table Lines (a stat each, in its group; none: Detail Stats above)",
        "table",
        fields=_STAT_LINE,
        default=(),
        when=("kind", ("stat_details",)),
    ),
    F(
        "item_categories",
        "Item Page Tabs",
        "table",
        fields=_ITEM_CATEGORY,
        default=(),
        when=("kind", ("item_list",)),
    ),
    F(
        "item_filters",
        "Item Page Filters (F)",
        "table",
        fields=_ITEM_FILTER,
        default=(),
        when=("kind", ("item_list",)),
    ),
    F(
        "item_details",
        "Item Details (panel: beside the list; button: Details / D opens it; off)",
        "choice",
        choices=ITEM_DETAILS,
        default="panel",
        when=("kind", ("item_list",)),
    ),
)
_MODIFIER = (
    F("modifier_id", "Modifier ID", "row_id", default="bonus"),
    F("stat", "Stat", "text", default="power"),
    F("operation", "Operation", "choice", choices=("add", "multiply", "override"), default="add"),
    F("value", "Value", "float", default=0.0),
    F("priority", "Priority", "int", default=0),
    F("required_tags", "Required Properties", "string_list", default=()),
    F("blocked_tags", "Blocked Properties", "string_list", default=()),
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

_PET_EVOLUTION = (
    F("to_species_id", "Evolves Into", "ref", source="pet_species"),
    F("min_level", "Needs Level", "int", default=0),
    F("min_affinity", "Needs Affinity", "float", default=0.0),
    F("item_id", "Needs Item (empty: none)", "optional_ref", source="items", default=""),
    F("consume_item", "Spend The Item", "bool", default=True),
    F("automatic", "Evolves By Itself After A Battle", "bool", default=True),
)
_PET_MOVE = (
    F("ability_id", "Ability (usable only once learned)", "ref", source="abilities"),
    F("level", "Learned At Level", "int", default=1),
    F("min_affinity", "Needs Affinity", "float", default=0.0),
)

_STAT_FORMULA = (  # Pet Rules: how a stat grows (base x level with the creature's genes)
    F("stat", "Stat (* = every other stat)", "text", default="*"),
    F("base_scale", "Base ×", "float", default=2.0),
    F("gene_terms", "Gene × (gene prefix and coefficient)", "amounts", default={}),
    F("level_divisor", "÷ After × Level", "float", default=100.0),
    F("level_term", "+ Level ×", "float", default=0.0),
    F("flat", "+ Flat", "float", default=5.0),
    F("multiplier_gene", "× Gene (prefix, e.g. nature; empty: none)", "text", default=""),
    F("round_down", "Round Down", "bool", default=True),
)
_GENE_RANGE = (
    F("prefix", "Gene Prefix", "text", default="iv"),
    F("low", "Lowest", "int", default=0),
    F("high", "Highest", "int", default=31),
)
_GENE_SET = (
    F("prefix", "Gene Prefix", "text", default="nature"),
    F("values", "Stat Multipliers", "amounts", default={}),
)

_CONDITION = (  # a switch or variable check (shops: when an item is sold, a price changes)
    F("source", "Check a", "choice", choices=("switch", "variable"), default="switch"),
    F("name", "Switch / Variable Name", "text", default=""),
    F("operator", "Is", "choice", choices=("==", "!=", ">=", "<=", ">", "<"), default="=="),
    F("value", "Value (true / false / a number)", "text", default="true"),
)
_PRICE_RULE = (
    F("buy_multiplier", "Buy Price × (1 = unchanged)", "float", default=1.0),
    F("sell_multiplier", "Sell Price × (1 = unchanged)", "float", default=1.0),
    F("conditions", "When (every condition true)", "table", fields=_CONDITION, default=()),
)


FORMS = {
    "pet_species": (
        F("species_id", "Species ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        F(
            "stats",
            "Level 1 Stats",
            "amounts",
            default={},
            help="Stats At Level 1, HP and MP too (read in formulas as pet_<stat>)",
            pools_key="resources",
        ),
        F(
            "growth",
            "Stat Growth",
            "amounts",
            default={},
            help="Stat Growth Per Level",
            with_pools=True,
        ),
        F("max_level", "Highest Level", "int", default=50),
        F(
            "exp_base",
            "EXP per Level",
            "float",
            default=40.0,
            help="Experience To Level Up = this x level",
        ),
        F(
            "exp_per_battle",
            "EXP per Battle",
            "float",
            default=30.0,
            help="Experience After A Won Battle It Was Sent Out In",
        ),
        F("tags", "Properties", "string_list", default=()),
        F("evolutions", "Evolutions", "table", fields=_PET_EVOLUTION, default=()),
        F("learnset", "Learned Abilities", "table", fields=_PET_MOVE, default=()),
        F(
            "teachable",
            "Teachable Skills",
            "string_list",
            default=(),
            help="Abilities Items Can Teach (items tagged teaches:<ability>)",
        ),
        F(
            "affinity_per_battle",
            "Affinity per Battle",
            "float",
            default=0.0,
            help="Affinity Gained Per Battle",
        ),
        F("max_affinity", "Highest Affinity", "float", default=100.0),
        F(
            "battle_unit",
            "Battle Unit",
            "bool",
            default=False,
            help="Fights As Its Own Battle Unit",
        ),
        F(
            "resources",
            "Resources",
            "amounts",
            default={},
            help=SPECIAL_RESOURCES,
        ),
        F(
            "exp_curve",
            "EXP Curve",
            "text",
            default="",
            help="Experience Curve a, b, c, d (a·L³ + b·L² + c·L + d; empty: linear)",
        ),
        F(
            "exp_yield",
            "EXP Yield",
            "float",
            default=0.0,
            help="Experience Given When Beaten (× its level)",
        ),
        F("capture_rate", "Capture Rate", "float", default=0.0, help="Capture Rate (rate mode)"),
        F("visual_profile_id", "Front Visual", "text", default="", help="Battle Visual (front)"),
        F(
            "back_visual_profile_id",
            "Back Visual",
            "text",
            default="",
            help="Battle Visual On The Player's Side (back)",
        ),
        F(
            "battle_abilities",
            "Battle Skills",
            "ref_list",
            source="abilities",
            default=(),
            help="Abilities As A Battle Unit",
        ),
    ),
    "inventory_rules": (
        F("rules_id", "Rules ID", "id"),
        F("display_name", "Name", "text", default=""),
        F(
            "stack_limits",
            "Stack Limits",
            "bool",
            default=True,
            help="Items Stack Up to Their Stack Limit",
        ),
        F(
            "max_kinds",
            "Max Kinds",
            "optional_int",
            default=None,
            help="Most Different Items Carried (empty = no limit)",
        ),
        F(
            "exempt_tags",
            "Exempt Properties",
            "string_list",
            default=("item.key",),
            help="Properties That Never Take a Place (key items)",
        ),
        F(
            "overflow",
            "Overflow",
            "choice",
            choices=INVENTORY_OVERFLOW,
            default="fill",
            help="When Items Do Not Fit",
        ),
        F(
            "equip_offer",
            "Equip Offer",
            "choice",
            choices=EQUIP_OFFERS,
            default="never",
            help="Ask to Wear New Gear (never / a free place / always, swapping)",
        ),
        F(
            "battle_swap",
            "Battle Swap",
            "choice",
            choices=BATTLE_SWAPS,
            default="turn",
            help="The battle's Swap command takes a piece from a carried slot (Game Systems ▸"
            " Equipment Slots, Carried) into a worn one. turn: swapping uses the turn. free: the"
            " hero still acts. off: no Swap command.",
        ),
        F(
            "slot_conflict",
            "Slot Conflict",
            "choice",
            choices=SLOT_CONFLICTS,
            default="take_off",
            help="Wearing a piece whose place is taken - a two-handed weapon while the sub"
            " weapon slot holds one (the gear's Also Takes). take_off: the other piece goes back"
            " to the bag (or the carried slot when swapping). refuse: it cannot be worn until"
            " the other piece is taken off.",
        ),
    ),
    "drop_tables": (
        F("table_id", "Table ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("rolls", "Rolls", "int", default=1, help="Weighted Picks per Kill"),
        F("nothing_weight", "No Drop Weight", "float", default=0.0, help="Weight of No Drop"),
        F("entries", "Weighted Entries", "table", fields=_DROP, default=()),
        F("guaranteed", "Always Drops", "table", fields=_DROP, default=()),
        F(
            "pity",
            "Pity",
            "table",
            fields=(
                F("item_id", "Item", "ref", source="items"),
                F("after_misses", "After Misses", "int", default=10),
            ),
            default=(),
            help="Pity (guarantee after misses)",
        ),
        F(
            "luck_weight_bonus",
            "Luck Bonus",
            "float",
            default=0.0,
            help="Luck Bonus to Rare Weights",
        ),
    ),
    "world_interactions": (
        F("interaction_id", "Interaction ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("verb", "Verb", "choice", choices=VERBS, default="talk"),
        F("target_type", "Target Type", "text", default=""),
        F("actor_tag", "Member Property", "text", default="", help="Needs Party Member Property"),
        F(
            "required_item",
            "Required Item",
            "optional_ref",
            source="items",
            default="",
            help="Needs Item",
        ),
        F("requirements", "Requirements", "table", fields=_REQUIREMENT, default=()),
        F("cost_items", "Cost Items", "amounts", source="items", default={}, help="Cost: Items"),
        F("cost_currencies", "Cost: Currencies", "amounts", default={}),
        F(
            "check_stat",
            "Check Stat",
            "text",
            default="",
            help="Check Stat (empty = always succeeds)",
        ),
        F("difficulty", "Difficulty", "float", default=0.0),
        F("base_chance", "Base Chance", "float", default=0.5, help="Base Chance (0–1)"),
        F(
            "chance_per_point",
            "Chance per Point",
            "float",
            default=0.05,
            help="Chance per Stat Point",
        ),
        F(
            "success_items",
            "Success Items",
            "amounts",
            source="items",
            default={},
            help="Success: Items",
        ),
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
        F("icon_id", "Icon", "icon", default=""),
        F(
            "entries",
            "Stock",
            "table",
            default=(),
            fields=(
                F("item_id", "Item or Equipment", "ref", source="goods"),  # gear sells (D61)
                F("buy_prices", "Buy Price", "amounts", default={}),
                F("sell_prices", "Sell Price", "amounts", default={}),
                F("stock", "Limited Stock", "optional_int", default=None),
                F(
                    "visible_when",
                    "Sold Only When (every condition true; none = always)",
                    "table",
                    fields=_CONDITION,
                    default=(),
                ),
                F(
                    "price_rules",
                    "Price Changes (when their conditions are true)",
                    "table",
                    fields=_PRICE_RULE,
                    default=(),
                ),
            ),
        ),
    ),
    "quests": (
        F("quest_id", "Quest ID", "id"),
        F("display_name", "Name", "text"),
        F("icon_id", "Icon", "icon", default=""),
        F("description", "Description", "multiline", default=""),
        F(
            "objectives",
            "Objectives",
            "table",
            default=(),
            fields=(
                F("objective_id", "Objective ID", "row_id", default="objective"),
                F("kind", "Kind", "choice", choices=OBJECTIVE_KINDS, default="counter"),
                F("target", "Target (item / enemy / switch)", "text", default=""),
                F("required", "Required", "int", default=1),
                F("description", "Description", "text", default=""),
            ),
        ),
        F("prerequisites", "Prerequisite Quests", "ref_list", source="quests", default=()),
        F(
            "next_quest_ids",
            "Next Quests",
            "ref_list",
            source="quests",
            default=(),
            help="Next Quests (chain)",
        ),
        F("auto_complete", "Complete Automatically", "bool", default=True),
        F("reward", "Reward", "group", fields=_REWARD),
        # the quest board's card (U5)
        F("card_image", "Card Picture", "icon", default="", help="Card Picture (quest board)"),
        F("rank", "Card Rank", "text", default="", help="Card Rank (S, A, Bronze...)"),
        F(
            "category",
            "Card Category",
            "text",
            default="",
            help="Card Category (Hunt, Delivery...)",
        ),
        F("repeatable", "Repeatable", "bool", default=False, help="Repeatable From a Board"),
        F(
            "time_limit",
            "Time Limit",
            "float",
            default=0.0,
            help="Time Limit Once Taken (minutes of play, 0 = none)",
        ),  # fmt: skip
    ),
    "quest_boards": (
        F("board_id", "Board ID", "id", help="Board ID (OPEN_QUEST_BOARD names it)"),
        F("display_name", "Name", "text", default=""),
        F("description", "Description", "multiline", default=""),
        F(
            "quest_ids",
            "Quests",
            "ref_list",
            source="quests",
            default=(),
            help="Quests on the Board (card order)",
        ),  # fmt: skip
        F(
            "open_switch",
            "Open Switch",
            "text",
            default="",
            help="Open Only While Switch Is On (empty = always)",
        ),
        F("max_active", "Max Active", "int", default=0, help="Most Taken at Once (0 = no limit)"),
        F(
            "refresh_minutes",
            "Refresh Minutes",
            "float",
            default=0.0,
            help="Repeatable Quests Return After (minutes of play)",
        ),  # fmt: skip
        F("card_style", "Cards", "choice", choices=CARD_STYLES, default="grid"),
        F("music", "Music While Open", "text", default=""),
        F(
            "layout",
            "Menu Layout",
            "text",
            default="",
            help="Menu Layout (empty = quest_board.<id>, else quest_board)",
        ),  # fmt: skip
    ),
    "recruit_offices": (
        F("office_id", "Office ID", "id", help="Office ID (OPEN_RECRUIT names it)"),
        F("display_name", "Name", "text", default=""),
        EDITOR_ONLY_DESCRIPTION,
        F(
            "candidates",
            "Candidates",
            "table",
            default=(),
            fields=(
                F("actor_id", "Character", "ref", source="actors"),
                F("currency", "Currency", "text", default="gold"),
                F("cost", "Price", "float", default=0.0),
                F("require_switch", "Needs Switch On (empty = always)", "text", default=""),
                F("level_min", "Level From (0 = their own)", "int", default=0),
                F("level_max", "Level To", "int", default=0),
                F("portrait", "Portrait (empty = their battle portrait)", "icon", default=""),
                F("note", "Note on the Card", "text", default=""),
            ),
        ),
        F("party_limit", "Party Limit", "int", default=0, help="Largest Party (0 = no limit)"),
        F(
            "can_dismiss",
            "Can Dismiss",
            "bool",
            default=True,
            help="Members Can Be Sent Away Here",
        ),
        F(
            "dismiss_refund",
            "Dismiss Refund",
            "float",
            default=0.0,
            help="Refund When Sent Away (0–1 of the price)",
        ),
        F(
            "experience_per_level",
            "EXP per Level",
            "float",
            default=1000.0,
            help="Experience per Rolled Level",
        ),
        F("music", "Music While Open", "text", default=""),
        F(
            "layout",
            "Menu Layout",
            "text",
            default="",
            help="Menu Layout (empty = recruit.<id>, else recruit)",
        ),
    ),
    "gacha_banners": (
        F("banner_id", "Banner ID", "id", help="Banner ID (OPEN_GACHA names it)"),
        F("display_name", "Name", "text", default=""),
        F("description", "Description", "multiline", default=""),
        F("banner_image", "Banner Picture", "icon", default=""),
        F("currency", "Currency", "text", default="gold"),
        F("single_cost", "Single Pull Price", "float", default=100.0, help="Price of One Pull"),
        F("multi_cost", "Multi-Pull Price", "float", default=1000.0, help="Price of a Multi-Pull"),
        F("multi_count", "Multi-Pull Count", "int", default=10, help="Pulls in a Multi-Pull"),
        F(
            "rarities",
            "Rarities",
            "table",
            default=(),
            fields=(
                F("rarity_id", "Rarity ID", "row_id", default="common"),
                F("display_name", "Name", "text", default=""),
                F("color", "Colour", "rgb", default="235, 235, 245"),
                F("chest_image", "Closed Chest", "icon", default=""),
                F("open_image", "Open Chest", "icon", default=""),
                F("open_sound", "Opening Sound", "text", default=""),
            ),
            help="Rarities (lowest first)",
        ),
        F(
            "prizes",
            "Prizes",
            "table",
            default=(),
            fields=(
                F("target_id", "Prize", "text", default="", help="What the pull gives"),
                F("kind", "Kind", "choice", choices=PRIZE_KINDS, default="item"),
                F("amount", "Amount", "int", default=1),
                F("weight", "Weight", "float", default=1.0),
                F("rarity", "Rarity", "text", default=""),
                F("featured", "Rate Up (featured)", "bool", default=False),
                F("duplicate_item", "Already Owned: Give Item Instead", "text", default=""),
                F("duplicate_amount", "Already Owned: How Many", "int", default=0),
            ),
        ),
        F("featured_multiplier", "Rate Up ×", "float", default=1.0, help="Rate Up: Weight Times"),
        F("hard_pity", "Hard Pity", "int", default=0, help="Pity: Guaranteed by Pull (0 = none)"),
        F(
            "pity_rarity",
            "Pity Rarity",
            "text",
            default="",
            help="Pity Rarity (empty = the highest)",
        ),
        F(
            "soft_pity_start",
            "Soft Pity Start",
            "int",
            default=0,
            help="Soft Pity: Starts After Pull (0 = none)",
        ),
        F(
            "soft_pity_step",
            "Soft Pity Step",
            "float",
            default=0.0,
            help="Soft Pity: Chance Added per Pull (0–1)",
        ),
        F(
            "multi_guarantee",
            "Multi-Pull Guarantee",
            "text",
            default="",
            help="Multi-Pull: At Least One of Rarity",
        ),
        F(
            "open_switch",
            "Open Switch",
            "text",
            default="",
            help="Open Only While Switch Is On (empty = always)",
        ),
        F(
            "appear_seconds",
            "Chest Appear Time",
            "float",
            default=0.5,
            help="Chest Appears For (seconds)",
        ),
        F(
            "shake_seconds",
            "Chest Shake Time",
            "float",
            default=0.8,
            help="Chest Shakes For (seconds)",
        ),
        F(
            "open_seconds",
            "Chest Open Time",
            "float",
            default=0.6,
            help="Chest Opens For (seconds)",
        ),
        F("appear_sound", "Appear Sound", "text", default=""),
        F("shake_sound", "Shake Sound", "text", default=""),
        F("music", "Music While Open", "text", default=""),
        F(
            "layout",
            "Menu Layout",
            "text",
            default="",
            help="Menu Layout (empty = gacha.<id>, else gacha)",
        ),
    ),
    "factions": (
        F("faction_id", "Faction ID", "id"),
        F("display_name", "Name", "text"),
        F("icon_id", "Icon", "icon", default=""),
        F("minimum", "Minimum", "float", default=-100.0),
        F("maximum", "Maximum", "float", default=100.0),
        F("initial", "Initial", "float", default=0.0),
        F("ranks", "Ranks", "pairs", default=(), help="Ranks (threshold → name)"),
    ),
    "achievements": (
        F("achievement_id", "Achievement ID", "id"),
        F("display_name", "Name", "text"),
        F("icon_id", "Icon", "icon", default=""),
        F("description", "Description", "multiline", default=""),
        F("kind", "Condition", "choice", choices=ACHIEVEMENT_KINDS, default="switch"),
        F("target", "Target", "text"),
        F("value", "Value", "float", default=1.0),
        F("hidden", "Hidden Until Unlocked", "bool", default=False),
    ),
    "equipment_sets": (
        F("set_id", "Set ID", "id"),
        F("display_name", "Name", "text"),
        F("icon_id", "Icon", "icon", default=""),
        F("equipment_ids", "Equipment", "ref_list", source="equipment", default=()),
        F(
            "bonuses",
            "Bonuses",
            "table",
            default=(),
            fields=(
                F("pieces", "Pieces Equipped", "int", default=2),
                F("modifiers", "Stat Modifiers", "table", fields=_MODIFIER, default=()),
                F("tags", "Granted Properties", "string_list", default=()),
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
        F(
            "pet_item_id",
            "Pet Item",
            "optional_ref",
            source="items",
            default="",
            help="Becomes Pet Item",
        ),
        F(
            "pet_species_id",
            "Pet Species",
            "optional_ref",
            source="pet_species",
            default="",
            help="Becomes Owned Pet (species)",
        ),
        F("pet_level", "Pet Level", "int", default=1, help="Pet Starts At Level"),
        F("mode", "Chance Mode", "choice", choices=("linear", "rate"), default="linear"),
        F("base_chance", "Base Chance", "float", default=0.25, help="Base Chance (0–1)"),
        F("low_health_bonus", "Low-Health Bonus", "float", default=0.5),
        F(
            "capture_rate",
            "Capture Rate",
            "float",
            default=0.0,
            help="Capture Rate (rate mode; 0 = the species' own)",
        ),
        F("divisor", "Rate Divisor", "float", default=255.0),
        F("item_id", "Consumed Item", "optional_ref", source="items", default=""),
        F(
            "item_bonuses",
            "Item Bonuses",
            "amounts",
            source="items",
            default={},
            help="Capture Items And Their ×",
        ),
        F(
            "state_bonuses",
            "State Bonuses",
            "amounts",
            default={},
            help="State Bonuses (state id and ×)",
        ),
        F("shake_checks", "Shake Checks", "int", default=0, help="Shake Checks (0 = One Roll)"),
    ),
    "pet_rules": (
        F("rules_id", "Rules ID", "id"),
        F("party_size", "Party Size", "int", default=0, help="Party Size (0 = every owned pet)"),
        F(
            "battle_slots",
            "Battle Slots",
            "int",
            default=1,
            help="Creatures On The Stage At Once (0 = all)",
        ),
        F("storage", "Storage", "bool", default=False, help="Storage Box For The Rest"),
        F("actors_fight", "Characters Fight Too", "bool", default=True),
        F(
            "pets_decide_outcome",
            "Lose When All Fall",
            "bool",
            default=False,
            help="No Creature Standing = Lost",
        ),
        F(
            "switch_costs_turn",
            "Switch Costs Turn",
            "bool",
            default=True,
            help="Switching Costs The Turn",
        ),
        F("exp_share", "Experience From Foes", "choice", choices=EXP_SHARES, default="none"),
        F("exp_divisor", "Experience ÷", "float", default=1.0),
        F(
            "exp_whole",
            "Whole EXP",
            "bool",
            default=False,
            help="Whole Experience Points (rounded down)",
        ),
        F(
            "level_up_heal",
            "Level-Up Heal",
            "choice",
            choices=LEVEL_UP_HEALS,
            default="delta",
            help="Health On Level Up",
        ),
        F(
            "max_moves",
            "Max Moves",
            "int",
            default=0,
            help="Moves A Creature Knows At Once (0 = unlimited)",
        ),
        F(
            "heal_restores_pp",
            "Heal Restores Uses",
            "bool",
            default=True,
            help="HEAL_PETS Restores Move Uses",
        ),
        F(
            "out_of_uses_ability",
            "Out-of-Uses Skill",
            "optional_ref",
            source="abilities",
            default="",
            help="When No Move Has Uses Left, Use",
        ),
        F("stat_formulas", "Stat Formulas", "table", fields=_STAT_FORMULA, default=()),
        F(
            "gene_ranges",
            "Gene Ranges",
            "table",
            fields=_GENE_RANGE,
            default=(),
            help="Rolled Genes (whole numbers)",
        ),
        F(
            "gene_sets",
            "Gene Sets",
            "table",
            fields=_GENE_SET,
            default=(),
            help="Gene Sets (one picked per creature)",
        ),
    ),
}

# --- rules added in D26 (battle extensions, map rules, durability, messages ...) -----------------
_STEAL_ENTRY = (
    F("item_id", "Item", "ref", source="items"),
    F("chance", "Chance (0–1)", "float", default=1.0),
    F("amount", "Amount", "int", default=1),
)
_AREA_RULE = (
    F("key", "Area (region:<id> or tag:<name>)", "text", default="region:1"),
    F("damage_resource", "Floor Damage: Resource", "text", default=""),
    F("damage_per_second", "Floor Damage per Second", "float", default=0.0),
    F("can_kill", "Floor Damage Can Kill", "bool", default=False),
    F("slippery", "Slippery", "bool", default=False),
    F("slip_seconds", "Slide Seconds", "float", default=0.6),
    F("footstep_cue", "Footstep Sound (asset)", "text", default=""),
    F("step_distance", "Distance per Step", "float", default=28.0),
    F("blocks", "Blocks (player, enemy, npc, all)", "string_list", default=()),
    F("visibility", "Visibility (1 = normal, below 1 = harder to see)", "float", default=1.0),
    F("on_enter", "Event on Enter", "optional_ref", source="event_programs", default=""),
    F("on_leave", "Event on Leave", "optional_ref", source="event_programs", default=""),
    F("on_step", "Event on Each Step", "optional_ref", source="event_programs", default=""),
    F("switch", "Only While Switch Is On", "text", default=""),
    F("battle_background", "Battle Background For Fights Here", "icon", default=""),
    F("music", "Music Here (audio asset)", "text", default=""),
    F(
        "weather",
        "Weather Here",
        "choice",
        default="",
        choices=("", "none", "rain", "snow", "leaves", "dust", "ash", "sand", "fog"),
    ),
    F("title", "Area Name Shown on Entering", "text", default=""),
    F("encounters", "Random Encounters (weight each)", "amounts", source="encounters", default={}),
    F("encounter_chance", "Encounter Chance per Step (0–1)", "float", default=0.0),
    F("encounter_first_step", "Chance Scale on the Step Into the Area", "float", default=1.0),
    F(
        "autorun",
        "Run While Here (first whose condition holds)",
        "table",
        default=(),
        fields=(
            F("switch", "Switch (or leave empty)", "text", default=""),
            F("variable", "Variable (or leave empty)", "text", default=""),
            F("value", "Equals (switch: on unless false/0)", "text", default=""),
            F("program", "Event", "ref", source="event_programs"),
            F("when", "When", "choice", choices=("always", "enter"), default="always"),
        ),
    ),
)

D26_FORMS = {
    "battle_extension_rules": (
        F("rules_id", "Rules ID", "id"),
        F(
            "damage_resource",
            "Damage Resource",
            "text",
            default="",
            help="Resource That Counts as Damage (hp)",
        ),
        F("taunt_tag", "Taunt Property", "text", default=""),
        F(
            "lifesteal_stat",
            "Life Steal Stat",
            "text",
            default="",
            help="Life Steal Stat (0–1 on the actor)",
        ),
        F("overkill_rate", "Overkill Reward Rate", "float", default=0.0),
        F(
            "overkill_cap",
            "Overkill Cap",
            "float",
            default=1.0,
            help="Overkill Cap (share of max)",
        ),
        F("use_limits", "Uses per Battle", "amounts", source="abilities", default={}),
        F(
            "mastery",
            "Mastery Levels",
            "table",
            default=(),
            fields=(
                F("ability_id", "Ability", "ref", source="abilities"),
                F("thresholds", "Uses for Each Level", "string_list", default=()),
            ),
            help="Mastery Levels (uses needed, comma separated)",
        ),
        F(
            "preemptive_chance",
            "Preemptive Chance",
            "float",
            default=0.0,
            help="Preemptive Chance (0–1)",
        ),
        F(
            "surprise_chance",
            "Surprise Chance",
            "float",
            default=0.0,
            help="Surprise Chance (0–1)",
        ),
        F(
            "steal_tables",
            "Steal Tables",
            "table",
            default=(),
            fields=(
                F("target_key", "Enemy ID or Property", "text", default=""),
                F("once", "Once per Enemy", "bool", default=True),
                F("entries", "Can Steal", "table", fields=_STEAL_ENTRY, default=()),
            ),
        ),
        F(
            "row_tag_prefix",
            "Row Property Prefix",
            "text",
            default="",
            help="Row Property Prefix (blank = off)",
        ),
        F(
            "gains",
            "Resource Gains",
            "table",
            default=(),
            fields=(
                F("event", "When", "choice", choices=GAIN_EVENTS, default="dealt"),
                F("resource", "Battle Resource", "text", default="tp"),
                F("flat", "Flat Amount", "float", default=0.0),
                F("per_damage", "Per Point of Damage", "float", default=0.0),
                F("per_max_hp", "Per Share of Victim Max", "float", default=0.0),
                F("ability_tag", "Only Abilities Tagged", "text", default=""),
                F("shared", "Fills A Party-Wide Gauge", "bool", default=False),
                F("side", "Counts Only For Side", "text", default="heroes"),
            ),
            help="Resource Gains (TP-style)",
        ),
        F(
            "shared_gauges",
            "Shared Gauges",
            "amounts",
            default={},
            help="Party-Wide Gauges (id and maximum, saved with the world)",
        ),
    ),
    "enemy_level_rules": (
        F("rules_id", "Rules ID", "id"),
        F(
            "stat_growth",
            "Stat Growth",
            "amounts",
            default={},
            help="Stat Growth per Level, HP and MP too",
            pools_key="resource_growth",
        ),
        F(
            "resource_growth",
            "Resource Growth",
            "amounts",
            default={},
            help=SPECIAL_RESOURCES,
        ),
        F("reward_growth", "Reward Growth", "float", default=0.0, help="Reward Growth per Level"),
        F(
            "map_levels",
            "Levels by Map",
            "table",
            default=(),
            fields=(
                F("map_id", "Map / Area ID", "text", default=""),
                F("lowest", "Lowest", "int", default=1),
                F("highest", "Highest", "int", default=1),
            ),
        ),
        F(
            "party_level_offset",
            "Party Level Offset",
            "int",
            default=0,
            help="Level vs Party (no map entry)",
        ),
        F("max_level", "Highest Level", "int", default=99),
        F(
            "difficulties",
            "Difficulty Slider",
            "table",
            default=(),
            fields=(
                F("difficulty_id", "Name", "text", default="normal"),
                F("strength", "Enemy Strength x", "float", default=1.0),
                F("reward", "Reward x", "float", default=1.0),
                F("level_offset", "Level Offset", "int", default=0),
            ),
        ),
        F("default_difficulty", "Default Difficulty", "text", default=""),
    ),
    "map_rule_sets": (
        F("rules_id", "Rules ID", "id"),
        F(
            "region_layer",
            "Region Layer",
            "text",
            default="regions",
            help="Tile Layer Holding Regions",
        ),
        F("crouch_visibility", "Visibility When Crouching", "float", default=1.0),
        F(
            "still_visibility",
            "Still Visibility",
            "float",
            default=1.0,
            help="Visibility When Standing Still",
        ),
        F("rules", "Area Rules", "table", fields=_AREA_RULE, default=()),
    ),
    "durability_rules": (
        F("rules_id", "Rules ID", "id"),
        F("max_durability", "Durability per Equipment", "amounts", source="equipment", default={}),
        F(
            "default_max",
            "Default Durability",
            "float",
            default=0.0,
            help="Durability of Other Equipment (0 = none)",
        ),
        F(
            "wear",
            "Wear",
            "table",
            default=(),
            fields=(
                F("event", "Event (attack, hit ...)", "text", default="attack"),
                F("slots", "Slots", "string_list", default=("weapon",)),
                F("amount", "Wear per Event", "float", default=1.0),
            ),
        ),
        F(
            "on_break",
            "When Broken",
            "choice",
            choices=ON_BREAK,
            default="disable",
            help="When It Breaks",
        ),
        F("repair_currency", "Repair Currency", "text", default=""),
        F("repair_cost_per_point", "Repair Cost per Point", "float", default=0.0),
    ),
    "refine_rules": (
        F("rules_id", "Rules ID", "id"),
        F("max_level", "Max Refine Level", "int", default=10, help="Maximum Refine Level (+N)"),
        F(
            "equipment_tags",
            "Equipment Properties",
            "string_list",
            default=(),
            help="Only Equipment With Any Property (empty = all)",
        ),
        F(
            "bonuses",
            "Bonus per Level",
            "amounts",
            default={},
            help="Bonus per Level (stat = amount)",
        ),
        F("operation", "Bonus Operation", "choice", choices=("add", "multiply"), default="add"),
        F("currency", "Cost Currency", "text", default=""),
        F("base_cost", "Base Cost", "float", default=0.0, help="Cost of the First Attempt"),
        F("cost_growth", "Cost Growth", "float", default=0.0, help="Extra Cost per Level"),
        F(
            "success",
            "Success Chances",
            "text",
            default="1.0",
            help="Success Chance per Level (0-1, comma separated)",
        ),
        F("on_fail", "On Failure", "choice", choices=ON_FAIL, default="keep"),
        F("safe_until", "Safe Levels", "int", default=0, help="Levels Below This Never Fail"),
        F(
            "materials",
            "Materials",
            "amounts",
            source="items",
            default={},
            help="Materials Used per Attempt",
        ),
        F(
            "protect_item",
            "Protection Item",
            "optional_ref",
            source="items",
            default="",
            help="Protection Item (keeps the level on a failure)",
        ),
    ),
    "disassembly_recipes": (
        F("item_id", "Item", "id", help="Item / Equipment ID"),
        F(
            "yields",
            "Yields",
            "table",
            default=(),
            fields=(
                F("item_id", "Item", "ref", source="items"),
                F("minimum", "Minimum", "int", default=1),
                F("maximum", "Maximum", "int", default=1),
                F("chance", "Chance (0–1)", "float", default=1.0),
            ),
        ),
        F("fee_currency", "Fee Currency", "text", default=""),
        F("fee", "Fee", "float", default=0.0),
    ),
    "workstations": (
        F("station_id", "Station ID", "id", help="Station ID (recipes and OPEN_CRAFTING name it)"),
        F("display_name", "Name", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        EDITOR_ONLY_DESCRIPTION,
        F(
            "categories",
            "Tabs",
            "table",
            default=(),
            fields=(
                F("category_id", "Tab ID", "row_id", default="tab"),
                F("display_name", "Name", "text", default=""),
                F(
                    "tags",
                    "Recipe Properties (empty = every recipe left)",
                    "string_list",
                    default=(),
                ),
                F("icon_id", "Icon", "icon", default=""),
            ),
            help="Tabs (recipe categories)",
        ),
        F(
            "show_undiscovered",
            "Show Undiscovered",
            "bool",
            default=True,
            help="Show Undiscovered Recipes as ???",
        ),
        F("max_quantity", "Max Quantity", "int", default=99, help="Most Made at Once"),
        F("disassembly", "Disassembly Tab", "bool", default=False),
        F(
            "disassembly_tags",
            "Disassembly Properties",
            "string_list",
            default=(),
            help="Break Down Only Items With Any Property (empty = all)",
        ),
        F("craft_sound", "Success Sound", "text", default=""),
        F("fail_sound", "Failure Sound", "text", default=""),
        F(
            "success_image",
            "Success Picture",
            "icon",
            default="",
            help="Picture Shown After a Success",
        ),
        F(
            "success_seconds",
            "Picture Time",
            "float",
            default=0.6,
            help="Picture Shown For (seconds)",
        ),
        F("music", "Music While Open", "text", default=""),
        F(
            "layout",
            "Menu Layout",
            "text",
            default="",
            help="Menu Layout (empty = crafting.<station>, else crafting)",
        ),
    ),
    "job_point_rules": (
        F("rules_id", "Rules ID", "id"),
        F(
            "prefix",
            "Balance Prefix",
            "text",
            default="jp",
            help="Balance Prefix (jp -> jp.<class>)",
        ),
        F("per_battle", "Points per Battle", "float", default=0.0),
        F("per_enemy", "Points per Enemy", "float", default=0.0, help="Points per Defeated Enemy"),
        F(
            "secondary",
            "Sub Job Share",
            "float",
            default=0.5,
            help="Share for Each Extra Class (0–1)",
        ),
    ),
    "stat_definitions": (  # what each number of the game is (D91)
        F("stat_id", "Stat ID", "id", help="The name formulas use: str, power, boss_damage."),
        F("display_name", "Name", "text", default="", help="Strength, Physical Attack..."),
        F(
            "short_name",
            "Short Name",
            "text",
            default="",
            help="For tight tables: STR, ATK. Empty: the name.",
        ),
        F(
            "display",
            "Written As",
            "choice",
            choices=STAT_DISPLAY,
            default="number",
            help="Number: 299. Percent: 12.5% (the stat counts in percent points). Share: a"
            " 0-1 stat written as a percent (0.12: 12%).",
        ),
        F(
            "grows_with_level",
            "Grows with Level",
            "bool",
            default=False,
            help="Jobs raise it every level (their Growth per Level lists it), and the actors'"
            " and jobs' Growth Curves chart it. Off: it stays at its starting value, or comes"
            " from Stat Formulas, gear and points.",
        ),
        F(
            "base_stats",
            "Base Stats",
            "group",
            fields=tuple(
                F(x, SET_ON_WORDS[x], "bool", default=False) for x in SET_ON if x != "classes"
            ),
            help="Ticked: that record's Base Stats list it (an actor's starting stats, an"
            " enemy's stats). Unticked: it comes from gear, Stat Formulas, passives and points.",
        ),
        F("order", "Order", "int", default=0, help="Lower comes first in every list."),
        F(
            "description",
            "Description",
            "multiline",
            default="",
            help="The definition, in your words: what the number does in the game. Players"
            " read it under the Status page's stat table.",
        ),
        F(
            "usage",
            "Usage",
            "info",
            default="",
            help="Worked out from the whole project: the stat formula, the records and gear"
            " that set it, the battle checks, rules and skills that read it.",
        ),
    ),
    "equipment_slots": (  # the places gear is worn or carried in (D92)
        F(
            "slot_id",
            "Slot",
            "id",
            help="The id gear names in its Slot: weapon, sub_weapon, special. Every hero has"
            " every slot defined here.",
        ),
        F("display_name", "Name", "text", default="", help="What players read: Main Weapon."),
        F("order", "Order", "int", default=0, help="Lower comes first on the equipment screen."),
        F(
            "capacity",
            "Capacity",
            "optional_int",
            default=1,
            help="How many pieces fit: 1 for a hand, 2 for two rings, 6 carried weapons.",
        ),
        F(
            "accepted_tags",
            "Accepted Properties",
            "string_list",
            default=(),
            help="Gear made for another slot fits too when it carries one of these properties:"
            " a sub"
            " weapon slot taking weapon takes every weapon. Empty: only gear made for this slot.",
        ),
        F(
            "stowed",
            "Carried, Not Worn",
            "bool",
            default=False,
            help="Its pieces give no stats, skills, properties or set bonuses: they wait to be"
            " swapped"
            " into a worn slot with the battle's Swap command (Inventory Rules ▸ Swap Carried"
            " Weapons in Battle).",
        ),
        F(
            "required_capabilities",
            "Required Capabilities",
            "string_list",
            default=(),
            help="Capabilities (properties) a hero needs to use the slot, from a job's Granted"
            " Properties:"
            " capability.carry_weapons lets only that job carry weapons. Empty: everyone.",
        ),
        F(
            "description",
            "Description",
            "multiline",
            default="",
            help="What players read on the equipment screen when they pick the slot.",
        ),
    ),
    "tag_definitions": (  # what each tag of the game means (D91)
        F(
            "tag_id",
            "Property",
            "id",
            help="The property rules look for: weapon.sword, weak.fire, no_escape. End it in *"
            " for a"
            " family: rune.* covers every property starting with rune.",
        ),
        F("display_name", "Name", "text", default="", help="What players read: Sword, Fire."),
        F("order", "Order", "int", default=0, help="Lower comes first in every list."),
        F(
            "description",
            "Description",
            "multiline",
            default="",
            help="The definition, in your words: what carrying the property does in the game."
            " Players read it under an item's or a piece's description.",
        ),
        F(
            "usage",
            "Usage",
            "info",
            default="",
            help="Worked out from the whole project: what the engine itself does with the"
            " property,"
            " the records that carry it and the rules that read it.",
        ),
    ),
    "derived_stats": (
        F("stat_id", "Stat", "id", help="Stat (the one computed)"),
        F("display_name", "Name", "text", default=""),
        F(
            "expression",
            "Formula",
            "formula",
            choices=("self",),
            default="",
            help="What the stat gains, written as a formula of this fighter's stats: self.dex"
            " + 0.5 * self.luk. Only stats declared in Game Systems ▸ Stats can be read. Empty:"
            " Read From and Base Amount are used.",
        ),
        F("terms", "Terms", "amounts", default={}, help="Read From (stat: coefficient)"),
        F("base", "Base Amount", "float", default=0.0),
        F("minimum", "Never Below", "float", default=0.0),
        F("maximum", "Maximum", "float", default=0.0, help="At Most (0 = no cap)"),
        F(
            "applies_to",
            "Used By",
            "choice",
            choices=("actors", "enemies", "all"),
            default="all",  # one set of formulas for both sides
        ),
        F("order", "Order", "int", default=0, help="Order (lower runs first)"),
        EDITOR_ONLY_DESCRIPTION,
    ),
    "new_game_plus_rules": (
        F("rules_id", "Rules ID", "id"),
        F("carry", "Carried Over", "ref_list", source="carry_parts", default=()),
        F(
            "carry_switches",
            "Kept Switches",
            "string_list",
            default=(),
            help="Switch Prefixes That Stay On",
        ),
        F("level_cap", "Level Cap", "int", default=0, help="Level Cap (0 = none)"),
        F(
            "keep_currency_share",
            "Currency Kept",
            "float",
            default=1.0,
            help="Share of Currency Kept (0–1)",
        ),
    ),
    "locale_tables": (
        F("locale", "Locale", "id", help="Locale (fr, zh-TW ...)"),
        # key / text rows: the engine's built-in words are listed with their English
        # (editor/translation_table.py), and any key of the project's own can be added
        F(
            "entries",
            "Translations",
            "translations",
            default=(),
            fields=(F("key", "Key", "text", default=""), F("text", "Text", "text", default="")),
        ),
    ),
    "message_settings": (
        F("settings_id", "Settings ID", "id"),
        F(
            "macros",
            "Macros",
            "table",
            default=(),
            fields=(F("name", "Name", "text", default=""), F("text", "Text", "text", default="")),
            help="Macros (\\M[name])",
        ),
        F("currency_id", "Currency", "text", default="gold", help="Currency Shown by \\G and \\$"),
        F("currency_label", "Currency Label", "text", default=""),
        F("backlog_limit", "Log Size", "int", default=0, help="Message Log Size (0 = no log)"),
        F("default_locale", "Default Locale", "text", default=""),
        # how a dialogue line's portrait shows: a face inside the window or a figure above it
        F("portrait_style", "Portrait Style", "choice", choices=("face", "bust"), default="face"),
        F(
            "portrait_size",
            "Portrait Size",
            "int",
            default=0,
            help="Portrait Size (px, 0 = automatic)",
        ),
        F(
            "icons",
            "Icons for \\I[n]",
            "table",
            default=(),
            fields=(
                F("number", "Number", "text", default="1"),
                F("icon_id", "Icon", "icon", default=""),
            ),
        ),
    ),
    "music_tracks": (
        F("track_id", "Track ID", "id"),
        F("name", "Name", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        F("asset_id", "Audio Asset", "text", default=""),
        F(
            "unlock_switch",
            "Unlock Switch",
            "text",
            default="",
            help="Unlock Switch (blank = always open)",
        ),
        F("note", "Note", "text", default=""),
    ),
    "credits_pages": (
        F("page_id", "Page ID", "id"),
        F("title", "Title", "text", default=""),
        F("lines", "Lines", "multiline", default="", help="Lines (one per line)"),
        F("order", "Order", "int", default=0),
    ),
    "battle_options": (
        F("options_id", "Options ID", "id"),
        F(
            "auto_key",
            "Auto-Battle Key",
            "bool",
            default=False,
            help="T Key Plays The Turn (auto-battle)",
        ),
        F(
            "weak_below",
            "Weak Pose Below",
            "float",
            default=0.0,
            help="Weak Pose Below Health (0-1, 0 = never)",
        ),
    ),
    "ability_loadout_rules": (
        F("rules_id", "Rules ID", "id"),
        F("capacity", "Ability Slots", "int", default=4),
        F(
            "capacity_by_level",
            "Slots by Level",
            "amounts",
            default={},
            help="Slots From Level (level and slots)",
        ),
        F(
            "limited_sources",
            "Limited Sources",
            "string_list",
            choices=(  # where an ability can come from (CharacterState's grants)
                ("learned", "Learned (taught, bought, read)"),
                ("class", "Jobs"),
                ("intrinsic", "The character's own"),
                ("progression", "Level-ups"),
                ("allocation", "Skill tree"),
                ("equipment", "Equipment"),
                ("equipment_growth", "Equipment growth"),
                ("attachment", "Attachments"),
                ("passive", "Passives"),
            ),
            default=("learned",),
            help="Abilities from these places need a slot to be used; the rest always can.",
        ),
        F("always_usable", "Always Usable Abilities", "ref_list", source="abilities", default=()),
    ),
    "menu_entries": (
        F("entry_id", "Entry ID", "id"),
        F("label", "Menu Label", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        F("event_program_id", "Event Program", "ref", source="event_programs"),
        F(
            "visible_switch",
            "Visible Switch",
            "text",
            default="",
            help="Shown While Switch Is On (empty: always)",
        ),
        F(
            "enabled_switch",
            "Enabled Switch",
            "text",
            default="",
            help="Usable While Switch Is On (empty: always)",
        ),
        F("order", "Order", "int", default=0),
    ),
    "menu_rules": (  # the pause menu (D96: the pages' settings moved to Menu Pages)
        F("rules_id", "Rules ID", "id"),
        F("display_name", "Name", "text", default=""),
        F(
            "pause_entries",
            "Pause Menu",
            "pause_order",
            source="pause_entries",
            hidden_key="pause_hidden",
            default=(),
            help="Every entry of the pause menu as the game lists it. Untick an entry to hide"
            " it; drag it up or down to move it. Status and Items open the Menu Pages status"
            " and items; every other menu page (Page: …) and Pause Menu Entry (Entry: …) is"
            " an entry of its own. A grey entry needs something the game does not have yet;"
            " it shows once the game has it. A page added later takes its place in the"
            " engine's order: after Items.",
        ),
    ),
    "menu_pages": (  # a page of the game menu built from blocks (D96)
        F("page_id", "Page ID", "id"),
        F("display_name", "Name", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        F(
            "blocks",
            "Page Blocks",
            "table",
            fields=_MENU_BLOCK,
            default=(),
            help="What the page shows, each block in its place: left or right column, or the"
            " full width across the top. A block keeps its height; blocks without one share"
            " what is left of their column. The page status is the pause menu's Status, items"
            " its Items; any other page is a pause entry of its own.",
        ),
    ),
    "doodads": (
        F("doodad_id", "Doodad ID", "id"),
        F("sprite_sheet_asset_id", "Sprite Sheet", "text", default=""),
        F("frame", "Frame", "int", default=0),
        F("solid_width", "Solid Width", "float", default=0.0, help="Solid Width (0 = none)"),
        F("solid_height", "Solid Height", "float", default=0.0),
        F("solid_offset_y", "Solid Offset Y", "float", default=0.0),
        F("layer", "Layer", "int", default=0),
        F("depth", "Depth", "float", default=0.0),
        F("snap", "Snap", "float", default=0.0, help="Snap to Grid (0 = free)"),
        F("tags", "Properties", "string_list", default=()),
    ),
}
FORMS.update(D26_FORMS)

# every record's own Note (the database's author_notes): for the people making the game, never
# shown in it; the pause menu's records are edited on their own page and keep theirs out
NOTE = "author_note"
NOTE_FIELD = F(NOTE, "Note", "multiline", default="")
for _kind in FORMS:
    if _kind not in ("menu_rules", "menu_pages", "menu_entries"):
        FORMS[_kind] = (*FORMS[_kind], NOTE_FIELD)

# the description players read can be kept from them (the database's hidden_descriptions):
# a switch after the description of every kind the game shows one of
SHOWN = "description_shown"
SHOWN_FIELD = F(
    SHOWN,
    "Shown",
    "bool",
    default=True,
    help="Ticked: the game shows the description. Unticked: it stays in the editor.",
)
for _kind in (
    "stat_definitions", "tag_definitions", "equipment_slots", "quests", "achievements",
    "quest_boards", "gacha_banners",
):  # fmt: skip
    _at = next(i for i, f in enumerate(FORMS[_kind]) if f.key == "description") + 1
    FORMS[_kind] = (*FORMS[_kind][:_at], SHOWN_FIELD, *FORMS[_kind][_at:])


def _stat_label(db, stat_id, labels=None):
    rule = db.stat_definitions.get(stat_id) or db.derived_stats.get(stat_id)
    name = getattr(rule, "display_name", "") if rule is not None else ""
    name = name or (labels or {}).get(stat_id, "")
    return f"{name} ({stat_id})" if name and name != stat_id else stat_id


def _dict_rows(mapping, key_name, value_name):
    return [{key_name: k, value_name: v} for k, v in dict(mapping or {}).items()]


def _rows_dict(rows, key_name, value_name):
    return {r[key_name]: r[value_name] for r in rows or () if str(r.get(key_name, "")).strip()}


def _encode_extension(data):
    data = dict(data)
    data["mastery"] = [
        {"ability_id": k, "thresholds": [str(x) for x in v]}
        for k, v in dict(data.get("mastery", {})).items()
    ]
    return data


def _decode_extension(data):
    data = dict(data)
    data["mastery"] = {
        r["ability_id"]: [int(x) for x in r.get("thresholds", ())]
        for r in data.get("mastery", ())
        if r.get("ability_id")
    }
    data["use_limits"] = {k: int(v) for k, v in dict(data.get("use_limits", {})).items()}
    return data


def _encode_stat(data):
    """``set_on`` as switches: Grows with Level (``classes`` underneath) and Base Stats, a
    tick per record kind (actors, enemies)."""
    data = dict(data)
    places = list(data.pop("set_on", None) or ())
    data["grows_with_level"] = "classes" in places
    data["base_stats"] = {x: x in places for x in SET_ON if x != "classes"}
    return data


def _decode_stat(data):
    data = dict(data)
    ticked = dict(data.pop("base_stats", None) or {})
    if data.pop("grows_with_level", False):
        ticked["classes"] = True
    data["set_on"] = [x for x in SET_ON if ticked.get(x)]  # actors, classes, enemies
    return data


def _encode_levels(data):
    data = dict(data)
    data["map_levels"] = [
        {"map_id": k, "lowest": v[0], "highest": v[1]}
        for k, v in dict(data.get("map_levels", {})).items()
    ]
    return data


def _decode_levels(data):
    data = dict(data)
    data["map_levels"] = {
        r["map_id"]: [r["lowest"], r["highest"]] for r in data.get("map_levels", ()) if r["map_id"]
    }
    return data


def _encode_text_map(field, key_name, value_name):
    def encode(data):
        data = dict(data)
        data[field] = _dict_rows(data.get(field), key_name, value_name)
        return data

    return encode


def _decode_text_map(field, key_name, value_name):
    def decode(data):
        data = dict(data)
        data[field] = _rows_dict(data.get(field), key_name, value_name)
        return data

    return decode


def _encode_message_settings(data):
    data = _encode_text_map("macros", "name", "text")(data)
    return _encode_text_map("icons", "number", "icon_id")(data)


def _decode_message_settings(data):
    data = _decode_text_map("macros", "name", "text")(data)
    return _decode_text_map("icons", "number", "icon_id")(data)


def _encode_credits(data):
    data = dict(data)
    data["lines"] = "\n".join(data.get("lines", ()))
    return data


def _decode_credits(data):
    data = dict(data)
    data["lines"] = [x for x in str(data.get("lines", "")).split("\n")]
    while data["lines"] and not data["lines"][-1].strip():
        data["lines"].pop()
    return data


def _condition_value(text):
    text = str(text).strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def _condition_row(c):
    """A condition as form rows (its value as text: true, false, 3)."""
    value = c.get("value", True)
    value = str(value).lower() if isinstance(value, bool) else str(value)
    return {
        "source": c.get("source", "switch"),
        "name": c.get("name", ""),
        "operator": c.get("operator", "=="),
        "value": value,
    }


def _condition_from_row(row):
    name = str(row.get("name", "")).strip()
    if not name:
        return None  # an empty row is left out
    text = str(row.get("value", "")).strip()
    return {
        "source": row.get("source") or "switch",
        "name": name,
        "operator": row.get("operator") or "==",
        "value": _condition_value(text) if text else True,
    }


def _encode_shop(data):
    data = copy.deepcopy(data)
    for entry in data.get("entries", ()):
        entry["visible_when"] = [_condition_row(c) for c in entry.get("visible_when", ())]
        entry["price_rules"] = [
            {
                "buy_multiplier": float(r.get("buy_multiplier", 1.0)),
                "sell_multiplier": float(r.get("sell_multiplier", 1.0)),
                "conditions": [_condition_row(c) for c in r.get("conditions", ())],
            }
            for r in entry.get("price_rules", ())
        ]
    return data


def _decode_shop(data):
    data = copy.deepcopy(data)
    for entry in data.get("entries", ()):
        rows = entry.get("visible_when", ())
        entry["visible_when"] = [c for c in map(_condition_from_row, rows) if c]
        rules = []
        for rule in entry.get("price_rules", ()):
            conditions = [c for c in map(_condition_from_row, rule.get("conditions", ())) if c]
            rules.append(
                {
                    "buy_multiplier": float(rule.get("buy_multiplier", 1.0)),
                    "sell_multiplier": float(rule.get("sell_multiplier", 1.0)),
                    "conditions": conditions,
                }
            )
        entry["price_rules"] = rules
    return data


def _encode_refine(data):
    data = dict(data)
    data["success"] = ", ".join(f"{float(x):g}" for x in data.get("success", (1.0,)))
    return data


def _decode_refine(data):
    data = dict(data)
    text = str(data.get("success", "")).replace(";", ",")
    data["success"] = [float(x) for x in text.split(",") if x.strip()] or [1.0]
    return data


# kind id -> (record data -> form data, form data -> record data)
def _encode_pet_species(data):
    data = dict(data)
    curve = data.get("exp_curve") or {}
    data["exp_curve"] = ", ".join(f"{x:g}" for x in curve.get("cubic", ())) if curve else ""
    return data


def _decode_pet_species(data):
    data = dict(data)
    text = str(data.get("exp_curve") or "").strip()
    if not text:
        data.pop("exp_curve", None)
    else:
        parts = [float(x) for x in text.replace(",", " ").split()]
        if len(parts) != 4:
            raise ValueError("the experience curve needs four numbers a, b, c, d")
        data["exp_curve"] = {"cubic": parts}
    return data


def _encode_pet_rules(data):
    data = dict(data)
    data["stat_formulas"] = [
        {"stat": k, **v} for k, v in dict(data.get("stat_formulas", {})).items()
    ]
    data["gene_ranges"] = [
        {"prefix": k, "low": v[0], "high": v[1]}
        for k, v in dict(data.get("gene_ranges", {})).items()
    ]
    data["gene_sets"] = [
        {"prefix": k, "values": v}
        for k, sets in dict(data.get("gene_sets", {})).items()
        for v in sets
    ]
    return data


def _decode_pet_rules(data):
    data = dict(data)
    formulas = {}
    for row in data.get("stat_formulas", ()):
        row = dict(row)
        stat = str(row.pop("stat", "") or "*").strip() or "*"
        formulas[stat] = row
    data["stat_formulas"] = formulas
    data["gene_ranges"] = {
        r["prefix"]: [r["low"], r["high"]] for r in data.get("gene_ranges", ()) if r["prefix"]
    }
    sets = {}
    for row in data.get("gene_sets", ()):
        if row.get("prefix"):
            sets.setdefault(row["prefix"], []).append(dict(row.get("values") or {}))
    data["gene_sets"] = sets
    return data


def _encode_gacha(data):
    data = copy.deepcopy(data)
    for rarity in data.get("rarities", ()):  # the colour as "r, g, b" words
        rarity["color"] = ", ".join(str(int(v)) for v in rarity.get("color") or ())
    return data


def _decode_gacha(data):
    data = copy.deepcopy(data)
    for rarity in data.get("rarities", ()):
        text = str(rarity.get("color") or "").replace(";", ",")
        rarity["color"] = [int(float(v)) for v in text.split(",") if v.strip()] or None
    taken = {str(p.get("prize_id")) for p in data.get("prizes", ()) if p.get("prize_id")}
    for prize in data.get("prizes", ()):  # a new prize's id: made from what it gives
        if not str(prize.get("prize_id") or "").strip():
            base = str(prize.get("target_id") or "prize").strip() or "prize"
            key, n = base, 2
            while key in taken:
                key, n = f"{base}_{n}", n + 1
            prize["prize_id"] = key
            taken.add(key)
    return data


ADAPTERS = {
    "pet_species": (_encode_pet_species, _decode_pet_species),
    "pet_rules": (_encode_pet_rules, _decode_pet_rules),
    "refine_rules": (_encode_refine, _decode_refine),
    "shops": (_encode_shop, _decode_shop),
    "battle_extension_rules": (_encode_extension, _decode_extension),
    "enemy_level_rules": (_encode_levels, _decode_levels),
    "stat_definitions": (_encode_stat, _decode_stat),
    "locale_tables": (
        _encode_text_map("entries", "key", "text"),
        _decode_text_map("entries", "key", "text"),
    ),
    "message_settings": (_encode_message_settings, _decode_message_settings),
    "credits_pages": (_encode_credits, _decode_credits),
    "gacha_banners": (_encode_gacha, _decode_gacha),
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
        "pet_rules": lambda key, c: PetRules(key),
        "world_interactions": lambda key, c: WorldInteraction(key, key),
        "drop_tables": lambda key, c: DropTable(key, key),
        "inventory_rules": lambda key, c: InventoryRules(key, key),
        "menu_rules": lambda key, c: MenuRules(key, key),
        # status / items start as the engine draws them; any other page as a bag
        "menu_pages": lambda key, c: (
            default_pages(menu_rules(c.database)).get(key)
            or MenuPage(key, key, blocks=(MenuBlock("item_list"),))
        ),
        "battle_extension_rules": lambda key, c: BattleExtensionRules(key),
        "enemy_level_rules": lambda key, c: EnemyLevelRules(key),
        "map_rule_sets": lambda key, c: MapRuleSet(key),
        "durability_rules": lambda key, c: DurabilityRules(key),
        "refine_rules": lambda key, c: RefineRules(key),
        "disassembly_recipes": lambda key, c: DisassemblyRecipe(key),
        "workstations": lambda key, c: WorkstationDefinition(key, key),
        "quest_boards": lambda key, c: QuestBoardDefinition(key, key),
        "recruit_offices": lambda key, c: RecruitOfficeDefinition(key, key),
        "gacha_banners": lambda key, c: GachaBanner(
            key,
            key,
            rarities=[{"rarity_id": "common"}],
            prizes=[{"prize_id": "potion", "rarity": "common"}],
        ),  # fmt: skip
        "job_point_rules": lambda key, c: JobPointRules(key),
        "derived_stats": lambda key, c: DerivedStatRule(key, applies_to="all"),
        "stat_definitions": lambda key, c: StatDefinition(key),
        "tag_definitions": lambda key, c: TagDefinition(key),
        "equipment_slots": lambda key, c: EquipmentSlotDefinition(key),
        "new_game_plus_rules": lambda key, c: NewGamePlusRules(key),
        "locale_tables": lambda key, c: LocaleTable(key),
        "message_settings": lambda key, c: MessageSettings(key),
        "music_tracks": lambda key, c: MusicTrack(key, key, "audio_asset"),
        "credits_pages": lambda key, c: CreditsPage(key, key),
        "battle_options": lambda key, c: BattleOptions(key),
        "ability_loadout_rules": lambda key, c: AbilityLoadoutRules(key),
        "menu_entries": lambda key, c: MenuEntry(
            key, key, next(iter(sorted(c.project.event_programs.ids())), "program")
        ),
        "doodads": lambda key, c: DoodadDefinition(key, "sprite_sheet"),
    }


KINDS = (
    _Kind("shops", "Shops", "shops", "shop_id", ShopDefinition),
    _Kind("quests", "Quests", "quests", "quest_id", QuestDefinition),
    _Kind("factions", "Factions", "factions", "faction_id", FactionDefinition),
    _Kind("achievements", "Achievements", "achievements", "achievement_id", AchievementDefinition),
    _Kind("equipment_sets", "Equipment Sets", "equipment_sets", "set_id", EquipmentSetDefinition),
    _Kind("capture_rules", "Capture Rules", "capture_rules", "enemy_id", CaptureRule),
    _Kind("pet_species", "Pet Species", "pet_species", "species_id", PetSpeciesDefinition),
    _Kind("pet_rules", "Pet Rules (creature party)", "pet_rules", "rules_id", PetRules),
    _Kind(
        "world_interactions",
        "World Interactions",
        "world_interactions",
        "interaction_id",
        WorldInteraction,
    ),
    _Kind("drop_tables", "Drop Tables", "drop_tables", "table_id", DropTable),
    _Kind("inventory_rules", "Inventory Rules", "inventory_rules", "rules_id", InventoryRules),
    _Kind(
        "battle_extension_rules",
        "Battle Extras (taunt, steal, TP...)",
        "battle_extension_rules",
        "rules_id",
        BattleExtensionRules,
    ),
    _Kind("enemy_level_rules", "Enemy Levels", "enemy_level_rules", "rules_id", EnemyLevelRules),
    _Kind(
        "map_rule_sets", "Map Areas (regions, hazards)", "map_rule_sets", "rules_id", MapRuleSet
    ),
    _Kind(
        "durability_rules", "Equipment Durability", "durability_rules", "rules_id", DurabilityRules
    ),
    _Kind("refine_rules", "Weapon Refine (+N)", "refine_rules", "rules_id", RefineRules),
    _Kind(
        "disassembly_recipes", "Disassembly", "disassembly_recipes", "item_id", DisassemblyRecipe
    ),
    _Kind(
        "workstations",
        "Workstations (crafting)",
        "workstations",
        "station_id",
        WorkstationDefinition,
    ),  # fmt: skip
    _Kind("quest_boards", "Quest Boards", "quest_boards", "board_id", QuestBoardDefinition),
    _Kind(
        "recruit_offices",
        "Recruiting Offices",
        "recruit_offices",
        "office_id",
        RecruitOfficeDefinition,
    ),  # fmt: skip
    _Kind("gacha_banners", "Gacha Banners", "gacha_banners", "banner_id", GachaBanner),
    _Kind("job_point_rules", "Job Points", "job_point_rules", "rules_id", JobPointRules),
    _Kind("stat_definitions", "Stats", "stat_definitions", "stat_id", StatDefinition),
    _Kind("tag_definitions", "Properties", "tag_definitions", "tag_id", TagDefinition),
    _Kind(
        "equipment_slots", "Equipment Slots", "equipment_slots", "slot_id", EquipmentSlotDefinition
    ),
    _Kind(
        "derived_stats",
        "Stat Formulas (derived stats)",
        "derived_stats",
        "stat_id",
        DerivedStatRule,
    ),
    _Kind(
        "new_game_plus_rules", "New Game Plus", "new_game_plus_rules", "rules_id", NewGamePlusRules
    ),
    _Kind("locale_tables", "Translations", "locale_tables", "locale", LocaleTable),
    _Kind(
        "message_settings", "Message Settings", "message_settings", "settings_id", MessageSettings
    ),
    _Kind("music_tracks", "Music Room", "music_tracks", "track_id", MusicTrack),
    _Kind("credits_pages", "Credits", "credits_pages", "page_id", CreditsPage),
    _Kind("battle_options", "Battle Options", "battle_options", "options_id", BattleOptions),
    _Kind(
        "ability_loadout_rules",
        "Ability Slots",
        "ability_loadout_rules",
        "rules_id",
        AbilityLoadoutRules,
    ),
    _Kind("menu_entries", "Pause Menu Entries", "menu_entries", "entry_id", MenuEntry),
    _Kind("menu_rules", "Pause Menu", "menu_rules", "rules_id", MenuRules),
    _Kind("menu_pages", "Menu Pages", "menu_pages", "page_id", MenuPage),
    _Kind("doodads", "Doodads", "doodads", "doodad_id", DoodadDefinition),
)
# the order the Game Systems list shows them in (D90): the characters and their stats first,
# then their gear, battles, the party, the world, and menus and presentation last
KIND_ORDER = (
    *("stat_definitions", "derived_stats", "tag_definitions", "job_point_rules"),
    "ability_loadout_rules",
    *("menu_rules", "menu_pages", "menu_entries"),
    *("equipment_slots", "equipment_sets", "refine_rules", "durability_rules"),
    *("disassembly_recipes", "battle_options", "battle_extension_rules", "enemy_level_rules"),
    *("capture_rules", "drop_tables", "pet_species", "pet_rules", "recruit_offices", "shops"),
    *("quests", "quest_boards", "factions", "achievements", "world_interactions"),
    *("map_rule_sets", "workstations", "gacha_banners", "inventory_rules"),
    *("message_settings", "music_tracks", "credits_pages", "locale_tables", "doodads"),
    "new_game_plus_rules",
)
KINDS = tuple(
    sorted(KINDS, key=lambda k: KIND_ORDER.index(k.kind_id) if k.kind_id in KIND_ORDER else 99)
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
        """The records' ids by their ``order`` when they have one (stats, D91), else by id."""
        store = self.store(kind_id)
        return tuple(sorted(store, key=lambda k: (getattr(store[k], "order", 0), k)))

    def get(self, kind_id, key):
        value = self.store(kind_id).get(str(key))
        if value is None:
            raise GameSystemsAuthoringError(f"unknown {kind_id}: {key}")
        return value

    def form_data(self, kind_id, key, *, info=True):
        """Canonical data of a record with every form field present; ``info=False`` leaves the
        worked-out ``info`` fields empty (a list naming its records: each one walks the whole
        project, a hundred tags took four seconds)."""
        data = self.get(kind_id, key).to_data()
        if kind_id in ADAPTERS:
            data = ADAPTERS[kind_id][0](data)
        data = _with_defaults(FORMS[kind_id], data)
        for f in FORMS[kind_id]:
            if f.kind == "info":  # worked out, never stored
                data[f.key] = self.info(kind_id, key) if info else ""
        if NOTE in data:
            data[NOTE] = self.note(kind_id, key)
        if SHOWN in data:
            from .record_notes import is_shown

            data[SHOWN] = is_shown(self.project, self.get(kind_id, key))
        return data

    def note(self, kind_id, key):
        """The makers' own note on a record (its form's Note box)."""
        from .record_notes import note_of

        return note_of(self.project, self.kind(kind_id).store, key)

    def info(self, kind_id, key):
        """The words of a record's read-only ``info`` field."""
        if kind_id == "stat_definitions":
            from .stat_usage import stat_usage

            return stat_usage(self.project, key)
        if kind_id == "tag_definitions":
            from .tag_usage import tag_usage

            return tag_usage(self.project, key)
        return ""

    def decode(self, kind_id, data):
        if isinstance(data, dict) and (NOTE in data or SHOWN in data):  # kept beside the record
            data = {k: v for k, v in data.items() if k not in (NOTE, SHOWN)}
        try:
            if kind_id in ADAPTERS:
                data = ADAPTERS[kind_id][1](data)
            return self.kind(kind_id).cls.from_data(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise GameSystemsAuthoringError(f"invalid {kind_id} record: {exc}") from exc

    @property
    def icon_library(self):
        from .image_tools import IconLibrary

        return IconLibrary(self.document)

    def _pause_entries(self):
        """``(id, name, why_not)`` of every pause entry in the engine's order: ``why_not`` what
        the game lacks for one it cannot show yet (``rpg.menu_pages.PAUSE_NEEDS``)."""
        from asteria.runtime.game_menus import PAUSE_WORDS

        from .i18n import translate

        db = self.database
        messages = db.message_settings
        backlog = messages[sorted(messages)[0]].backlog_limit if messages else 0
        usable = usable_pause_entries(
            db,
            loadouts=bool(db.equipment),  # the party's slots come with the game's equipment
            backlog=backlog,
            abilities=self.project.gameplay_library.abilities.ids(),
        )
        out = []
        for entry in engine_pause_order(db):
            if entry.startswith(PAGE_ENTRY):  # D96: the project's own pages
                name = db.menu_pages[entry[len(PAGE_ENTRY) :]].display_name
                name = translate("Page: {0}").format(name)
            elif entry.startswith(MENU_ENTRY):  # Pause Menu Entries
                found = db.menu_entries[entry[len(MENU_ENTRY) :]]
                name = translate("Entry: {0}").format(found.label or found.entry_id)
            else:
                name = translate(PAUSE_WORDS.get(entry, entry))
            out.append((entry, name, "" if entry in usable else PAUSE_NEEDS[entry]))
        return tuple(out)

    def references(self, source):
        """Choices for ``ref`` / ``ref_list`` form fields."""
        db = self.database
        if source == "abilities":
            return tuple(sorted(self.project.gameplay_library.abilities.ids()))
        if source == "event_programs":
            return tuple(sorted(self.project.event_programs.ids()))
        if source == "carry_parts":
            return tuple(CARRY)
        if source == "pause_entries":  # the whole pause menu (D87, D97): (id, name, why not)
            return self._pause_entries()
        if source == "stat_graphs":
            graphs = db.progression_graphs
            return (NO_STAT_GRAPH,) + tuple(
                (g, graphs[g].display_name or g) for g in sorted(graphs)
            )
        if source == "stats":  # the stat formulas' stats, then every stat the data names
            from .data_translation import _stat_labels, stat_ids

            defined = sorted(db.stat_definitions.values(), key=lambda d: (d.order, d.stat_id))
            known = [d.stat_id for d in defined]  # Game Systems ▸ Stats first (D91)
            known += [k for k in db.derived_stats if k not in known]
            known += [s for s in stat_ids(self.project) if s not in known]
            labels = _stat_labels(self.project)  # the character screen's names (D89)
            return tuple((s, _stat_label(db, s, labels)) for s in known)
        if source == "stat_columns":  # the Status page's stat table (D89)
            return tuple((c, STAT_COLUMN_WORDS[c]) for c in STAT_COLUMNS)
        if source == "outcome_checks":  # crit, land, block... (a detail line's chance, D89)
            return tuple(sorted(db.outcome_checks))
        if source == "goods":  # what a shop can sell: items, then equipment (D61)
            return tuple(sorted(db.items)) + tuple(sorted(db.equipment))
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

    def simulate_gacha(self, banner_id, pulls=10000, seed=0):
        """Draw ``pulls`` times from a fresh save (multi-pulls, the seed fixed): ``{"rarity":
        {id: count}, "prize": {id: count}, "pity": n, "guaranteed": n, "pulls": n}`` and the
        most pulls in a row without the pity rarity (``"longest_dry"``)."""
        banner = self.database.gacha_banners[str(banner_id)]
        runtime = GachaRuntime(banner)
        out = runtime.simulate(pulls, seed)
        import random

        from asteria.rpg.gacha import GachaState

        rng, state, dry, longest, done = random.Random(seed), GachaState(), 0, 0, 0
        top = banner.rank(banner.top_rarity())
        while done < pulls:
            for pull in runtime.pull(rng, state, min(banner.multi_count, pulls - done)):
                done += 1
                dry = 0 if banner.rank(pull.rarity) >= top else dry + 1
                longest = max(longest, dry)
        out["longest_dry"] = longest
        return out

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
        extra = []  # the note and Players See It: kept beside the record, not in it
        if isinstance(value, dict) and (NOTE in value or SHOWN in value):
            from .record_notes import note_command, shown_command

            value = dict(value)
            if NOTE in value:
                extra.append(note_command(self.project, kind.store, key, value.pop(NOTE)))
            if SHOWN in value:
                extra.append(shown_command(self.project, old, value.pop(SHOWN)))
        value = self._coerce(kind_id, value)
        if getattr(value, kind.key) != key:
            raise GameSystemsAuthoringError(f"{kind.key} cannot change during edit")
        self._validated(kind_id, key, value)
        command = _MapCommand(
            self.store(kind_id), key, value, old, f"Edit {kind.label[:-1]} {key}"
        )
        self.document.execute(_StepsCommand((command, *(x for x in extra if x is not None))))
        return value

    def duplicate(self, kind_id, key, new_key):
        # the stored record's own data, read back by its class: not through the form's
        # adapter, which expects the form's shape (a translation's rows, not its mapping)
        kind = self.kind(kind_id)
        data = self.get(kind_id, key).to_data()
        data[kind.key] = str(new_key)
        try:
            value = kind.cls.from_data(data)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise GameSystemsAuthoringError(f"could not copy {key}: {exc}") from exc
        return self.create(kind_id, value)

    def delete(self, kind_id, key):
        kind = self.kind(kind_id)
        key = str(key)
        old = self.get(kind_id, key)
        users = self.where_used(kind_id, key)
        if users:
            raise GameSystemsAuthoringError(f"{key} is used by " + ", ".join(users))
        command = _MapCommand(
            self.store(kind_id), key, None, old, f"Delete {kind.label[:-1]} {key}"
        )
        from .record_notes import note_command, shown_command

        extra = (  # its note and hidden mark go with it (undo: back)
            note_command(self.project, kind.store, key, ""),
            shown_command(self.project, old, True),
        )
        self.document.execute(_StepsCommand((command, *(x for x in extra if x is not None))))
        return old


__all__ = [
    "FORMS",
    "FormField",
    "GameSystemsAuthoringController",
    "GameSystemsAuthoringError",
    "KINDS",
    "new_row",
]
