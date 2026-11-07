"""What a record's data looks like to the record form (Qt-free): which keys are format or
view keys, list templates, choices, nouns and titles for entries, ids and AI entry kinds."""

from __future__ import annotations

import re

from asteria.editor.records.vocabulary import (
    AI_COMPARISONS,
    AI_CONDITIONS,
    HELP,
    JOB_HELP,
    REFERENCES,
    TECHNICAL,
    label_for,
    trigger_label,
    words,
)
from asteria.editor.ui.i18n import translate
from asteria.gameplay import Effect, EffectOperation, PeriodicEffect, StatModifier

FORMAT_KEYS = ("schema", "version")


# written by another view of the same record, not typed here: a skill tree's node positions
# come from dragging its nodes in the graph view (Save Graph Layout)
OWN_VIEW_KEYS = ("node_positions",)


NAME_KEYS = ("display_name", "name", "label", "title")


_SCALARS = (str, int, float, bool, type(None))


LIST_TEMPLATES = {  # what a new entry of an empty list starts as
    "hits": {"tags": [], "power": 1.0, "checks": []},
    "apply_states": {"state": "", "to": "targets", "remove": False},
    "battle_resource_gains": {"to": "targets", "resource": "", "amount": 1.0},
    "commands": {"command": "", "args": {}},
    "modifiers": {
        "modifier_id": "",
        "stat": "",
        "operation": "add",
        "value": 0.0,
        "priority": 0,
        "required_tags": [],
        "blocked_tags": [],
    },
    "sockets": {"socket_id": "", "accepted_tags": ["gem"], "locked": False},
}


# hand-kept fixed sets; the engine's own checks are read (engine_enums)
_EASINGS = ("linear", "ease_in", "ease_out", "ease_in_out", "smoothstep")  # easing_value


ENUMS = {"easing": _EASINGS, "transition_easing": _EASINGS}


ENUMS["default_transition_easing"] = _EASINGS


def engine_template(key):
    """A new entry for a list the engine defines (built by its own type, so it decodes)."""

    def effect(name):
        operation = EffectOperation("resource_delta", "vitality", 0.0)
        return Effect(name, (operation,))

    builders = {
        "modifiers": lambda: StatModifier("modifier1", "power", "add", 0.0).to_data(),
        "on_apply": lambda: effect("on_apply1").to_data(),
        "on_remove": lambda: effect("on_remove1").to_data(),
        "on_expire": lambda: effect("on_expire1").to_data(),
        "periodic": lambda: PeriodicEffect(1, effect("tick1")).to_data(),
        "operations": lambda: EffectOperation("resource_delta", "vitality", 0.0).to_data(),
    }
    build = builders.get(str(key))
    return build() if build else None


RECORD_LISTS = set(LIST_TEMPLATES) | {
    "modifiers", "on_apply", "on_remove", "on_expire", "periodic", "operations", "effects",
    "triggers", "forms", "nodes", "entries", "impacts", "thresholds", "steps", "rules",
}  # fmt: skip


def choice_text(choice, repeated=()):
    """A choice as players read it: its name only; a name two
    choices share carries the id too, so they can be told apart."""
    shown = translate(choice.label)  # a list item is drawn as given
    if choice.label in repeated and choice.label != choice.value:
        return f"{shown}  ({choice.value})"
    return shown


def repeated_choices(choices):
    seen, twice = set(), set()
    for choice in choices:
        (twice if choice.label in seen else seen).add(choice.label)
    return twice


def formula_names(data, key):
    """The names a formula in ``data[key]`` may use, or None when it holds no formula."""
    from asteria.gameplay.expressions import FORMULA_FIELDS

    schema = data.get("schema") if isinstance(data, dict) else None
    return FORMULA_FIELDS.get((schema, key))


# -- the form ---------------------------------------------------------------------------------
# the Base Stats a stat definition's "Set On" narrows (D91): an actor's starting stats, a
# job's growth per level, an enemy's stats
BASE_STAT_FIELDS = {"actors": ("base_stats",), "classes": ("level_growth",), "enemies": ("stats",)}


# where the engine keeps a record's stats and its resources (HP, MP, a shield)
PAIRED_NUMBERS = {
    "actors": (("base_stats", "base_resources"),),
    "classes": (("level_growth", "resource_growth"), ("stat_bonuses", "resource_bonuses")),
    "enemies": (("stats", "resources"),),
}


def paired_keys(category, key):
    """The ``(stats, resources)`` fields ``key`` belongs to in a ``category``, or None."""
    return next((p for p in PAIRED_NUMBERS.get(category, ()) if key in p), None)


def pool_amount(pool):
    """A resource's one number: an actor's is ``{current, maximum, minimum}``."""
    return pool["maximum"] if isinstance(pool, dict) else pool


def basic_first(choices):
    """The resources with HP and MP first, then as the game lists them."""
    rank = {"vitality": 0, "technique": 1}
    return sorted(choices, key=lambda c: rank.get(c.value, 2))


TABLE_COLUMNS = 6  # an entry with more fields than this keeps its card


# lists whose table shows these fields (the rest under ⋯), whatever the entries hold
TABLE_FIELDS = {"class_assignments": ("class_id", "role")}


def table_columns(entries, key=""):
    """The columns when ``entries`` read best as a table - each a few plain values (a stat
    change, a drop): the fields any entry has written, in order; ``None`` when an entry holds
    a written list or part (it keeps its card)."""
    if not entries or not all(isinstance(e, dict) for e in entries):
        return None
    if str(key) in TABLE_FIELDS:
        columns = [k for k in TABLE_FIELDS[str(key)] if any(k in e for e in entries)]
        if all(_cell_value(k, e.get(k)) for e in entries for k in columns):
            return columns
        return None
    columns = []
    list_key = key
    for entry in entries:
        for key, value in entry.items():
            if key in FORMAT_KEYS or key in TECHNICAL or is_empty_optional(value):
                continue
            if own_id(list_key, key):  # a slot's slot_id: made for it, under ⋯
                continue
            if not _cell_value(key, value):
                return None
            if key not in columns:
                columns.append(key)
    if not columns or len(columns) > TABLE_COLUMNS:
        return None
    for entry in entries:  # a column one entry fills and another holds a part in
        if any(not _cell_value(key, entry.get(key)) for key in columns):
            return None
    return columns


def node_pair(list_key, entry):
    """A ``[node id, rank]`` a node needs (equipment growth's prerequisites)."""
    return (
        str(list_key) in ("prerequisites", "any_prerequisites")
        and isinstance(entry, list)
        and len(entry) == 2
        and isinstance(entry[0], str)
        and isinstance(entry[1], int)
        and not isinstance(entry[1], bool)
    )


def own_id(list_key, key):
    """``key`` is the id each entry of the list ``list_key`` is made with (``slots`` ->
    ``slot_id``, ``nodes`` -> ``node_id``): generated, unique, and kept out of sight."""
    stem = str(list_key)
    stem = stem[:-2] if stem.endswith(("ches", "shes", "xes")) else stem.removesuffix("s")
    return bool(stem) and str(key) == f"{stem}_id"


def has_positions(entries):
    """Entries that each stand somewhere (a formation's slots): a number ``x`` and ``y``."""
    numbers = (int, float)
    return len(entries) > 1 and all(
        isinstance(e, dict)
        and isinstance(e.get("x"), numbers)
        and isinstance(e.get("y"), numbers)
        and not isinstance(e.get("x"), bool)
        for e in entries
    )


def field_help(data, key):
    """A field's help; a job entry's own words for the names other records use too."""

    if isinstance(data, dict) and "class_id" in data and "assignment_id" in data:
        if str(key) in JOB_HELP:
            return JOB_HELP[str(key)]
    return HELP.get(str(key), "")


def _cell_value(key, value):
    """A value that fits a table cell: a plain value, or a few tags (opened from the cell)."""
    if isinstance(value, list):
        return is_scalar_list(key, value) and len(value) <= 4
    return isinstance(value, _SCALARS)


# -- helpers ----------------------------------------------------------------------------------
_IDENTIFIER = re.compile(r"^[a-z0-9_.:\-]+$")


FREE_TEXT = {"label", "name", "title", "text", "description", "message", "prefix", "suffix"}


def closed_choices(key, values):
    """A text field whose values across the project are a few id-like words (a mode, a
    target...) becomes a drop-down of them."""
    if key in FREE_TEXT or key.endswith("_id") or key.endswith("_label"):
        return False
    return 1 <= len(values) <= 24 and all(_IDENTIFIER.match(v) for v in values)


def is_scalar_list(key, value):
    """A list of plain values (tags, ids), not of entries; an empty list counts as entries
    when its field is known to hold them."""
    if not value:
        return str(key) not in RECORD_LISTS
    return all(isinstance(v, _SCALARS) for v in value)


def is_empty_optional(value):
    """Nothing written yet: an empty list, table or text (numbers and switches always show)."""
    return value in ("", None) or value == [] or value == {}


def is_empty_value(value):
    return value in ("", None, 0, 0.0, False) or value == [] or value == {}


def is_number_map(value):
    return isinstance(value, dict) and all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in value.values()
    )


def is_number_matrix(value):
    """``{row: {column: number}}`` with every row's columns alike (a resource's current,
    maximum and minimum): one table, not a card per row."""
    if not isinstance(value, dict) or not value:
        return False
    rows = list(value.values())
    if not all(isinstance(r, dict) and r and is_number_map(r) for r in rows):
        return False
    return all(set(r) == set(rows[0]) for r in rows)


def is_text_map(value):
    return isinstance(value, dict) and all(isinstance(v, str) for v in value.values())


def is_nested_record(value):
    return any(k in FORMAT_KEYS for k in value)


def parse_numbers(text):
    out = []
    for part in re.split(r"[,\s]+", text.strip()):
        try:
            out.append(float(part))
        except ValueError:
            continue
    return out


CLIP_KEYS = {"combatant_visuals": ("clip_role", "state_id", "fallback_state_id")}


# sections shown first on a kind's page, and what they are called there
FIRST_SECTIONS = {"combatant_visuals": ("assets",)}


SECTION_TITLES = {("combatant_visuals", "assets"): "Pictures"}


PORTRAIT_KEYS = ("portrait_asset_id", "small_portrait_asset_id")  # pictures a fighter shows


def entry_noun(key):
    """What one entry of a list field is, for "+ Add …": its label when that is one word
    ("Jobs" -> job), else the key's last word ("gain_rules" -> rule)."""
    label = label_for(key)
    if label and label.isupper():  # HP's numbers: "+ Add value", not "+ Add hp"
        return "value"
    if label and " " not in label.strip():
        return singular(label.lower())
    word = str(key).replace("-", "_").split("_")[-1].lower()
    special = {"operations": "step", "impacts": "rule", "entries": "entry", "members": "member"}
    if word in special:
        return special[word]
    if word == "ids":  # roster_actor_ids -> actor
        parts = str(key).split("_")
        word = parts[-2].lower() if len(parts) > 1 else ""
    return singular(word) if word and word != "id" else "entry"


def lists_title(labels):
    """A card of lists is called after what is in it: its one list, Properties and the other
    one, or Lists when there are more."""
    labels = list(dict.fromkeys(labels))
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2 and "Properties" in labels:
        return "Properties and " + next(x for x in labels if x != "Properties")
    return "Lists"


def plural(noun):
    """``currency`` -> "currencies", ``entry`` -> "entries", ``stat`` -> "stats"."""
    noun = str(noun)
    if noun.endswith("y") and noun[-2:-1] not in "aeiou":
        return noun[:-1] + "ies"
    if noun.endswith(("s", "x", "ch", "sh")):
        return noun + "es"
    return noun + "s"


def singular(text):
    """``stats`` -> "stat"; a phrase ("what it does") is an "entry"."""
    text = str(text).strip()
    if " " in text:
        return "entry"
    # "phases" -> "phase" (not "phas"), "statuses" -> "status"
    for suffix, replacement in (("ies", "y"), ("ases", "ase"), ("ses", "s"), ("s", "")):
        if text.endswith(suffix) and len(text) > 3:
            return text[: -len(suffix)] + replacement
    return text


def entry_title(entry, noun, names=None):
    """A card's title: the entry's name, or what it refers to by its display name (``Brave``
    for ``class_id: brave``)."""
    names = names or {}
    title = entry_name(entry, noun, names)
    if isinstance(entry, dict) and isinstance(entry.get("trigger"), str) and entry["trigger"]:
        moment = trigger_label(entry["trigger"])  # a rule also says the moment it reacts to
        return moment if title == noun.title() else f"{title}  ·  {moment}"
    return title


def title_names(vocabulary):
    """Display names by id for card titles: records, then stats and resources as the game
    writes them (HP, not Vitality)."""
    names = dict(vocabulary.names())
    choices = getattr(vocabulary, "choices", None)
    for kind in ("stats", "resources") if choices else ():
        names.update({c.value: c.label for c in choices(kind)})
    return names


def is_boss_phase(entry):
    """A boss phase of an enemy AI: ``phase_id`` and the rules it uses."""
    return isinstance(entry, dict) and "phase_id" in entry and "decision_rule_ids" in entry


def ai_context(data, entry, names):
    """A quiet second part of a card's title: the phases an AI rule belongs to and when it
    applies ("Opening · Round is 1"); when a phase starts ("starts when HP % is at most 30 %",
    "at the start")."""
    names = names or {}
    if is_ai_rule(entry):
        phases = [
            words(str(p["phase_id"]))
            for p in data.get("phases") or ()
            if is_boss_phase(p) and entry["rule_id"] in (p.get("decision_rule_ids") or ())
        ]
        when = [ai_condition_words(c, names) for c in entry.get("conditions") or ()]
        return "  ·  ".join([", ".join(phases)] * bool(phases) + when)
    if is_boss_phase(entry):
        when = [ai_condition_words(c, names) for c in entry.get("conditions") or ()]
        if when:
            return "starts when " + " and ".join(when)
        return "at the start" if data.get("initial_phase_id") == entry["phase_id"] else ""
    return ""


def is_ai_condition(entry):
    """An enemy AI condition: a ``kind`` the engine checks, its ``params`` and ``negate``."""
    return (
        isinstance(entry, dict)
        and isinstance(entry.get("kind"), str)
        and isinstance(entry.get("params"), dict)
        and "negate" in entry
    )


def ai_condition_defaults(kind, form):
    """A new condition of ``kind`` that works as it is: HP at most 50 %, round 1…"""
    vocabulary = form.vocabulary

    def first(source, fallback):
        choices = vocabulary.choices(source)
        values = [c.value for c in choices]
        return fallback if fallback in values or not values else values[0]

    phases = [p.get("phase_id") for p in form._data.get("phases") or () if isinstance(p, dict)]
    health = first("resources", "vitality")
    return {
        "round_index": {"op": "==", "value": 1},
        "resource": {"resource_id": health, "op": "<=", "value": 100.0},
        "resource_ratio": {"resource_id": health, "op": "<=", "value": 0.5},
        "stat": {"stat_id": first("stats", "atk"), "op": ">=", "value": 10.0},
        "memory": {"key": "flag", "op": "==", "value": 1},
        "phase": {"op": "==", "value": phases[0] if phases else ""},
    }.get(kind, {})


def ai_condition_words(entry, names):
    """A condition in one line: "HP is at most 50 %", "Round is 1", "Not: Can act"."""

    p, kind = entry["params"], entry["kind"]
    what = AI_CONDITIONS.get(kind) or words(kind)
    op = AI_COMPARISONS.get(str(p.get("op", "")), str(p.get("op", "")))
    value = p.get("value")
    if kind == "resource_ratio" and isinstance(value, (int, float)):
        value = f"{value * 100:g} %"
    elif isinstance(value, float):
        value = f"{value:g}"
    target = p.get("resource_id") or p.get("stat_id") or p.get("key")
    if target:
        what = names.get(target) or words(str(target))
        if kind == "resource_ratio":
            what = f"{what} %"
    if kind == "phase":
        value = words(str(value))
    text = f"{what} {op} {value}" if "op" in p else what
    return f"Not: {text}" if entry.get("negate") else text


def is_ai_rule(entry):
    """An enemy AI decision rule: ``rule_id``, ``action_kind`` and its ``payload``."""
    return (
        isinstance(entry, dict)
        and "rule_id" in entry
        and isinstance(entry.get("action_kind"), str)
        and isinstance(entry.get("payload"), dict)
    )


def entry_name(entry, noun, names):
    if is_ai_condition(entry):
        return ai_condition_words(entry, names)
    if is_ai_rule(entry):  # named by what it does: the skill, else the hook
        target = entry["payload"].get("ability_id") or entry["payload"].get("hook")
        if isinstance(target, str) and target:
            return names.get(target) or words(target)
    if isinstance(entry, dict):
        for key in ("display_name", "name", "label", "state", "stat", "ability_id", "class_id",
                    "item_id", "resource", "command", "socket_id", "form_id", "key",
                    "kind"):  # fmt: skip
            value = entry.get(key)
            if isinstance(value, str) and value:
                extra = ""
                if isinstance(entry.get("value"), (int, float)) and entry["value"]:
                    extra = f"  {entry['value']:+g}"
                if "to" in entry and isinstance(entry["to"], str):
                    extra += f"  → {names.get(entry['to'], entry['to'])}"
                return f"{names.get(value) or words(value)}{extra}"
        for key, value in entry.items():
            if key.endswith("_id") and isinstance(value, str) and value:
                return names.get(value) or words(value)
    elif isinstance(entry, (str, int, float)):
        return str(entry)
    return noun.title()


def fresh_ids(entry, siblings, form):
    """A new entry's own ids (``modifier_id``, ``socket_id``...) are made unique."""
    if not isinstance(entry, dict):
        return entry
    for key, value in list(entry.items()):
        if not key.endswith("_id") or REFERENCES.get(key) not in (None,):
            continue
        if key in ("icon_id",):
            continue
        used = {str(s.get(key)) for s in siblings if isinstance(s, dict)}
        base = re.sub(r"[._-]?\d+$", "", str(value or key[:-3])) or key[:-3]
        n = len(siblings) + 1
        while f"{base}{n}" in used:
            n += 1
        entry[key] = f"{base}{n}"
    return entry
