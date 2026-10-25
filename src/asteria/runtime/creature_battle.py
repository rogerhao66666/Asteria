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
info boxes slide in from their edges. A switch's lines follow the foe's health as the
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

from __future__ import annotations

import random
from pathlib import Path

from asteria.presentation.creature_screens import creature_settings

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

# colours of the GBA-era battle screens (approximate, per element)
WHITE, INK, INK_SHADOW = (248, 248, 248), (72, 72, 72), (208, 208, 200)
MSG_FILL, MSG_EDGE, MSG_INNER = (40, 80, 104), (24, 40, 56), (72, 128, 152)
MSG_TEXT, MSG_SHADOW = (248, 248, 248), (104, 88, 112)
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


class _Step:
    """One beat of the battle story: a message, a bar draining, a creature appearing..."""

    __slots__ = ("args", "kind", "text", "wait")

    def __init__(self, kind, text="", wait=True, **args):
        self.kind, self.text, self.wait, self.args = kind, text, wait, args


class CreatureBattleScreen:
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

    # -- music ----------------------------------------------------------------------------------
    def music(self, moment="start"):
        """The track for the battle's start or its win (``battle.creature_screen.music``)."""
        tracks = dict(self.settings.get("music") or {})
        if moment == "victory":
            own = self.trainer.get("victory_music")
            key = "victory_trainer" if self.trainer else "victory_wild"
            return own or tracks.get(key, "")
        chosen = next((t.split(":", 1)[1] for t in self.tags if t.startswith("music:")), "")
        if chosen:
            return tracks.get(chosen, chosen)
        if self.trainer:
            return self.trainer.get("music") or tracks.get("trainer", "")
        if "legendary" in self.tags:
            return tracks.get("legendary", "") or tracks.get("wild", "")
        return tracks.get("wild", "")

    def _play(self, track):
        if track:
            self.rt._music(track, fade=0.1)

    # -- words ----------------------------------------------------------------------------------
    def tr(self, key, english, **params):
        return self.game.tr(key, english, **params)

    def name(self, member_id, *, owner=False):
        """A unit's name; with ``owner`` a foe's carries "Wild" or "Foe" before it."""
        record = self.game.unit_record(member_id)
        if record is not None:
            text = record.name(self.game.pet_species(record))
        else:
            text = self._commands_name(member_id)
        side = self.game.battle.member(member_id).side if self.game.battle else "heroes"
        if owner and side == "enemies":
            if self.trainer:
                return self.tr("creature.foe_name", "Foe {name}", name=text)
            return self.tr("creature.wild_name", "Wild {name}", name=text)
        return text

    def _commands_name(self, member_id):
        return self.rt.battle_commands.display_name(member_id)

    def move_name(self, ability_id):
        definition = self.game.project.gameplay_library.abilities.get(ability_id)
        return getattr(definition, "display_name", "") or str(ability_id).replace("_", " ").title()

    def player_name(self):
        db = self.game.project.rpg_database
        ids = (
            self.game.save.rpg_state.party_active_actor_ids
            or self.game.save.rpg_state.party_actor_ids
        )
        actor = db.actors.get(ids[0]) if ids else None
        if self.encounter.get("player_name"):  # someone else's battle (a tutorial)
            return self.game.expand_message(self.encounter["player_name"], plain=True)
        name = getattr(actor, "display_name", "") or self.game.expand_message(
            self.settings.get("player_name", ""), plain=True
        )  # "\\V[player.name]": a name the player chose
        return name or self.tr("creature.you", "You")

    def trainer_title(self):
        title, name = self.trainer.get("title", ""), self.trainer.get("name", "")
        return f"{title} {name}".strip()

    # -- the story ------------------------------------------------------------------------------
    def say(self, text, *, wait=True):
        """A message: wrapped to the window's width, two lines a page (each page waits)."""
        lines = self.wrap(text)
        pages = [lines[i : i + 2] for i in range(0, len(lines), 2)] or [[""]]
        for index, page in enumerate(pages):
            last = index == len(pages) - 1
            self.steps.append(_Step("text", "\n".join(page), wait if last else True))

    MESSAGE_WIDTH = 208  # pixels of text a line of the message window holds (26 tiles)

    def text_width(self, value):
        value = str(value)
        if self.font is not None and self.font.covers(value):
            return self.font.width(value)
        from asteria.platform.pygame_battle_ui import font_for_text

        base = self._font(16)
        return font_for_text(self.pg, base, value, self._cjk, 12).size(value)[0]

    def wrap(self, text, width=None):
        """Lines of ``text`` that fit ``width`` (the message window): its own line breaks
        kept, words moved down whole (a word longer than a line is split by characters,
        which is also how text without spaces - Chinese - wraps)."""
        width = width or self.MESSAGE_WIDTH
        lines = []
        for paragraph in str(text).split("\n"):
            line = ""
            for word in paragraph.split(" ") if " " in paragraph else list(paragraph):
                joiner = " " if line and " " in paragraph else ""
                candidate = line + joiner + word
                if self.text_width(candidate) <= width or not line:
                    line = candidate
                    while self.text_width(line) > width and len(line) > 1:
                        cut = len(line)
                        while cut > 1 and self.text_width(line[:cut]) > width:
                            cut -= 1
                        lines.append(line[:cut])
                        line = line[cut:]
                else:
                    lines.append(line)
                    line = word
            lines.append(line)
        return lines

    def act(self, kind, **args):
        self.steps.append(_Step(kind, wait=False, **args))

    def _hp(self, member_id):
        battle = self.game.battle
        if battle is None or member_id not in battle.members:
            return 0.0
        pool = battle.member(member_id).subject.resources
        resource = self.game.rules.knockout_resource_id
        return float(pool.current(resource)) if pool.contains(resource) else 0.0

    def _max_hp(self, member_id):
        """A unit's top health; remembered, so the story can still draw it after the battle
        itself has ended (the last foe's fall is told after the win is settled)."""
        battle = self.game.battle
        if battle is not None and member_id in battle.members:
            pool = battle.member(member_id).subject.resources
            resource = self.game.rules.knockout_resource_id
            self.max_hp[member_id] = (
                float(pool.maximum(resource)) if pool.contains(resource) else 1.0
            )
        return self.max_hp.get(member_id, 1.0)

    def _remember_hp(self):
        battle = self.game.battle
        for member_id in battle.members if battle is not None else ():
            self._max_hp(member_id)
            value = self._hp(member_id)
            self.shown_hp.setdefault(member_id, value)
            self.target_hp.setdefault(member_id, value)

    def _stage(self, side):
        ids = self.game.stage_ids(side) if self.game.battle is not None else ()
        return ids[0] if ids else None

    def _intro(self):
        """The opening as the handheld games play it: the foe (or its trainer) slides in from
        the left while the player slides in from the right; the foe's line; a trainer steps
        away and throws; the foe's info box slides in; the player throws the first creature,
        its box slides in."""
        foe = self._stage("enemies")
        mine = self._stage("heroes")
        self._lead(mine)
        self.back_shown = bool(self.settings.get("player_back"))
        self.slides["intro"] = (self.time, SLIDE_SECONDS)  # from the very first frame
        if self.trainer:
            self.trainer_shown = True
        else:
            self.visible["enemies"] = foe
        self.act("slide", name="intro", seconds=SLIDE_SECONDS)
        if self.trainer:
            self.say(
                self.tr(
                    "creature.trainer_challenge",
                    "{trainer} would like to battle!",
                    trainer=self.trainer_title(),
                )
            )
            self.act("slide", name="trainer_out", seconds=0.4)
            self.act("trainer", show=False)
            self.say(
                self.tr(
                    "creature.trainer_sent_out",
                    "{trainer} sent out {name}!",
                    trainer=self.trainer_title(),
                    name=self.name(foe),
                ),
                wait=False,
            )
            self.act("send_out", side="enemies", member=foe)
        else:
            if "legendary" in self.tags:
                line = self.tr(
                    "creature.legendary_appeared", "{name} appeared!", name=self.name(foe)
                )
            else:
                line = self.tr("creature.appeared", "Wild {name} appeared!", name=self.name(foe))
            self.say(line)
        self.act("box", side="enemies")
        if mine is not None:
            self.say(self.tr("creature.go", "Go! {name}!", name=self.name(mine)), wait=False)
            self.act("send_out", side="heroes", member=mine)
            self.act("box", side="heroes")
        self.act("mark")
        if self.game.battle is not None:
            self.act("command")

    # -- the party's battle order ----------------------------------------------------------------
    def _party(self):
        """The party in the battle's order: the creature out first; a switch swaps the two
        places for the battle (the party's own order is untouched)."""
        pets = {p.instance_id: p for p in self.game.party_pets()}
        order = [i for i in self.order if i in pets]
        order += [i for i in pets if i not in order]
        self.order = order
        return [pets[i] for i in order]

    def _lead(self, member_id):
        """Put ``member_id``'s creature first in the battle order (the one sent out)."""
        pet = self.game.pet_of_member(member_id) if member_id else None
        order = [p.instance_id for p in self._party()]
        if pet is not None and pet.instance_id in order:
            order.remove(pet.instance_id)
            order.insert(0, pet.instance_id)
        self.order = order

    def _swap_order(self, out_member, in_member):
        a, b = self.game.pet_of_member(out_member), self.game.pet_of_member(in_member)
        order = [p.instance_id for p in self._party()]
        if a is not None and b is not None and a.instance_id in order and b.instance_id in order:
            i, j = order.index(a.instance_id), order.index(b.instance_id)
            order[i], order[j] = order[j], order[i]
        self.order = order

    def _foe_hp_share(self):
        """(health, top health) of the foe on the screen (a fallen one until the next comes
        out - the game reads the one that is there)."""
        foe = self.visible["enemies"] or self._stage("enemies")
        if foe is None:
            return 0, 0.0
        return self._hp(foe), max(1.0, self._max_hp(foe))

    def _go_line(self, member_id):
        """A creature sent in mid-battle: the line follows how hurt the foe is (the game's
        hpthresholds)."""
        hp, top = self._foe_hp_share()
        share = max(1, int(hp * 100 / top)) if hp else 0
        name = self.name(member_id)
        if share > 69 or hp == 0:
            return self.tr("creature.go", "Go! {name}!", name=name)
        if share > 39:
            return self.tr("creature.do_it", "Do it! {name}!", name=name)
        if share > 9:
            return self.tr("creature.go_for_it", "Go for it, {name}!", name=name)
        return self.tr("creature.foe_weak", "Your foe's weak!\nGet 'em, {name}!", name=name)

    def _come_back_line(self, member_id):
        """A creature called back: the line follows how much the foe lost since it came out."""
        hp, _top = self._foe_hp_share()
        before = self.foe_hp_mark
        name = self.name(member_id)
        if before is None or hp >= before or before <= 0:
            return self.tr(
                "creature.thats_enough", "{name}, that's enough!\nCome back!", name=name
            )
        lost = (before - hp) * 100 / before
        if lost <= 29:
            return self.tr("creature.come_back", "{name}, come back!", name=name)
        if lost <= 69:
            return self.tr("creature.ok_come_back", "{name}, OK!\nCome back!", name=name)
        return self.tr("creature.good_come_back", "{name}, good!\nCome back!", name=name)

    # -- the round -------------------------------------------------------------------------------
    def choose(self, choice):
        """The player's choice for this round: ``("move", ability_id)``, ``("switch",
        member_id)``, ``("item", item_id)``, ``("ball", item_id)`` or ``("run",)``. Switches,
        items, balls and running happen at once (before any move); a move waits for its turn."""
        game = self.game
        actor = self._stage("heroes")
        self.phase = "story"
        kind = choice[0]
        if kind == "run":
            reason = game.escape_unavailable()
            if self.trainer or "no_escape" in self.tags:
                self.say(
                    self.game.expand_message(self.encounter["no_running_text"], plain=True)
                    if self.encounter.get("no_running_text")
                    else self.tr(
                        "creature.no_running", "No! There's no running from a trainer battle!"
                    )
                )
                self.act("command")
                return
            if reason:
                self.say(reason)
                self.act("command")
                return
            result = game.attempt_escape(actor)
            if result.succeeded:
                self.say(self.tr("creature.got_away", "Got away safely!"))
                self.act("end")
                return
            self.say(self.tr("creature.cant_escape", "Can't escape!"))
            self.choice = ("done",)
        elif kind == "switch":
            self._switch_in(actor, choice[1])
            self.choice = ("done",)
        elif kind == "ball":
            self._throw_ball(actor, choice[1])
            if game.battle is None or not game.active_enemy_ids():
                return
            self.choice = ("done",)
        elif kind == "item":
            item = game.project.rpg_database.items.get(choice[1])
            self.say(
                self.tr(
                    "creature.used_item",
                    "{player} used {item}!",
                    player=self.player_name(),
                    item=getattr(item, "display_name", choice[1]),
                )
            )
            before = self._hp(actor)
            game.use_battle_item(actor, choice[1], (actor,))
            self.act("hp", values={actor: self._hp(actor)})
            if self._hp(actor) > before:
                self.say(
                    self.tr(
                        "creature.hp_restored", "{name}'s HP was restored.", name=self.name(actor)
                    )
                )
            game.drain_battle_log()
            self.choice = ("done",)
        else:
            self.choice = choice
        self._resolve_round()

    def _resolve_round(self):
        """Every turn of the round in the battle's order: the player's creature uses its move
        (or nothing, when it already switched, threw or ran), the foes use theirs."""
        game = self.game
        battle = game.battle
        actor = self._stage("heroes")
        move = self.choice[1] if self.choice is not None and self.choice[0] == "move" else None
        game.plan_round({actor: move} if actor is not None else {})  # foes choose too
        start = None  # the round the choice is for: the one the next turn belongs to
        guard = 0
        while game.battle is not None and guard < 50:
            guard += 1
            if not game.active_enemy_ids() or not game.active_hero_ids():
                break
            actor = game.current_turn_actor()  # may begin a new round: then that round is it
            if actor is None:
                break
            if start is None:
                start = battle.turn_queue.round_index
            elif battle.turn_queue.round_index != start:
                break
            side = battle.member(actor).side
            if side == "heroes":
                if self.choice is not None and self.choice[0] == "out_of_uses":
                    game.use_out_of_uses_move(actor)
                elif self.choice is not None and self.choice[0] == "move":
                    try:
                        game.use_ability(actor, self.choice[1])
                    except Exception as exc:  # noqa: BLE001 - told to the player, turn passes
                        from asteria.rpg.built_in_text import translated

                        self.say(translated(exc, game.tr))
                self.choice = ("done",)
            else:
                game.enemy_act(actor)
            self._tell(game.drain_battle_log())
            game.end_turn()
            self._tell(game.drain_battle_log())
        if game.battle is not None:  # turns skipped as the round turned over (asleep...)
            self._tell(game.drain_battle_log())
        self.choice = None
        self._after_round()

    def _switch_in(self, out_member, in_member):
        """Call ``out_member`` back (when there is one) and send ``in_member`` out."""
        game = self.game
        if out_member is not None:
            self.say(self._come_back_line(out_member), wait=False)
            self.act("withdraw", side="heroes", member=out_member)
            game.switch_pet(out_member, in_member)
            self._swap_order(out_member, in_member)
        else:
            game.send_in_pet(in_member)
            self._lead(in_member)
        game.drain_battle_log()
        for name in self.counter_names:  # a creature coming in starts from even stages
            self.counter_seen.pop((in_member, name), None)
        self.say(self._go_line(in_member), wait=False)
        self.act("send_out", side="heroes", member=in_member)
        self.act("box", side="heroes")
        self.act("mark")

    def _state_line(self, state_id, moment, member_id, fallback=None):
        """The project's line for an ailment ``moment`` (``applied``, ``already``, ``tick``,
        ``prevented``, ``expired``, ``cured``) from ``state_messages``, with ``{name}``."""
        lines = dict(self.state_messages.get(state_id) or {})
        template = lines.get(moment)
        if template == "":  # the project keeps this moment silent
            return ""
        if not template:
            return fallback
        return str(template).replace("{name}", self.name(member_id, owner=True))

    def _tell(self, entries):
        """Battle log entries as the story: who used what, a miss, bars, critical blows,
        effectiveness, stat stages, ailments, fainting."""
        game = self.game
        rolled = []  # the outcome tags of the next action's hit checks
        later = []  # drain / recoil logged before the action they belong to
        for entry in entries:
            kind = entry.kind
            data = dict(entry.data or {})
            if kind == "hit_check":
                rolled.extend(str(t) for t in data.get("tags", ()))
            elif kind in ("drain", "recoil"):
                later.append(entry)
            elif kind == "action" and entry.ability_id:
                self._tell_action(entry, rolled)
                for extra in later:
                    self._tell_drain_or_recoil(extra)
                rolled, later = [], []
            elif kind == "strikes":
                count = int(data.get("count", 1))
                self.say(self.tr("creature.hit_times", "Hit {count} time(s)!", count=count))
            elif kind == "sent_in" and data.get("side") == "enemies":
                self._tell_foe_sent_in(entry.member_id)
            elif kind == "state_applied":
                self._tell_state(entry, data)
            elif kind == "turn_skipped":
                for state_id in data.get("states", ()):
                    line = self._state_line(state_id, "prevented", entry.member_id)
                    if line:
                        self.say(line)
                        break
            elif kind == "state_tick":
                line = self._state_line(data.get("state", ""), "tick", entry.member_id)
                if line:
                    self.say(line, wait=False)
                member = entry.member_id
                if game.battle is not None and member in game.battle.members:
                    self.act("hp", values={member: self._hp(member)}, hit=(member,))
                    self._faint_if_down(member)
            elif kind == "state_expired":
                line = self._state_line(data.get("state", ""), "expired", entry.member_id)
                if line:
                    self.say(line)
            elif kind == "state_removed" and data.get("trigger") == "chance":
                line = self._state_line(data.get("state", ""), "cured", entry.member_id)
                if line:
                    self.say(line)

    def _tell_drain_or_recoil(self, entry):
        game = self.game
        member = entry.member_id
        if game.battle is None or member not in game.battle.members:
            return
        self.act("hp", values={member: self._hp(member)})
        if entry.kind == "drain":
            target = (entry.target_ids or (member,))[0]
            self.say(
                self.tr(
                    "creature.drained",
                    "{name} had its\nenergy drained!",
                    name=self.name(target, owner=True),
                )
            )
        else:
            self.say(
                self.tr(
                    "creature.recoil",
                    "{name} is hit\nwith recoil!",
                    name=self.name(member, owner=True),
                )
            )
            self._faint_if_down(member)

    def _tell_action(self, entry, rolled):
        game = self.game
        user = entry.member_id
        self.say(
            self.tr(
                "creature.used",
                "{user} used {move}!",
                user=self.name(user, owner=True),
                move=self.move_name(entry.ability_id),
            ),
            wait=False,  # the game moves on by itself: the bars drain under the line
        )
        definition = game.project.gameplay_library.abilities.get(entry.ability_id)
        fail = self.settings.get("fail_tag", "")
        if fail and fail in getattr(definition, "tags", ()):  # a move with nothing it can do
            self.say(self.tr("creature.but_it_failed", "But it failed!"))
            return
        if self.settings.get("miss_tag", "outcome.miss") in rolled:
            self.say(
                self.tr(
                    "creature.missed",
                    "{name}'s\nattack missed!",
                    name=self.name(user, owner=True),
                )
            )
            return
        values = {t: self._hp(t) for t in entry.target_ids if t in game.battle.members}
        values[user] = self._hp(user)
        self.act("hp", values=values, hit=tuple(entry.target_ids))
        if self.settings.get("crit_tag", "outcome.crit") in rolled:
            self.say(self.tr("creature.critical", "A critical hit!"))
        prefix = str(self.settings.get("effectiveness_rules", ""))
        outcome_lines = dict(self.settings.get("outcome_lines") or {})
        for target_id, outcome in entry.outcomes or ():
            tags = set(getattr(outcome, "outcome_tags", ()) or ())
            special = next((t for t in outcome_lines if t in tags), None)
            if special is not None:  # e.g. a target that protected itself
                self.say(
                    str(outcome_lines[special]).replace("{name}", self.name(target_id, owner=True))
                )
                continue
            ratio = _effectiveness(outcome, prefix)
            if ratio == 0:
                self.say(
                    self.tr(
                        "creature.no_effect",
                        "It doesn't affect {name}...",
                        name=self.name(target_id, owner=True),
                    )
                )
            elif ratio > 1.001:
                self.say(self.tr("creature.super_effective", "It's super effective!"))
            elif ratio < 0.999:
                self.say(self.tr("creature.not_very_effective", "It's not very effective..."))
        self._tell_counters(entry)
        for target_id in values:
            self._faint_if_down(target_id)

    def _tell_counters(self, entry):
        """Stat stages that moved since last told (``counters`` names them): rose / fell,
        sharply / harshly - from the action or anything it set off; a stage the action meant
        to move that was already at its end would not go further."""
        game = self.game
        if not self.counter_names or game.battle is None:
            return
        battle = game.battle
        moved_any = set()
        for member_id in (*game.stage_ids("enemies"), *game.stage_ids("heroes")):
            pool = battle.member(member_id).subject.resources
            for counter, label in self.counter_names.items():
                if not pool.contains(counter):
                    continue
                now = pool.current(counter)
                before = self.counter_seen.get((member_id, counter), 0.0)
                self.counter_seen[(member_id, counter)] = now
                moved = int(round(now - before))
                if moved:
                    moved_any.add((member_id, counter))
                    words = dict(name=self.name(member_id, owner=True), stat=label)
                    self.say(self._stat_line(max(-2, min(2, moved)), words))
        definition = game.project.gameplay_library.abilities.get(entry.ability_id)
        for application in getattr(definition, "effects", ()) or ():
            members = (entry.member_id,) if application.mode.value == "self" else entry.target_ids
            for operation in application.effect.operations:
                counter = operation.target
                if counter not in self.counter_names:
                    continue
                value = operation.value
                wanted = (
                    float(value)
                    if isinstance(value, (int, float))
                    else sum(
                        t.coefficient
                        for t in getattr(value, "terms", ())
                        if t.source.value == "constant"
                    )
                )
                for member_id in members:
                    if (member_id, counter) in moved_any or member_id not in battle.members:
                        continue
                    words = dict(
                        name=self.name(member_id, owner=True), stat=self.counter_names[counter]
                    )
                    if wanted > 0:
                        self.say(
                            self.tr(
                                "creature.stat_wont_rise",
                                "{name}'s {stat}\nwon't go higher!",
                                **words,
                            )
                        )
                    elif wanted < 0:
                        self.say(
                            self.tr(
                                "creature.stat_wont_fall",
                                "{name}'s {stat}\nwon't go lower!",
                                **words,
                            )
                        )

    def _stat_line(self, moved, words):
        """The line for a stat stage that moved by ``moved`` (-2..2)."""
        if moved >= 2:
            return self.tr("creature.stat_sharply_rose", "{name}'s {stat}\nsharply rose!", **words)
        if moved == 1:
            return self.tr("creature.stat_rose", "{name}'s {stat}\nrose!", **words)
        if moved == -1:
            return self.tr("creature.stat_fell", "{name}'s {stat}\nfell!", **words)
        return self.tr("creature.stat_harshly_fell", "{name}'s {stat}\nharshly fell!", **words)

    def _tell_state(self, entry, data):
        state_id = data.get("state", "")
        member = entry.member_id
        if data.get("applied"):
            definition = self.game.project.gameplay_library.states.get(state_id)
            label = getattr(definition, "display_name", "") or state_id
            fallback = self.tr(
                "creature.state_applied",
                "{name} is now {state}!",
                name=self.name(member, owner=True),
                state=label,
            )
            line = self._state_line(state_id, "applied", member, fallback)
            if line:
                self.say(line)
            return
        if float(data.get("chance", 1.0)) < 1.0:
            return  # a secondary effect that did not come: nothing is said
        reason = data.get("reason", "")
        if reason == "immune":
            self.say(
                self.tr(
                    "creature.no_effect",
                    "It doesn't affect {name}...",
                    name=self.name(member, owner=True),
                )
            )
        elif reason == "already" and self._state_line(state_id, "already", member):
            self.say(self._state_line(state_id, "already", member))
        else:
            self.say(self.tr("creature.but_it_failed", "But it failed!"))

    def _tell_foe_sent_in(self, member):
        """A trainer's next creature: the player may first change theirs (the game asks
        when it has another one ready), then the foe comes out."""
        if self.trainer and self.game.bench_ids("heroes") and self._stage("heroes"):
            self.say(
                self.tr(
                    "creature.about_to_use",
                    "{trainer} is\nabout to use {name}.",
                    trainer=self.trainer_title(),
                    name=self.name(member),
                )
            )
            self.say(
                self.tr(
                    "creature.will_change",
                    "Will {player} change\ncreatures?",
                    player=self.player_name(),
                ),
                wait=False,
            )
            self.act("ask", question="change", member=member)
        self.say(
            self.tr(
                "creature.trainer_sent_out",
                "{trainer} sent out {name}!",
                trainer=self.trainer_title() or self.tr("creature.foe", "The foe"),
                name=self.name(member),
            ),
            wait=False,
        )
        self.act("send_out", side="enemies", member=member)
        self.act("box", side="enemies")
        self.act("mark")

    def _faint_if_down(self, member_id):
        if member_id in self.drop or self._hp(member_id) > 0:
            return
        self.act("faint", member=member_id)
        self.say(
            self.tr("creature.fainted", "{name} fainted!", name=self.name(member_id, owner=True))
        )

    def _after_round(self):
        game = self.game
        if game.battle is None:
            return
        if not game.side_standing("enemies"):
            self._victory()
            return
        if not game.active_hero_ids():
            if game.switch_needed("heroes"):
                if not self.trainer and "no_escape" not in self.tags:
                    # in the wild the game asks first; "no" tries to run
                    self.say(self.tr("creature.use_next", "Use next creature?"), wait=False)
                    self.act("ask", question="next")
                    return
                self.act("party", forced=True)
                return
            self._defeat()
            return
        self.act("command")

    def _throw_ball(self, actor, item_id):
        game = self.game
        target = self._stage("enemies")
        item = game.project.rpg_database.items.get(item_id)
        self.say(
            self.tr(
                "creature.threw",
                "{player} used {item}!",
                player=self.player_name(),
                item=getattr(item, "display_name", item_id),
            ),
            wait=False,
        )
        chance = game.capture_chance(target, item_id) or 0.0
        caught = game.attempt_capture(actor, target, item_id=item_id)
        logged = [e for e in game.drain_battle_log() if e.kind == "capture"]
        shakes = (logged[-1].data or {}).get("shakes") if logged else None
        if shakes is None:  # a rule without shake checks: as many shakes as the odds suggest
            rng = random.Random(f"{game.encounter_id}:{target}:{len(game.pets())}")
            shakes = 3 if caught else min(3, sum(rng.random() < chance**0.25 for _ in range(3)))
        self.act("throw", member=target, shakes=min(3, int(shakes)), caught=caught)
        if caught:
            self.say(
                self.tr("creature.caught", "Gotcha! {name} was caught!", name=self.name(target))
            )
            pet = game.pets()[-1]
            if pet.instance_id not in {p.instance_id for p in game.party_pets()}:
                self.say(
                    self.tr(
                        "creature.sent_to_storage",
                        "{name} was transferred to storage.",
                        name=pet.name(game.pet_species(pet)),
                    )
                )
            if not game.active_enemy_ids() and not game.bench_ids("enemies"):
                self._victory(caught=True)
        else:
            lines = (
                lambda: self.tr("creature.broke_free", "Oh, no! It broke free!"),
                lambda: self.tr("creature.almost", "Aww! It appeared to be caught!"),
                lambda: self.tr("creature.so_close", "Aargh! Almost had it!"),
                lambda: self.tr("creature.shoot", "Shoot! It was so close, too!"),
            )
            self.say(lines[min(shakes, 3)]())

    def _victory(self, caught=False):
        game = self.game
        self.act("music", track=self.music("victory"))  # the win's tune starts as the foe falls
        before = {p.instance_id: (p.level, p.experience, p.species_id) for p in game.pets()}
        currencies = dict(game.save.rpg_state.currencies)
        try:
            game.finish_victory()
        except Exception as exc:  # noqa: BLE001 - the field must come back
            self.say(str(exc))
        game.drain_battle_log()
        for pet in game.pets():
            old = before.get(pet.instance_id)
            if old is None:
                continue
            species = game.pet_species(pet)
            gained = _experience_between(species, old[0], old[1], pet.level, pet.experience)
            if gained > 0:
                self.say(
                    self.tr(
                        "creature.exp",
                        "{name} gained {amount} EXP. Points!",
                        name=pet.name(species),
                        amount=f"{gained:g}",
                    )
                )
            if pet.level > old[0]:
                self.say(
                    self.tr(
                        "creature.level_up",
                        "{name} grew to LV. {level}!",
                        name=pet.name(species),
                        level=pet.level,
                    )
                )
            if pet.species_id != old[2]:
                self.say(
                    self.tr(
                        "creature.evolved",
                        "{name} evolved into {species}!",
                        name=pet.nickname
                        or game.project.rpg_database.pet_species[old[2]].display_name,
                        species=species.display_name,
                    )
                )
        if self.trainer:
            self.say(
                self.tr(
                    "creature.defeated_trainer",
                    "{player} defeated {trainer}!",
                    player=self.player_name(),
                    trainer=self.trainer_title(),
                )
            )
            speech = self.trainer.get("defeat_text")
            if speech:  # the trainer comes back out and says a word
                self.slides.pop("trainer_out", None)
                self.visible["enemies"] = None
                self.act("trainer", show=True)
                self.act("slide", name="trainer_in", seconds=0.4)
                for page in speech if isinstance(speech, list) else [speech]:
                    self.say(self.game.expand_message(str(page), plain=True))
            prize = float(self.trainer.get("prize", 0) or 0)
            currency = self.settings.get("currency", "gold")
            if prize:
                state = game.save.rpg_state
                state.currencies[currency] = state.currencies.get(currency, 0.0) + prize
                self.say(
                    self.tr(
                        "creature.prize",
                        "{player} got {amount} for winning!",
                        player=self.player_name(),
                        amount=f"{self.settings.get('currency_symbol', '$')}{prize:g}",
                    )
                )
        _ = currencies, caught
        self.act("end")

    def _defeat(self):
        self.say(
            self.tr(
                "creature.out_of_creatures",
                "{player} is out of usable creatures!",
                player=self.player_name(),
            )
        )
        self.say(self.tr("creature.whited_out", "{player} whited out!", player=self.player_name()))
        self.act("lost")

    # -- running the story -----------------------------------------------------------------------
    def update(self, dt, events=()):
        self.time += dt
        for member_id in list(self.flash):
            self.flash[member_id] -= dt
            if self.flash[member_id] <= 0:
                del self.flash[member_id]
        for member_id in list(self.drop):
            self.drop[member_id] += dt
        moving = self._drain_bars(dt)
        if self.phase != "story":
            self._menu_input()
            return
        if self.step is None:
            if moving or self.throw_busy():
                return
            if not self.steps:
                return
            self._begin(self.steps.pop(0))
        self._run_step(dt, moving)

    def throw_busy(self):
        return self.throw is not None and self.time - self.throw["start"] < self._throw_length()

    def _throw_length(self):
        return 0.9 + 0.55 * self.throw["shakes"] + (0.3 if self.throw["caught"] else 0.4)

    def _begin(self, step):
        self.step, self.step_time = step, 0.0
        kind = step.kind
        if kind == "text":
            self.message, self.shown_chars = step.text, 0.0
        elif kind == "hp":
            self.target_hp.update(step.args["values"])
            for member_id in step.args.get("hit", ()):
                if self.target_hp.get(member_id, 0) < self.shown_hp.get(member_id, 0):
                    self.flash[member_id] = 0.5
        elif kind == "show":
            member = step.args["member"]
            self.visible[step.args["side"]] = member
            self.boxes[step.args["side"]] = self.time - BOX_SLIDE if member else None
            if member is not None:
                value = self._hp(member)
                self.shown_hp[member] = self.target_hp[member] = value
                self.drop.pop(member, None)
        elif kind == "trainer":
            self.trainer_shown = step.args["show"]
        elif kind == "faint":
            self.drop[step.args["member"]] = 0.0
        elif kind == "music":
            self._play(step.args.get("track"))
            self.step = None
        elif kind == "throw":
            self.throw = {"start": self.time, **step.args}
        elif kind == "command":
            self.phase, self.cursor = "command", self.cursor if self.cursor < 4 else 0
            actor = self._stage("heroes")
            self.message = self.tr(
                "creature.what_will",
                "What will\n{name} do?",
                name=self.name(actor) if actor else "",
            )
            self.shown_chars = len(self.message)
            self.step = None
        elif kind == "party":
            self.forced_switch = bool(step.args.get("forced"))
            self.free_switch = False
            self.party_note = ""
            self.phase, self.list_cursor = "party", 0
            self.step = None
        elif kind == "slide":
            self.slides[step.args["name"]] = (self.time, step.args["seconds"])
            if step.args["name"] == "trainer_out":
                pass
        elif kind == "box":
            self.boxes[step.args["side"]] = self.time
        elif kind == "send_out":
            side, member = step.args["side"], step.args["member"]
            self.visible[side] = member
            if member is not None:
                value = self._hp(member)
                self.shown_hp[member] = self.target_hp[member] = value
                self.drop.pop(member, None)
            start = self.time
            if side == "heroes" and self.back_shown:
                self.slides["back_out"] = (start, THROW_SECONDS)
                start += THROW_SECONDS * 0.6
            self.ball = {"start": start, "side": side}
            self.grow[member] = (start + BALL_SECONDS, GROW_SECONDS, True)
            self.boxes[side] = None
        elif kind == "withdraw":
            member = step.args["member"]
            self.grow[member] = (self.time, GROW_SECONDS, False)
            self.boxes[step.args["side"]] = None
        elif kind == "mark":  # someone came out: the foe's health now (the switch lines)
            self.foe_hp_mark = self._foe_hp_share()[0]
            self.step = None
        elif kind == "ask":
            self.prompt = {"kind": step.args["question"], "cursor": 0, **step.args}
            self.phase = "yesno"
            self.step = None
        elif kind == "end":
            self.done = True
            self.step = None
        elif kind == "lost":
            self.done = self.defeated = True
            self.step = None

    def _run_step(self, dt, moving):
        step = self.step
        if step is None:
            return
        self.step_time += dt
        if step.kind == "text":
            self.shown_chars = min(len(self.message), self.shown_chars + TEXT_SPEED * dt)
            typed = self.shown_chars >= len(self.message)
            if self.rt.input.just_pressed("confirm") or self.rt.input.just_pressed("cancel"):
                if not typed:
                    self.shown_chars = len(self.message)
                    return
                self.step = None
                return
            if typed and not step.wait and self.step_time > 0.5:
                self.step = None
            return
        if step.kind == "faint":
            if self.step_time > 0.45:
                self.step = None
            return
        if step.kind == "throw":
            if not self.throw_busy():
                self.step = None
            return
        if step.kind == "slide":
            if self.step_time >= step.args["seconds"]:
                self.step = None
            return
        if step.kind == "box":
            if self.step_time >= BOX_SLIDE:
                self.step = None
            return
        if step.kind == "send_out":
            start, seconds, _ = self.grow.get(step.args["member"], (0, 0, True))
            if self.time >= start + seconds:
                self.ball = None
                self.back_shown = self.back_shown and step.args["side"] != "heroes"
                self.step = None
            return
        if step.kind == "withdraw":
            if self.step_time >= GROW_SECONDS:
                self.visible[step.args["side"]] = None
                self.grow.pop(step.args["member"], None)
                self.step = None
            return
        if step.kind == "show" and self.step_time < 0.25:
            return
        if not moving:
            self.step = None

    def _drain_bars(self, dt):
        moving = False
        for member_id, target in self.target_hp.items():
            shown = self.shown_hp.get(member_id, target)
            if abs(shown - target) < 0.01:
                self.shown_hp[member_id] = target
                continue
            moving = True
            top = max(1.0, self._max_hp(member_id)) if self.game.battle else 1.0
            speed = max(top / 1.2, 20.0) * dt  # a full bar drains in a little over a second
            self.shown_hp[member_id] = (
                max(target, shown - speed) if shown > target else min(target, shown + speed)
            )
        return moving

    # -- menus -----------------------------------------------------------------------------------
    def _pressed(self, name):
        return self.rt.input.just_pressed(name)

    def _menu_input(self):
        if self.phase == "command" and self.auto_choices:  # the game chooses, after a moment
            if self._auto_at is None:
                self._auto_at = self.time
            elif self.time - self._auto_at > float(self.encounter.get("auto_delay", 0.8)):
                self._auto_at = None
                self.choose(self.auto_choices.pop(0))
            return
        if self.phase == "command":
            self._grid_input(4)
            if self._pressed("confirm"):
                [self._open_fight, self._open_bag, self._open_party, self._run][self.cursor]()
        elif self.phase == "fight":
            moves = self._moves()
            self._grid_input(len(moves), attr="list_cursor")
            if self._pressed("cancel"):
                self.phase = "command"
            elif self._pressed("confirm") and self.game.out_of_uses_move(self._stage("heroes")):
                actor = self._stage("heroes")
                self.phase = "story"
                self.say(
                    self.tr(
                        "creature.no_moves_left",
                        "{name} has no moves left!",
                        name=self.name(actor),
                    )
                )
                self.choose(("out_of_uses",))
            elif self._pressed("confirm") and moves:
                move = moves[min(self.list_cursor, len(moves) - 1)]
                record = self.game.unit_record(self._stage("heroes"))
                if record is not None and self.game.pet_uses_left(record, move) == 0:
                    self.phase = "story"
                    self.say(self.tr("creature.no_pp", "There's no PP left for this move!"))
                    self.act("command")
                    return
                self.choose(("move", move))
        elif self.phase == "bag":
            items = self._bag_items()
            if self._pressed("cancel"):
                self.phase = "command"
                return
            if self._pressed("move_left") or self._pressed("move_right"):
                self.pocket, self.list_cursor = 1 - self.pocket, 0
                return
            rows = len(items) + 1  # the last row closes the bag
            if self._pressed("move_up"):
                self.list_cursor = (self.list_cursor - 1) % rows
            if self._pressed("move_down"):
                self.list_cursor = (self.list_cursor + 1) % rows
            if self._pressed("confirm") and self.list_cursor >= len(items):
                self.phase = "command"
                return
            if self._pressed("confirm") and items:
                item_id = items[min(self.list_cursor, len(items) - 1)][0]
                if self.pocket == 1:
                    if self.trainer or "no_capture" in self.tags:
                        self.phase = "story"
                        self.say(
                            self.tr(
                                "creature.no_stealing",
                                "The trainer blocked the ball! Don't be a thief!",
                            )
                        )
                        self.act("command")
                        return
                    self.choose(("ball", item_id))
                else:
                    self.choose(("item", item_id))
        elif self.phase == "yesno":
            self._yes_no_input()
        elif self.phase == "party":
            slots = self._party()
            count = len(slots) + (0 if self.forced_switch else 1)  # + cancel
            if self._pressed("move_up") or self._pressed("move_left"):
                self.list_cursor = (self.list_cursor - 1) % count
            if self._pressed("move_down") or self._pressed("move_right"):
                self.list_cursor = (self.list_cursor + 1) % count
            if self._pressed("cancel") and not self.forced_switch:
                self.phase = "story" if self.free_switch else "command"
                return
            if not self._pressed("confirm"):
                return
            if self.list_cursor >= len(slots):
                self.phase = "story" if self.free_switch else "command"
                return
            pet = slots[self.list_cursor]
            member_id = self.game.pet_member_id(pet)
            if member_id == self._stage("heroes"):
                self.party_note = self.tr(
                    "creature.already_out",
                    "{name} is already in battle!",
                    name=self.name(member_id),
                )
                return
            if member_id not in self.game.bench_ids("heroes"):
                self.party_note = self.tr("creature.no_energy", "There's no will to battle!")
                return
            if self.forced_switch:  # after a faint: in at once, no turn
                self.phase = "story"
                self._switch_in(None, member_id)
                self.act("command")
                return
            if self.free_switch:  # before a trainer's next creature: in before it, no turn
                self.phase = "story"
                waiting, self.steps = self.steps, []
                self._switch_in(self._stage("heroes"), member_id)
                self.steps += waiting
                return
            self.choose(("switch", member_id))

    def _yes_no_input(self):
        prompt = self.prompt or {}
        if self._pressed("move_up") or self._pressed("move_down"):
            prompt["cursor"] = 1 - prompt.get("cursor", 0)
        answer = None
        if self._pressed("cancel"):
            answer = False
        elif self._pressed("confirm"):
            answer = prompt.get("cursor", 0) == 0
        if answer is None:
            return
        self.prompt = None
        game = self.game
        if prompt.get("kind") == "change":
            if answer:
                self.phase, self.list_cursor = "party", 0
                self.forced_switch, self.free_switch, self.party_note = False, True, ""
            else:
                self.phase = "story"
            return
        if prompt.get("kind") == "next":
            if answer:
                self.phase, self.list_cursor = "party", 0
                self.forced_switch, self.free_switch, self.party_note = True, False, ""
                return
            self.phase = "story"
            runner = (game.bench_ids("heroes") or (None,))[0]
            reason = game.escape_unavailable()
            result = None if reason else game.attempt_escape(runner)
            game.drain_battle_log()
            if result is not None and result.succeeded:
                self.say(self.tr("creature.got_away", "Got away safely!"))
                self.act("end")
                return
            self.say(reason or self.tr("creature.cant_escape", "Can't escape!"))
            self.act("party", forced=True)

    def _grid_input(self, count, attr="cursor"):
        """A 2 x 2 grid: left / right move along a row, up / down between the rows."""
        if count <= 0:
            return
        value = getattr(self, attr)
        if self._pressed("move_right") and value % 2 == 0 and value + 1 < count:
            value += 1
        elif self._pressed("move_left") and value % 2 == 1:
            value -= 1
        elif self._pressed("move_down") and value + 2 < count:
            value += 2
        elif self._pressed("move_up") and value >= 2:
            value -= 2
        setattr(self, attr, value)

    def _open_fight(self):
        self.phase, self.list_cursor = "fight", 0

    def _open_bag(self):
        self.phase, self.list_cursor, self.pocket = "bag", 0, 0

    def _open_party(self):
        self.phase, self.list_cursor, self.forced_switch = "party", 0, False
        self.free_switch = False
        self.party_note = ""

    def _run(self):
        self.choose(("run",))

    def _moves(self):
        actor = self._stage("heroes")
        if actor is None:
            return ()
        return tuple(self.game.battle.member(actor).ability_ids)[:4]

    def _bag_items(self):
        """``[(item_id, count)]`` of the open pocket: 0 = items usable in battle, 1 = capture
        items (any capture rule's)."""
        from asteria.runtime.session.ability_use import cured_states

        game = self.game
        db = game.project.rpg_database
        inventory = game.save.rpg_state.inventory
        balls = set()
        for rule in db.capture_rules.values():
            balls |= set(rule.capture_items())
        result = []
        for item_id in sorted(db.items):
            count = inventory.count(item_id)
            if count <= 0:
                continue
            item = db.items[item_id]
            if self.pocket == 1 and item_id in balls:
                result.append((item_id, count))
            elif (
                self.pocket == 0
                and item_id not in balls
                and (item.battle_ability or item.use_effects or cured_states(item))
            ):
                result.append((item_id, count))
        return result

    # -- drawing ---------------------------------------------------------------------------------
    def _font(self, size=16):
        font = self._fonts.get(size)
        if font is None:
            font = self._fonts[size] = self.pg.font.Font(None, size)
        return font

    def _text(self, value, x, y, colour=INK, shadow=INK_SHADOW, size=16, anchor="topleft"):
        value = str(value)
        if self.font is not None and self.font.covers(value):
            rect = self.pg.Rect(0, 0, self.font.width(value), self.font.line)
            setattr(rect, anchor, (int(x), int(y)))
            self.font.render(self.surface, value, rect.x, rect.y, colour, shadow)
            return rect
        from asteria.platform.pygame_battle_ui import font_for_text, renderable_text

        base = self._font(size)
        font = font_for_text(self.pg, base, value, self._cjk, max(9, size - 4))
        text = renderable_text(self.pg, font, str(value), self._glyphs)
        image = font.render(text, False, colour)
        rect = image.get_rect(**{anchor: (int(x), int(y))})
        if shadow is not None:
            back = font.render(text, False, shadow)
            self.surface.blit(back, rect.move(1, 0))
            self.surface.blit(back, rect.move(0, 1))
            self.surface.blit(back, rect.move(1, 1))
        self.surface.blit(image, rect)
        return rect

    def _image(self, kind, key, size):
        """Project art for ``kind`` (front / back / trainer / background) named by ``key``, at
        ``size``; ``None`` when the project has none."""
        cache_key = (kind, key, size)
        if cache_key in self._images:
            return self._images[cache_key]
        image = None
        pattern = self.settings.get(kind)
        if pattern:
            path = Path(self.rt.resource_root) / str(pattern).format(
                species=key, trainer=key, item=key
            )
            if path.is_file():
                try:
                    image = self.pg.image.load(str(path)).convert_alpha()
                except Exception:  # noqa: BLE001 - a broken file is drawn as a shape
                    image = None
                if image is not None and size and image.get_size() != size:
                    from asteria.graphics.scaling import resized

                    image = resized(self.pg, image, size)
        self._images[cache_key] = image
        return image

    def _load_font(self, name):
        if not self.settings.get(name):
            return None
        from asteria.graphics.bitmap_font import BitmapFont

        try:
            return BitmapFont(self.pg, self._path(self.settings[name]))
        except (OSError, ValueError, KeyError):
            return None

    def _path(self, value):
        return Path(self.rt.resource_root) / str(value)

    def _art(self, name):
        """The project's picture for a part of the screen (``battle.creature_screen[name]``)."""
        key = ("art", name)
        if key not in self._images:
            image = None
            value = self.settings.get(name)
            if isinstance(value, str) and "\\" in value:  # \\V[..]: a picture per variable value
                value = self.game.expand_message(value, plain=True)
            if isinstance(value, str) and self._path(value).is_file():
                try:
                    image = self.pg.image.load(str(self._path(value))).convert_alpha()
                except Exception:  # noqa: BLE001 - a broken file is drawn as before
                    image = None
            self._images[key] = image
        return self._images[key]

    def _bar_tiles(self, colour):
        key = ("bar", colour)
        if key not in self._images:
            image = None
            value = (
                self.settings.get("hp_bar") if colour != "exp" else self.settings.get("exp_bar")
            )
            if isinstance(value, dict):
                value = value.get(colour)
            if isinstance(value, str) and self._path(value).is_file():
                image = self.pg.image.load(str(self._path(value))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _tile_bar(self, tiles, x, y, share, cells):
        """A bar of ``cells`` 8-pixel tiles, each the tile of its fill (0-8 pixels)."""
        pixels = round(cells * 8 * max(0.0, min(1.0, share)))
        if share > 0 and pixels == 0:
            pixels = 1
        offset = 9 if tiles.get_width() >= 80 else 0  # strips with a leading cap tile
        for cell in range(cells):
            filled = max(0, min(8, pixels - cell * 8))
            self.surface.blit(
                tiles, (x + cell * 8, y), ((offset + filled) * 8 % tiles.get_width(), 0, 8, 8)
            )

    def _offset(self, member_id, side):
        """How far a creature's picture sits below its battle spot (``sprite_offsets``)."""
        table = self._images.get(("offsets",))
        if table is None:
            value = self.settings.get("sprite_offsets") or {}
            if isinstance(value, str):
                import json

                path = self._path(value)
                value = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
            table = self._images[("offsets",)] = dict(value)
        entry = table.get(self._species_key(member_id), {})
        if side == "heroes":
            return int(entry.get("back", 0))
        return int(entry.get("front", 0)) - int(entry.get("lift", 0))

    def _species_key(self, member_id):
        record = self.game.unit_record(member_id) if member_id else None
        return record.species_id if record is not None else str(member_id).split(":", 1)[0]

    def draw(self):
        s = self.surface
        s.fill((0, 0, 0, 255))
        self._draw_background()
        if self.phase == "party":
            self._draw_party()
        elif self.phase == "bag":
            self._draw_bag()
        else:
            self._draw_creatures()
            self._draw_info_boxes()
            self._draw_message()
            if self.phase == "command":
                self._draw_commands()
            elif self.phase == "fight":
                self._draw_fight()
            elif self.phase == "yesno":
                self._draw_yes_no()
        screen = self.rt.screen
        sw, sh = screen.get_size()
        scale = max(1, min(sw // W, sh // H))
        screen.fill((0, 0, 0, 255))
        big = self.pg.transform.scale(s, (W * scale, H * scale))
        screen.blit(big, ((sw - W * scale) // 2, (sh - H * scale) // 2))

    def _draw_background(self):
        pg, s = self.pg, self.surface
        picture = self._art("background")
        if picture is not None:
            s.blit(picture, (0, 0))
        else:
            s.fill(GRASS, (0, 0, W, BOX_TOP))
            for y in range(4, BOX_TOP, 8):
                pg.draw.line(s, GRASS_BAND, (0, y), (W, y), 3)
            for rect in ((120, 52, 112, 24), (8, 94, 128, 28)):  # the two platforms
                pg.draw.ellipse(s, PAD, rect)
                pg.draw.ellipse(s, PAD_EDGE, rect, 2)
        s.fill(MSG_FILL, (0, BOX_TOP, W, H - BOX_TOP))

    def _creature_picture(self, member_id, side):
        kind = "back" if side == "heroes" else "front"
        key = self._species_key(member_id)
        image = self._image(kind, key, (64, 64))
        if image is not None:
            return image
        return self._shape(key, back=side == "heroes")

    def _shape(self, key, *, back):
        """A stand-in 64 x 64 creature: a round body in a colour of its own with ears."""
        cache_key = ("shape", key, back)
        if cache_key in self._images:
            return self._images[cache_key]
        pg = self.pg
        image = pg.Surface((64, 64), pg.SRCALPHA)
        seed = sum(ord(c) for c in key)
        colour = ((seed * 53) % 160 + 60, (seed * 97) % 160 + 60, (seed * 31) % 160 + 60)
        dark = tuple(max(0, c - 70) for c in colour)
        pg.draw.ellipse(image, colour, (10, 18, 44, 42))
        pg.draw.ellipse(image, dark, (10, 18, 44, 42), 2)
        pg.draw.polygon(image, colour, ((16, 26), (20, 6), (28, 22)))
        pg.draw.polygon(image, colour, ((48, 26), (44, 6), (36, 22)))
        if not back:
            pg.draw.circle(image, (40, 40, 40), (26, 36), 3)
            pg.draw.circle(image, (40, 40, 40), (38, 36), 3)
        self._images[cache_key] = image
        return image

    def _progress(self, name):
        """How far a slide has gone, 0..1 (None when it never started)."""
        slide = self.slides.get(name)
        if slide is None:
            return None
        start, seconds = slide
        return max(0.0, min(1.0, (self.time - start) / seconds)) if seconds else 1.0

    def _intro_offsets(self):
        """(foe side dx, player side dx) of the opening slide."""
        k = self._progress("intro")
        k = 1.0 if k is None else k
        return -round((1 - k) * W), round((1 - k) * W)

    def _draw_creatures(self):
        pg, s = self.pg, self.surface
        foe_dx, mine_dx = self._intro_offsets()
        foe = self.visible["enemies"]
        if self.trainer_shown:
            image = self._image("trainer", self.trainer.get("sprite", "trainer"), (64, 64))
            if image is None:
                image = self._shape(self.trainer.get("sprite", "trainer"), back=False)
            out = self._progress("trainer_out") or 0.0
            back_in = self._progress("trainer_in")
            if back_in is not None:  # sliding back in from the right after the win
                out = 1.0 - back_in
            centre = (FOE_CENTRE[0] + foe_dx + round(out * 120), FOE_CENTRE[1])
            s.blit(image, image.get_rect(center=centre))
        if foe is not None and not self._in_ball(foe):
            spot = (FOE_CENTRE[0] + foe_dx, FOE_CENTRE[1] + self._offset(foe, "enemies"))
            self._blit_creature(foe, "enemies", spot)
        if self.throw is not None:
            self._draw_throw()
        mine = self.visible["heroes"]
        if mine is not None:
            bob = 1 if self.phase in ("command", "fight") and int(self.time * 2.5) % 2 else 0
            spot = (MINE_CENTRE[0] + mine_dx, MINE_CENTRE[1] + self._offset(mine, "heroes") + bob)
            self._blit_creature(mine, "heroes", spot)
        if self.back_shown:
            self._draw_player_back(mine_dx)
        if self.ball is not None:
            self._draw_ball_out()
        _ = pg

    def _draw_player_back(self, dx):
        """The player seen from behind (``player_back``: frames under each other, 64 x 64):
        standing, then winding up, throwing and stepping out to the left."""
        image = self._art("player_back")
        if image is None:
            return
        size = int(self.settings.get("player_back_size", 64))
        frames = max(1, image.get_height() // size)
        k = self._progress("back_out")
        frame, out = 0, 0
        if k is not None:
            frame = min(frames - 1, int(k / 0.55 * frames)) if k < 0.55 else frames - 1
            out = round(max(0.0, (k - 0.45) / 0.55) * 110)
        centre = (MINE_CENTRE[0] + dx - out, MINE_CENTRE[1] + 4)
        piece = image.subsurface((0, frame * size, size, size))
        self.surface.blit(piece, piece.get_rect(center=centre))

    def _draw_ball_out(self):
        """A ball flying from the thrower to the spot, opening as the creature comes out."""
        ball = self.ball
        t = (self.time - ball["start"]) / BALL_SECONDS
        if t < 0:
            return
        if ball["side"] == "heroes":
            (x0, y0), (x1, y1) = (36, 92), (MINE_CENTRE[0], MINE_CENTRE[1] + 10)
        else:
            (x0, y0), (x1, y1) = (W - 20, 24), (FOE_CENTRE[0], FOE_CENTRE[1] + 10)
        k = min(1.0, t)
        x = x0 + (x1 - x0) * k
        y = y0 + (y1 - y0) * k - 34 * 4 * k * (1 - k)
        image = self._art("ball")
        if image is None:
            self.pg.draw.circle(self.surface, (232, 64, 56), (round(x), round(y)), 5)
            return
        size = image.get_width()
        frames = max(1, image.get_height() // size)
        frame = 0 if t < 1.0 else min(frames - 1, 1 + int((t - 1.0) * 6))
        if t > 1.0 + GROW_SECONDS / BALL_SECONDS:
            return
        piece = image.subsurface((0, frame * size, size, size))
        self.surface.blit(piece, piece.get_rect(center=(round(x), round(y))))

    def _blit_creature(self, member_id, side, centre):
        image = self._creature_picture(member_id, side)
        if member_id in self.flash and int(self.flash[member_id] * 16) % 2:
            return
        grow = self.grow.get(member_id)
        if grow is not None:  # coming out of its ball, or going back in
            start, seconds, appearing = grow
            k = max(0.0, min(1.0, (self.time - start) / seconds)) if seconds else 1.0
            scale = k if appearing else 1.0 - k
            if scale <= 0.02:
                return
            if scale < 1.0:
                w, h = image.get_size()
                image = self.pg.transform.scale(
                    image, (max(1, round(w * scale)), max(1, round(h * scale)))
                )
                bottom = centre[1] + 32
                self.surface.blit(image, image.get_rect(midbottom=(centre[0], bottom)))
                return
        rect = image.get_rect(center=centre)
        if member_id in self.drop:
            fall = int(min(1.0, self.drop[member_id] / 0.4) * 64)
            if fall >= 64:
                return
            area = self.pg.Rect(0, 0, 64, 64 - fall)
            self.surface.blit(image, rect.move(0, fall), area)
            return
        self.surface.blit(image, rect)

    def _in_ball(self, member_id):
        throw = self.throw
        if throw is None or throw["member"] != member_id:
            return False
        t = self.time - throw["start"]
        return t > 0.6 and (throw["caught"] or t < self._throw_length() - 0.15)

    def _draw_throw(self):
        pg, s = self.pg, self.surface
        throw = self.throw
        t = self.time - throw["start"]
        if t < 0.6:  # the arc from the player towards the foe
            k = t / 0.6
            x = 40 + (FOE_CENTRE[0] - 40) * k
            y = 90 - 70 * k + 90 * k * k * 0.5
        else:
            x, y = FOE_CENTRE[0], FOE_CENTRE[1] + 16
        if t > self._throw_length() and not throw["caught"]:
            self.throw = None
            return
        shake = 0
        if 0.9 < t < 0.9 + 0.55 * throw["shakes"]:
            phase = (t - 0.9) % 0.55
            shake = -3 if phase < 0.14 else 3 if phase < 0.28 else 0
        centre = (int(x) + shake, int(y))
        pg.draw.circle(s, (232, 64, 56), centre, 5)
        pg.draw.rect(s, WHITE, (centre[0] - 5, centre[1], 11, 5))
        pg.draw.circle(s, (32, 32, 32), centre, 5, 1)
        pg.draw.line(s, (32, 32, 32), (centre[0] - 5, centre[1]), (centre[0] + 5, centre[1]))
        pg.draw.circle(s, WHITE, centre, 2)
        pg.draw.circle(s, (32, 32, 32), centre, 2, 1)

    def _bar(self, x, y, member_id, width=48):
        """The health bar: the project's label and tiles when it has them, else drawn."""
        pg, s = self.pg, self.surface
        top = max(1.0, self._max_hp(member_id))
        share = max(0.0, min(1.0, self.shown_hp.get(member_id, 0.0) / top))
        colour_name = "green" if share > 0.5 else "yellow" if share > 0.2 else "red"
        label, tiles = self._art("hp_label"), self._bar_tiles(colour_name)
        if label is not None and tiles is not None:
            s.blit(label, (x - label.get_width(), y))
            self._tile_bar(tiles, x, y, share, width // 8)
            return
        colour = {"green": HP_GREEN, "yellow": HP_YELLOW, "red": HP_RED}[colour_name]
        pg.draw.rect(s, BAR_FRAME, (x - 17, y - 1, width + 18, 6), border_radius=2)
        pg.draw.rect(s, HP_LABEL, (x - 16, y, 14, 4))
        self._text("HP", x - 15, y - 2, colour=WHITE, shadow=None, size=9)
        pg.draw.rect(s, BAR_TRACK, (x, y, width, 4))
        filled = round(width * share)
        if share > 0 and filled == 0:
            filled = 1
        pg.draw.rect(s, colour, (x, y, filled, 3))

    def _level(self, member_id):
        record = self.game.unit_record(member_id)
        return record.level if record is not None else 1

    def _box(self, name, size):
        """An info box at its layout corner: the project's picture or a drawn frame."""
        pg, s = self.pg, self.surface
        x, y = self.layout[f"{name}_box"]
        picture = self._art(f"healthbox_{name}")
        if picture is not None:
            s.blit(picture, (x, y))
            return
        box = pg.Rect(x, y, *size)
        pg.draw.rect(s, BOX_DARK, box.inflate(2, 2), border_radius=4)
        pg.draw.rect(s, BOX_FILL, box, border_radius=4)
        pg.draw.rect(s, BOX_EDGE, box, 1, border_radius=4)

    def _at(self, name, dy=0):
        x, y = self.layout[name]
        return x, y + dy

    BOX_KEYS = {
        "enemies": ("foe_box", "foe_name", "foe_level", "foe_hp"),
        "heroes": ("mine_box", "mine_name", "mine_level", "mine_hp", "mine_hp_text", "exp"),
    }

    def _draw_info_boxes(self):
        """Both info boxes, each sliding in from its own edge when it appears."""
        saved = dict(self.layout)
        try:
            for side, sign in (("enemies", -1), ("heroes", 1)):
                start = self.boxes.get(side)
                if start is None:
                    for key in self.BOX_KEYS[side]:  # not shown: drawn far off the screen
                        self.layout[key] = (self.layout[key][0] + sign * 400, self.layout[key][1])
                    continue
                k = max(0.0, min(1.0, (self.time - start) / BOX_SLIDE))
                dx = sign * round((1 - k) * 130)
                for key in self.BOX_KEYS[side]:
                    self.layout[key] = (self.layout[key][0] + dx, self.layout[key][1])
            self._draw_info_boxes_at()
        finally:
            self.layout = saved

    def _ailment_mark(self, member_id, side):
        """The healthbox mark of the member's ailment (``status_icons``: state id -> picture,
        at ``status_at[side]`` from the box's corner)."""
        icons = dict(self.settings.get("status_icons") or {})
        battle = self.game.battle
        if not icons or battle is None or member_id not in battle.members:
            return
        states = battle.member(member_id).subject.states
        if states is None:
            return
        for active in states.active_states():
            if active.state_id in icons:
                key = ("status", active.state_id)
                if key not in self._images:
                    path = self._path(icons[active.state_id])
                    self._images[key] = (
                        self.pg.image.load(str(path)).convert_alpha() if path.is_file() else None
                    )
                picture = self._images[key]
                if picture is None:
                    return
                at = dict(self.settings.get("status_at") or {}).get(side)
                if at is None:  # in place of the bar's HP label, as the handheld games show it
                    x, y = self.layout["foe_hp" if side == "enemies" else "mine_hp"]
                    self.surface.blit(picture, (x - picture.get_width(), y))
                    return
                box = self.layout["foe_box" if side == "enemies" else "mine_box"]
                self.surface.blit(picture, (box[0] + at[0], box[1] + at[1]))
                return

    def _draw_info_boxes_at(self):
        pg, s = self.pg, self.surface
        letter, shadow = self.colours["box"]
        foe = self.visible["enemies"]
        if foe is not None and foe not in self.drop and not self._in_ball(foe):
            self._box("foe", FOE_BOX[2:])
            self._text(self.name(foe), *self._at("foe_name"), colour=letter, shadow=shadow)
            level = self.tr("creature.level", "Lv{level}", level=self._level(foe))
            self._text(
                level, *self._at("foe_level"), colour=letter, shadow=shadow, anchor="topright"
            )
            self._bar(*self._at("foe_hp"), foe)
            self._ailment_mark(foe, "enemies")
            if self._caught_before(foe):
                x, y = self.layout["foe_box"]
                pg.draw.circle(s, (232, 64, 56), (x + 6, y + 20), 3)
                pg.draw.circle(s, WHITE, (x + 6, y + 22), 2)
        mine = self.visible["heroes"]
        if mine is not None and mine not in self.drop:
            bob = 1 if self.phase in ("command", "fight") and int(self.time * 2.5 + 1) % 2 else 0
            box_x, box_y = self.layout["mine_box"]
            self.layout["mine_box"] = (box_x, box_y + bob)
            self._box("mine", MINE_BOX[2:])
            self.layout["mine_box"] = (box_x, box_y)
            self._text(self.name(mine), *self._at("mine_name", bob), colour=letter, shadow=shadow)
            level = self.tr("creature.level", "Lv{level}", level=self._level(mine))
            self._text(
                level,
                *self._at("mine_level", bob),
                colour=letter,
                shadow=shadow,
                anchor="topright",
            )
            self._bar(*self._at("mine_hp", bob), mine)
            self._ailment_mark(mine, "heroes")
            current = max(0, round(self.shown_hp.get(mine, 0)))
            self._text(
                f"{current}/{round(self._max_hp(mine))}",
                *self._at("mine_hp_text", bob),
                colour=letter,
                shadow=shadow,
                anchor="topright",
            )
            record = self.game.unit_record(mine)
            species = self.game.pet_species(record) if record is not None else None
            share = 0.0
            if species is not None and record.level < species.max_level:
                share = max(0.0, min(1.0, record.experience / species.exp_to_next(record.level)))
            x, y = self._at("exp", bob)
            tiles = self._bar_tiles("exp")
            if tiles is not None:
                self._tile_bar(tiles, x, y, share, 8)
            else:
                pg.draw.rect(s, EXP_TRACK, (x, y, 64, 3))
                pg.draw.rect(s, EXP_BLUE, (x, y, round(64 * share), 3))

    def _caught_before(self, member_id):
        record = self.game.foe_record(member_id)
        if record is None or self.trainer:
            return False
        return any(p.species_id == record.species_id for p in self.game.pets())

    def _bottom(self, name):
        """The bottom 48 rows from the project's picture of that state; True when drawn."""
        picture = self._art(name)
        if picture is None:
            return False
        self.surface.blit(picture, (0, BOX_TOP))
        return True

    def _window(self, rect, fill, edge, inner=None):
        pg, s = self.pg, self.surface
        pg.draw.rect(s, edge, rect, border_radius=4)
        pg.draw.rect(s, fill, rect.inflate(-4, -4), border_radius=3)
        if inner is not None:
            pg.draw.rect(s, inner, rect.inflate(-4, -4), 1, border_radius=3)

    def _draw_message(self):
        pg = self.pg
        state = {"command": "window_commands", "fight": "window_moves"}.get(self.phase)
        if not self._bottom(state or "window_message"):
            self._window(pg.Rect(0, BOX_TOP, W, H - BOX_TOP), MSG_FILL, MSG_EDGE, MSG_INNER)
        if self.phase == "fight":
            return
        letter, shadow = self.colours["message"]
        shown = self.message[: int(self.shown_chars)]
        for i, line in enumerate(shown.split("\n")[:2]):
            self._text(line, MSG_X, (ROW_1, ROW_2)[i], colour=letter, shadow=shadow)
        typed = int(self.shown_chars) >= len(self.message)
        if self.phase == "story" and self.step is not None and self.step.kind == "text":
            if typed and self.step.wait and int(self.time * 3) % 2:
                x, y = 226, H - 12
                pg.draw.polygon(self.surface, (248, 96, 56), ((x, y), (x + 6, y), (x + 3, y + 4)))

    def _draw_yes_no(self):
        """The yes / no box at the right above the message window."""
        pg = self.pg
        rect = pg.Rect(*self.layout.get("yes_no", (200, 72)), 40, 40)
        picture = self._art("window_yes_no")
        if picture is not None:
            self.surface.blit(picture, rect.topleft)
        else:
            self._window(rect, WHITE, CMD_EDGE, CMD_LINE)
        letter, shadow = self.colours["menu"]
        words = (self.tr("creature.yes", "YES"), self.tr("creature.no", "NO"))
        for row, word in enumerate(words):
            y = rect.y + 8 + row * 16
            self._text(word, rect.x + 14, y, colour=letter, shadow=shadow)
            if (self.prompt or {}).get("cursor", 0) == row:
                self._cursor(rect.x + 6, y + 2)

    def _cursor(self, x, y):
        letter, shadow = self.colours["menu"]
        if self.font is not None and self.font.covers("▶"):
            self.font.render(self.surface, "▶", x, y - 2, letter, shadow)
            return
        self.pg.draw.polygon(self.surface, INK, ((x, y), (x, y + 8), (x + 4, y + 4)))

    def _draw_commands(self):
        pg = self.pg
        rect = pg.Rect(120, BOX_TOP, 120, H - BOX_TOP)
        if self._art("window_commands") is None:
            self._window(rect, WHITE, CMD_EDGE, CMD_LINE)
        letter, shadow = self.colours["menu"]
        labels = (
            self.tr("creature.cmd.fight", "FIGHT"),
            self.tr("creature.cmd.bag", "BAG"),
            self.tr("creature.cmd.party", "PARTY"),
            self.tr("creature.cmd.run", "RUN"),
        )
        for i, label in enumerate(labels):
            x = CMD_X[i % 2]
            y = (ROW_1, ROW_2)[i // 2]
            self._text(label, x, y, colour=letter, shadow=shadow)
            if i == self.cursor:
                self._cursor(x - 8, y + 2)

    def _draw_fight(self):
        pg = self.pg
        left = pg.Rect(0, BOX_TOP, 160, H - BOX_TOP)
        right = pg.Rect(160, BOX_TOP, 80, H - BOX_TOP)
        if self._art("window_moves") is None:
            self._window(left, WHITE, CMD_EDGE, CMD_LINE)
            self._window(right, WHITE, CMD_EDGE, CMD_LINE)
        letter, shadow = self.colours["menu"]
        moves = self._moves()
        for i in range(4):
            x = MOVE_X[i % 2]
            y = (ROW_1, ROW_2)[i // 2]
            label = self.move_name(moves[i]) if i < len(moves) else "-"
            self._text(label, x, y, colour=letter, shadow=shadow)
            if i == self.list_cursor and i < len(moves):
                self._cursor(x - 8, y + 2)
        if not moves:
            return
        move = moves[min(self.list_cursor, len(moves) - 1)]
        record = self.game.unit_record(self._stage("heroes"))
        left_uses = self.game.pet_uses_left(record, move) if record is not None else None
        definition = self.game.project.gameplay_library.abilities.get(move)
        top = int(getattr(definition, "max_uses", 0) or 0)
        pp = "--/--" if left_uses is None else f"{left_uses}/{top}"
        colour = letter if left_uses is None or left_uses > top // 4 else HP_RED
        self._text(self.tr("creature.pp", "PP"), INFO_X, ROW_1, colour=letter, shadow=shadow)
        self._text(pp, 232, ROW_1, colour=colour, shadow=shadow, anchor="topright")
        kind = _move_type(definition)
        self._text(
            self.tr("creature.type", "TYPE/{type}", type=kind.upper() if kind else "-"),
            INFO_X,
            ROW_2,
            colour=letter,
            shadow=shadow,
        )

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

    def _party_art(self, name, state=None):
        """A picture of the party screen (``battle.creature_screen.party``)."""
        party = self.settings.get("party") or {}
        value = party.get(name)
        if isinstance(value, dict):
            value = value.get(state)
        key = ("party", name, state)
        if key not in self._images:
            image = None
            if isinstance(value, str) and self._path(value).is_file():
                image = self.pg.image.load(str(self._path(value))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _icon(self, species):
        image = self._image("icon", species, None)
        if image is not None and image.get_height() > image.get_width():
            image = image.subsurface((0, 0, image.get_width(), image.get_width()))
        return image

    def slot_label(self, pet):
        """Words shown in a party slot instead of its HP (None: the HP)."""
        return None

    def _draw_party(self):
        main, self.font = self.font, self.font_small
        try:
            self._draw_party_screen()
        finally:
            self.font = main

    def _draw_party_screen(self):
        pg, s = self.pg, self.surface
        background = self._party_art("background")
        if background is None:
            self._draw_party_drawn()
            return
        s.blit(background, (0, 0))
        pets = self._party()
        letter, shadow = (248, 248, 248), (112, 112, 112)
        for index in range(6):
            x, y, _w, _h = self.PARTY_SLOTS[index]
            kind = "main" if index == 0 else "wide"
            pet = pets[index] if index < len(pets) else None
            if pet is None:
                frame = self._party_art(f"slot_{kind}_empty") if kind == "wide" else None
                if frame is not None:
                    s.blit(frame, (x, y))
                continue
            member_id = self.game.pet_member_id(pet)
            current, top = self._pet_health(pet, member_id)
            selected = index == self.list_cursor
            state = ("fainted_" if current <= 0 else "") + ("selected" if selected else "")
            state = state.rstrip("_") or "normal"
            frame = self._party_art(f"slot_{kind}", state)
            if frame is not None:
                s.blit(frame, (x, y))
            ball = self._party_art("ball_open" if selected else "ball_closed")
            if ball is not None:
                s.blit(ball, self.PARTY_BALL[index])
            species = self.game.pet_species(pet)
            icon = self._icon(pet.species_id)
            if icon is not None:
                bob = -2 if selected and int(self.time * 6) % 2 else 0
                s.blit(icon, (self.PARTY_ICON[index][0], self.PARTY_ICON[index][1] + bob))
            name_at, level_at, hp_at, top_at, bar_at = self.PARTY_TEXT[kind]
            self._text(pet.name(species), x + name_at[0], y + name_at[1], letter, shadow)
            level = self.tr("creature.level", "Lv{level}", level=pet.level)
            self._text(level, x + level_at[0], y + level_at[1], letter, shadow)
            label = self.slot_label(pet)
            if label is not None:  # ABLE / NOT ABLE... in place of the HP (a TM chosen)
                self._text(label, x + top_at[0], y + hp_at[1], letter, shadow, anchor="topright")
                continue
            self._text(
                f"{current:.0f}", x + hp_at[0], y + hp_at[1], letter, shadow, anchor="topright"
            )
            self._text("/", x + hp_at[0] + 1, y + hp_at[1], letter, shadow)
            self._text(
                f"{top:.0f}", x + top_at[0], y + top_at[1], letter, shadow, anchor="topright"
            )
            self._party_bar(x + bar_at[0], y + bar_at[1], current, top)
        if not self.forced_switch:
            selected = self.list_cursor >= len(pets)
            cancel = self._party_art("cancel_selected" if selected else "cancel_normal")
            if cancel is not None:
                s.blit(cancel, self.PARTY_CANCEL)
            label = self.tr("creature.cancel", "CANCEL")
            cx = self.PARTY_CANCEL[0] + 28
            self._text(label, cx, self.PARTY_CANCEL[1] + 1, letter, shadow, anchor="midtop")
        message = self._party_art("message")
        if message is not None:
            s.blit(message, self.PARTY_MESSAGE)
        text = self.party_note or self.tr("creature.choose", "Choose a creature.")
        self._text(
            text, self.PARTY_MESSAGE[0] + 8, self.PARTY_MESSAGE[1] + 8, *self.colours["menu"]
        )
        _ = pg

    def _draw_party_drawn(self):
        """The party screen without project pictures: shapes in the same places."""
        pg, s = self.pg, self.surface
        s.fill(PARTY_BG)
        for y in range(0, H, 8):
            pg.draw.line(s, (64, 144, 176), (0, y), (W, y))
        pets = self._party()
        for index in range(6):
            pet = pets[index] if index < len(pets) else None
            rect = pg.Rect(self.PARTY_SLOTS[index])
            selected = index == self.list_cursor
            fill = PARTY_SLOT if pet is not None else (72, 120, 144)
            member_id = self.game.pet_member_id(pet) if pet is not None else None
            current, top = self._pet_health(pet, member_id) if pet is not None else (0, 1)
            if pet is not None and current <= 0:
                fill = (200, 104, 96)
            edge = PARTY_SEL if selected else (32, 80, 104)
            pg.draw.rect(s, edge, rect.inflate(2, 2), border_radius=5)
            pg.draw.rect(s, fill, rect, border_radius=4)
            if pet is None:
                continue
            species = self.game.pet_species(pet)
            kind = "main" if index == 0 else "wide"
            icon = self._icon(pet.species_id) or self.pg.transform.scale(
                self._creature_picture(member_id, "enemies"), (32, 32)
            )
            s.blit(icon, self.PARTY_ICON[index])
            name_at, level_at, hp_at, top_at, bar_at = self.PARTY_TEXT[kind]
            x, y = rect.x, rect.y
            white, grey = (248, 248, 248), (64, 64, 64)
            self._text(pet.name(species), x + name_at[0], y + name_at[1], white, grey)
            level = self.tr("creature.level", "Lv{level}", level=pet.level)
            self._text(level, x + level_at[0], y + level_at[1], white, grey)
            self._text(
                f"{current:.0f}/{top:.0f}",
                x + top_at[0],
                y + top_at[1],
                white,
                grey,
                anchor="topright",
            )
            self._party_bar(x + bar_at[0], y + bar_at[1], current, top)
        if not self.forced_switch:
            cancel = pg.Rect(self.PARTY_CANCEL, (52, 18))
            selected = self.list_cursor >= len(pets)
            pg.draw.rect(
                s, PARTY_SEL if selected else (32, 80, 104), cancel.inflate(2, 2), border_radius=5
            )
            pg.draw.rect(s, PARTY_SLOT, cancel, border_radius=4)
            label = self.tr("creature.cancel", "CANCEL")
            self._text(
                label, cancel.centerx, cancel.y + 3, (248, 248, 248), (64, 64, 64), anchor="midtop"
            )
        box = pg.Rect(2, 132, 178 if not self.forced_switch else 236, 26)
        self._window(box, WHITE, CMD_EDGE, CMD_LINE)
        text = self.party_note or self.tr("creature.choose", "Choose a creature.")
        self._text(text, box.x + 8, box.y + 6)

    def _pet_health(self, pet, member_id):
        if self.game.battle is not None and member_id in self.game.battle.members:
            return max(0.0, self._hp(member_id)), self._max_hp(member_id)
        resource = self.game.rules.knockout_resource_id
        top = self.game.pet_resources_at(pet).get(resource, 1.0)
        return pet.resources.get(resource, top), top

    def _party_bar(self, x, y, current, top):
        pg, s = self.pg, self.surface
        share = max(0.0, min(1.0, current / max(1.0, top)))
        colour = HP_GREEN if share > 0.5 else HP_YELLOW if share > 0.2 else HP_RED
        filled = round(48 * share)
        if share > 0 and filled == 0:
            filled = 1
        pg.draw.rect(s, colour, (x, y, filled, 3))
        pg.draw.rect(s, BAR_TRACK, (x + filled, y, 48 - filled, 3))

    # -- the bag ----------------------------------------------------------------------------
    # pokeemerald's bag: the bag picture's centre, the pocket name window and its arrows, the
    # item list window (rows of 16 pixels), the description window and the item's icon
    BAG_CENTRE, BAG_POCKET_NAME, BAG_ARROWS = (68, 66), (64, 9), ((20, 8), (92, 8))
    BAG_LIST, BAG_DESCRIPTION, BAG_ICON = (112, 16, 120), (4, 106), (12, 76)
    BAG_POCKETS = ("items", "balls")

    def _bag_art(self, name):
        bag = self.settings.get("bag") or {}
        value = bag.get(name)
        key = ("bag", name)
        if key not in self._images:
            image = None
            if isinstance(value, str) and self._path(value).is_file():
                image = self.pg.image.load(str(self._path(value))).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _bag_picture(self, pocket):
        bag = self.settings.get("bag") or {}
        pattern = bag.get("bag")
        key = ("bag_picture", pocket)
        if key not in self._images:
            image = None
            if isinstance(pattern, str):
                path = self._path(pattern.format(pocket=pocket))
                if path.is_file():
                    image = self.pg.image.load(str(path)).convert_alpha()
            self._images[key] = image
        return self._images[key]

    def _draw_bag(self):
        background = self._bag_art("background")
        if background is None:
            self._draw_bag_drawn()
            return
        pg, s = self.pg, self.surface
        s.blit(background, (0, 0))
        picture = self._bag_picture(self.BAG_POCKETS[self.pocket])
        if picture is not None:
            s.blit(picture, picture.get_rect(center=self.BAG_CENTRE))
        pockets = (
            self.tr("creature.pocket.items", "ITEMS"),
            self.tr("creature.pocket.balls", "BALLS"),
        )
        self._text(
            pockets[self.pocket],
            *self.BAG_POCKET_NAME,
            (248, 248, 248),
            (232, 64, 56),
            anchor="midtop",
        )
        arrow = self._bag_art("arrow")
        if arrow is not None and int(self.time * 3) % 2:
            s.blit(arrow, self.BAG_ARROWS[0])
            s.blit(pg.transform.flip(arrow, True, False), self.BAG_ARROWS[1])
        items = self._bag_items()
        db = self.game.project.rpg_database
        left, top, width = self.BAG_LIST
        ink, ink_shadow = (72, 72, 72), (208, 208, 200)
        rows = [(i, db.items[i].display_name, f"x{n}") for i, n in items]
        rows.append(("", self.tr("creature.close_bag", "CLOSE BAG"), ""))
        for i, (_item, name, count) in enumerate(rows[:8]):
            y = top + 1 + i * 16
            self._text(name, left + 8, y, ink, ink_shadow)
            if count:
                self._text(count, left + width - 4, y, ink, ink_shadow, anchor="topright")
            if i == self.list_cursor:
                self.font_cursor(left, y)
        if self.list_cursor < len(items):
            item_id = items[self.list_cursor][0]
            item = db.items[item_id]
            icon = self._image("item_icon", item_id, None)
            if icon is not None:
                s.blit(icon, self.BAG_ICON)
            words = getattr(item, "description", "") or item.display_name
            for i, line in enumerate(self.wrap(words, 104)[:3]):
                y = self.BAG_DESCRIPTION[1] + i * 14
                self._text(line, self.BAG_DESCRIPTION[0], y, (248, 248, 248), (98, 98, 98))

    def font_cursor(self, x, y):
        letter, shadow = self.colours["menu"]
        if self.font is not None and self.font.covers("▶"):
            self.font.render(self.surface, "▶", x, y, letter, shadow)
        else:
            self._cursor(x, y + 2)

    def _draw_bag_drawn(self):
        """The bag without project pictures: shapes in the same places."""
        pg, s = self.pg, self.surface
        s.fill((232, 208, 152))
        for y in range(0, H, 6):
            pg.draw.line(s, (224, 192, 136), (0, y), (W, y))
        pockets = (
            self.tr("creature.pocket.items", "ITEMS"),
            self.tr("creature.pocket.balls", "BALLS"),
        )
        tab = pg.Rect(8, 8, 80, 18)
        self._window(tab, (248, 232, 184), (144, 96, 48))
        self._text(f"< {pockets[self.pocket]} >", tab.centerx, tab.y + 3, anchor="midtop")
        bag = pg.Rect(16, 34, 64, 70)
        pg.draw.rect(s, (200, 120, 72), bag, border_radius=10)
        pg.draw.rect(s, (136, 72, 40), bag, 2, border_radius=10)
        listing = pg.Rect(96, 6, 140, 98)
        self._window(listing, (248, 248, 232), (144, 96, 48))
        items = self._bag_items()
        db = self.game.project.rpg_database
        for i, (item_id, count) in enumerate(items[:6]):
            y = listing.y + 6 + i * 15
            self._text(db.items[item_id].display_name, listing.x + 14, y)
            self._text(f"x{count}", listing.right - 6, y, anchor="topright")
            if i == self.list_cursor:
                self._cursor(listing.x + 5, y + 2)
        if not items:
            self._text(
                self.tr("creature.bag_empty", "Nothing here."), listing.x + 14, listing.y + 6
            )


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


__all__ = ["CreatureBattleScreen"]
