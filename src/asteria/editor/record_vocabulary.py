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
    "stat_order": "stats",  # a screen profile's lead stats, shown by name (U1)
    "resource_order": "resources",
    "initiative_stat": "stats",
    "source_stat": "stats",
    "opponent_stat": "stats",
    "lifesteal_stat": "stats",
    "penetration_stat": "stats",
    "slot": "slots",
    "slot_id": "slots",
    "blocks_slots": "slots",
    "composition_id": "gauges",
    "rules_id": None,  # a record's own id
    "source_ability_id": "abilities",
    "result_ability_id": "abilities",
    "battle_ability": "abilities",
    "progression_track_id": "tracks",
    "evolution_equipment_id": "equipment",
    "fallback_state_id": "states",
    "initial_phase_id": None,
    "species_id": None,
}
# the same field name meaning something else in one kind of record: no list (the form offers
# the values that kind of record uses instead)
NOT_REFERENCES = {
    "combatant_visuals": ("state", "state_id", "fallback_state_id"),  # animation poses
    "formations": ("slot_id",),  # places in the formation, not equipment slots
    "parties": ("slot_id",),
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
    return (
        key == "tags"
        or key.endswith("_tags")
        or key.endswith("_tags_all")
        or (key.endswith("_tags_any"))
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
}


# -- the names and help shown beside fields ---------------------------------------------------
LABELS = {
    "expression": "Formula",  # a skill's damage, a stat formula (D94)
    "chance_expression": "Chance Formula",
    "initiative_expression": "Turn Order Formula",
    "final_damage_expression": "Final Damage Formula",
    "initiative_stat": "Turn Order Stat",
    "penetration_stat": "Penetration Stat",
    "display_name": "Name",
    "class_assignments": "Jobs",
    "base_stats": "Base Stats",
    "base_resources": "HP, MP and other resources",
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
    "blocks_slots": "Also takes (two-handed)",
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
    "duration": "Lasts",
    "power": "Power ×",
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
    # ability evolutions
    "source_ability_id": "Skill that changes",
    "result_ability_id": "Becomes",
    "progression_track_id": "Rank counted on (track)",
    "minimum_rank": "Needs rank at least",
    "retain_source": "Keep the original skill too",
    "required_tags": "Needs these tags",
    "blocked_tags": "Not when it has these tags",
    # skill trees
    "max_rank": "Most ranks",
    "rank_costs": "Cost per rank",
    "rewards": "Each rank gives",
    "prerequisites": "Needs all of",
    "any_prerequisites": "Needs one of",
    "exclusive_group": "Only one from group",
    "granted_capabilities": "Capabilities it gives",
    "unlocked_passives": "Passives it unlocks",
    "node_positions": "Positions in the graph view",
    "editor_view": "Opens as",
    # skills
    "menu_category": "Battle menu page",
    "input_workflow": "Input steps",
    "requires_pet": "Needs a pet",
    "requires_items": "Needs items (kept)",
    "item_costs": "Uses up items",
    "currency_costs": "Costs money",
    "gauge_costs": "Costs party gauge",
    "follow_tags": "Tags carried into follow-ups",
    "forms": "Forms (cast choices)",
    "battle_resource_gains": "Gives battle points",
    "commands": "World commands it runs",
    "concoct_station": "Concoction station",
    "cooldown_seconds": "Cooldown (seconds, real-time)",
    "move_while_acting": "Can move while acting (0-1)",
    "interrupts_actions": "Interrupts the target",
    "cooldown_formula": "Cooldown formula",
    "targeting": "Targets",
    "effects": "What it does",
    "use_effects": "When used",
    "destroyed_on_removal": "Destroyed when taken out",
    "timeline_id": "Animation timeline",
    # states
    "immune_target_tags": "Immune when the target has",
    "duration_multiplier": "Duration ×",
    "prevent_action": "Stops the holder from acting",
    "blocked_ability_tags": "Blocks skills tagged",
    "allowed_ability_tags": "Only skills tagged",
    "tick_trigger": "Counts down",
    "tick_amount": "Turns used per count",
    "remove_triggers": "Removed when",
    "interaction_tags": "Damage tags of its ticks",
    "target_override": "Makes it target",
    "interval": "Every (turns)",
    "growth": "Grows by",
    # targeting and timing
    "relation": "Who it targets",
    "selection_mode": "How targets are picked",
    "selection_count": "How many are picked",
    "adjacent_to_actor": "Only neighbours",
    "active_only": "Only fighters still standing",
    "startup": "Wind-up (s)",
    "cast_time": "Cast time (s)",
    "recovery": "Recovery (s)",
    "interruptible": "Can be interrupted",
    "interrupt_threshold": "Interrupted by damage over",
    "cost_commit": "Costs are paid",
    "interrupt_cost": "If interrupted, the cost is",
    # enemies and encounters
    "members": "Who is in it",
    "count": "How many",
    "weight": "How likely (weight)",
    "pet_species_id": "Pet species (a creature foe)",
    "level_max": "Level up to (0 = exactly the level)",
    "reserve": "Waits on the bench",
    "moves": "Moves (empty: what its species taught it)",
    "genes": "Genes (its own numbers)",
    "max_uses": "Uses before resting (0 = unlimited)",
    "experience": "Experience",
    "currencies": "Money",
    "loot": "Items it may drop",
    "phases": "Phases",
    "actions_per_ready": "Actions per turn",
    # resources and gauges
    "start_mode": "Starts at",
    "start_value": "Starting value",
    "end_mode": "After battle",
    "overflow_limit": "Can go over by",
    "subject_maximum": "Maximum comes from the fighter",
    "impacts": "What changes it",
    "thresholds": "When it reaches",
    "recipient": "Who it changes",
    "delta": "Changes by",
    "value_scale": "× the damage",
    "required_outcome_tags_all": "Only when the result has all of",
    "required_outcome_tags_any": "Only when the result has one of",
    "blocked_outcome_tags": "Not when the result has",
    # presentation
    "battlefield_visible": "Shown on the battlefield",
    "hud_visible": "Shown in the HUD",
    "battlefield_asset_id": "Battlefield picture",
    "portrait_asset_id": "Portrait",
    "small_portrait_asset_id": "Small portrait",
    "clip_role": "Animation to play",
    "fallback_state_id": "If missing, use",
    "persistent": "Stays after it plays",
    "z_order": "Drawn in front order",
    "page_size": "Rows per page",
    "playback_rate": "Playback speed",
    "transition_duration": "Blend time (s)",
}
HELP = {
    # formulas (D94): typed or built with the buttons; variables are declared stats only
    "expression": "The amount as a formula of source (the one acting) and target: source.power"
    " * 2 - target.defense. Only stats declared in Game Systems ▸ Stats can be read. Empty:"
    " the other fields are used.",
    "chance_expression": "The chance (0-1) as a formula: 0.95 + 0.003 * source.accuracy -"
    " 0.003 * target.evade. Only stats declared in Game Systems ▸ Stats can be read. Empty:"
    " the base chance and the stat terms are used. The lowest and highest chance still apply.",
    "initiative_expression": "Each fighter's turn order as a formula of self: self.speed +"
    " random() * 10. Only stats declared in Game Systems ▸ Stats can be read. Empty: the turn"
    " order stat is used.",
    "final_damage_expression": "The damage after every rule, as a formula of value (the damage"
    " so far), source and target: value * (0.9 + random() * 0.2). Only stats declared in Game"
    " Systems ▸ Stats can be read. Empty: the damage is kept as it is.",
    "display_name": "What players see.",
    "icon_id": "The picture in menus and lists. Pick one, or Browse for your own file.",
    "portrait_style": "Face: a dialogue line's portrait sits inside the message window. "
    "Bust: the figure stands above the window.",
    "portrait_size": "Face: its width and height in pixels. Bust: its height. 0 = fit the "
    "window (face) or 55% of the screen height (bust).",
    "hud_portraits": "Where a party card in battle shows its member's portrait (set on the "
    "member's Combatant Sprites record): left or right of the name and bars, above them (the "
    "card grows taller, into the room a full list or column has left), or off. A card without "
    "a portrait looks the same either way.",
    "hud_portrait_size": "The portrait's square in layout units. 0 = as tall as the card's "
    "rows. Beside the rows it is never taller than they are, and the name and bars always keep "
    "their room.",
    "stage_front_right": "How far in from the right edge the front column of the side on the "
    "right stands, as a share of the stage width. The same as Stage Front = follow it; 0 = the "
    "side stands against its edge.",
    "column_spacing": "How far apart neighbouring columns of one side stand, centre to centre, "
    "in layout units. 0 = automatic: far enough that their whole pictures never overlap. A "
    "column with a boss in it always keeps the automatic distance.",
    "column_spacing_right": "Column Spacing for the side standing on the right (the party, "
    "unless the game places it elsewhere). The same as Column Spacing = follow it.",
    "feet_on_ground": "Every fighter's feet stay on the ground, between Stage Top and the "
    "bottom of the stage, even where a Side-View Positions or Portrait Party Layout record puts "
    "them higher or lower. A sprite's own Offset Y still lifts a flyer. Off = a record's "
    "positions are used as written.",
    "class_assignments": "The jobs this character has; the first is the main job.",
    "base_stats": "Starting numbers before jobs, levels, gear and points. The list offers the "
    "stats Game Systems ▸ Stats sets on this kind of record (an actor: STR, DEX, INT, LUK, VIT, "
    "SPD).",
    "initiative_stat": "The stat that orders the turns: every round the highest goes first. "
    "An Initiative Expression, when given, decides instead.",
    "penetration_stat": "The attacker's stat (a percent) that ignores that share of the "
    "target's stats in damage formulas. Empty: no penetration.",
    "base_resources": "HP, MP and other pools at the start.",
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
    "blocks_slots": "Slots this piece also takes while worn, which must stay empty: a"
    " two-handed weapon names the sub-weapon slot. What happens to a piece already there is"
    " the inventory rules' When a Place Is Taken.",
    "rarity": "Its colour and rank name in the bag.",
    "multiplier": "Damage is multiplied by this (1 = unchanged, 2 = double).",
    "flat_delta": "Added to the damage before the multiplier.",
    "base_chance": "How often it happens before stats (100% = always).",
    "chance": "How often it happens (100% = always).",
    "duration": "How long it lasts: turns for a status, seconds for a hitbox or an effect.",
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
    "source_ability_id": "The skill the character has now.",
    "result_ability_id": "The stronger version that replaces it once the conditions are met.",
    "progression_track_id": "Optional: the track whose rank counts (empty = rank not checked).",
    "minimum_rank": "Rank needed on that track (only when a track is chosen).",
    "retain_source": "On: the character keeps both skills. Off: the new one replaces the old.",
    "required_tags": "The character must have all of these (a rune node in a tree gives one).",
    "blocked_tags": "Does nothing while any of these is present.",
    "max_rank": "How many times this node can be learned.",
    "rank_costs": "Points each rank costs (job points, stat points...).",
    "prerequisites": "Every one of these nodes must be learned first.",
    "any_prerequisites": "At least one of these nodes must be learned first.",
    "exclusive_group": "Only one node of the same group can be learned.",
    "granted_capabilities": "What anyone with this can do (wear plate, use bows...).",
    "menu_category": "The page of the battle menu it is listed on.",
    "requires_items": "Items the user must own; they are not used up.",
    "item_costs": "Items used up each time.",
    "forms": "Ways to cast it, chosen when it is used (fire / ice...).",
    "battle_resource_gains": "Points it gives when used (boost points, gauge...).",
    "prevent_action": "While this lasts, the holder loses its turns.",
    "tick_trigger": "When one turn of its duration is used up.",
    "target_override": "Confusion-like: the holder picks this kind of target instead.",
    "relation": "Allies, opponents, itself or anyone.",
    "selection_mode": "Manual (the player picks), all, random...",
    "members": "The foes in this fight and how many of each. A member can be a creature of a "
    "pet species instead of an enemy: give it a level (or a range), its moves and genes.",
    "pet_species_id": "A creature of this pet species fights here instead of an enemy "
    "definition: its stats come from the species at the level, its moves from the species' "
    "learnset. Leave the enemy empty.",
    "level_max": "Roll the creature's level between the level and this (0 = always the level).",
    "reserve": "This member waits on the bench and comes in when a stage slot of its side "
    "empties (Pet Rules: battle slots) - a trainer's team.",
    "moves": "The creature's moves here (empty: what its species taught it by its level).",
    "genes": "The creature's own numbers for the stat formulas (iv.attack, nature.speed...); "
    "empty = rolled by the Pet Rules.",
    "max_uses": "How many times the ability can be used before something restores it (a "
    "creature's move keeps its uses between battles; HEAL_PETS restores them). 0 = unlimited.",
    "weight": "Higher = more often, compared with the others.",
    "start_mode": "Full, empty or a fixed value when the battle starts.",
    "end_mode": "What happens to it when the battle ends.",
    "impacts": "Each rule changes the gauge when something happens (a weak hit...).",
    "thresholds": "What happens when the gauge reaches a value (Break...).",
    "clip_role": "Which animation of the sprite this pose plays.",
    "fallback_state_id": "Played when this pose has no animation.",
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


_SHARED_VOCABULARY = {}  # the last one built, by (project, revision)


def vocabulary_for(document):
    """The project's vocabulary, shared until the project changes (an edit, an undo, another
    project): every form used to rescan the whole database for its drop-downs."""
    project = getattr(document, "project", None)
    revision = getattr(document, "revision", None)
    if document is None or revision is None:
        return ProjectVocabulary(project)
    stamp = (id(project), revision)
    cached = _SHARED_VOCABULARY.get("last")
    if cached is None or cached[0] != stamp or cached[1].project is not project:
        cached = (stamp, ProjectVocabulary(project))
        _SHARED_VOCABULARY["last"] = cached
    return cached[1]


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
                label = getattr(value, "display_name", "") or words(key)
                yield Choice(key, label, getattr(value, "icon_id", "") or "")
        elif source == "states":
            for key in sorted(library.states._definitions):
                yield Choice(key, words(key))
        elif source == "items_and_equipment":
            yield from self.choices("items")
            yield from self.choices("equipment")
        elif source in ("classes", "actors", "items", "equipment", "attachments", "enemies",
                        "passives", "encounters"):  # fmt: skip
            if source == "actors":  # a party command's stand-in for whoever uses the skill
                yield Choice("@actor", "The one using the skill")
            yield from records(getattr(db, source))
        elif source == "graphs":
            yield from records(db.progression_graphs)
        elif source == "tracks":
            yield from records(db.progression_tracks)
        elif source == "resources":
            names = set(db.battle_resources)
            names.update(self.values_for("resource"))  # a skill's own pool (rage, focus...)
            names.update(self.values_for("resource_id"))
            for actor in db.actors.values():
                names.update(actor.base_resources)
            for enemy in db.enemies.values():
                names.update(enemy.resources)
            for name in sorted(names):
                yield Choice(name, _resource_label(name))
        elif source == "stats":  # Game Systems ▸ Stats first, by their order (D91)
            defined = getattr(db, "stat_definitions", {})
            first = [d.stat_id for d in sorted(defined.values(), key=lambda d: d.order)]
            rest = sorted((s for s in self.stats() if s not in defined), key=_stat_order)
            for name in (*first, *rest):
                record = defined.get(name)
                label = record.short if record is not None else _stat_label(name)  # STR, SPD
                yield Choice(name, label)
        elif source == "checks":
            for key in sorted(db.outcome_checks):
                yield Choice(key, words(key))
        elif source == "rarities":
            for rarity in sorted(db.loot_rarities().values(), key=lambda r: r.order):
                yield Choice(rarity.rarity_id, rarity.display_name or rarity.rarity_id)
        elif source == "drop_tables":
            for key in sorted(db.drop_tables):
                yield Choice(key, words(key))
        elif source == "growth":
            for key in sorted(db.equipment_growth):
                yield Choice(key, words(key))
        elif source == "gauges":
            for key in sorted(db.gauge_compositions):
                yield Choice(key, words(key))
        elif source == "scenes":
            for scene in project.scenes():
                yield Choice(scene.id, getattr(scene, "name", "") or scene.id)
        elif source == "slots":  # the defined equipment slots, then the ones gear names
            defined = sorted(db.equipment_slots.values(), key=lambda x: (x.order, x.slot_id))
            for slot in defined:
                yield Choice(slot.slot_id, slot.display_name or words(slot.slot_id))
            slots = {e.slot for e in db.equipment.values()} - set(db.equipment_slots)
            for name in sorted(slots):
                yield Choice(name, words(name))
        elif source == "clips":  # every animation name the project's sprite sheets have
            from .animation_editor_widget import clip_title

            names = set()
            for asset in project.assets.query(kind="sprite_sheet"):
                names.update(dict(asset.meta().get("clips", {}) or {}))
            for name in sorted(names):
                yield Choice(name, clip_title(name))
        elif source.startswith("assets:"):  # project assets of one kind, by their names
            kind = source.split(":", 1)[1]
            seen = set()
            for record in project.assets.records():
                if record.kind == kind and record.id not in seen:
                    seen.add(record.id)
                    yield Choice(record.id, record.name or words(record.id))
            for asset in project.assets.query(kind=kind):
                if asset.asset_id not in seen:
                    seen.add(asset.asset_id)
                    yield Choice(asset.asset_id, words(asset.asset_id.rsplit(".", 1)[-1]))
        elif source == "currencies":
            names = set(getattr(project.game_start, "currencies", {}) or {}) | {"gold"}
            for name in sorted(names):
                yield Choice(name, words(name))

    def description(self, source, key):
        """What a skill / item / state says about itself (shown under its picker)."""
        project = self.project
        if project is None or not key:
            return ""
        value = None
        if source == "abilities":
            library = project.gameplay_library.abilities
            value = library.get(key) if key in library.ids() else None
        elif source in ("items", "equipment", "classes", "states"):
            value = getattr(project.rpg_database, source, {}).get(key)
        return str(getattr(value, "description", "") or "")

    def names(self):
        """Display names by id of jobs, skills, states, items and gear (for tags in words)."""
        if "__names" not in self._cache:
            names = {}
            sources = ("classes", "abilities", "states", "items", "equipment", "enemies", "actors")
            for source in sources:
                for choice in self.choices(source):
                    names.setdefault(choice.value, choice.label)
            self._cache["__names"] = names
        return self._cache["__names"]

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
            names.update(getattr(db, "stat_definitions", {}))
            for record in (*db.equipment.values(), *db.attachments.values()):
                names.update(m.stat for m in record.modifiers)
        names.discard("")
        self._cache["__stats"] = names
        return names

    def base_stat_choices(self, record_kind, choices, held=()):
        """``choices`` narrowed to the stats Game Systems ▸ Stats sets on ``record_kind``
        (D91), in their order, then any other stat ``held`` already has; all of ``choices``
        when the project defines no stats."""
        from asteria.rpg.stat_definitions import set_on

        db = getattr(self.project, "rpg_database", None)
        wanted = set_on(getattr(db, "stat_definitions", {}), record_kind)
        if wanted is None:
            return choices
        by_id = {c.value: c for c in choices}
        keep = [*wanted, *(k for k in held if k not in wanted)]
        return tuple(by_id.get(k) or Choice(k, _stat_label(k)) for k in keep)

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
_RESOURCE_NAMES = {"vitality": "HP", "technique": "MP"}  # in the order a status screen reads
# short forms that stay in capitals whenever an id is turned into words
ACRONYMS = frozenset({
    "hp", "sp", "mp", "bp", "tp", "ap", "jp", "xp", "exp", "atb", "ai", "hud", "ui", "id",
    "vfx", "fx", "str", "dex", "int", "luk", "vit", "agi", "npc", "aoe", "ko", "dps", "rpg",
})  # fmt: skip


def words(text):
    """An id in words, short forms in capitals: ``bp_gain`` -> "BP Gain"."""
    out = []
    for word in str(text).replace("_", " ").split():
        out.append(word.upper() if word.lower() in ACRONYMS else word[:1].upper() + word[1:])
    return " ".join(out)


def _stat_order(name):
    """Stats in the order a status screen reads: the points the player spends (STR, DEX, INT,
    LUK, VIT), the core numbers, then elements and the rest alphabetically."""
    head = list(_STAT_NAMES) + ["vit"]
    if name in head:
        return (0, head.index(name), name)
    if name.endswith(("_attack", "_resist")):
        return (2, 0, name)
    return (1, 0, name)


def _stat_label(name):
    if name in _STAT_NAMES:
        return _STAT_NAMES[name]
    if name.endswith("_attack") or name.endswith("_resist"):
        element, kind = name.rsplit("_", 1)
        return f"{words(element)} {words(kind)} %"
    return words(name)


def _resource_label(name):
    return _RESOURCE_NAMES.get(name, words(name))


def resource_order(name):
    """Where a resource stands in a list: HP, then MP, then the rest as they come."""
    names = list(_RESOURCE_NAMES)
    return names.index(name) if name in names else len(names)


def label_for(key):
    """The name a field shows: ours, else its key in words without a trailing "ID" for a
    reference (``growth_id`` -> "Growth", it is a drop-down of names)."""
    from .authoring_hub_widget import field_label

    key = str(key)
    if key in LABELS:
        return LABELS[key]
    if key in _STAT_NAMES or key.endswith("_attack") or key.endswith("_resist"):
        return _stat_label(key)
    if key in _RESOURCE_NAMES:
        return _resource_label(key)
    if key.startswith("jp."):
        return f"Job Points ({words(key[3:])})"
    if key in _POINTS:
        return _POINTS[key]
    if key.endswith("_id") and REFERENCES.get(key):
        return field_label(key[:-3])
    return field_label(key)


_POINTS = {"ap": "Ability Points", "stat_points": "Stat Points", "skill_points": "Skill Points"}


def record_title(category, data, vocabulary, key=None):
    """A readable title for a record that has no name of its own (the list shows it):
    an evolution as "Fire Bolt → Fire Bolt (Echo)", a skill's targeting by the skill's name,
    a fighter's look by its fighter's name (Vaelor); else its id in words."""
    names = vocabulary.names() if vocabulary is not None else {}
    if not isinstance(data, dict):
        return words(key) if key else ""
    source, result = data.get("source_ability_id"), data.get("result_ability_id")
    if source and result:
        return f"{names.get(source, source)}  →  {names.get(result, result)}"
    ability = data.get("ability_id")
    if isinstance(ability, str) and ability in names:
        return names[ability]
    for field in ("display_name", "name", "label", "title"):
        if isinstance(data.get(field), str) and data[field]:
            return data[field]
    if key and str(key) in names:  # a record named after a fighter, a skill...
        return names[str(key)]
    return words(str(key).replace(".", " ")) if key else ""


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


# -- tags in words ------------------------------------------------------------------------------
_TAG_PREFIXES = (  # prefix -> how the rest reads
    ("capability.weapon.", "Can use: {} weapons"),
    ("capability.armor.", "Can wear: {} armour"),
    ("capability.", "Can: {}"),
    ("class.", "Job: {}"),
    ("job.", "Job tree: {}"),
    ("weak.", "Weak to {}"),
    ("resist.", "Resists {}"),
    ("absorb.", "Absorbs {}"),
    ("immune.", "Immune to {}"),
    ("damage.", "{} damage"),
    ("weapon.", "{} weapon blow"),
    ("equip.", "Equipment: {}"),
    ("status.", "Has status: {}"),
    ("state.", "In state: {}"),
    ("stance.", "Stance: {}"),
    ("trait.", "Trait: {}"),
    ("attune.", "Attuned to {}"),
    ("mastery.", "Mastery: {}"),
    ("weather.", "Weather: {}"),
    ("rune.", "Rune: {}"),
    ("roster.", "Party slot {}"),
    ("boost.", "Boosted: {}"),
    ("set.", "Set: {}"),
    ("tier.", "Tier {}"),
    ("form.", "Form: {}"),
    ("vigil.", "Vigil: {}"),
    ("action.", "Action: {}"),
    ("ai.", "AI: {}"),
)
_OUTCOMES = {
    "outcome.crit": "Result: critical hit",
    "outcome.weak": "Result: hit a weakness",
    "outcome.evade": "Result: dodged (miss)",
    "outcome.block": "Result: blocked",
    "outcome.guard": "Result: guarded",
}
_PLAIN_TAGS = {
    "boss": "Boss",
    "ability": "Is a skill",
    "magic": "Magic (a spell)",
    "support": "Support skill",
    "divine": "Divine skill",
    "follow_up": "Follow-up attack",
    "combo": "Combo",
    "consumable": "Used up when used",
    "unique": "Unique (one only)",
    "weapon": "Is a weapon",
    "actor.playable": "Playable character",
    "gem": "Gem",
    "card": "Card",
    "charm": "Charm",
}


def tag_label(tag, names=None):
    """A tag in words: ``capability.weapon.ring`` -> "Can use: Ring weapons", ``class.brave``
    -> "Job: Brave" (``names`` gives records' display names by id)."""
    tag = str(tag)
    names = names or {}
    if tag in _OUTCOMES:
        return _OUTCOMES[tag]
    if tag in _PLAIN_TAGS:
        return _PLAIN_TAGS[tag]
    for prefix, pattern in _TAG_PREFIXES:
        if tag.startswith(prefix):
            rest = tag[len(prefix) :]
            word = names.get(rest) or words(rest.replace(".", " · "))
            return pattern.format(word)
    if tag.startswith("outcome."):
        return "Result: " + tag[8:].replace("_", " ")
    for mark in (":", "."):  # "stage:vigil_portrait" -> "Stage: Vigil Portrait"
        if mark in tag:
            head, rest = tag.split(mark, 1)
            rest = names.get(rest) or words(rest.replace(".", " · ").replace(":", " · "))
            return f"{words(head)}: {rest}"
    return words(tag)


# -- triggers (moments in a battle) in words ----------------------------------------------------
TRIGGERS = {  # trigger id -> when it happens
    "battle.hit": "When a hit lands",
    "*": "Any moment",
    "battle.break": "When a shield breaks (Break)",
    "battle.overdrive": "When the gauge fills (Overdrive)",
    "battle.action": "When an action is used",
    "battle.turn": "When a turn starts",
    "rpg.battle.started": "When the battle starts",
    "rpg.battle.finished": "When the battle ends",
    "rpg.battle.round_started": "When a new round starts",
    "rpg.battle.round_ended": "When a round ends",
    "rpg.battle.turn_ready": "When its turn comes",
    "rpg.battle.turn_ended": "When its turn ends",
    "rpg.battle.turn_skipped": "When its turn is skipped",
    "rpg.battle.before_action": "Before an action",
    "rpg.battle.after_action": "After an action",
    "rpg.battle.action_cancelled": "When an action is cancelled",
    "rpg.battle.state_applied": "When a state is put on",
    "rpg.battle.state_removed": "When a state is taken off",
    "rpg.battle.state_expired": "When a state runs out",
    "rpg.battle.state_resisted": "When a state is resisted",
    "rpg.battle.combatant_revived": "When someone is revived",
    "rpg.battle.combatant_summoned": "When someone is summoned",
    "rpg.battle.combatant_removed": "When someone leaves the battle",
    "rpg.battle.escape_resolved": "When an escape is tried",
    "rpg.battle.mastery_up": "When a skill's mastery rises",
}


def is_trigger_field(key):
    key = str(key)
    return "trigger" in key or key in ("hook", "enter_hook", "exit_hook", "event_kind")


def trigger_label(trigger):
    """A trigger in words: ``rpg.battle.turn_ready`` -> "When its turn comes"."""
    trigger = str(trigger)
    if trigger in TRIGGERS:
        return TRIGGERS[trigger]
    words = trigger.removeprefix("rpg.").removeprefix("battle.").replace(".", " ")
    return "When: " + words.replace("_", " ")


CATEGORY_HELP.update(
    {
        "tracks": "Level-like tracks (job levels...) that count up with points.",
        "evolutions": "A skill turns into a stronger version when the character qualifies - "
        "usually a rune node in a skill tree gives the tag it needs. Example: Fire Bolt becomes "
        "Fire Bolt (Echo) once the Echo rune is learned.",
        "growth": "Weapons that grow with use: what each growth node unlocks.",
        "recipes": "Crafting and alchemy: what goes in, what comes out.",
        "parties": "The starting party and its order.",
        "formations": "Where party members stand.",
        "party_ui": "Rules for the party menu.",
        "ai": "How each foe picks its actions, and its boss phases.",
        "action_timelines": "Real-time field actions: wind-up, hit and recovery.",
        "attacks": "Real-time attacks: damage, range, knock-back.",
        "projectiles": "Shots that fly: speed, range, what they hit.",
        "rarities": "Loot rarity: colour, chance, how many bonuses.",
        "affixes": "Random bonuses loot can roll (prefixes and suffixes).",
        "resources": "Battle-only points: boost points, shields, gauges.",
        "targeting": "Who each skill can target and how targets are picked.",
        "schedulers": "Turn order: rounds, speed order or a timeline.",
        "timing": "Wind-up, casting and recovery time of skills.",
        "sequences": "Multi-step actions (combos) and their steps.",
        "reactions": "Counters and follow-ups: who reacts and with what.",
        "objectives": "How a battle is won or lost.",
        "escape": "The chance to run away from a fight.",
        "transactions": "When a skill's costs are paid, and refunds.",
        "session": "Battle-wide rules: knock-out, boost points, shields.",
        "combatant_visuals": "How each fighter looks: sprite, poses, size and place.",
        "feedback": "Damage numbers and labels (WEAK, CRITICAL...).",
        "hud": "The battle HUD: bars and numbers shown.",
        "ui_layout": "Where the battle UI sits on screen.",
        "ui_polish": "Spacing and sizes of the battle UI.",
        "motion_sequences": "Each skill's animation beats: moves, effects, sounds.",
        "rpg_character_screen": "The status screen: sections, stat names and order.",
    }
)
