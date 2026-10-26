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
from asteria.rpg.items import EQUIP_OFFERS, INVENTORY_OVERFLOW, InventoryRules
from asteria.rpg.job_points import JobPointRules
from asteria.rpg.localization import LocaleTable, MessageSettings
from asteria.rpg.map_rules import MapRuleSet
from asteria.rpg.menu_rules import (
    ITEM_DETAILS,
    NO_STAT_GRAPH,
    PAUSE_ENTRIES,
    STAT_FORMATS,
    MenuRules,
)
from asteria.rpg.new_game_plus import CARRY, NewGamePlusRules
from asteria.rpg.pets import EXP_SHARES, LEVEL_UP_HEALS, PetRules
from asteria.rpg.quests import OBJECTIVE_KINDS
from asteria.rpg.refine import ON_FAIL, RefineRules
from asteria.rpg.workstations import WorkstationDefinition
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
    ``icon`` (a picture id picked from the project's icons or the built-in library),
    ``choice`` (``choices``), ``ref`` / ``ref_list`` (``source`` names a
    reference list, see :meth:`GameSystemsAuthoringController.references`),
    ``optional_ref`` (may be empty; ``empty_label`` names that choice), ``optional_int`` (None
    allowed). A reference list may hold ``(id, name)`` pairs: the form shows the name and keeps
    the id,
    ``string_list``, ``amounts`` (``{key: number}``, keys from ``source`` when
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


def F(key, label, kind, **values):  # noqa: N802 - short spec constructor
    return FormField(key, label, kind, **values)


_ITEM_CATEGORY = (  # a tab of the Items page (D87)
    F("category_id", "Tab ID", "text", default="all"),
    F("display_name", "Tab Name", "text", default=""),
    F("tags", "Items With Any of These Tags (none: every item)", "string_list", default=()),
    F("icon_id", "Icon", "icon", default=""),
)
_ITEM_FILTER = (  # what the Items page's F key narrows a tab to (D87)
    F("filter_id", "Filter ID", "text", default="usable"),
    F("display_name", "Filter Name", "text", default=""),
    F("tags", "Items With All of These Tags", "string_list", default=()),
    F("usable", "Only Items the Menu Can Use", "bool", default=False),
)
_STAT_GROUP = (  # a heading of the Status page's detail table (D89)
    F("group_id", "Group ID", "text", default="attack"),
    F("display_name", "Group Name", "text", default=""),
)
_STAT_LINE = (  # a stat of the Status page's detail table (D89)
    F("stat_id", "Stat", "ref", source="stats"),
    F("group", "Group ID (empty: Other)", "text", default=""),
    F(
        "format",
        "Written As (number; percent; range: attack's low ~ high; chance: a battle check's %)",
        "choice",
        choices=STAT_FORMATS,
        default="number",
    ),
    F("spread", "Range: Percent Either Way", "float", default=0.0),
    F("label", "Own Name (empty: the stat's)", "text", default=""),
    F(
        "check",
        "Chance: Battle Check (crit, land...)",
        "optional_ref",
        source="outcome_checks",
        empty_label="(none)",
        default="",
    ),
)
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
        F("evolutions", "Evolutions", "table", fields=_PET_EVOLUTION, default=()),
        F("learnset", "Learned Abilities", "table", fields=_PET_MOVE, default=()),
        F(
            "teachable",
            "Abilities Items Can Teach (items tagged teaches:<ability>)",
            "string_list",
            default=(),
        ),
        F("affinity_per_battle", "Affinity Gained Per Battle", "float", default=0.0),
        F("max_affinity", "Highest Affinity", "float", default=100.0),
        F("battle_unit", "Fights As Its Own Battle Unit", "bool", default=False),
        F("resources", "Battle Resources (maximums, e.g. vitality)", "amounts", default={}),
        F(
            "exp_curve",
            "Experience Curve a, b, c, d (a·L³ + b·L² + c·L + d; empty: linear)",
            "text",
            default="",
        ),
        F("exp_yield", "Experience Given When Beaten (× its level)", "float", default=0.0),
        F("capture_rate", "Capture Rate (rate mode)", "float", default=0.0),
        F("visual_profile_id", "Battle Visual (front)", "text", default=""),
        F(
            "back_visual_profile_id",
            "Battle Visual On The Player's Side (back)",
            "text",
            default="",
        ),
        F(
            "battle_abilities",
            "Abilities As A Battle Unit",
            "ref_list",
            source="abilities",
            default=(),
        ),
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
        F(
            "equip_offer",
            "Ask to Wear New Gear (never / a free place / always, swapping)",
            "choice",
            choices=EQUIP_OFFERS,
            default="never",
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
        # the quest board's card (U5)
        F("card_image", "Card Picture (quest board)", "icon", default=""),
        F("rank", "Card Rank (S, A, Bronze...)", "text", default=""),
        F("category", "Card Category (Hunt, Delivery...)", "text", default=""),
        F("repeatable", "Repeatable From a Board", "bool", default=False),
        F(
            "time_limit", "Time Limit Once Taken (minutes of play, 0 = none)", "float", default=0.0
        ),  # fmt: skip
    ),
    "quest_boards": (
        F("board_id", "Board ID (OPEN_QUEST_BOARD names it)", "id"),
        F("display_name", "Name", "text", default=""),
        F("description", "Description", "multiline", default=""),
        F(
            "quest_ids",
            "Quests on the Board (card order)",
            "ref_list",
            source="quests",
            default=(),
        ),  # fmt: skip
        F("open_switch", "Open Only While Switch Is On (empty = always)", "text", default=""),
        F("max_active", "Most Taken at Once (0 = no limit)", "int", default=0),
        F(
            "refresh_minutes",
            "Repeatable Quests Return After (minutes of play)",
            "float",
            default=0.0,
        ),  # fmt: skip
        F("card_style", "Cards", "choice", choices=CARD_STYLES, default="grid"),
        F("music", "Music While Open", "text", default=""),
        F(
            "layout",
            "Menu Layout (empty = quest_board.<id>, else quest_board)",
            "text",
            default="",
        ),  # fmt: skip
    ),
    "recruit_offices": (
        F("office_id", "Office ID (OPEN_RECRUIT names it)", "id"),
        F("display_name", "Name", "text", default=""),
        F("description", "Description", "multiline", default=""),
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
        F("party_limit", "Largest Party (0 = no limit)", "int", default=0),
        F("can_dismiss", "Members Can Be Sent Away Here", "bool", default=True),
        F("dismiss_refund", "Refund When Sent Away (0–1 of the price)", "float", default=0.0),
        F("experience_per_level", "Experience per Rolled Level", "float", default=1000.0),
        F("music", "Music While Open", "text", default=""),
        F("layout", "Menu Layout (empty = recruit.<id>, else recruit)", "text", default=""),
    ),
    "gacha_banners": (
        F("banner_id", "Banner ID (OPEN_GACHA names it)", "id"),
        F("display_name", "Name", "text", default=""),
        F("description", "Description", "multiline", default=""),
        F("banner_image", "Banner Picture", "icon", default=""),
        F("currency", "Currency", "text", default="gold"),
        F("single_cost", "Price of One Pull", "float", default=100.0),
        F("multi_cost", "Price of a Multi-Pull", "float", default=1000.0),
        F("multi_count", "Pulls in a Multi-Pull", "int", default=10),
        F(
            "rarities",
            "Rarities (lowest first)",
            "table",
            default=(),
            fields=(
                F("rarity_id", "Rarity ID", "text", default="common"),
                F("display_name", "Name", "text", default=""),
                F("color", "Colour (r, g, b)", "text", default="235, 235, 245"),
                F("chest_image", "Closed Chest", "icon", default=""),
                F("open_image", "Open Chest", "icon", default=""),
                F("open_sound", "Opening Sound", "text", default=""),
            ),
        ),
        F(
            "prizes",
            "Prizes",
            "table",
            default=(),
            fields=(
                F("prize_id", "Prize ID", "text", default="prize"),
                F("kind", "Kind", "choice", choices=PRIZE_KINDS, default="item"),
                F("target_id", "Item / Equipment / Character / Pet ID", "text", default=""),
                F("amount", "Amount", "int", default=1),
                F("weight", "Weight", "float", default=1.0),
                F("rarity", "Rarity ID", "text", default=""),
                F("featured", "Rate Up (featured)", "bool", default=False),
                F("duplicate_item", "Already Owned: Give Item Instead", "text", default=""),
                F("duplicate_amount", "Already Owned: How Many", "int", default=0),
            ),
        ),
        F("featured_multiplier", "Rate Up: Weight Times", "float", default=1.0),
        F("hard_pity", "Pity: Guaranteed by Pull (0 = none)", "int", default=0),
        F("pity_rarity", "Pity Rarity (empty = the highest)", "text", default=""),
        F("soft_pity_start", "Soft Pity: Starts After Pull (0 = none)", "int", default=0),
        F("soft_pity_step", "Soft Pity: Chance Added per Pull (0–1)", "float", default=0.0),
        F("multi_guarantee", "Multi-Pull: At Least One of Rarity", "text", default=""),
        F("open_switch", "Open Only While Switch Is On (empty = always)", "text", default=""),
        F("appear_seconds", "Chest Appears For (seconds)", "float", default=0.5),
        F("shake_seconds", "Chest Shakes For (seconds)", "float", default=0.8),
        F("open_seconds", "Chest Opens For (seconds)", "float", default=0.6),
        F("appear_sound", "Appear Sound", "text", default=""),
        F("shake_sound", "Shake Sound", "text", default=""),
        F("music", "Music While Open", "text", default=""),
        F("layout", "Menu Layout (empty = gacha.<id>, else gacha)", "text", default=""),
    ),
    "factions": (
        F("faction_id", "Faction ID", "id"),
        F("display_name", "Name", "text"),
        F("icon_id", "Icon", "icon", default=""),
        F("minimum", "Minimum", "float", default=-100.0),
        F("maximum", "Maximum", "float", default=100.0),
        F("initial", "Initial", "float", default=0.0),
        F("ranks", "Ranks (threshold → name)", "pairs", default=()),
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
        F("mode", "Chance Mode", "choice", choices=("linear", "rate"), default="linear"),
        F("base_chance", "Base Chance (0–1)", "float", default=0.25),
        F("low_health_bonus", "Low-Health Bonus", "float", default=0.5),
        F("capture_rate", "Capture Rate (rate mode; 0 = the species' own)", "float", default=0.0),
        F("divisor", "Rate Divisor", "float", default=255.0),
        F("item_id", "Consumed Item", "optional_ref", source="items", default=""),
        F("item_bonuses", "Capture Items And Their ×", "amounts", source="items", default={}),
        F("state_bonuses", "State Bonuses (state id and ×)", "amounts", default={}),
        F("shake_checks", "Shake Checks (0 = One Roll)", "int", default=0),
    ),
    "pet_rules": (
        F("rules_id", "Rules ID", "id"),
        F("party_size", "Party Size (0 = every owned pet)", "int", default=0),
        F("battle_slots", "Creatures On The Stage At Once (0 = all)", "int", default=1),
        F("storage", "Storage Box For The Rest", "bool", default=False),
        F("actors_fight", "Characters Fight Too", "bool", default=True),
        F("pets_decide_outcome", "No Creature Standing = Lost", "bool", default=False),
        F("switch_costs_turn", "Switching Costs The Turn", "bool", default=True),
        F("exp_share", "Experience From Foes", "choice", choices=EXP_SHARES, default="none"),
        F("exp_divisor", "Experience ÷", "float", default=1.0),
        F("exp_whole", "Whole Experience Points (rounded down)", "bool", default=False),
        F(
            "level_up_heal",
            "Health On Level Up",
            "choice",
            choices=LEVEL_UP_HEALS,
            default="delta",
        ),
        F("max_moves", "Moves A Creature Knows At Once (0 = unlimited)", "int", default=0),
        F("heal_restores_pp", "HEAL_PETS Restores Move Uses", "bool", default=True),
        F(
            "out_of_uses_ability",
            "When No Move Has Uses Left, Use",
            "optional_ref",
            source="abilities",
            default="",
        ),
        F("stat_formulas", "Stat Formulas", "table", fields=_STAT_FORMULA, default=()),
        F("gene_ranges", "Rolled Genes (whole numbers)", "table", fields=_GENE_RANGE, default=()),
        F(
            "gene_sets",
            "Gene Sets (one picked per creature)",
            "table",
            fields=_GENE_SET,
            default=(),
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
        F("damage_resource", "Resource That Counts as Damage (hp)", "text", default=""),
        F("taunt_tag", "Taunt Tag", "text", default=""),
        F("lifesteal_stat", "Life Steal Stat (0–1 on the actor)", "text", default=""),
        F("overkill_rate", "Overkill Reward Rate", "float", default=0.0),
        F("overkill_cap", "Overkill Cap (share of max)", "float", default=1.0),
        F("use_limits", "Uses per Battle", "amounts", source="abilities", default={}),
        F(
            "mastery",
            "Mastery Levels (uses needed, comma separated)",
            "table",
            default=(),
            fields=(
                F("ability_id", "Ability", "ref", source="abilities"),
                F("thresholds", "Uses for Each Level", "string_list", default=()),
            ),
        ),
        F("preemptive_chance", "Preemptive Chance (0–1)", "float", default=0.0),
        F("surprise_chance", "Surprise Chance (0–1)", "float", default=0.0),
        F(
            "steal_tables",
            "Steal Tables",
            "table",
            default=(),
            fields=(
                F("target_key", "Enemy ID or Tag", "text", default=""),
                F("once", "Once per Enemy", "bool", default=True),
                F("entries", "Can Steal", "table", fields=_STEAL_ENTRY, default=()),
            ),
        ),
        F("row_tag_prefix", "Row Tag Prefix (blank = off)", "text", default=""),
        F(
            "gains",
            "Resource Gains (TP-style)",
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
        ),
        F(
            "shared_gauges",
            "Party-Wide Gauges (id and maximum, saved with the world)",
            "amounts",
            default={},
        ),
    ),
    "enemy_level_rules": (
        F("rules_id", "Rules ID", "id"),
        F("stat_growth", "Stat Growth per Level", "amounts", default={}),
        F("resource_growth", "Resource Growth per Level", "amounts", default={}),
        F("reward_growth", "Reward Growth per Level", "float", default=0.0),
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
        F("party_level_offset", "Level vs Party (no map entry)", "int", default=0),
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
        F("region_layer", "Tile Layer Holding Regions", "text", default="regions"),
        F("crouch_visibility", "Visibility When Crouching", "float", default=1.0),
        F("still_visibility", "Visibility When Standing Still", "float", default=1.0),
        F("rules", "Area Rules", "table", fields=_AREA_RULE, default=()),
    ),
    "durability_rules": (
        F("rules_id", "Rules ID", "id"),
        F("max_durability", "Durability per Equipment", "amounts", source="equipment", default={}),
        F("default_max", "Durability of Other Equipment (0 = none)", "float", default=0.0),
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
        F("on_break", "When It Breaks", "choice", choices=ON_BREAK, default="disable"),
        F("repair_currency", "Repair Currency", "text", default=""),
        F("repair_cost_per_point", "Repair Cost per Point", "float", default=0.0),
    ),
    "refine_rules": (
        F("rules_id", "Rules ID", "id"),
        F("max_level", "Maximum Refine Level (+N)", "int", default=10),
        F(
            "equipment_tags",
            "Only Equipment With Any Tag (empty = all)",
            "string_list",
            default=(),
        ),
        F("bonuses", "Bonus per Level (stat = amount)", "amounts", default={}),
        F("operation", "Bonus Operation", "choice", choices=("add", "multiply"), default="add"),
        F("currency", "Cost Currency", "text", default=""),
        F("base_cost", "Cost of the First Attempt", "float", default=0.0),
        F("cost_growth", "Extra Cost per Level", "float", default=0.0),
        F("success", "Success Chance per Level (0-1, comma separated)", "text", default="1.0"),
        F("on_fail", "On Failure", "choice", choices=ON_FAIL, default="keep"),
        F("safe_until", "Levels Below This Never Fail", "int", default=0),
        F("materials", "Materials Used per Attempt", "amounts", source="items", default={}),
        F(
            "protect_item",
            "Protection Item (keeps the level on a failure)",
            "optional_ref",
            source="items",
            default="",
        ),
    ),
    "disassembly_recipes": (
        F("item_id", "Item / Equipment ID", "id"),
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
        F("station_id", "Station ID (recipes and OPEN_CRAFTING name it)", "id"),
        F("display_name", "Name", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        F("description", "Description", "multiline", default=""),
        F(
            "categories",
            "Tabs (recipe categories)",
            "table",
            default=(),
            fields=(
                F("category_id", "Tab ID", "text", default="tab"),
                F("display_name", "Name", "text", default=""),
                F("tags", "Recipe Tags (empty = every recipe left)", "string_list", default=()),
                F("icon_id", "Icon", "icon", default=""),
            ),
        ),
        F("show_undiscovered", "Show Undiscovered Recipes as ???", "bool", default=True),
        F("max_quantity", "Most Made at Once", "int", default=99),
        F("disassembly", "Disassembly Tab", "bool", default=False),
        F(
            "disassembly_tags",
            "Break Down Only Items With Any Tag (empty = all)",
            "string_list",
            default=(),
        ),
        F("craft_sound", "Success Sound", "text", default=""),
        F("fail_sound", "Failure Sound", "text", default=""),
        F("success_image", "Picture Shown After a Success", "icon", default=""),
        F("success_seconds", "Picture Shown For (seconds)", "float", default=0.6),
        F("music", "Music While Open", "text", default=""),
        F("layout", "Menu Layout (empty = crafting.<station>, else crafting)", "text", default=""),
    ),
    "job_point_rules": (
        F("rules_id", "Rules ID", "id"),
        F("prefix", "Balance Prefix (jp -> jp.<class>)", "text", default="jp"),
        F("per_battle", "Points per Battle", "float", default=0.0),
        F("per_enemy", "Points per Defeated Enemy", "float", default=0.0),
        F("secondary", "Share for Each Extra Class (0–1)", "float", default=0.5),
    ),
    "derived_stats": (
        F("stat_id", "Stat (the one computed)", "id"),
        F("display_name", "Name", "text", default=""),
        F("terms", "Read From (stat: coefficient)", "amounts", default={}),
        F("base", "Base Amount", "float", default=0.0),
        F("minimum", "Never Below", "float", default=0.0),
        F("maximum", "At Most (0 = no cap)", "float", default=0.0),
        F(
            "applies_to",
            "Used By",
            "choice",
            choices=("actors", "enemies", "all"),
            default="actors",
        ),
        F("order", "Order (lower runs first)", "int", default=0),
        F("description", "Description", "multiline", default=""),
    ),
    "new_game_plus_rules": (
        F("rules_id", "Rules ID", "id"),
        F("carry", "Carried Over", "ref_list", source="carry_parts", default=()),
        F("carry_switches", "Switch Prefixes That Stay On", "string_list", default=()),
        F("level_cap", "Level Cap (0 = none)", "int", default=0),
        F("keep_currency_share", "Share of Currency Kept (0–1)", "float", default=1.0),
    ),
    "locale_tables": (
        F("locale", "Locale (fr, zh-TW ...)", "id"),
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
            "Macros (\\M[name])",
            "table",
            default=(),
            fields=(F("name", "Name", "text", default=""), F("text", "Text", "text", default="")),
        ),
        F("currency_id", "Currency Shown by \\G and \\$", "text", default="gold"),
        F("currency_label", "Currency Label", "text", default=""),
        F("backlog_limit", "Message Log Size (0 = no log)", "int", default=0),
        F("default_locale", "Default Locale", "text", default=""),
        # how a dialogue line's portrait shows: a face inside the window or a figure above it
        F("portrait_style", "Portrait Style", "choice", choices=("face", "bust"), default="face"),
        F("portrait_size", "Portrait Size (px, 0 = automatic)", "int", default=0),
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
        F("unlock_switch", "Unlock Switch (blank = always open)", "text", default=""),
        F("note", "Note", "text", default=""),
    ),
    "credits_pages": (
        F("page_id", "Page ID", "id"),
        F("title", "Title", "text", default=""),
        F("lines", "Lines (one per line)", "multiline", default=""),
        F("order", "Order", "int", default=0),
    ),
    "battle_options": (
        F("options_id", "Options ID", "id"),
        F("auto_key", "T Key Plays The Turn (auto-battle)", "bool", default=False),
        F("weak_below", "Weak Pose Below Health (0-1, 0 = never)", "float", default=0.0),
    ),
    "ability_loadout_rules": (
        F("rules_id", "Rules ID", "id"),
        F("capacity", "Ability Slots", "int", default=4),
        F("capacity_by_level", "Slots From Level (level and slots)", "amounts", default={}),
        F(
            "limited_sources",
            "Limited Grant Sources (learned, class, equipment...)",
            "string_list",
            default=("learned",),
        ),
        F("always_usable", "Always Usable Abilities", "ref_list", source="abilities", default=()),
    ),
    "menu_entries": (
        F("entry_id", "Entry ID", "id"),
        F("label", "Menu Label", "text", default=""),
        F("icon_id", "Icon", "icon", default=""),
        F("event_program_id", "Event Program", "ref", source="event_programs"),
        F("visible_switch", "Shown While Switch Is On (empty: always)", "text", default=""),
        F("enabled_switch", "Usable While Switch Is On (empty: always)", "text", default=""),
        F("order", "Order", "int", default=0),
    ),
    "menu_rules": (
        F("rules_id", "Rules ID", "id"),
        F("display_name", "Name", "text", default=""),
        F(
            "pause_entries",
            "Pause Menu Pages, in Order (none ticked: the engine's order; drag to reorder)",
            "ref_list",
            source="pause_entries",
            default=(),
        ),
        F(
            "stat_graph",
            "Stat Points Are Spent In (empty: the graph tagged attributes; - : no +)",
            "optional_ref",
            source="stat_graphs",
            empty_label="(the graph tagged attributes)",
            default="",
        ),
        F(
            "stat_rows",
            "Detail Stats of the Status Page, in Order (none ticked: every stat formula)",
            "ref_list",
            source="stats",
            default=(),
        ),
        F(
            "stat_groups",
            "Detail Table Groups (Attack, Defence...: a heading each)",
            "table",
            fields=_STAT_GROUP,
            default=(),
        ),
        F(
            "stat_lines",
            "Detail Table Lines (a stat each, in its group; none: Detail Stats above)",
            "table",
            fields=_STAT_LINE,
            default=(),
        ),
        F("item_categories", "Item Page Tabs", "table", fields=_ITEM_CATEGORY, default=()),
        F("item_filters", "Item Page Filters (F)", "table", fields=_ITEM_FILTER, default=()),
        F(
            "item_details",
            "Item Details (panel: beside the list; button: Details / D opens it; off)",
            "choice",
            choices=ITEM_DETAILS,
            default="panel",
        ),
    ),
    "doodads": (
        F("doodad_id", "Doodad ID", "id"),
        F("sprite_sheet_asset_id", "Sprite Sheet", "text", default=""),
        F("frame", "Frame", "int", default=0),
        F("solid_width", "Solid Width (0 = none)", "float", default=0.0),
        F("solid_height", "Solid Height", "float", default=0.0),
        F("solid_offset_y", "Solid Offset Y", "float", default=0.0),
        F("layer", "Layer", "int", default=0),
        F("depth", "Depth", "float", default=0.0),
        F("snap", "Snap to Grid (0 = free)", "float", default=0.0),
        F("tags", "Tags", "string_list", default=()),
    ),
}
FORMS.update(D26_FORMS)


def _stat_label(db, stat_id, labels=None):
    rule = db.derived_stats.get(stat_id)
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
    return data


ADAPTERS = {
    "pet_species": (_encode_pet_species, _decode_pet_species),
    "pet_rules": (_encode_pet_rules, _decode_pet_rules),
    "refine_rules": (_encode_refine, _decode_refine),
    "shops": (_encode_shop, _decode_shop),
    "battle_extension_rules": (_encode_extension, _decode_extension),
    "enemy_level_rules": (_encode_levels, _decode_levels),
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
        "derived_stats": lambda key, c: DerivedStatRule(key),
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
    _Kind("menu_rules", "Menu Pages (status, items)", "menu_rules", "rules_id", MenuRules),
    _Kind("doodads", "Doodads", "doodads", "doodad_id", DoodadDefinition),
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
        data = self.get(kind_id, key).to_data()
        if kind_id in ADAPTERS:
            data = ADAPTERS[kind_id][0](data)
        return _with_defaults(FORMS[kind_id], data)

    def decode(self, kind_id, data):
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

    def references(self, source):
        """Choices for ``ref`` / ``ref_list`` form fields."""
        db = self.database
        if source == "abilities":
            return tuple(sorted(self.project.gameplay_library.abilities.ids()))
        if source == "event_programs":
            return tuple(sorted(self.project.event_programs.ids()))
        if source == "carry_parts":
            return tuple(CARRY)
        if source == "pause_entries":  # the built-in pages of the pause menu (D87)
            from asteria.runtime.game_menus import PAUSE_WORDS

            return tuple((e, PAUSE_WORDS.get(e, e)) for e in PAUSE_ENTRIES)
        if source == "stat_graphs":
            graphs = db.progression_graphs
            return (NO_STAT_GRAPH,) + tuple(
                (g, graphs[g].display_name or g) for g in sorted(graphs)
            )
        if source == "stats":  # the stat formulas' stats, then every stat the data names
            from .data_translation import _stat_labels, stat_ids

            known = list(db.derived_stats)
            known += [s for s in stat_ids(self.project) if s not in known]
            labels = _stat_labels(self.project)  # the character screen's names (D89)
            return tuple((s, _stat_label(db, s, labels)) for s in known)
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
        value = self._coerce(kind_id, value)
        if getattr(value, kind.key) != key:
            raise GameSystemsAuthoringError(f"{kind.key} cannot change during edit")
        self._validated(kind_id, key, value)
        self.document.execute(
            _MapCommand(self.store(kind_id), key, value, old, f"Edit {kind.label[:-1]} {key}")
        )
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
