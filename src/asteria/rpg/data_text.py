"""Project data in the player's language (D60): names and descriptions from the locale tables.

The text of the project's own records - actors, classes, skills, items, equipment, states,
enemies, quests, maps, pet species... - can differ per locale. A translation lives in the same
locale tables as the engine's built-in words (``rpg/built_in_text.py``, D52), under a key made
from the record's kind and id:

    data.<kind>.<id>.name          the record's display name
    data.<kind>.<id>.description   its description (skills, quests, objectives, achievements...)
    data.stat.<id>.short           a stat's short name (STR), D91
    data.map.<scene id>.name       a map's name
    data.speaker.<name>.name       who speaks a dialogue line (by the name written in the event)

Dialogue lines and choices are looked up by their own optional ``text_key`` (``events/dialogue``).

Nothing changes for a project without such keys: the lookups fall back to the text the record
carries, so old projects draw exactly as before, and the record data itself never changes. A
key in the default locale's table renames a record without touching it (like D52's renames).

``kind_of(record)`` names the kind from the record's class (``ItemDefinition`` -> ``item``), so
the screens call ``name_of(lookup, record)`` without knowing what they hold.
"""

from __future__ import annotations

# record class name -> (kind used in keys, the attribute holding the record's id)
KINDS = {
    "ActorDefinition": ("actor", "actor_id"),
    "ClassDefinition": ("class", "class_id"),
    "AbilityDefinition": ("ability", "ability_id"),
    "PassiveDefinition": ("passive", "passive_id"),
    "AttackDefinition": ("attack", "attack_id"),
    "StateDefinition": ("state", "state_id"),
    "ItemDefinition": ("item", "item_id"),
    "EquipmentDefinition": ("equipment", "equipment_id"),
    "AttachmentDefinition": ("attachment", "attachment_id"),
    "EquipmentSetDefinition": ("equipment_set", "set_id"),
    "EquipmentGrowthDefinition": ("growth", "growth_id"),
    "EquipmentGrowthNodeDefinition": ("growth_node", "node_id"),
    "RarityDefinition": ("rarity", "rarity_id"),
    "AffixDefinition": ("affix", "affix_id"),
    "EnemyDefinition": ("enemy", "enemy_id"),
    "QuestDefinition": ("quest", "quest_id"),
    "QuestObjective": ("objective", "objective_id"),
    "ShopDefinition": ("shop", "shop_id"),
    "CompositionRecipeDefinition": ("recipe", "recipe_id"),
    "PetSpeciesDefinition": ("pet_species", "species_id"),
    "ProgressionGraphDefinition": ("skill_tree", "graph_id"),
    "ProgressionNodeDefinition": ("skill_tree_node", "node_id"),
    "ProgressionTrackDefinition": ("track", "track_id"),
    "DerivedStatRule": ("stat", "stat_id"),
    "StatDefinition": ("stat", "stat_id"),
    "TagDefinition": ("tag", "tag_id"),
    "EquipmentSlotDefinition": ("slot", "slot_id"),
    "FactionDefinition": ("faction", "faction_id"),
    "AchievementDefinition": ("achievement", "achievement_id"),
    "WorldInteraction": ("interaction", "interaction_id"),
    "PartySetupDefinition": ("party", "party_id"),
    "DropTable": ("drop_table", "table_id"),
    "WorkstationDefinition": ("workstation", "station_id"),
    "WorkstationCategory": ("workstation_category", "category_id"),
    "QuestBoardDefinition": ("quest_board", "board_id"),
    "RecruitOfficeDefinition": ("recruit_office", "office_id"),
    "GachaBanner": ("gacha_banner", "banner_id"),
    "GachaRarity": ("gacha_rarity", "rarity_id"),
    "MenuRules": ("menu_rules", "rules_id"),
    "ItemCategory": ("item_category", "category_id"),
    "ItemFilter": ("item_filter", "filter_id"),
    "StatGroup": ("stat_group", "group_id"),
}
FIELDS = ("name", "description", "short")  # short: a stat's short name, STR (D91)
PREFIX = "data."


def kind_of(record):
    """``(kind, id)`` of a project record, or ``None`` for an object that is not one."""
    known = KINDS.get(type(record).__name__)
    if known is None:
        return None
    kind, attribute = known
    record_id = getattr(record, attribute, "")
    return (kind, str(record_id)) if record_id else None


def key(kind, record_id, field="name"):
    """The locale-table key of one text of one record: ``data.<kind>.<id>.<field>``."""
    if field not in FIELDS:
        raise ValueError(f"field must be one of {FIELDS}")
    return f"{PREFIX}{kind}.{record_id}.{field}"


def record_key(record, field="name"):
    """The key for ``record``'s name or description, or ``None`` when it is not a record."""
    known = kind_of(record)
    return None if known is None else key(*known, field)


def name_of(lookup, record, fallback=None):
    """``record``'s name in the current locale: the locale table's ``data.<kind>.<id>.name``
    (``lookup`` is ``Localizer.lookup``, or None), else its ``display_name``, else
    ``fallback``."""
    if record is None:
        return fallback
    own = getattr(record, "display_name", "") or fallback
    if lookup is None:
        return own
    found = record_key(record, "name")
    text = lookup(found) if found else None
    return text if text else own


def description_of(lookup, record, fallback=""):
    """``record``'s description in the current locale (like ``name_of``)."""
    if record is None:
        return fallback
    own = getattr(record, "description", "") or fallback
    if lookup is None:
        return own
    found = record_key(record, "description")
    text = lookup(found) if found else None
    return text if text else own


def text_by_key(lookup, text_key, own):
    """The text stored under ``text_key`` (a dialogue line's), else ``own``."""
    if not text_key or lookup is None:
        return own
    return lookup(str(text_key)) or own


def map_name(lookup, scene_id, own):
    """A map's name in the current locale (``data.map.<scene id>.name``), else ``own``."""
    if lookup is None or not scene_id:
        return own
    return lookup(key("map", scene_id)) or own


def speaker_name(lookup, speaker):
    """Who speaks, in the current locale (``data.speaker.<name>.name``), else as written."""
    if lookup is None or not speaker:
        return speaker
    return lookup(key("speaker", speaker)) or speaker


def is_data_key(text_key):
    return str(text_key).startswith(PREFIX)


def words(identifier):
    """An id in words for a name nobody gave: ``fire_attack`` -> ``Fire attack``."""
    return str(identifier).replace("_", " ").replace(".", " ").strip().capitalize()


def stat_name(lookup, stat_id, labels=None, definition=None):
    """A stat's or resource's name (``data.stat.<id>.name``, then ``data.resource.<id>.name``),
    else its stat definition's (D91), else the screen profile's label (``labels``), else the id
    in words (U1)."""
    stat_id = str(stat_id)
    if lookup is not None:
        found = lookup(key("stat", stat_id)) or lookup(key("resource", stat_id))
        if found:
            return found
    if definition is not None and definition.display_name != stat_id:
        return definition.display_name
    return (labels or {}).get(stat_id) or words(stat_id)


def stat_short_name(lookup, stat_id, labels=None, definition=None):
    """A stat's short name (``data.stat.<id>.short``, else its definition's ``STR``), else its
    name (``stat_name``) - for tight tables (D91)."""
    stat_id = str(stat_id)
    found = lookup(key("stat", stat_id, "short")) if lookup is not None else None
    if found:
        return found
    if definition is not None and definition.short_name:
        return definition.short_name
    return stat_name(lookup, stat_id, labels, definition)


def slot_name(lookup, slot_id, labels=None):
    """An equipment slot's name (``data.slot.<id>.name``), else the profile's, else words."""
    slot_id = str(slot_id)
    found = lookup(key("slot", slot_id)) if lookup is not None else None
    return found or (labels or {}).get(slot_id) or words(slot_id)


def quality_name(lookup, quality):
    """A crafting quality tier's name (``data.quality.<name>.name``), else as written (U4)."""
    quality = str(quality)
    found = lookup(key("quality", quality)) if lookup is not None and quality else None
    return found or quality


def credits_key(page_id, part):
    """The key of a credits page's title (``part`` "title") or line (``line1``, ``line2``...)."""
    return f"{PREFIX}credits.{page_id}.{part}"
