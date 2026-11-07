"""One round of a creature battle: choosing moves, who goes first, hits, effects and fainting."""

from __future__ import annotations

import random

from asteria.runtime.creature.battle_style import _effectiveness, _experience_between


class BattleRoundMixin:
    """One round of a creature battle: moves, turn order, hits, effects and fainting."""

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
                game.last_battle_outcome = "ran"
                self._sound("flee")
                self.say(self.tr("creature.got_away", "Got away safely!"))
                self.act("end")
                return
            self.say(self.tr("creature.cant_escape", "Can't escape!"))
            self.choice = ("done",)
        elif kind == "switch":
            if game.held_on_stage(actor):
                self.say(
                    self.tr(
                        "creature.cant_switch",
                        "{name} can't be\nswitched out!",
                        name=self.name(actor),
                    )
                )
                self.act("command")
                return
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
            # only the first turn may begin a new round: then that round is it
            actor = game.current_turn_actor(new_round=start is None)
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
                        from asteria.rpg.text.built_in_text import translated

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

    def _sound(self, moment):
        """A sound of the battle (``sounds``: {moment: sound}), in its place in the story."""
        if self.sounds.get(moment):
            self.act("sound", asset=str(self.sounds[moment]))

    def _cry(self, member_id):
        pattern = str(self.sounds.get("cry", ""))
        if pattern and member_id is not None:
            self.act("sound", asset=pattern.replace("{species}", self._species_key(member_id)))

    def _weather_line(self, kind, moment, member_id=None):
        line = dict(self.weather_rules.get(kind) or {}).get(moment)
        if line:
            name = self.name(member_id, owner=True) if member_id else ""
            self.say(str(line).replace("{name}", name))

    def _state_line(self, state_id, moment, member_id, fallback=None, source=None):
        """The project's line for an ailment ``moment`` (``applied``, ``already``, ``tick``,
        ``prevented``, ``expired``, ``cured``) from ``state_messages``, with ``{name}``."""
        lines = dict(self.state_messages.get(state_id) or {})
        template = lines.get(moment)
        if template == "":  # the project keeps this moment silent
            return ""
        if not template:
            return fallback
        line = str(template).replace("{name}", self.name(member_id, owner=True))
        return line.replace("{source}", self.name(source, owner=True) if source else "")

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
                        self.say(line, wait=False)
                        break
                if data.get("hp") is not None:  # it lost its turn to a blow of its own
                    self.act("hp", values={entry.member_id: data["hp"]}, hit=(entry.member_id,))
                self._faint_if_down(entry.member_id)
            elif kind == "state_turn":
                line = self._state_line(data.get("state", ""), "turn", entry.member_id)
                if line:
                    self.say(line)
            elif kind == "weather_set":
                self._weather_line(data.get("kind", ""), "started")
            elif kind == "weather_failed":
                self.say(self.tr("creature.but_it_failed", "But it failed!"))
            elif kind == "weather_line":
                self._weather_line(data.get("kind", ""), data.get("moment", ""))
            elif kind == "weather_hurt":
                member = entry.member_id
                self._weather_line(data.get("kind", ""), "hurt", member)
                if game.battle is not None and member in game.battle.members:
                    self.act("hp", values={member: self._hp(member)}, hit=(member,))
                    self._faint_if_down(member)
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
        for target_id, outcome in entry.outcomes or ():
            ratio = _effectiveness(outcome, str(self.settings.get("effectiveness_rules", "")))
            if ratio and values.get(target_id, 0) < self.target_hp.get(target_id, 0):
                self._sound("super" if ratio > 1.001 else "weak" if ratio < 0.999 else "hit")
                break
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
            line = self._state_line(state_id, "applied", member, fallback, data.get("source"))
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
        self._cry(member_id)
        self._sound("faint")
        self.act("faint", member=member_id)
        self.say(
            self.tr("creature.fainted", "{name} fainted!", name=self.name(member_id, owner=True))
        )

    def _after_round(self):
        game = self.game
        if game.battle is None:
            return
        if self.weather_rules:
            game.weather_round(self.weather_rules)
            self._tell(game.drain_battle_log())
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
        game.last_battle_outcome = "caught" if caught else "won"
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
        self.game.last_battle_outcome = "lost"
        self.say(
            self.tr(
                "creature.out_of_creatures",
                "{player} is out of usable creatures!",
                player=self.player_name(),
            )
        )
        self.say(self.tr("creature.whited_out", "{player} whited out!", player=self.player_name()))
        self.act("lost")
