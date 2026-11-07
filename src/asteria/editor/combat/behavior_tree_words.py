"""A behavior tree in plain words: a name for each kind of node, a short sentence for each node,
and what each of its settings is called. The data keeps its keys (``player_within``, ``radius``);
only what the editor shows is said this way.

The kinds have wording of their own, in the language table under these English sentences:
``translate("sequence")`` would find the table's ``Sequence``, which is a cutscene.
"""

from __future__ import annotations

from asteria.editor.combat.behavior_tree_authoring import PARAMS, parse_points
from asteria.editor.records.vocabulary import words
from asteria.editor.ui.i18n import translate

KIND_NAMES = {
    "sequence": "Do all in order",
    "selector": "Do the first that works",
    "parallel": "Do all at once",
    "inverter": "Opposite result",
    "succeeder": "Always counts as success",
    "repeater": "Repeat",
    "cooldown": "Cooldown",
    "player_within": "Player is near",
    "player_beyond": "Player is far",
    "switch": "Switch is on",
    "chance": "Chance",
    "home_within": "Near home",
    "hp_below": "Stat is low",
    "hp_above": "Stat is high",
    "ability_ready": "Skill is ready",
    "has_state": "Has a state",
    "acting": "Busy using a skill",
    "chase": "Chase the player",
    "flee": "Run from the player",
    "move_to": "Go to a place",
    "return_home": "Go back home",
    "patrol": "Patrol",
    "wander": "Wander",
    "wait": "Wait",
    "face_player": "Face the player",
    "set_switch": "Set a switch",
    "start_encounter": "Start an encounter",
    "use_ability": "Use a skill",
    "keep_distance": "Keep a distance from the player",
    "strafe": "Circle the player",
    "side_patrol": "Walk back and forth",
    "jump": "Jump",
    "summon": "Summon",
    "apply_state": "Give a state",
}

_HOME = "Home is the place this character started from."
KIND_HELP = {  # shown on the ⓘ beside the kind
    "sequence": "Runs the nodes inside from top to bottom and stops as soon as one fails.",
    "selector": (
        "Tries the nodes inside from top to bottom and does the first that works. "
        "The ones above it are checked all the time, so they can interrupt it."
    ),
    "parallel": (
        "Runs all the nodes inside at the same time, until as many as you ask for have succeeded."
    ),
    "inverter": (
        "Holds one node and counts its success as a failure, and its failure as a success."
    ),
    "succeeder": "Holds one node: however it ends, it counts as a success.",
    "repeater": "Holds one node and runs it again each time it ends.",
    "cooldown": (
        "Holds one node: after it succeeds, it cannot run again until this time has passed."
    ),
    "home_within": _HOME,
    "return_home": _HOME,
    "wander": _HOME,
    "acting": "Succeeds while this character is in the middle of a skill.",
    "side_patrol": "For side-view maps: walks along and turns at walls and ledges.",
    "jump": "For side-view maps: jumps when standing on the ground.",
}

# -- the settings ------------------------------------------------------------------------------
PARAM_LABELS = {
    "ability": "Skill",
    "arrive": "Stop within",
    "count": "How many",
    "direction": "Direction",
    "encounter_id": "Encounter",
    "lose_radius": "Give up past",
    "max": "At most",
    "min": "At least",
    "name": "Switch",
    "points": "Places",
    "once": "Rounds",
    "prefab": "Prefab",
    "probability": "Chance",
    "radius": "Distance",
    "resource": "Stat",
    "seconds": "How long",
    "speed": "Speed",
    "state": "State",
    "success_count": "Must succeed",
    "to": "Who",
    "value": "Set to",
    "wait": "Then",
    "x": "X",
    "y": "Y",
}
_KIND_LABELS = {  # where the same setting means something else
    ("player_within", "radius"): "Within",
    ("player_beyond", "radius"): "Farther than",
    ("home_within", "radius"): "Within",
    ("flee", "radius"): "Run until",
    ("wander", "radius"): "Within",
    ("summon", "radius"): "Spread",
    ("hp_below", "fraction"): "Lower than",
    ("hp_above", "fraction"): "Higher than",
    ("repeater", "count"): "Times",
}
PARAM_HELP = {  # shown on the ⓘ beside the setting
    "arrive": "How close counts as having arrived.",
    "lose_radius": (
        "When the player is farther away than this, the chase gives up. At 0 it never does."
    ),
    "points": "The places it walks between in turn, in the map's pixels.",
    "once": "One round: back at the first place after the last one, the node succeeds. Over and"
    " over: it patrols until something else takes over.",
    "speed": (
        "Pixels a second. A character with its own movement settings moves at that speed instead."
    ),
    "success_count": (
        "How many of the nodes inside must succeed for this one to be done. At 0, all of them."
    ),
    "x": "A place on the map, in pixels.",
    "y": "A place on the map, in pixels.",
}
PIXELS = frozenset({"arrive", "lose_radius", "max", "min", "radius", "x", "y"})
SECONDS = frozenset({"seconds"})
SHARES = frozenset({"fraction", "probability"})
WHOLE_NUMBERS = frozenset({"count", "success_count"})
MAY_BE_NEGATIVE = frozenset({"x", "y"})
FOREVER_AT_ZERO = frozenset({("repeater", "count"), ("side_patrol", "seconds")})
AT_LEAST_ONE = frozenset({("summon", "count")})
# what a 0 reads as where a setting left out of the data means no number at all
ZERO_WORDS = {("chase", "lose_radius"): "Never", ("parallel", "success_count"): "All"}
SETTING_CHOICES = {  # settings picked from a fixed list: (value, words)
    "direction": ((1, "Counter-clockwise"), (-1, "Clockwise")),
    "to": (("self", "Itself"), ("player", "The player")),
    "value": ((True, "Turned on"), (False, "Turned off")),
    "wait": ((False, "Go on at once"), (True, "Wait until it ends")),
    "once": ((False, "Over and over"), (True, "One round")),
}


def param_label(kind, name):
    """What the setting ``name`` of a ``kind`` node is called."""
    return _KIND_LABELS.get((kind, name)) or PARAM_LABELS.get(name) or words(name)


def setting_value(name, value):
    """A setting with a fixed list of choices, as that list holds it (old data may differ)."""
    if name == "direction":
        return 1 if _float(value, 1.0) >= 0 else -1
    if name == "to":
        return "player" if value == "player" else "self"
    return bool(value)


# -- the sentences -----------------------------------------------------------------------------
_STOP = ("arrive", ", stop within {arrive} px")
_SPEED = ("speed", ", speed {speed}")
_SENTENCES = {  # kind -> the sentence, then what it adds for the values the node holds
    "cooldown": ("Cooldown {seconds} sec", ()),
    "player_within": ("Player within {radius} px", ()),
    "player_beyond": ("Player more than {radius} px away", ()),
    "switch": ("Switch {name} is on", ()),
    "chance": ("{probability} chance", ()),
    "home_within": ("Within {radius} px of home", ()),
    "hp_below": ("{resource} below {fraction}", ()),
    "hp_above": ("{resource} above {fraction}", ()),
    "ability_ready": ("{ability} is ready", ()),
    "has_state": ("Has {state}", ()),
    "chase": (
        "Chase the player",
        (_STOP, ("lose_radius", ", give up past {lose_radius} px"), _SPEED),
    ),
    "flee": ("Run from the player until {radius} px away", (_SPEED,)),
    "move_to": ("Go to ({x}, {y})", (_STOP, _SPEED)),
    "return_home": ("Go back home", (_STOP, _SPEED)),
    "patrol": ("Patrol {points}", (_STOP, _SPEED)),
    "wander": ("Wander within {radius} px of home", (_STOP, _SPEED)),
    "wait": ("Wait {seconds} sec", ()),
    "start_encounter": ("Start encounter {encounter_id}", ()),
    "use_ability": ("Use {ability}", ()),
    "keep_distance": ("Stay {min} to {max} px from the player", (_SPEED,)),
    "summon": ("Summon {count} × {prefab} within {radius} px", ()),
}
_QUIET = frozenset({"arrive", "speed"})  # said only when they differ from the usual
_NAMED = frozenset({"ability", "encounter_id", "name", "prefab", "resource", "state"})
_MOST_PLACES_SAID = 3


def _float(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _number(value):
    if isinstance(value, str) and _float(value, None) is None:
        return value
    return f"{_float(value):.3f}".rstrip("0").rstrip(".")


def _share(value):
    return f"{_number(_float(value) * 100.0)}%"


def _places(text):
    try:
        points = parse_points(text)
    except ValueError:  # hand-written data the game itself cannot read either
        return translate("(none)")
    said = [f"({_number(x)}, {_number(y)})" for x, y in points[:_MOST_PLACES_SAID]]
    if len(points) > _MOST_PLACES_SAID:
        said.append("…")
    return " → ".join(said) or translate("(none)")


def _shown(name, value, names):
    if name in SHARES:
        return _share(value)
    if name == "points":
        return _places(value)
    if name in _NAMED:
        if not str(value or ""):
            return translate("(none)")
        return translate(names(name, value) if names else words(value))
    return _number(value)


def _template(node):
    """The sentence of a node whose wording depends on what it holds."""
    kind, held = node.kind, node.params
    if kind == "parallel":
        return "Do all at once: {success_count} must succeed" if "success_count" in held else None
    if kind == "repeater":
        count = int(_float(held.get("count", 0)))
        return {0: "Repeat forever", 1: "Repeat once"}.get(count, "Repeat {count} times")
    if kind == "set_switch":
        return "Turn on switch {name}" if held.get("value", True) else "Turn off switch {name}"
    if kind == "strafe":
        clockwise = _float(held.get("direction", 1), 1.0) < 0
        return (
            "Circle the player clockwise for {seconds} sec"
            if clockwise
            else "Circle the player counter-clockwise for {seconds} sec"
        )
    if kind == "side_patrol":
        if _float(held.get("seconds", 0)) > 0:
            return "Walk back and forth for {seconds} sec"
        return "Walk back and forth forever"
    if kind == "patrol" and held.get("once"):
        return "Patrol {points} once"
    if kind == "apply_state":
        if held.get("to") == "player":
            return "Give {state} to the player"
        return "Give {state} to itself"
    found = _SENTENCES.get(kind)
    return found[0] if found else None


def kind_name(kind):
    """The name of a kind of node, in the editor's language."""
    return translate(KIND_NAMES.get(kind) or words(kind))


def _said(template, values):
    return translate(template).format(**values)


def describe(node, names=None):
    """``node`` as a short sentence in the editor's language. ``names(setting, value)`` gives the
    name of what a setting refers to (a skill's, a state's), else its id is put in words."""
    held = dict(node.params)
    defaults = dict(PARAMS.get(node.kind, ()))
    values = {key: _shown(key, value, names) for key, value in {**defaults, **held}.items()}
    template = _template(node)
    if template is None:
        return kind_name(node.kind)
    if node.kind == "use_ability" and held.get("wait"):
        template = "Use {ability} and wait until it ends"
    sentence = _said(template, values)
    for key, clause in _SENTENCES.get(node.kind, ("", ()))[1]:
        if key not in held or (key in _QUIET and _float(held[key]) == _float(defaults.get(key))):
            continue
        sentence += _said(clause, values)
    return sentence


__all__ = [
    "AT_LEAST_ONE",
    "FOREVER_AT_ZERO",
    "ZERO_WORDS",
    "KIND_HELP",
    "KIND_NAMES",
    "MAY_BE_NEGATIVE",
    "PARAM_HELP",
    "PARAM_LABELS",
    "PIXELS",
    "SECONDS",
    "SETTING_CHOICES",
    "SHARES",
    "WHOLE_NUMBERS",
    "describe",
    "kind_name",
    "param_label",
    "setting_value",
]
