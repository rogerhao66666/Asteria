"""The battle screen: turns, commands, skills, victory and the battle input."""

from __future__ import annotations

from asteria.runtime.battle_commands import BattleCommands
from asteria.runtime.battle_extras import draw_blocks, extras_layout

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class BattleFlowMixin:
    def _creature_style(self):
        """The one-on-one creature battle screen: the project's Creature battle settings are
        on, or the manifest's ``battle.style`` is ``creature``."""
        from asteria.presentation.creature_screens import creature_battle_on

        return creature_battle_on(self)

    def _battle_actor(self):
        return None if self.game.battle is None else self._turn_actor

    def _finish_battle_victory(self):
        """Every foe is down: rewards, levels, the victory screen and jingle."""
        try:
            before = self.game.capture_hero_state()
            applied = self.game.finish_victory()
            self._victory_summary = []
            rewards = self.manifest.get("progression_rewards", {})
            gained = {}
            for hero_id in self.save.rpg_state.party_active_actor_ids:
                gained[hero_id] = rewards.get("experience", 1600)
                info = self.game.grant_actor_experience(
                    hero_id,
                    rewards.get("experience", 1600),
                    level_threshold=rewards.get("level_threshold", 1000),
                    ap_per_level=rewards.get("ap_per_level", 2),
                    ability_points_per_level=rewards.get("ability_points_per_level", 1),
                )
                self._victory_summary.append(
                    f"{hero_id}: Lv {info['old_level']}→{info['new_level']} "
                    f"+{info['levels_gained'] * 2:g} AP +{info['levels_gained']:g} ability pts"
                )
            self._victory_screen = None
            if self.manifest.get("battle", {}).get("victory_aftermath"):
                self._victory_screen = self._make_victory_screen(applied, before, gained)
            self._victory = True
            # The jingle waits for the presentation to finish showing the final blows.
            self._victory_audio_pending = True  # played by _present_battle once the screen is idle
            self._last_action_name = "Victory — rewards + progression applied"
        except Exception as exc:
            self._last_action_name = f"Victory finalize failed: {exc}"

    def _advance_to_hero_turn(self):
        """Let the battle scheduler run enemy turns until a hero must act."""
        hero, log = self.game.run_enemy_turns()
        if log:
            member_id, outcome = log[-1]
            name = member_id.split(":", 1)[0].replace("_", " ").title()
            self._last_action_name = (
                f"Enemy AI: {outcome}" if isinstance(outcome, Exception) else f"{name} acts"
            )
        self._turn_actor = hero
        self._boost_level = 0
        if not self.game.active_hero_ids():
            if self.game.switch_needed("heroes"):  # a creature fell: the bench fills its place
                self._switch_menu = True
            else:
                self._defeat = True
        elif not self.game.active_enemy_ids() and not self._victory:
            self._finish_battle_victory()  # the last foe fell on its own turn (poison, burn...)

    @property
    def battle_commands(self):
        """The player's battle command menu for the current game (skills, items, concoct, boost,
        targets)."""
        commands = getattr(self, "_battle_commands", None)
        if commands is None or commands.game is not self.game:
            labels = self.manifest.get("battle", {}).get("skills", {})
            style = self.manifest.get("battle", {}).get("command_style", "categories")
            commands = self._battle_commands = BattleCommands(
                self.game, labels=labels, style=style
            )
        return commands

    @property
    def _boost_level(self):
        commands = getattr(self, "_battle_commands", None)
        return commands.boost if commands is not None and commands.game is self.game else 0

    @_boost_level.setter
    def _boost_level(self, value):
        self.battle_commands.boost = int(value)

    def _skills_for_actor(self, actor_id):
        if actor_id is None:
            return []
        member = self.game.battle.member(actor_id)
        authored = self.manifest["battle"].get("skills", {})
        values = []
        for ability_id in authored:
            if ability_id in member.ability_ids:
                values.append((ability_id, authored[ability_id]))
            if len(values) >= 4:
                break
        # Ensure at least some menu entries if a custom save changed build.
        for ability_id in member.ability_ids:
            if ability_id not in {x[0] for x in values}:
                values.append((ability_id, {"label": ability_id.replace("_", " ").title()}))
            if len(values) >= 4:
                break
        return values[:4]

    def _enemy_layout(self, member_id):
        enemy_id = str(member_id).split(":", 1)[0]
        return self.manifest["battle"].get("enemy_layouts", {}).get(enemy_id)

    def _draw_battle(self):
        self._battle_presentation.draw()
        if self._capture_menu and self.game.mode == "battle":
            self._draw_capture_menu()
        if self._switch_menu and self.game.mode == "battle":
            self._draw_switch_menu()

    def _presentation_busy(self):
        busy = getattr(self._battle_presentation, "busy", None)
        return bool(callable(busy) and busy())

    def _flush_victory_audio(self):
        pending_cues = getattr(self._battle_presentation, "audio_cues", ())
        if (
            getattr(self, "_victory_audio_pending", False)
            and not self._presentation_busy()
            and not pending_cues
        ):
            self._victory_audio_pending = False
            self.audio.stop_music(fade_out=0.3)
            self._sound(self.manifest["battle"].get("victory_jingle"))

    def _present_battle(self, dt):
        """Feed new canonical battle facts to the active presentation adapter and draw."""
        with self.profiler.section("update"):
            self._battle_presentation.consume(self.game.drain_battle_log())
        with self.profiler.section("animation"):
            self._battle_presentation.update(dt)
        with self.profiler.section("render"):
            self._battle_presentation.draw()
            self._draw_battle_extras()
            if self._switch_menu and self.game.mode == "battle" and not self._presentation_busy():
                self._draw_switch_menu()
            screen = getattr(self, "_victory_screen", None)
            if screen is not None and self._victory and not self._presentation_busy():
                screen.update(dt)
                screen.draw(self)
        self._flush_victory_audio()

    def _draw_battle_extras(self):
        """Shield and weaknesses under each enemy, boost points under each hero (unless the
        party panel has them), the chosen boost level (runtime/battle_extras.py)."""
        game, adapter = self.game, self._battle_presentation
        box = getattr(adapter, "member_screen_box", None)
        if game.battle is None or box is None or self._victory or self._defeat:
            return
        pg, battle = self.pg, game.battle
        scale = getattr(getattr(adapter, "textures", None), "scale", 3.0)
        composer = getattr(getattr(adapter, "screen", None), "composer", None)
        ui_layout = getattr(composer, "layout", None)
        below = ui_layout is not None and getattr(ui_layout, "overhead_below", False)
        drop = 17.0 * scale if below and getattr(ui_layout, "overhead_zones", ()) else 0.0
        shown = [  # zones whose combatants float a name and bar over the head
            z
            for z in getattr(ui_layout, "overhead_zones", ())
            if z not in getattr(ui_layout, "hidden_zones", ())
        ]
        head_gap = 24.0 * scale if shown and not below else None  # past that name and bar
        labels = getattr(composer, "overhead_labels", None) or {}
        caption_at = {  # state names fill the line each overhead label kept over the name
            member_id: ((x + w / 2) * scale, (y + 8.0) * scale)
            for member_id, (x, y, w, _h) in labels.items()
        }
        zones = getattr(getattr(adapter, "screen", None), "placement_by_member", None) or {}
        follows = {m for m, zone in zones.items() if zone in shown}  # names over heads
        blocks = extras_layout(
            game, box, scale, self.width, drop, head_gap, caption_at, caption_follows=follows
        )
        draw_blocks(self, blocks, scale)
        self.battle_extras_blocks = blocks  # what was drawn (tests check it for overlaps)
        bp = game.rules.boost_resource_id if game.rules.boost_enabled else ""
        layout = getattr(getattr(adapter, "screen", None), "composer", None)
        panel_has_bp = (
            layout is not None and getattr(layout.layout, "party_hud", "") == "side_list"
        )
        for member in battle.members.values():
            if member.side != "heroes" or not battle.is_active(member):
                continue
            where = box(member.member_id)
            if where is None:
                continue
            x, _top, feet = where
            y = feet + 6
            if (
                bp
                and not panel_has_bp
                and battle.battle_resources.get(member.member_id, bp) is not None
            ):
                value = battle.battle_resources.current(member.member_id, bp)
                top = battle.battle_resources.get(member.member_id, bp).maximum
                for i in range(int(top)):
                    filled = i < value
                    centre = (round(x - (top - 1) * 5 + i * 10), round(y + 4))
                    pg.draw.circle(
                        self.screen, (255, 196, 70) if filled else (60, 66, 84), centre, 4
                    )
            states = member.subject.states
            names = []
            for active in states.active_states() if states is not None else ():
                definition = states.registry.get(active.state_id)
                shown = self.game.name_of(definition) or active.state_id
                names.append(shown.replace("_", " "))
            if names and not panel_has_bp:  # the side panel shows them as chips
                from asteria.presentation.text_cells import cut

                label = cut(" ".join(names), 28)  # a Chinese name takes the room of two letters
                self.text(label, x, y + 20, size=15, color=(220, 180, 255), center=True)
        actor = self._battle_actor()
        commands = getattr(self, "_battle_commands", None)
        if actor is not None and commands is not None and commands.game is game:
            where = box(actor)
            if where is not None and commands.boost:
                self.text(
                    game.tr("battle.boost_level", "BOOST x{level}", level=commands.boost + 1),
                    where[0],
                    where[1] - 22,
                    size=22,
                    color=(255, 210, 90),
                    center=True,
                )
            if commands.message:
                self.text(
                    commands.message,
                    self.width / 2,
                    70,
                    size=20,
                    color=(255, 170, 150),
                    center=True,
                )

    def _use_skill(self, slot):
        actor = self._battle_actor()
        skills = self._skills_for_actor(actor)
        if actor is None or slot < 0 or slot >= len(skills):
            return
        ability_id, meta = skills[slot]
        boost = self._boost_level
        try:
            self.game.use_ability(actor, ability_id, boost_level=boost)
            self._last_action_name = f"{actor}: {meta.get('label', ability_id)} x{boost + 1}"
            self._boost_level = 0
            # Sound and VFX belong to the battle screen's choreography (motion sequence, or the
            # manifest skill's sfx / fx in the default cues), timed to the impact.
        except Exception as exc:
            self._last_action_name = f"Action failed: {exc}"
            return
        self._after_hero_action()

    def _after_hero_action(self):
        """End the hero's turn; finish the battle or run enemies until a hero acts."""
        if self.game.battle is None:  # the party ran away: no reward, back on the field
            self._turn_actor = None
            self._last_action_name = "Got away safely"
            return
        self.game.end_turn()
        if not self.game.active_enemy_ids():
            self._finish_battle_victory()
            return
        self._advance_to_hero_turn()

    @property
    def _COMMAND_KEYS(self):  # noqa: N802 - a key table
        pg = self.pg
        return {
            pg.K_UP: "up",
            pg.K_w: "up",
            pg.K_DOWN: "down",
            pg.K_s: "down",
            pg.K_LEFT: "left",
            pg.K_a: "left",
            pg.K_RIGHT: "right",
            pg.K_d: "right",
            pg.K_RETURN: "confirm",
            pg.K_SPACE: "confirm",
            pg.K_e: "confirm",
            pg.K_ESCAPE: "cancel",
            pg.K_BACKSPACE: "cancel",
            pg.K_TAB: "category",
            pg.K_q: "boost_down",
            pg.K_r: "boost_up",
            **({pg.K_t: "auto"} if self.battle_option("auto_key") else {}),
        }

    def _make_victory_screen(self, applied, before, gained):
        from asteria.runtime.skill_tree_screen import StatNames
        from asteria.runtime.victory_screen import VictoryScreen

        db = self.game.project.rpg_database
        aftermath = self.game.build_aftermath(applied, before, gained)
        return VictoryScreen(
            aftermath,
            item_names={k: self.game.name_of(v) for k, v in {**db.items, **db.equipment}.items()},
            currency_names=self.game.currency_names() or None,
            stat_names=StatNames(self.game),
            tr=self.game.tr,
        )

    def _battle_input(self, events):
        if self._victory:
            if self._presentation_busy():
                return  # the result is still being presented
            for event in events:
                if event.type == self.pg.KEYDOWN and event.key in (
                    self.pg.K_RETURN,
                    self.pg.K_e,
                    self.pg.K_SPACE,
                ):
                    screen = getattr(self, "_victory_screen", None)
                    if screen is not None and not screen.confirm():
                        continue  # the next results page
                    self._victory_screen = None
                    self._victory = False
                    self.game.mode = "field"
                    self._last_action_name = ""
            return
        if self._defeat:
            return
        if self._switch_menu:
            if not self._presentation_busy():
                self._switch_input(events)
            return
        if self._capture_menu:
            self._capture_input(events)
            return
        busy = getattr(self._battle_presentation, "busy", None)
        if callable(busy) and busy():
            return  # the previous action's choreography is still playing
        for event in events:
            if event.type != self.pg.KEYDOWN:
                continue
            if event.key == self.pg.K_x and self._battle_actor() and self.game.capture_targets():
                self._capture_menu = True
            elif event.key == self.pg.K_b:
                actor = self._battle_actor()
                if actor:
                    self._boost_level = (self._boost_level + 1) % (
                        self.game.max_boost_level(actor) + 1
                    )
            elif event.key in self._COMMAND_KEYS:
                actor = self._battle_actor()
                commands = self.battle_commands
                if commands.press(self._COMMAND_KEYS[event.key], actor):
                    self._last_action_name = f"{actor} acts"
                    self._after_hero_action()
                    return
                if commands.message == "capture":
                    commands.message = ""
                    self._capture_menu = bool(self.game.capture_targets())
            elif event.key in (self.pg.K_1, self.pg.K_KP1):
                self._use_skill(0)
            elif event.key in (self.pg.K_2, self.pg.K_KP2):
                self._use_skill(1)
            elif event.key in (self.pg.K_3, self.pg.K_KP3):
                self._use_skill(2)
            elif event.key in (self.pg.K_4, self.pg.K_KP4):
                self._use_skill(3)
