"""Field overlays, equip offers, pictures, popups, dialogue and the field input."""

from __future__ import annotations

import zipfile

from asteria.core import Transform
from asteria.graphics.scaling import resized
from asteria.platform.pygame_battle_ui import cjk_size, contains_cjk, font_for_text
from asteria.presentation.text.animated import (
    AnimatedTextRuntime,
    AnimatedTextSpec,
    TextKey,
    TextTransform,
)
from asteria.presentation.text.cells import cells
from asteria.presentation.text.render_integration import AnimatedTextRenderComposer
from asteria.runtime.menus.icons import icon_source
from asteria.runtime.playtest.dialogue_ui import DialogueUiMixin
from asteria.runtime.playtest.field_input import FieldInputMixin
from asteria.runtime.scene.movies import Movie, is_movie


class FieldUiMixin(DialogueUiMixin, FieldInputMixin):
    def _draw_field_overlays(self):
        """Everything drawn over the field's world: HUD, effects, popups, dialogue, help."""
        self._draw_multiplayer_world()
        if self.game.action_scene:
            self.action_hud.draw_world(self)
        elif self._field_abilities():  # field strikes in a turn-based game: its thrown shots
            self.action_hud.draw_projectiles(self)
        self._draw_field_effects()
        self._draw_popups()
        self._draw_pictures()
        self._draw_event_timers()
        self._draw_field_windows()
        self._draw_entity_icons()
        self._draw_area_name()
        self._draw_emotes()
        if self.game.cutscene_active:
            self._draw_dialogue()
            return
        if self.game.action_scene:
            self.action_hud.draw_overlay(self)
            if self.message and self.pg.time.get_ticks() < self.message_until:
                self.text(
                    self.message, self.width / 2, 92, size=22, color=(175, 235, 255), center=True
                )
            self._draw_dialogue()
            return

        tr = self.game.tr
        # the playtest's own hints (its controls and the "E Interact" line); a game drawn as
        # its own (field.test_hints: false) shows the field alone
        hints = self.manifest.get("field", {}).get("test_hints", True)
        if hints:
            c = self.menu_canvas("field_hint", {"map.name": self._map_title})
            c.begin()
            c.panel("frame", (18, self.height - 92, self.width - 36, 72))
            c.text(
                "title",
                tr("field.title", "Field Test"),
                34,
                self.height - 82,
                size=24,
                color=c.tone("title", (255, 220, 124)),
            )
            c.text(
                "controls",
                tr(
                    "field.controls",
                    "Move: WASD / Arrows   C: Build   Q: Quests   E: Interact   F5: Save   "
                    "Esc: Pause",
                ),
                34,
                self.height - 52,
                size=19,
                color=c.tone("text", (245, 245, 250)),
            )
            c.finish()
        candidate = self._interaction_candidate() if hints else None
        if candidate is not None and not self.game.event_busy:
            self.text(
                tr(
                    "field.interact",
                    "E  Interact — {name}",
                    name=self.game.speaker_name(candidate.entity.name),
                ),
                self.width / 2,
                55,
                size=26,
                color=(255, 226, 129),
                center=True,
            )
        if self.message and self.pg.time.get_ticks() < self.message_until:
            self.text(
                self.message, self.width / 2, 92, size=22, color=(175, 235, 255), center=True
            )
        self._draw_dialogue()
        self._draw_equip_offer()

    def _equip_offer_text(self, offer):
        """("Wear the Demon Ring?", "Aldric - weapon (a free hand)") for an offer."""
        db = self.project.rpg_database
        bag = self.game.save.rpg_state.equipment_bag
        item = next((g for g in bag if g.instance_id == offer.instance_id), None)
        name = self.game.name_of(item.equipment) if item is not None else offer.instance_id
        actor = db.actors.get(offer.actor_id)
        who = self.game.name_of(actor, offer.actor_id) or offer.actor_id
        if offer.replaces:
            loadout = self.game.save.rpg_state.loadouts[offer.actor_id]
            worn = next(
                (g for g in loadout.equipped(offer.slot_id) if g.instance_id == offer.replaces),
                None,
            )
            old = self.game.name_of(worn.equipment) if worn is not None else offer.replaces
            return (
                self.game.tr("equip_offer.new", "New: {name}", name=name),
                self.game.tr(
                    "equip_offer.instead",
                    "{who}: wear it instead of {old}?",
                    who=who,
                    old=old,
                ),
            )
        return (
            self.game.tr("equip_offer.new", "New: {name}", name=name),
            self.game.tr(
                "equip_offer.free",
                "{who} has a free {slot} place. Wear it now?",
                who=who,
                slot=self.game.slot_name(offer.slot_id),
            ),
        )

    def _draw_equip_offer(self):
        """New gear asks whether to wear it (InventoryRules.equip_offer)."""
        offers = self.game.equip_offers
        if not offers or self.game.pending_dialogue is not None:
            return
        title, question = self._equip_offer_text(offers[0])
        c = self.menu_canvas("equip_offer")
        c.begin()
        box = (self.width / 2 - 300, self.height - 250, 600, 150)
        box = c.panel("frame", box, fill=(10, 14, 24, 240), border=(240, 201, 93))
        middle = box[0] + box[2] / 2
        title_color = c.tone("title", (255, 220, 124))
        c.text("title", title, middle, box[1] + 26, size=26, color=title_color, center=True)
        c.text(
            "question",
            question,
            middle,
            box[1] + 64,
            size=21,
            color=c.tone("text", (245, 245, 250)),
            center=True,
        )
        c.text(
            "keys",
            self.game.tr("equip_offer.keys", "1 / Enter: wear it     2 / Esc: keep it in the bag"),
            middle,
            box[1] + 108,
            size=18,
            color=c.tone("muted", (170, 210, 240)),
            center=True,
        )
        c.finish()

    def _equip_offer_input(self, events):
        """Keys for a waiting equip offer. Returns True when one is open."""
        if not self.game.equip_offers or self.game.event_busy:
            return False
        wear = self.input.just_pressed("confirm") or any(
            e.type == self.pg.KEYDOWN and e.key == self.pg.K_1 for e in events
        )
        keep = self.input.just_pressed("cancel") or any(
            e.type == self.pg.KEYDOWN and e.key == self.pg.K_2 for e in events
        )
        if wear or keep:
            self.game.answer_equip_offer(bool(wear))
        return True

    def _picture_image(self, picture):
        """The sub-image of a picture's asset for its sprite-sheet cell (or its words drawn),
        or ``None``."""

        if picture.text:
            return self._text_picture(picture)
        source = icon_source(self.project, picture.asset_id)
        if source is None:
            return None
        if is_movie(source[0]):
            return self._movie_image(source[0], picture)
        try:
            image = self.load_image(source[0])
        except (OSError, ValueError, self.pg.error):
            return None
        x, y, w, h = picture.cell(*image.get_size())
        return image.subsurface(self.pg.Rect(x, y, w, h).clip(image.get_rect()))

    def _movie_image(self, source, picture):
        """The frame a movie picture is at: ``frame_rate`` frames a second since it was shown,
        from ``frame`` on; the last one stays unless it loops."""
        movies = self._movies
        try:
            movie = movies.get(source) or movies.setdefault(
                source, Movie(self.pg, self.path(source))
            )
            index = movie.frame_at(picture.age, picture.frame_rate, picture.frame,
                                   picture.frame_loop)  # fmt: skip
            return movie.image(index)
        except (OSError, ValueError, KeyError, self.pg.error, zipfile.BadZipFile):
            return None

    def _text_picture_font(self, font_id):
        """A text picture's font: the bitmap font ``font_id``, else the message window's."""
        if font_id:
            return self.bitmap_font(font_id)
        settings = self.dialogue_settings() or {}
        if settings.get("font_id"):
            return self.bitmap_font(settings["font_id"])
        if settings.get("font"):
            from asteria.graphics.bitmap_font import BitmapFont

            fonts = self._text_picture_fonts
            if settings["font"] not in fonts:
                fonts[settings["font"]] = BitmapFont(self.pg, self.path(settings["font"]))
            return fonts[settings["font"]]
        return None

    def _text_picture(self, picture):
        """A picture's words (\\V[...] filled in) at the font's own size, a line under the
        other; kept while they stay the same."""
        text = self.game.expand_message(picture.text, plain=True)
        key = (text, picture.font, picture.text_color, picture.shadow_color)
        cache = self._text_pictures
        if key in cache:
            return cache[key]
        font = self._text_picture_font(picture.font)
        lines = text.split("\n")
        if font is not None and font.covers(text):
            step = int(getattr(font, "line", 16))
            width = max(1, max(font.width(line) for line in lines))
            image = self.pg.Surface((width, step * len(lines)), self.pg.SRCALPHA)
            for row, line in enumerate(lines):
                font.render(image, line, 0, row * step, picture.text_color, picture.shadow_color)
        else:  # words the font lacks: a system face
            face = self.pg.font.Font(None, 16)
            parts = [face.render(line, False, picture.text_color) for line in lines]
            image = self.pg.Surface(
                (max(1, max(p.get_width() for p in parts)) + 1, 16 * len(parts) + 1),
                self.pg.SRCALPHA,
            )
            for row, part in enumerate(parts):
                if picture.shadow_color is not None:
                    under = face.render(lines[row], False, picture.shadow_color)
                    image.blit(under, (1, row * 16 + 1))
                image.blit(part, (0, row * 16))
        if len(cache) > 256:  # (a clock's words change every second)
            cache.clear()
        cache[key] = image
        return image

    def _picture_size(self, picture):
        image = self._picture_image(picture)
        if image is None:
            return None
        if is_movie(self._picture_path(picture)):
            return image.get_size()
        return self.load_image(self._picture_path(picture)).get_size()

    def _picture_path(self, picture):
        return icon_source(self.project, picture.asset_id)[0]

    def _draw_pictures(self):
        """Pictures events put on screen (SHOW_PICTURE), bottom layer first."""
        for picture in self.game.pictures.pictures():
            image = self._picture_image(picture)
            if image is None or picture.opacity <= 0:
                continue
            image = self._picture_motion(image, picture)
            w, h = image.get_size()
            image = resized(self.pg, image, (round(w * picture.scale), round(h * picture.scale)))
            if picture.tint > 0:  # mixed: colour x (1 - tint) + tint_color x tint
                image = image.copy()
                keep = round(255 * (1 - picture.tint))
                add = tuple(round(c * picture.tint) for c in picture.tint_color)
                image.fill((keep, keep, keep), special_flags=self.pg.BLEND_RGB_MULT)
                image.fill(add, special_flags=self.pg.BLEND_RGB_ADD)
            if picture.blend == "add":  # its colours x alpha x opacity added (a glow)
                glow = self.pg.Surface(image.get_size())
                glow.blit(image, (0, 0))
                keep = round(255 * picture.opacity)
                glow.fill((keep, keep, keep), special_flags=self.pg.BLEND_RGB_MULT)
                image, flags = glow, self.pg.BLEND_RGB_ADD
            else:
                flags = 0
            if picture.opacity < 1.0 and not flags:
                image = image.copy()
                image.set_alpha(round(255 * picture.opacity))
            x = picture.x  # words: their x is their left, right end or middle
            x -= {"right": image.get_width(), "center": image.get_width() / 2}.get(
                picture.text_align if picture.text else "left", 0
            )
            self.screen.blit(image, (round(x), round(picture.y)), special_flags=flags)

    def _picture_motion(self, image, picture):
        """The cell with its content scrolled (wrapping round) and its rows waved, at the
        image's own pixels (as a console's background scrolls and its scanlines shift)."""
        dx, dy = picture.scroll_offset()
        if not (dx or dy or picture.wave_amplitude):
            return image
        w, h = image.get_size()
        ox, oy = round(dx) % w, round(dy) % h
        rolled = self.pg.Surface((w, h), self.pg.SRCALPHA)
        for x in (ox - w, ox):  # the content moves by (ox, oy): the rest comes round
            for y in (oy - h, oy):
                rolled.blit(image, (x, y))
        if not picture.wave_amplitude:
            return rolled
        waved = self.pg.Surface((w, h), self.pg.SRCALPHA)
        for row in range(h):
            shift = round(picture.wave_offset(row)) % w  # the row wraps round too
            strip = self.pg.Rect(0, row, w, 1)
            waved.blit(rolled, (shift, row), strip)
            waved.blit(rolled, (shift - w, row), strip)
        return waved

    def _click_picture(self, x, y):
        return self.game.click_picture(x, y, self._picture_size)

    def _draw_event_timers(self):
        """Visible event timers (TIMER_START) stacked at the top right: ``MM:SS``."""
        for row, (timer_id, clock) in enumerate(self.game.timers.display()):
            low = (self.game.timers.remaining(timer_id) or 99) <= 10
            color = (255, 150, 140) if low else (245, 245, 250)
            self.panel((self.width - 118, 14 + row * 40, 104, 34))
            self.text(clock, self.width - 66, 31 + row * 40, size=30, color=color, center=True)

    def battle_option(self, name):
        """A battle option: the project's ``BattleOptions`` record (first by id) when it has one,
        else the manifest's ``battle.<name>``; ``False`` / ``0`` when neither says."""
        values = self.project.rpg_database.battle_options
        if values:
            return getattr(values[sorted(values)[0]], name)
        return self.manifest.get("battle", {}).get(name, 0)

    def _draw_entity_icons(self):
        """Icons events keep over entities (``SET_ENTITY_ICON``), above their heads."""

        icons = self.game.entity_icons()
        for entity_id, icon_id in icons.items():
            entity = self.game.scene.get_entity(entity_id)
            if entity is None or not entity.has(Transform):
                continue
            transform = entity.get(Transform)
            x, y = self._field_screen_xy(transform.x, transform.y)
            self._draw_icon(icon_id, round(x) - 11, round(y) - 64, 22)

    def _draw_field_windows(self):
        """Optional map windows (manifest ``field.hud``): ``gold`` shows the wallet and
        ``quest_tracker`` the active quests' objectives, stacked at the top left. Off unless the
        project asks, so existing games look as they did."""
        hud = self.manifest.get("field", {}).get("hud", {})
        if not isinstance(hud, dict) or not (hud.get("gold") or hud.get("quest_tracker")):
            return
        lines = []
        state = self.game.save.rpg_state
        if hud.get("gold"):
            wallet = "   ".join(f"{state.currencies[k]:g} {k}" for k in sorted(state.currencies))
            if wallet:
                lines.append((wallet, (255, 222, 150)))
        if hud.get("quest_tracker"):
            quests = self.project.rpg_database.quests
            for quest_id, progress in sorted(state.quests.items()):
                if progress.status != "active" or quest_id not in quests:
                    continue
                quest = quests[quest_id]
                lines.append((self.game.name_of(quest), (245, 245, 250)))
                for objective in quest.objectives:
                    have = progress.counts.get(objective.objective_id, 0)
                    done = have >= objective.required
                    label = self.game.description_of(objective, objective.objective_id)
                    lines.append(
                        (
                            f"  {label}  {min(have, objective.required)}/{objective.required}",
                            (170, 240, 170) if done else (200, 205, 220),
                        )
                    )
        if not lines:
            return

        row_h = 22  # a full-width (Chinese) character takes the room of two
        width = min(420, max(160, 14 + 9 * max(cells(text) for text, _ in lines)))
        self.panel((14, 14, width, 12 + row_h * len(lines)))
        for row, (text, color) in enumerate(lines):
            self.text(text, 24, 20 + row * row_h, size=18, color=color)

    # -- popups (CMP-03: generic animated text above field characters) ----------------------------
    POPUP_COLORS = {"item": (170, 240, 170), "warning": (255, 170, 150), "info": (230, 232, 240)}

    def _update_popups(self, dt):
        if getattr(self, "popups", None) is None:
            self.popups, self._popup_serial = AnimatedTextRuntime(), 0
        notices = self.game.drain_notices()
        if self.manifest.get("field", {}).get("notices", True) is False:
            notices = ()  # the game says it in its own windows (field.notices: false)
        for notice in notices:
            self._popup_serial += 1
            rise = TextTransform(y=-34.0, opacity=0.0, scale=1.0)
            spec = AnimatedTextSpec(
                notice["text"],
                duration_ms=notice["duration_ms"],
                space="world",
                anchor_id=notice["entity"] or "player",
                keys=(
                    TextKey(0.0, TextTransform(y=0.0, opacity=0.0, scale=0.8)),
                    TextKey(0.15, TextTransform(y=-8.0, opacity=1.0, scale=1.0)),
                    TextKey(0.7, TextTransform(y=-22.0, opacity=1.0)),
                    TextKey(1.0, rise),
                ),
                metadata={"kind": notice["kind"]},
            )
            self.popups.spawn(f"popup.{self._popup_serial}", spec)
        self.popup_frame = self.popups.update(dt * 1000.0)

    def _popup_anchor(self, anchor_id):
        if anchor_id == "player":
            entity = self.game.player
        else:
            entity = next(
                (
                    e
                    for e in self.game.scene.entities()
                    if e.name == anchor_id or e.id == anchor_id
                ),
                None,
            )
        transform = entity.get(Transform) if entity is not None else None
        if transform is None:
            return None
        x, y = self._field_screen_xy(transform.x, transform.y)
        return x, y - 48 * self.field_camera.zoom  # above the head

    def _draw_popups(self):
        resolved = getattr(self, "popup_frame", ())
        if not resolved:
            return
        composer = AnimatedTextRenderComposer(anchor_resolver=self._popup_anchor)
        packets = []
        for item in resolved:
            try:
                packets.extend(composer.compose((item,)))
            except ValueError:
                continue  # the anchor left the scene

        latin = self.pg.font.Font(None, 30)
        for packet in packets:
            color = self.POPUP_COLORS.get(packet.metadata.get("kind"), self.POPUP_COLORS["info"])
            # Chinese, Japanese or Korean words come from a system face that has them
            cjk_pt = cjk_size(latin, self.pg) if contains_cjk(packet.text) else 0  # 0: unused
            font = font_for_text(self.pg, latin, packet.text, self._cjk_fonts, cjk_pt)
            image = font.render(packet.text, True, color)
            if packet.scale != 1.0:
                size = (
                    max(1, round(image.get_width() * packet.scale)),
                    max(1, round(image.get_height() * packet.scale)),
                )
                image = self.pg.transform.smoothscale(image, size)
            shadow = font.render(packet.text, True, (10, 12, 20))
            shadow.set_alpha(round(160 * packet.opacity))
            image.set_alpha(round(255 * packet.opacity))
            at = (
                round(packet.x - image.get_width() / 2),
                round(packet.y - image.get_height() / 2),
            )
            self.screen.blit(shadow, (at[0] + 2, at[1] + 2))
            self.screen.blit(image, at)

    PORTRAIT_BUST_SHARE = 0.55  # a bust's height on screen when Portrait Size is 0
    DIALOGUE_BOX_HEIGHT = 130
