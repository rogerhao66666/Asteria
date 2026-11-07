"""The creature battle screen: a one-on-one battle drawn the way handheld creature-collecting
games of the GBA era draw it, at their own 240 x 160 resolution scaled up by whole pixels.

The foe stands on its platform at the top right with an info box (name, level, health bar) at
the top left; the player's creature stands at the bottom left, seen from behind, with an info
box (name, level, health bar, health numbers, experience bar) at the right. The bottom of the
screen is the message window; when it is the player's turn the right half shows four
commands - fight, bag, party, run - and fight opens the creature's moves with their uses and
type. Everything is told through messages that wait for the confirm key, while health bars
drain and creatures appear, faint, switch and are caught in balls.

A project turns it on with the playtest manifest's ``battle.style: "creature"``; the rules are
the engine's creature party (``rpg.pets.PetRules``): the stage creature of each side fights,
the bench comes in when one falls, capture items come from the capture rules. Nothing here
names a game: every word goes through ``game.tr`` (``creature.*`` keys) and every picture is
project art found by the paths in ``battle.creature_screen`` (``front``, ``back``, ``trainer``
and ``background`` with ``{species}`` / ``{trainer}``); a missing picture is drawn as a plain
shape of the same size, so the battle always plays.

``battle.creature_screen.trainers`` maps an encounter id to a trainer: ``name``, ``title``
(the class shown before the name), ``sprite`` (a ``{trainer}`` key) and ``prize`` (currency).
An encounter tagged ``legendary`` opens with its own line. ``encounters`` maps an encounter id
to its own words: ``no_running_text`` is said when running is refused there; ``player_name`` /
``player_back`` stand for the player's (someone else's battle) and ``auto_choices`` (``["move",
id]`` / ``["ball", item]`` in order, ``auto_delay`` seconds apart) are chosen by the game.

``sprite_offsets`` (a JSON path or a table) moves each species' picture from its battle spot:
``{species: {"front": dy, "back": dy, "lift": dy}}`` - the foe's picture is drawn ``front``
pixels lower and ``lift`` higher (a flier), the player's ``back`` pixels lower.

``music`` picks the tracks by the kind of battle: ``wild``, ``trainer``, ``legendary`` and
``victory_wild`` / ``victory_trainer`` (a trainer may name its own ``music`` and
``victory_music``; an encounter tag ``music:<key>`` picks any key of ``music``). A missing
key keeps the manifest's battle track.

Optional pictures replace the drawn parts one by one (paths in ``battle.creature_screen``):
``background`` (240 x 160), ``window_message`` / ``window_commands`` / ``window_moves`` (the
bottom 240 x 48 in its three states), ``healthbox_foe`` / ``healthbox_mine``, ``hp_label``
(24 x 8, drawn before the bar), ``hp_bar`` (``{"green", "yellow", "red"}``: strips of nine 8 x 8
tiles, 0 to 8 pixels filled), ``exp_bar`` (the same for experience) and ``font`` (a
``graphics.bitmap_font`` JSON; text it cannot draw falls back to a system face). ``layout``
moves any point of ``LAYOUT`` and ``colours`` any text colour pair of ``COLOURS``.

The opening: the foe (or its trainer) slides in from the left while the player's back picture
(``player_back``: frames of ``player_back_size`` under each other - standing, then throwing)
slides in from the right; creatures come out of a ball (``ball``: square frames under each
other - closed, opening, open) and grow from it, go back into it when called back, and their
info boxes slide in from their edges. ``ball_spin``: the turns a thrown ball makes in flight (0:
it does not spin). A switch's lines follow the foe's health as the
handheld games do ("Go!" / "Do it!" / "Go for it" / "Your foe's weak!", "that's enough" /
"come back" / "OK!" / "good!"); before a trainer's next creature the player is asked whether
to change theirs, and after a faint in the wild whether to send the next one (no: run). The
party screen lists the creatures in the battle's order (the one out first).

The rules' words: ``miss_tag`` / ``crit_tag`` (the hit-check outcome tags told as a miss and a
critical blow), ``effectiveness_rules`` (the id prefix of the interaction rules that count as
effectiveness - the type chart, not a critical blow), ``counters`` (battle counters told as
stat stages: ``{counter: name}``), ``state_messages`` (``{state: {applied, already, tick,
prevented, expired, cured}}``, with ``{name}``) and ``status_icons`` (``{state: picture}``,
drawn over the bar's HP label, or at ``status_at[side]`` from the info box's corner);
``outcome_lines`` (``{outcome tag: line}``, with ``{name}``: a hit whose interaction gave that
tag is told so - "protected itself!"). A trainer's ``defeat_text`` (a line or a list of pages)
is said by the trainer, back on the screen, after the win."""

from __future__ import annotations

from asteria.presentation.screens.creature import creature_settings
from asteria.runtime.creature.battle_draw import BattleDrawMixin
from asteria.runtime.creature.battle_menus import BattleMenusMixin
from asteria.runtime.creature.battle_party import BattlePartyMixin
from asteria.runtime.creature.battle_round import BattleRoundMixin
from asteria.runtime.creature.battle_story import BattleStoryMixin
from asteria.runtime.creature.battle_style import H, W

"""The creature battle screen: a one-on-one battle drawn the way handheld creature-collecting
games of the GBA era draw it, at their own 240 x 160 resolution scaled up by whole pixels.

The foe stands on its platform at the top right with an info box (name, level, health bar) at
the top left; the player's creature stands at the bottom left, seen from behind, with an info
box (name, level, health bar, health numbers, experience bar) at the right. The bottom of the
screen is the message window; when it is the player's turn the right half shows four
commands - fight, bag, party, run - and fight opens the creature's moves with their uses and
type. Everything is told through messages that wait for the confirm key, while health bars
drain and creatures appear, faint, switch and are caught in balls.

A project turns it on with the playtest manifest's ``battle.style: "creature"``; the rules are
the engine's creature party (``rpg.pets.PetRules``): the stage creature of each side fights,
the bench comes in when one falls, capture items come from the capture rules. Nothing here
names a game: every word goes through ``game.tr`` (``creature.*`` keys) and every picture is
project art found by the paths in ``battle.creature_screen`` (``front``, ``back``, ``trainer``
and ``background`` with ``{species}`` / ``{trainer}``); a missing picture is drawn as a plain
shape of the same size, so the battle always plays.

``battle.creature_screen.trainers`` maps an encounter id to a trainer: ``name``, ``title``
(the class shown before the name), ``sprite`` (a ``{trainer}`` key) and ``prize`` (currency).
An encounter tagged ``legendary`` opens with its own line. ``encounters`` maps an encounter id
to its own words: ``no_running_text`` is said when running is refused there; ``player_name`` /
``player_back`` stand for the player's (someone else's battle) and ``auto_choices`` (``["move",
id]`` / ``["ball", item]`` in order, ``auto_delay`` seconds apart) are chosen by the game.

``sprite_offsets`` (a JSON path or a table) moves each species' picture from its battle spot:
``{species: {"front": dy, "back": dy, "lift": dy}}`` - the foe's picture is drawn ``front``
pixels lower and ``lift`` higher (a flier), the player's ``back`` pixels lower.

``music`` picks the tracks by the kind of battle: ``wild``, ``trainer``, ``legendary`` and
``victory_wild`` / ``victory_trainer`` (a trainer may name its own ``music`` and
``victory_music``; an encounter tag ``music:<key>`` picks any key of ``music``). A missing
key keeps the manifest's battle track.

Optional pictures replace the drawn parts one by one (paths in ``battle.creature_screen``):
``background`` (240 x 160), ``window_message`` / ``window_commands`` / ``window_moves`` (the
bottom 240 x 48 in its three states), ``healthbox_foe`` / ``healthbox_mine``, ``hp_label``
(24 x 8, drawn before the bar), ``hp_bar`` (``{"green", "yellow", "red"}``: strips of nine 8 x 8
tiles, 0 to 8 pixels filled), ``exp_bar`` (the same for experience) and ``font`` (a
``graphics.bitmap_font`` JSON; text it cannot draw falls back to a system face). ``layout``
moves any point of ``LAYOUT`` and ``colours`` any text colour pair of ``COLOURS``.

The opening: the foe (or its trainer) slides in from the left while the player's back picture
(``player_back``: frames of ``player_back_size`` under each other - standing, then throwing)
slides in from the right; creatures come out of a ball (``ball``: square frames under each
other - closed, opening, open) and grow from it, go back into it when called back, and their
info boxes slide in from their edges. ``ball_spin``: the turns a thrown ball makes in flight (0:
it does not spin). A switch's lines follow the foe's health as the
handheld games do ("Go!" / "Do it!" / "Go for it" / "Your foe's weak!", "that's enough" /
"come back" / "OK!" / "good!"); before a trainer's next creature the player is asked whether
to change theirs, and after a faint in the wild whether to send the next one (no: run). The
party screen lists the creatures in the battle's order (the one out first).

The rules' words: ``miss_tag`` / ``crit_tag`` (the hit-check outcome tags told as a miss and a
critical blow), ``effectiveness_rules`` (the id prefix of the interaction rules that count as
effectiveness - the type chart, not a critical blow), ``counters`` (battle counters told as
stat stages: ``{counter: name}``), ``state_messages`` (``{state: {applied, already, tick,
prevented, expired, cured}}``, with ``{name}``) and ``status_icons`` (``{state: picture}``,
drawn over the bar's HP label, or at ``status_at[side]`` from the info box's corner);
``outcome_lines`` (``{outcome tag: line}``, with ``{name}``: a hit whose interaction gave that
tag is told so - "protected itself!"). A trainer's ``defeat_text`` (a line or a list of pages)
is said by the trainer, back on the screen, after the win.
"""


# every point a project can move (battle.creature_screen.layout): boxes are top-left corners,
# names and bars start there, "level" and "hp_text" are right edges
LAYOUT = {
    "foe_box": (12, 14),
    "mine_box": (126, 72),
    "foe_name": (20, 15),
    "foe_level": (106, 15),
    "foe_hp": (52, 31),
    "mine_name": (140, 73),
    "mine_level": (226, 73),
    "mine_hp": (174, 89),
    "mine_hp_text": (222, 94),
    "exp": (158, 106),
}


COLOURS = {  # (letter, shadow) of each kind of text
    "message": ((248, 248, 248), (104, 88, 112)),
    "menu": ((72, 72, 72), (208, 208, 200)),
    "box": ((64, 64, 64), (216, 208, 176)),
}


MSG_TEXT, MSG_SHADOW = (248, 248, 248), (104, 88, 112)


class CreatureBattleScreen(
    BattleStoryMixin, BattleRoundMixin, BattleMenusMixin, BattleDrawMixin, BattlePartyMixin
):
    """Made when a battle starts; each frame ``update(dt, events)`` then ``draw()``.
    ``done`` turns true when the battle is over and the field resumes; ``defeated`` when the
    player lost."""

    def __init__(self, runtime):
        self.rt = runtime
        self.game = runtime.game
        self.pg = runtime.pg
        # the project's settings (Creature screens…), else the manifest's (V5)
        self.settings = creature_settings(runtime, "battle.creature_screen")
        # opaque pixels with an alpha channel: the window's surface keeps per-pixel alpha, and a
        # plain surface blitted onto it left alpha 0 (frames captured as see-through)
        self.surface = self.pg.Surface((W, H), self.pg.SRCALPHA)
        self.time = 0.0
        self.done = self.defeated = False
        self.steps = []
        self.step = None
        self.step_time = 0.0
        self.shown_chars = 0.0
        self.message = ""
        self.phase = "story"  # story / command / fight / bag / party
        self.cursor = 0
        self.list_cursor = 0
        self.pocket = 0
        self.forced_switch = False
        self.free_switch = False  # a switch offered before a trainer's next creature (no turn)
        self.party_note = ""
        self.choice = None
        self.shown_hp = {}  # member id -> health drawn on the bar now
        self.max_hp = {}  # member id -> its top health, kept after the battle ends
        self.target_hp = {}  # member id -> health the bar is draining towards
        self.visible = {"heroes": None, "enemies": None}  # the creature drawn on each side
        self.trainer_shown = False
        self.throw = None  # the ball in flight: {"start", "shakes", "caught", "member"}
        self.flash = {}  # member id -> seconds left blinking (a hit)
        self.drop = {}  # member id -> seconds into fainting
        self._images = {}
        self._fonts = {}
        self.layout = {
            **LAYOUT,
            **{k: tuple(v) for k, v in self.settings.get("layout", {}).items()},
        }
        self.colours = {
            **COLOURS,
            **{k: (tuple(v[0]), tuple(v[1])) for k, v in self.settings.get("colours", {}).items()},
        }
        self.font = self._load_font("font")
        # the party screen's smaller face (``font_small``), else the main one
        self.font_small = self._load_font("font_small") or self.font
        self._cjk = {}
        self._glyphs = {}
        self._remember_hp()
        encounter = self.game.project.rpg_database.encounters.get(self.game.encounter_id or "")
        self.tags = set(encounter.tags) if encounter is not None else set()
        self.trainer = dict(self.settings.get("trainers", {}).get(self.game.encounter_id, {}))
        # per-encounter words: "no_running_text" (what refusing to run says in this battle)
        self.encounter = dict(self.settings.get("encounters", {}).get(self.game.encounter_id, {}))
        if self.encounter.get("player_back"):  # someone else's battle (a tutorial)
            self.settings = {**self.settings, "player_back": self.encounter["player_back"]}
        # a battle the game plays by itself: its choices in order (["move", id], ["ball", id])
        self.auto_choices = [tuple(c) for c in self.encounter.get("auto_choices") or ()]
        self._auto_at = None
        # counters the battle moves (stat stages) -> their names; ailment lines by state id
        self.counter_names = dict(self.settings.get("counters") or {})
        self.state_messages = dict(self.settings.get("state_messages") or {})
        self.sounds = dict(self.settings.get("sounds") or {})
        self.weather_rules = dict(self.settings.get("weather") or {})
        self.low_beep_at = 0.0
        self.counter_seen = {}  # (member id, counter) -> the value last told
        self.order = []  # the battle's party order (instance ids): the creature out comes first
        self.foe_hp_mark = None  # the foe's health when someone was last sent in
        self.prompt = None  # a yes / no question: {"kind", "cursor", "member"}
        self.slides = {}  # "intro" / "trainer_out" / "back_out" -> (start, seconds)
        self.boxes = {"heroes": None, "enemies": None}  # when each info box began sliding in
        self.grow = {}  # member id -> (start, seconds, appearing): out of / into a ball
        self.ball = None  # a ball in flight to a spot: {"start", "side"}
        self.back_shown = False  # the player's back picture (before the first throw)
        self.back_frame = 0
        self._intro()

    MESSAGE_WIDTH = 208  # pixels of text a line of the message window holds (26 tiles)

    BOX_KEYS = {
        "enemies": ("foe_box", "foe_name", "foe_level", "foe_hp"),
        "heroes": ("mine_box", "mine_name", "mine_level", "mine_hp", "mine_hp_text", "exp"),
    }

    # -- the party screen --------------------------------------------------------------------
    # where pokeemerald's single-battle party menu puts things: the big first slot and the five
    # wide ones (top-left corners), the text and bar spots inside a slot, the icons and balls
    PARTY_SLOTS = ((8, 24, 80, 56),) + tuple((96, 8 + 24 * k, 144, 24) for k in range(5))
    PARTY_TEXT = {  # name, level, hp (right edge), max hp (right edge), bar
        "main": ((24, 11), (32, 20), (51, 37), (77, 37), (24, 35)),
        "wide": ((22, 3), (30, 12), (115, 12), (141, 12), (88, 10)),
    }
    PARTY_ICON = ((0, 24),) + tuple((88, 2 + 24 * k) for k in range(5))
    PARTY_BALL = ((0, 18),) + tuple((86, 9 + 24 * k) for k in range(5))
    PARTY_CANCEL, PARTY_MESSAGE = (184, 136), (0, 128)

    # -- the bag ----------------------------------------------------------------------------
    # pokeemerald's bag: the bag picture's centre, the pocket name window and its arrows, the
    # item list window (rows of 16 pixels), the description window and the item's icon
    BAG_CENTRE, BAG_POCKET_NAME, BAG_ARROWS = (68, 66), (64, 9), ((20, 8), (92, 8))
    BAG_LIST, BAG_DESCRIPTION, BAG_ICON = (112, 16, 120), (4, 106), (12, 76)
    BAG_POCKETS = ("items", "balls")


__all__ = ["CreatureBattleScreen"]
