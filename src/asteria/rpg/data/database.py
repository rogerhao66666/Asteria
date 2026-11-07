"""The RPG database: every kind of record a project defines, by id, and its file format.

Each kind is one row of ``RECORD_KINDS``: the store it lives in (``db.items``), the class of its
records, the field that is its id, and the database version that added it. The store, its
``add_<kind>`` method, ``to_data`` and ``from_data`` all come from that row, so a new kind of
record is one new row (plus a version bump when older files must still load).
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from asteria.rpg.characters.actors import RpgActorRuntime
from asteria.rpg.data.references import reference_errors

VERSION = 30
VERSIONS = frozenset(range(1, VERSION + 1))


@dataclass(frozen=True, slots=True)
class RecordKind:
    """One kind of record the database keeps."""

    store: str  # the dict attribute and the key in the file ("items")
    kind: str  # add_<kind>
    module: str  # where the record class lives
    cls: str  # the record class
    key: str  # the record field that is its id in the store
    label: str  # how errors name it
    since: int = 25  # the database version that added it; older files lack it
    written: str = "always"  # "always" in to_data, or "when_set" (only when it has records)

    def record_class(self):
        return getattr(import_module(self.module), self.cls)


def _kind(store, kind, module, cls, key, label, since=25, written="always"):
    return RecordKind(store, kind, f"asteria.rpg.{module}", cls, key, label, since, written)


SET = "when_set"
# In loading order: (store, kind, module under asteria.rpg, class, id field, label, since,
# written). Files up to version 15 always hold every kind they know; later kinds may be absent.
# fmt: off
RECORD_KINDS = (
    _kind("classes", "class", "characters.actors", "ClassDefinition", "class_id", "class", 1),
    _kind("actors", "actor", "characters.actors", "ActorDefinition", "actor_id", "actor", 1),
    _kind("items", "item", "items.definitions", "ItemDefinition", "item_id", "item", 2),
    _kind(
        "equipment", "equipment", "items.definitions", "EquipmentDefinition", "equipment_id",
        "equipment", 2,
    ),
    _kind(
        "attachments", "attachment", "items.definitions", "AttachmentDefinition", "attachment_id",
        "attachment", 2,
    ),
    _kind("enemies", "enemy", "enemies.definitions", "EnemyDefinition", "enemy_id", "enemy", 3),
    _kind(
        "encounters", "encounter", "enemies.definitions", "EncounterDefinition", "encounter_id",
        "encounter", 3,
    ),
    _kind(
        "progression_tracks", "progression_track", "characters.progression",
        "ProgressionTrackDefinition", "track_id", "progression track", 4,
    ),
    _kind(
        "passives", "passive", "characters.abilities", "PassiveDefinition", "passive_id",
        "passive", 6,
    ),
    _kind(
        "ability_evolutions", "ability_evolution", "characters.abilities", "AbilityEvolutionRule",
        "rule_id", "ability evolution", 6,
    ),
    _kind(
        "progression_graphs", "progression_graph", "characters.progression_graph",
        "ProgressionGraphDefinition", "graph_id", "progression graph", 7,
    ),
    _kind(
        "equipment_growth", "equipment_growth", "items.growth", "EquipmentGrowthDefinition",
        "growth_id", "equipment growth", 8,
    ),
    _kind(
        "battle_resources", "battle_resource", "battle.resources", "BattleResourceDefinition",
        "resource_id", "battle resource", 9,
    ),
    _kind(
        "interaction_rules", "interaction_rule", "battle.interactions", "InteractionRule",
        "rule_id", "interaction rule", 10,
    ),
    _kind(
        "outcome_checks", "outcome_check", "battle.interactions", "OutcomeCheckDefinition",
        "check_id", "outcome check", 10,
    ),
    _kind(
        "battle_state_policies", "battle_state_policy", "battle.states", "BattleStatePolicy",
        "state_id", "battle state policy", 11,
    ),
    _kind(
        "formations", "formation", "battle.targeting", "FormationDefinition", "formation_id",
        "formation", 12,
    ),
    _kind(
        "battle_targeting", "battle_targeting", "battle.targeting", "BattleTargetingDefinition",
        "ability_id", "battle targeting", 12,
    ),
    _kind(
        "battle_objectives", "battle_objective", "battle.lifecycle", "BattleObjectiveDefinition",
        "objective_id", "battle objective", 13,
    ),
    _kind(
        "escape_rules", "escape_rule", "battle.lifecycle", "BattleEscapeRule", "rule_id",
        "escape rule", 13,
    ),
    _kind(
        "battle_schedulers", "battle_scheduler", "battle.scheduler", "BattleSchedulerDefinition",
        "scheduler_id", "battle scheduler", 14,
    ),
    _kind(
        "action_timings", "action_timing", "battle.timing", "ActionTimingDefinition",
        "ability_id", "action timing", 15,
    ),
    _kind(
        "action_sequences", "action_sequence", "battle.action_sequences",
        "ActionSequenceDefinition", "sequence_id", "action sequence", 16,
    ),
    _kind(
        "gauge_compositions", "gauge_composition", "battle.gauges", "GaugeCompositionDefinition",
        "composition_id", "gauge composition", 17,
    ),
    _kind(
        "reactions", "reaction", "battle.reactions", "ReactionDefinition", "reaction_id",
        "reaction", 18,
    ),
    _kind("enemy_ai", "enemy_ai", "enemies.ai", "EnemyAIDefinition", "ai_id", "enemy AI", 19),
    _kind(
        "action_transactions", "action_transaction", "battle.transactions",
        "ActionTransactionPolicy", "ability_id", "action transaction", 20,
    ),
    _kind(
        "composition_recipes", "composition_recipe", "items.crafting",
        "CompositionRecipeDefinition", "recipe_id", "composition recipe", 21,
    ),
    _kind(
        "party_setups", "party_setup", "characters.party_setup", "PartySetupDefinition",
        "party_id", "party setup", 22,
    ),
    _kind(
        "party_presentation_policies", "party_presentation_policy", "characters.party_setup",
        "PartyPresentationPolicyDefinition", "profile_id", "party presentation policy", 22,
    ),
    _kind(
        "enemy_behavior_bindings", "enemy_behavior_binding", "enemies.behavior",
        "EnemyBehaviorBinding", "enemy_id", "enemy behavior binding", 23,
    ),
    _kind(
        "battle_session_rules", "battle_session_rules", "battle.session_rules",
        "BattleSessionRules", "rules_id", "battle session rules", 24,
    ),
    _kind(
        "behavior_trees", "behavior_tree", "world.behavior_tree", "BehaviorTree", "tree_id",
        "behavior tree", 28,
    ),
    _kind("rarities", "rarity", "items.loot", "RarityDefinition", "rarity_id", "rarity", 30),
    _kind("affixes", "affix", "items.loot", "AffixDefinition", "affix_id", "affix", 30),
    _kind(
        "inventory_rules", "inventory_rules", "items.definitions", "InventoryRules", "rules_id",
        "inventory rules", 29,
    ),
    _kind(
        "drop_tables", "drop_table", "items.drop_tables", "DropTable", "table_id", "drop table",
        27,
    ),
    _kind(
        "world_interactions", "world_interaction", "world.interactions", "WorldInteraction",
        "interaction_id", "world interaction", 26,
    ),
    _kind("shops", "shop", "items.shops", "ShopDefinition", "shop_id", "shop"),
    _kind("quests", "quest", "world.quests", "QuestDefinition", "quest_id", "quest"),
    _kind(
        "equipment_sets", "equipment_set", "items.sets", "EquipmentSetDefinition", "set_id",
        "equipment set",
    ),
    _kind("factions", "faction", "world.record", "FactionDefinition", "faction_id", "faction"),
    _kind(
        "achievements", "achievement", "world.record", "AchievementDefinition", "achievement_id",
        "achievement",
    ),
    _kind(
        "capture_rules", "capture_rule", "battle.capture", "CaptureRule", "enemy_id",
        "capture rule",
    ),
    _kind(
        "pet_species", "pet_species", "characters.pets", "PetSpeciesDefinition", "species_id",
        "pet species", written=SET,
    ),
    _kind(
        "battle_extension_rules", "battle_extension_rules", "battle.extensions",
        "BattleExtensionRules", "rules_id", "battle extension rules", written=SET,
    ),
    _kind(
        "enemy_level_rules", "enemy_level_rules", "enemies.levels", "EnemyLevelRules", "rules_id",
        "enemy level rules", written=SET,
    ),
    _kind(
        "map_rule_sets", "map_rule_set", "world.map_rules", "MapRuleSet", "rules_id",
        "map rule set", written=SET,
    ),
    _kind(
        "durability_rules", "durability_rules", "items.durability", "DurabilityRules", "rules_id",
        "durability rules", written=SET,
    ),
    _kind(
        "refine_rules", "refine_rules", "items.refine", "RefineRules", "rules_id", "refine rules",
        written=SET,
    ),
    _kind(
        "disassembly_recipes", "disassembly_recipe", "items.disassembly", "DisassemblyRecipe",
        "item_id", "disassembly recipe", written=SET,
    ),
    _kind(
        "job_point_rules", "job_point_rules", "characters.job_points", "JobPointRules",
        "rules_id", "job point rules", written=SET,
    ),
    _kind(
        "derived_stats", "derived_stat", "characters.derived_stats", "DerivedStatRule", "stat_id",
        "derived stat", written=SET,
    ),
    _kind(
        "stat_definitions", "stat_definition", "data.stat_definitions", "StatDefinition",
        "stat_id", "stat definition", written=SET,
    ),
    _kind(
        "tag_definitions", "tag_definition", "data.tag_definitions", "TagDefinition", "tag_id",
        "tag definition", written=SET,
    ),
    _kind(
        "equipment_slots", "equipment_slot", "items.definitions", "EquipmentSlotDefinition",
        "slot_id", "equipment slot", written=SET,
    ),
    _kind(
        "new_game_plus_rules", "new_game_plus_rules", "world.new_game_plus", "NewGamePlusRules",
        "rules_id", "new game plus rules", written=SET,
    ),
    _kind(
        "locale_tables", "locale_table", "text.localization", "LocaleTable", "locale",
        "locale table", written=SET,
    ),
    _kind(
        "message_settings", "message_settings", "text.localization", "MessageSettings",
        "settings_id", "message settings", written=SET,
    ),
    _kind(
        "music_tracks", "music_track", "world.extras", "MusicTrack", "track_id", "music track",
        written=SET,
    ),
    _kind(
        "credits_pages", "credits_page", "world.extras", "CreditsPage", "page_id", "credits page",
        written=SET,
    ),
    _kind(
        "ability_loadout_rules", "ability_loadout_rules", "characters.ability_slots",
        "AbilityLoadoutRules", "rules_id", "ability loadout rules", written=SET,
    ),
    _kind(
        "battle_options", "battle_options", "world.extras", "BattleOptions", "options_id",
        "battle options", written=SET,
    ),
    _kind(
        "pet_rules", "pet_rules", "characters.pets", "PetRules", "rules_id", "pet rules",
        written=SET,
    ),
    _kind(
        "menu_entries", "menu_entry", "world.extras", "MenuEntry", "entry_id", "menu entry",
        written=SET,
    ),
    _kind(
        "menu_rules", "menu_rules", "menus.rules", "MenuRules", "rules_id", "menu rules",
        written=SET,
    ),
    _kind(
        "menu_pages", "menu_page", "menus.pages", "MenuPage", "page_id", "menu page", written=SET,
    ),
    _kind(
        "doodads", "doodad", "world.doodads", "DoodadDefinition", "doodad_id", "doodad",
        written=SET,
    ),
    _kind(
        "workstations", "workstation", "items.workstations", "WorkstationDefinition",
        "station_id", "workstation", written=SET,
    ),
    _kind(
        "quest_boards", "quest_board", "world.boards", "QuestBoardDefinition", "board_id",
        "quest board", written=SET,
    ),
    _kind(
        "recruit_offices", "recruit_office", "world.boards", "RecruitOfficeDefinition",
        "office_id", "recruiting office", written=SET,
    ),
    _kind(
        "gacha_banners", "gacha_banner", "world.gacha", "GachaBanner", "banner_id",
        "gacha banner", written=SET,
    ),
)
# fmt: on
KIND_BY_STORE = {kind.store: kind for kind in RECORD_KINDS}


class RpgDatabase:
    """Every record of a project's RPG data, by kind (``db.items``, ``db.quests``...) and id.

    Add records with ``add_<kind>`` (``add_item``, ``add_quest``...): each checks the record's
    class and refuses a second record with the same id.
    """

    def __init__(self):
        for kind in RECORD_KINDS:
            setattr(self, kind.store, {})
        # the makers' own notes: {store ("items", "tag_definitions"...): {record id: text}};
        # the editor's Note box on every record writes them, the game never reads them
        self.author_notes = {}
        # descriptions kept from players: {record kind ("item", "tag"...): {record id: True}};
        # the game reads such a record's description as empty (Players See It, unticked)
        self.hidden_descriptions = {}

    def add_record(self, kind, value):
        """Add ``value`` to the store of ``kind`` (a ``RecordKind`` or its store name)."""
        kind = KIND_BY_STORE[kind] if isinstance(kind, str) else kind
        cls = kind.record_class()
        if not isinstance(value, cls):
            raise TypeError(f"{kind.label} must be {cls.__name__}")
        store = getattr(self, kind.store)
        record_id = getattr(value, kind.key)
        if record_id in store:
            raise ValueError(f"duplicate {kind.label}: {record_id}")
        store[record_id] = value
        return value

    def loot_rarities(self):
        """The project's rarities, or the defaults when it authored none."""
        from asteria.rpg.items.loot import DEFAULT_RARITIES

        return dict(self.rarities) if self.rarities else {r.rarity_id: r for r in DEFAULT_RARITIES}

    def reference_errors(self):
        """Every dangling cross-record reference, one message each (Problems panel, EDT-15)."""
        return reference_errors(self)

    def validate(self):
        errors = self.reference_errors()
        if errors:
            raise ValueError("invalid RPG database references: " + "; ".join(errors))
        return True

    def build_actor(self, actor_id):
        actor = self.actors[str(actor_id)]
        definitions = {
            assignment.class_id: self.classes[assignment.class_id]
            for assignment in actor.enabled_class_assignments()
        }
        return RpgActorRuntime(actor, class_definitions=definitions)

    def description_hidden(self, kind, record_id):
        """Whether players never read record ``record_id``'s description (``kind``: its
        locale-table kind, ``data_text.kind_of``)."""
        return bool(self.hidden_descriptions.get(str(kind), {}).get(str(record_id)))

    def to_data(self):
        data = {"schema": "asteria.rpg.database", "version": VERSION}
        for kind in RECORD_KINDS:
            store = getattr(self, kind.store)
            if store or kind.written == "always":
                data[kind.store] = [store[k].to_data() for k in sorted(store)]
        notes = {
            store: dict(sorted(notes.items()))
            for store, notes in sorted(self.author_notes.items())
            if notes
        }
        if notes:
            data["author_notes"] = notes
        hidden = {
            kind: sorted(ids) for kind, ids in sorted(self.hidden_descriptions.items()) if ids
        }
        if hidden:
            data["hidden_descriptions"] = hidden
        return data

    @classmethod
    def from_data(cls, data):
        version = data.get("version")
        if data.get("schema") != "asteria.rpg.database" or version not in VERSIONS:
            raise ValueError("unsupported RPG database")
        result = cls()
        for kind in RECORD_KINDS:
            if version < kind.since:
                continue
            # files up to version 15 always hold every kind they know
            records = data[kind.store] if kind.since <= 15 else data.get(kind.store, ())
            record_class = kind.record_class()
            for x in records:
                result.add_record(kind, record_class.from_data(x))
        result.hidden_descriptions = {
            str(kind): {str(x): True for x in ids}
            for kind, ids in dict(data.get("hidden_descriptions") or {}).items()
        }
        result.author_notes = {
            str(store): {str(k): str(v) for k, v in dict(notes).items() if v}
            for store, notes in dict(data.get("author_notes") or {}).items()
        }
        return result


def _adder(kind):
    def add(self, value):
        return self.add_record(kind, value)

    add.__name__ = add.__qualname__ = f"add_{kind.kind}"
    add.__doc__ = f"Add a {kind.label} ({kind.cls}), keyed by its ``{kind.key}``."
    return add


for _record_kind in RECORD_KINDS:
    setattr(RpgDatabase, f"add_{_record_kind.kind}", _adder(_record_kind))
del _record_kind
