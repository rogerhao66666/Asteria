"""The creature battle screen's sizes, colours and timings, and the rules its parts share
(type effectiveness, experience, owned items, story steps)."""

from __future__ import annotations

from asteria.rpg.items.definitions import Inventory

W, H = 240, 160


BOX_TOP = 112  # the message window takes the bottom 48 rows


# where things stand in a one-on-one battle (pokeemerald's singles coordinates): the centres
# of the 64 x 64 creature pictures and of the info boxes, the 8-pixel text rows and columns
FOE_CENTRE, MINE_CENTRE = (176, 40), (72, 80)


FOE_BOX, MINE_BOX = (12, 14, 100, 28), (126, 72, 104, 38)


ROW_1, ROW_2 = 121, 137  # the two text lines of the bottom windows (tile rows 15 and 17)


MSG_X = 16


CMD_X = (144, 200)  # the four commands: two columns, the cursor 8 pixels before each


MOVE_X = (16, 88)


INFO_X = 168  # PP and TYPE in the right window of the move menu


# colours of the GBA-era battle screens (approximate, per element)
WHITE, INK, INK_SHADOW = (248, 248, 248), (72, 72, 72), (208, 208, 200)


MSG_FILL, MSG_EDGE, MSG_INNER = (40, 80, 104), (24, 40, 56), (72, 128, 152)


CMD_EDGE, CMD_LINE = (112, 104, 128), (200, 200, 216)


BOX_FILL, BOX_EDGE, BOX_DARK = (248, 248, 216), (80, 104, 88), (40, 64, 56)


BAR_TRACK, BAR_FRAME = (72, 80, 88), (40, 48, 56)


HP_GREEN, HP_YELLOW, HP_RED = (112, 248, 168), (248, 224, 56), (248, 88, 56)


HP_LABEL = (248, 168, 48)


EXP_BLUE, EXP_TRACK = (64, 200, 248), (64, 64, 72)


GRASS, GRASS_BAND, PAD, PAD_EDGE = (
    (200, 232, 160),
    (184, 224, 144),
    (168, 208, 120),
    (128, 176, 96),
)


PARTY_BG, PARTY_SLOT, PARTY_SEL = (56, 136, 168), (96, 168, 200), (248, 168, 80)


TYPE_COLOURS = {
    "normal": (168, 168, 120),
    "fire": (240, 128, 48),
    "water": (104, 144, 240),
    "grass": (120, 200, 80),
    "electric": (248, 208, 48),
    "ice": (152, 216, 216),
    "fighting": (192, 48, 40),
    "poison": (160, 64, 160),
    "ground": (224, 192, 104),
    "flying": (168, 144, 240),
    "psychic": (248, 88, 136),
    "bug": (168, 184, 32),
    "rock": (184, 160, 56),
    "ghost": (112, 88, 152),
    "dragon": (112, 56, 248),
    "dark": (112, 88, 72),
    "steel": (184, 184, 208),
}


TEXT_SPEED = 90.0  # characters a second


SLIDE_SECONDS = 1.1  # the opening slide: the foe's side from the left, the player's from the right


BOX_SLIDE = 0.25  # an info box sliding in


THROW_SECONDS = 0.55  # the player winding up and throwing (the back picture's frames)


BALL_SECONDS = 0.45  # a ball flying out to the spot


GROW_SECONDS = 0.3  # a creature coming out of (or going back into) its ball


BALL_SPIN = 1.5  # turns a ball makes in flight (the handheld game's spinning throw)


class _Step:
    """One beat of the battle story: a message, a bar draining, a creature appearing..."""

    __slots__ = ("args", "kind", "text", "wait")

    def __init__(self, kind, text="", wait=True, **args):
        self.kind, self.text, self.wait, self.args = kind, text, wait, args


def _owned_item_ids(inventory, records):
    """The ids of ``records`` to list for ``inventory``, sorted: a plain ``Inventory`` names the
    ids it holds, so only those are visited (record ids are plain strings, as are its keys);
    any other inventory gets every record id. Callers still skip counts of 0 or less."""

    if type(inventory) is not Inventory:
        return sorted(records)
    return [item_id for item_id in inventory.item_ids() if item_id in records]


def _effectiveness(outcome, prefix=""):
    """How much the interaction rules multiplied a hit (1 = as it was); with ``prefix`` only
    the rules whose id starts with it count (the type chart, not a critical blow)."""
    value = getattr(outcome, "value", None)
    trace = tuple(getattr(value, "trace", ()) or ())
    ratio = 1.0
    for rule_id, before, after in trace:
        if prefix and not str(rule_id).startswith(prefix):
            continue
        before, after = float(before), float(after)
        if before == 0:
            continue
        ratio *= after / before
    return ratio


def _move_type(definition):
    """A move's type: its first ``type.<name>`` tag, else its first element-like tag."""
    tags = tuple(getattr(definition, "tags", ()) or ())
    for tag in tags:
        if str(tag).startswith("type."):
            return str(tag)[5:]
    for tag in tags:
        if str(tag) in TYPE_COLOURS:
            return str(tag)
    return ""


def _experience_between(species, old_level, old_exp, level, exp):
    """Experience gained going from (old_level, old_exp) to (level, exp)."""
    if species is None:
        return 0.0
    total = 0.0
    for current in range(old_level, level):
        total += species.exp_to_next(current)
    return total - old_exp + exp
