"""The battle's music, words and story: what is said, in what order, and the party's order."""

from __future__ import annotations

from asteria.platform.pygame_battle_ui import font_for_text
from asteria.runtime.creature.battle_style import (
    BALL_SECONDS,
    BOX_SLIDE,
    GROW_SECONDS,
    SLIDE_SECONDS,
    TEXT_SPEED,
    THROW_SECONDS,
    _Step,
)


class BattleStoryMixin:
    """The battle's music, words and story: what is said, in what order, and the party's order."""

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
        fallback = str(ability_id).replace("_", " ").title()
        return self.game.name_of(definition, fallback) or fallback  # the player's language

    def player_name(self):
        db = self.game.project.rpg_database
        ids = (
            self.game.save.rpg_state.party_active_actor_ids
            or self.game.save.rpg_state.party_actor_ids
        )
        actor = db.actors.get(ids[0]) if ids else None
        if self.encounter.get("player_name"):  # someone else's battle (a tutorial)
            return self.game.expand_message(self.encounter["player_name"], plain=True)
        name = self.game.name_of(actor, "") or self.game.expand_message(
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

    def text_width(self, value):
        value = str(value)
        if self.font is not None and self.font.covers(value):
            return self.font.width(value)

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
        field = self.game.field_weather
        if dict(self.weather_rules.get(field) or {}).get("from_field"):
            self.game.set_battle_weather(field)  # the map's weather: it stays for the battle
            self.game.drain_battle_log()
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
            self._cry(foe)
            self.say(line)
        self.act("box", side="enemies")
        if mine is not None:
            self.say(self.tr("creature.go", "Go! {name}!", name=self.name(mine)), wait=False)
            self.act("send_out", side="heroes", member=mine)
            self.act("box", side="heroes")
        self.act("mark")
        weather = self.game.battle_weather()
        if weather is not None:
            self._weather_line(weather[0], "started")
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
        elif kind == "sound":
            self.rt._sound(step.args.get("asset"))
            self.step = None
        elif kind == "throw":
            self.throw = {"start": self.time, **step.args}
            self.rt._sound(self.sounds.get("ball_throw"))
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
            self.rt._sound(self.sounds.get("ball_open"))
            if member is not None and self.sounds.get("cry"):
                cry = str(self.sounds["cry"]).replace("{species}", self._species_key(member))
                self.rt._sound(cry)
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
