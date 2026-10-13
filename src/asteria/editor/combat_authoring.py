"""Real-Time Combat authoring (D22 A9): attacks, projectiles, loot rarities and affixes in one workspace.

Qt-free controller behind ``combat_workspace``. Every record is plain project data; an edit replaces the record as one
undoable command. ``KINDS`` describes, per kind, the sections and fields the workspace shows (label, widget kind,
choices), so the form, the previews and the tests share one description.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay.attacks import HITSTOP_SCOPES, KNOCKBACK_DIRECTIONS, AttackDefinition
from asteria.gameplay.projectiles import WALL_BEHAVIOURS, ProjectileDefinition
from asteria.rpg.loot import AffixDefinition, RarityDefinition

from .rpg_actor_class_authoring import _DefinitionCommand


class CombatAuthoringError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    label: str
    kind: str  # float, int, bool, text, choice, tags, color, formula, attack, states, modifiers
    choices: tuple = ()
    hint: str = ""
    minimum: float = 0.0
    maximum: float = 1_000_000.0
    step: float = 1.0


@dataclass(frozen=True, slots=True)
class KindSpec:
    kind_id: str
    label: str  # plural, shown on the switcher
    noun: str  # singular, shown on buttons
    icon: str
    accent: str
    record: type
    id_field: str
    sections: tuple  # ((title, hint, (FieldSpec, ...)), ...)


def _f(name, label, kind="float", **kw):
    return FieldSpec(name, label, kind, **kw)


KINDS = (
    KindSpec(
        "attacks",
        "Attacks",
        "Attack",
        "battle",
        "#e06a5c",
        AttackDefinition,
        "attack_id",
        (
            (
                "Damage",
                "What one landed hit takes away. Formulas read the attacker's and the target's stats.",
                (
                    _f("display_name", "Name", "text"),
                    _f("damage", "Damage formula", "formula"),
                    _f("damage_formula_id", "…or shared formula", "text", hint="Uses a formula from Formulas instead"),
                    _f("damage_resource", "Lowers resource", "text", hint="Empty: the target's life resource"),
                    _f("tags", "Tags", "tags", hint="e.g. Element.Fire — formulas can multiply on them"),
                    _f("critical_chance", "Critical chance", maximum=1.0, step=0.05),
                    _f("critical_chance_stat", "+ chance from stat", "text", hint="stat / 100 is added"),
                    _f("critical_multiplier", "Critical ×", step=0.1),
                ),
            ),
            (
                "Reaction",
                "How the target reacts: poise, hitstun, knockback, hit-stop and i-frames.",
                (
                    _f("poise_damage", "Poise damage"),
                    _f("hitstun", "Hitstun (s)", step=0.05),
                    _f("knockback", "Knockback speed", minimum=-1_000_000.0, step=10.0),
                    _f("knockback_direction", "Knockback direction", "choice", choices=KNOCKBACK_DIRECTIONS),
                    _f("knockback_angle", "Knockback angle (°)", minimum=-360.0, maximum=360.0, step=15.0),
                    _f("knockback_lift", "Side view lift", minimum=-1_000_000.0, step=10.0),
                    _f("hitstop", "Hit-stop (s)", step=0.01),
                    _f("hitstop_scope", "Hit-stop freezes", "choice", choices=HITSTOP_SCOPES),
                    _f("target_iframes", "Target i-frames (s)", step=0.05),
                    _f("max_targets", "Max targets (0 = all)", "int"),
                ),
            ),
            (
                "Super Armor & Knockdown",
                "Armor holds while the target's armor level is above this attack's break level.",
                (
                    _f("armor_break", "Breaks armor up to", "int"),
                    _f("knockdown", "Knocks down", "bool"),
                    _f("knockdown_time", "Down for (s, 0 = target's)", step=0.1),
                ),
            ),
            (
                "States & Events",
                "Gameplay states put on the target, and an event for game rules.",
                (
                    _f("apply_states", "Applies states", "states"),
                    _f("on_hit_event", "Event on hit", "text"),
                ),
            ),
        ),
    ),
    KindSpec(
        "projectiles",
        "Projectiles",
        "Projectile",
        "vfx",
        "#e8894a",
        ProjectileDefinition,
        "projectile_id",
        (
            (
                "Flight",
                "Speed, life and arc. Homing turns toward the nearest target in range.",
                (
                    _f("display_name", "Name", "text"),
                    _f("speed", "Speed", step=10.0),
                    _f("lifetime", "Lifetime (s)", step=0.1),
                    _f("gravity", "Gravity", minimum=-1_000_000.0, step=10.0),
                    _f("homing_turn", "Homing (°/s)", step=15.0),
                    _f("homing_range", "Homing range", step=10.0),
                ),
            ),
            (
                "Hit",
                "The attack it applies, its box, and how many targets it passes through.",
                (
                    _f("attack_id", "Attack on hit", "attack"),
                    _f("width", "Box width"),
                    _f("height", "Box height"),
                    _f("pierce", "Pierce (−1 = every target)", "int", minimum=-1),
                ),
            ),
            (
                "Walls",
                "What a wall does to it. One-way platforms never stop shots.",
                (
                    _f("wall", "On a wall", "choice", choices=WALL_BEHAVIOURS),
                    _f("wall_mask", "Wall layers (mask)", "mask"),
                    _f("bounce_limit", "Bounces (0 = until it expires)", "int"),
                ),
            ),
            (
                "Look & Events",
                "",
                (
                    _f("sprite", "Sprite", "text"),
                    _f("clip", "Clip", "text"),
                    _f("align_to_velocity", "Turn with flight", "bool"),
                    _f("on_end_event", "Event when it ends", "text"),
                ),
            ),
        ),
    ),
    KindSpec(
        "rarities",
        "Loot Rarities",
        "Rarity",
        "item",
        "#dca545",
        RarityDefinition,
        "rarity_id",
        (
            (
                "Rarity",
                "A weight of 0 is never rolled — only given by drop tables (uniques).",
                (
                    _f("display_name", "Name", "text"),
                    _f("color", "Colour", "color"),
                    _f("min_affixes", "Affixes from", "int"),
                    _f("max_affixes", "Affixes up to", "int"),
                    _f("max_prefixes", "Max prefixes (−1 = any)", "int", minimum=-1),
                    _f("max_suffixes", "Max suffixes (−1 = any)", "int", minimum=-1),
                    _f("weight", "Roll weight", step=1.0),
                    _f("order", "Order (rarer = higher)", "int", minimum=-1000),
                ),
            ),
        ),
    ),
    KindSpec(
        "affixes",
        "Loot Affixes",
        "Affix",
        "skill",
        "#9a84e0",
        AffixDefinition,
        "affix_id",
        (
            (
                "Affix",
                "Shown before (prefix) or after (suffix) the item's name.",
                (
                    _f("display_name", "Name", "text"),
                    _f("position", "Position", "choice", choices=("prefix", "suffix")),
                    _f("group", "Exclusive group", "text", hint="One affix per group on an item"),
                    _f("weight", "Roll weight", step=1.0),
                    _f("min_level", "Item level from", "int"),
                    _f("max_level", "Item level up to (0 = any)", "int"),
                ),
            ),
            (
                "Where it rolls",
                "Empty lists mean any equipment, any slot, any rarity.",
                (
                    _f("allowed_tags", "Equipment tags", "tags"),
                    _f("slots", "Slots", "tags"),
                    _f("rarities", "Rarities", "tags"),
                ),
            ),
            (
                "Rolled values",
                "Each line rolls between its minimum and maximum (plus per item level above 1).",
                (_f("modifiers", "Modifiers", "modifiers"),),
            ),
        ),
    ),
)
KIND_BY_ID = {k.kind_id: k for k in KINDS}


class CombatAuthoringController:
    def __init__(self, document):
        self.document = document

    # -- tables ----------------------------------------------------------------------------------
    def _table(self, kind_id):
        project = self.document.project
        if project is None:
            return {}
        library, db = project.gameplay_library, project.rpg_database
        return {
            "attacks": library.attacks,
            "projectiles": library.projectiles,
            "rarities": db.rarities,
            "affixes": db.affixes,
        }[kind_id]

    def kind(self, kind_id):
        return KIND_BY_ID[kind_id]

    def ids(self, kind_id):
        return tuple(sorted(self._table(kind_id)))

    def get(self, kind_id, record_id):
        return self._table(kind_id).get(str(record_id))

    def data(self, kind_id, record_id):
        record = self.get(kind_id, record_id)
        return None if record is None else record.to_data()

    def choices(self, name):
        """Values offered for reference fields (attacks for projectiles, states for applied states...)."""
        project = self.document.project
        if project is None:
            return ()
        library = project.gameplay_library
        if name == "attack":
            return tuple(sorted(library.attacks))
        if name == "states":
            return tuple(library.states.ids())
        if name == "formulas":
            return tuple(sorted(library.formulas))
        if name == "rarities":
            return tuple(sorted(project.rpg_database.loot_rarities()))
        return ()

    # -- editing ---------------------------------------------------------------------------------
    def _execute(self, table, key, new, old, label):
        self.document.execute(_DefinitionCommand(table, key, new, old, label))

    def build(self, kind_id, data):
        """A record from form data (raises CombatAuthoringError with the reason when the values are invalid)."""
        spec = self.kind(kind_id)
        try:
            return spec.record.from_data(data)
        except (ValueError, TypeError, KeyError) as exc:
            raise CombatAuthoringError(str(exc)) from exc

    def apply(self, kind_id, record_id, data):
        table = self._table(kind_id)
        if record_id not in table:
            raise CombatAuthoringError(f"unknown {self.kind(kind_id).noun.lower()} {record_id}")
        record = self.build(kind_id, data)
        if getattr(record, self.kind(kind_id).id_field) != record_id:
            raise CombatAuthoringError("the id cannot change here (duplicate it instead)")
        self._execute(table, record_id, record, table[record_id], f"Edit {self.kind(kind_id).noun} {record_id}")
        return record

    def create(self, kind_id, record_id, *, source=None):
        spec = self.kind(kind_id)
        record_id = str(record_id).strip()
        table = self._table(kind_id)
        if not record_id:
            raise CombatAuthoringError("an id is required")
        if record_id in table:
            raise CombatAuthoringError(f"{record_id} already exists")
        if source is not None:
            data = dict(table[source].to_data())
            data[spec.id_field] = record_id
            if data.get("display_name") == source:
                data["display_name"] = record_id
            record = self.build(kind_id, data)
        else:
            record = spec.record(record_id)
        self._execute(table, record_id, record, None, f"New {spec.noun} {record_id}")
        return record

    def delete(self, kind_id, record_id):
        table = self._table(kind_id)
        if record_id not in table:
            raise CombatAuthoringError(f"unknown {record_id}")
        self._execute(table, record_id, None, table[record_id], f"Delete {self.kind(kind_id).noun} {record_id}")

    def usage(self, kind_id, record_id):
        """Where a record is used (so deleting or renaming it is not a surprise)."""
        project = self.document.project
        if project is None:
            return ()
        library = project.gameplay_library
        found = []
        if kind_id == "attacks":
            found += [f"projectile {p.projectile_id}" for p in library.projectiles.values() if p.attack_id == record_id]
            for timeline in library.timelines.values():
                if any(c.kind.value == "hitbox" and c.payload.get("hit_tag") == record_id for c in timeline.cues):
                    found.append(f"timeline {timeline.timeline_id}")
        elif kind_id == "projectiles":
            for timeline in library.timelines.values():
                if any(
                    c.kind.value == "projectile" and c.payload.get("projectile_id") == record_id for c in timeline.cues
                ):
                    found.append(f"timeline {timeline.timeline_id}")
        elif kind_id == "affixes":
            for rarity in project.rpg_database.loot_rarities().values():
                if rarity.max_affixes:
                    found.append(f"rolls on {rarity.display_name}")
        return tuple(found)


__all__ = ["KINDS", "KIND_BY_ID", "CombatAuthoringController", "CombatAuthoringError", "FieldSpec", "KindSpec"]
