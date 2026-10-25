"""Field overlays, equip offers, pictures, popups, dialogue and the field input."""

from __future__ import annotations

from asteria.core import Transform
from asteria.graphics.scaling import resized
from asteria.presentation.creature_screens import creature_settings
from asteria.runtime.collision import CollisionWorld

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


class FieldUiMixin:
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
        """The sub-image of a picture's asset for its sprite-sheet cell, or ``None``."""
        from asteria.runtime.menu_icons import icon_source

        source = icon_source(self.project, picture.asset_id)
        if source is None:
            return None
        try:
            image = self.load_image(source[0])
        except (OSError, ValueError, self.pg.error):
            return None
        x, y, w, h = picture.cell(*image.get_size())
        return image.subsurface(self.pg.Rect(x, y, w, h).clip(image.get_rect()))

    def _picture_size(self, picture):
        image = self._picture_image(picture)
        if image is None:
            return None
        return self.load_image(self._picture_path(picture)).get_size()

    def _picture_path(self, picture):
        from asteria.runtime.menu_icons import icon_source

        return icon_source(self.project, picture.asset_id)[0]

    def _draw_pictures(self):
        """Pictures events put on screen (SHOW_PICTURE), bottom layer first."""
        for picture in self.game.pictures.pictures():
            image = self._picture_image(picture)
            if image is None or picture.opacity <= 0:
                continue
            w, h = image.get_size()
            image = resized(self.pg, image, (round(w * picture.scale), round(h * picture.scale)))
            if picture.opacity < 1.0:
                image = image.copy()
                image.set_alpha(round(255 * picture.opacity))
            self.screen.blit(image, (round(picture.x), round(picture.y)))

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
        from asteria.core import Transform

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
        from asteria.presentation.text_cells import cells

        row_h = 22  # a full-width (Chinese) character takes the room of two
        width = min(420, max(160, 14 + 9 * max(cells(text) for text, _ in lines)))
        self.panel((14, 14, width, 12 + row_h * len(lines)))
        for row, (text, color) in enumerate(lines):
            self.text(text, 24, 20 + row * row_h, size=18, color=color)

    # -- popups (CMP-03: generic animated text above field characters) ----------------------------
    POPUP_COLORS = {"item": (170, 240, 170), "warning": (255, 170, 150), "info": (230, 232, 240)}

    def _update_popups(self, dt):
        from asteria.presentation.animated_text import (
            AnimatedTextRuntime,
            AnimatedTextSpec,
            TextKey,
            TextTransform,
        )

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
        from asteria.presentation.text_render_integration import AnimatedTextRenderComposer

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
        from asteria.platform.pygame_battle_ui import cjk_size, font_for_text

        latin = self.pg.font.Font(None, 30)
        for packet in packets:
            color = self.POPUP_COLORS.get(packet.metadata.get("kind"), self.POPUP_COLORS["info"])
            # Chinese, Japanese or Korean words come from a system face that has them
            font = font_for_text(self.pg, latin, packet.text, self._cjk_fonts, cjk_size(latin))
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

    def dialogue_portrait(self, portrait_id, width, height):
        """The picture ``portrait_id`` names (an image asset, a sheet cell or a project path)
        fitted inside ``width`` x ``height`` with its proportions kept, or ``None``. A picture
        made larger keeps sharp pixels (pixel-art faces); one made smaller is smoothed."""
        from asteria.runtime.menu_icons import icon_source

        key = (str(portrait_id or ""), int(width), int(height))
        cache = self._portrait_cache
        if key in cache:
            return cache[key]
        picture = None
        source = icon_source(self.project, portrait_id) if portrait_id else None
        if source is not None:
            uri, region = source
            try:
                image = self.load_image(uri)
                if region is not None:
                    image = image.subsurface(self.pg.Rect(region).clip(image.get_rect()))
                w, h = image.get_size()
                scale = min(width / max(1, w), height / max(1, h))
                size = (max(1, round(w * scale)), max(1, round(h * scale)))
                fit = self.pg.transform.scale if scale >= 1 else self.pg.transform.smoothscale
                picture = fit(image, size)
            except (OSError, ValueError, self.pg.error):
                picture = None  # a missing portrait: the line shows without one
        if len(cache) > 32:
            cache.clear()
        cache[key] = picture
        return picture

    PORTRAIT_BUST_SHARE = 0.55  # a bust's height on screen when Portrait Size is 0
    DIALOGUE_BOX_HEIGHT = 130

    def _dialogue_layout(self, line):
        """The message window ``(x, y, w, h)`` for ``line`` and its portrait as ``(picture,
        (x, y), style, room)`` or ``None``; ``room`` is the rect the portrait keeps. A face sits
        centred in a square at the window's left or right end (the window grows to hold a big
        one); a bust stands on the window's bottom edge."""
        settings = self.game.message_settings
        style = settings.portrait_style if settings is not None else "face"
        size = settings.portrait_size if settings is not None else 0
        height = self.DIALOGUE_BOX_HEIGHT
        box = (60, self.height - 100 - height, self.width - 120, height)
        portrait_id = getattr(line, "portrait_asset_id", "") if line is not None else ""
        if not portrait_id:
            return box, None
        left = line.portrait_side == "left"
        if style == "bust":
            x, y, w, h = box
            tall = size or round(self.height * self.PORTRAIT_BUST_SHARE)
            picture = self.dialogue_portrait(portrait_id, w // 2, tall)
            if picture is None:
                return box, None
            at = (
                x + 24 if left else x + w - 24 - picture.get_width(),
                y + h - picture.get_height(),
            )
            return box, (picture, at, style, (*at, *picture.get_size()))
        side = size or height - 24
        picture = self.dialogue_portrait(portrait_id, side, side)
        if picture is None:
            return box, None
        height = max(height, side + 24)  # a big face: the window grows upwards to hold it
        box = x, y, w, h = (60, self.height - 100 - height, self.width - 120, height)
        room = (x + 12 if left else x + w - 12 - side, y + (h - side) // 2, side, side)
        at = (
            room[0] + (side - picture.get_width()) // 2,
            room[1] + (side - picture.get_height()) // 2,
        )
        return box, (picture, at, style, room)

    def _draw_dialogue(self):
        request = (
            getattr(self, "_network_dialogue", None)
            if self._multiplayer_connected()
            else self.game.pending_dialogue
        )
        held = False
        if request is None and not self._multiplayer_connected():
            request = self.game.held_dialogue  # shown without waiting for a key
            held = request is not None
        if request is None:
            return
        line = getattr(request, "line", None)
        if held and self.dialogue_settings().get("window"):
            self._draw_dialogue_window(line, held=True)
            return
        if self.dialogue_settings().get("window"):
            if line is not None:
                self._draw_dialogue_window(line)
                return
            if self.dialogue_settings().get("choice_frame"):
                self._draw_choice_window(request)
                return
        from asteria.runtime.dialogue_screen import draw_message_window

        draw_message_window(self, request, line)  # through the dialogue layouts (V2)

    def _grid_steps(self, request):
        pg = self.pg
        return {pg.K_LEFT: -1, pg.K_RIGHT: 1, pg.K_UP: -request.columns,
                pg.K_DOWN: request.columns}  # fmt: skip

    def _choice_index(self, request):
        """The choice under the cursor (arrow keys move it; a new one starts on its ``cursor``)."""
        if getattr(self, "_choice_request", None) is not request:  # its own start (cursor)
            self._choice_request = request
            self._choice_cursor = getattr(request, "cursor", 0)
        return self._choice_cursor

    def _draw_choice_window(self, request):
        """A choice in the game's own windows: the prompt in the message window, the options in
        a framed box above its right end (``dialogue.choice_frame``: a 3 x 3 grid of 8-pixel
        border pieces; ``choice_fill``: the inside colour; ``choice_right`` / ``choice_bottom``:
        the box's right and bottom edges in window pixels, unless the choice gives ``box_at``,
        its inside's top left; ``choice_line_height``), a pointer at the option under the
        cursor."""
        settings = self.dialogue_settings()
        self._draw_dialogue_window(None, text=self.game.prompt_of(request))
        cache = self.__dict__.setdefault("_dialogue_window_cache", {})
        frame = cache.get("choice_frame")
        if frame is None:
            frame = cache["choice_frame"] = self.load_image(settings["choice_frame"])
        font, window = cache.get("font"), cache["window"]
        letter, shadow = (
            tuple(c) for c in settings.get("colours", ((98, 98, 98), (213, 213, 205)))
        )
        step = int(settings.get("choice_line_height", 16))
        names = [self.game.expand_message(self.game.line_text(c), plain=True) for c in
                 request.choices]  # fmt: skip
        width = max((font.width(n) if font is not None else len(n) * 6) for n in names) + 16
        columns = max(1, getattr(request, "columns", 1))
        rows = (len(names) + columns - 1) // columns
        column = (width + 7) // 8 * 8  # a grid's options side by side, a column each
        inner = column * columns, rows * step
        ww, wh = window.get_size()
        right = int(settings.get("choice_right", ww - 24))
        bottom = int(settings.get("choice_bottom", 160 - wh))
        if request.box_at is not None:  # the choice's own place: its inside's top left
            right = request.box_at[0] - 8 + inner[0] + 16
            bottom = request.box_at[1] - 8 + inner[1] + 16
        box = self.pg.Surface((inner[0] + 16, inner[1] + 16), self.pg.SRCALPHA)
        piece = frame.get_width() // 3
        fill = settings.get("choice_fill") or frame.get_at(
            (piece + piece // 2, piece + piece // 2)
        )
        box.fill(fill)
        bw, bh = box.get_size()
        for col, x in ((0, 0), (2, bw - piece)):
            for row, y in ((0, 0), (2, bh - piece)):
                box.blit(frame, (x, y), (col * piece, row * piece, piece, piece))
        for x in range(piece, bw - piece, piece):
            box.blit(frame, (x, 0), (piece, 0, piece, piece))
            box.blit(frame, (x, bh - piece), (piece, 2 * piece, piece, piece))
        for y in range(piece, bh - piece, piece):
            box.blit(frame, (0, y), (0, piece, piece, piece))
            box.blit(frame, (bw - piece, y), (2 * piece, piece, piece, piece))
        cursor = self._choice_index(request)
        for index, name in enumerate(names):
            tx, ty = 16 + index % columns * column, 8 + index // columns * step
            if font is not None and font.covers(name):
                font.render(box, name, tx, ty, letter, shadow)
            else:
                face = self.pg.font.Font(None, 16)
                box.blit(face.render(name, False, letter), (tx, ty))
            if index == cursor:  # the pointer (menu.c's arrow)
                tip = [(tx - 7, ty + 3), (tx - 7, ty + 11), (tx - 3, ty + 7)]
                self.pg.draw.polygon(box, shadow, [(x + 1, y + 1) for x, y in tip])
                self.pg.draw.polygon(box, letter, tip)
        scale = max(1, self.width // ww)
        big = self.pg.transform.scale(box, (bw * scale, bh * scale))
        left = (self.width - ww * scale) // 2 + (right - bw) * scale
        self.screen.blit(
            big, (left, self.height - wh * scale - (160 - wh - bottom) * scale - bh * scale)
        )

    def _draw_dialogue_window(self, line, text=None, held=False):
        """``dialogue.window``: the game's own message window, drawn at its own resolution and
        scaled by whole pixels. ``window`` is the picture (placed at the bottom of the screen),
        ``text_area`` ``[x, y, w, h]`` in it, ``line_height``, ``font`` (a bitmap font JSON;
        text it lacks is drawn in a system face), ``colours`` ``[letter, shadow]``, ``speed``
        (letters a second, 0 = all at once), ``arrow`` (a strip of frames under each other,
        ``arrow_size`` ``[w, h]``) shown at ``arrow_at`` once the line is written out."""
        settings = self.dialogue_settings()
        cache = self.__dict__.setdefault("_dialogue_window_cache", {})
        if cache.get("settings") is not settings:  # another window (edited in the editor)
            cache.clear()
            cache["settings"] = settings
        if "window" not in cache:
            cache["window"] = self.load_image(settings["window"])
            cache["arrow"] = self.load_image(settings["arrow"]) if settings.get("arrow") else None
            cache["font"] = None
            if settings.get("font_id"):  # the project's bitmap font (Bitmap fonts…)
                cache["font"] = self.bitmap_font(settings["font_id"])
            elif settings.get("font"):
                from asteria.graphics.bitmap_font import BitmapFont

                cache["font"] = BitmapFont(self.pg, self.path(settings["font"]))
        window, arrow, font = cache["window"], cache["arrow"], cache["font"]
        ww, wh = window.get_size()
        scale = max(1, self.width // ww)
        surface = window.copy()
        if text is None:
            text = self.game.line_text(line)
        else:
            line = ("text", text)  # a prompt: typed out like a line
        text = self.game.expand_message(text, plain=True)
        if cache.get("line") is not line and not (
            isinstance(line, tuple) and cache.get("line") == line  # the same prompt
        ):
            cache["line"], cache["start"] = line, self.pg.time.get_ticks()
        speed = float(settings.get("speed", 40))
        speeds = settings.get("speeds")  # letters a second by the option.text_speed choice
        if speeds:
            chosen = int(self.game.save.event_context.get_variable("option.text_speed", 0) or 0)
            speed = float(speeds[min(chosen, len(speeds) - 1)])
        shown = len(text)
        if speed > 0:
            shown = int((self.pg.time.get_ticks() - cache["start"]) / 1000 * speed)
        x0, y0, _w, _h = settings.get("text_area", (16, 8, 216, 32))
        step = int(settings.get("line_height", 16))
        letter, shadow = (
            tuple(c) for c in settings.get("colours", ((98, 98, 98), (213, 213, 205)))
        )
        left = shown
        for row, words in enumerate(text.split("\n")[:2]):
            part = words[: max(0, left)]
            left -= len(words) + 1
            if not part:
                continue
            if font is not None and font.covers(part):
                font.render(surface, part, x0, y0 + row * step, letter, shadow)
            else:
                from asteria.platform.pygame_battle_ui import font_for_text

                face = font_for_text(
                    self.pg, self.pg.font.Font(None, 16), part, self._cjk_fonts, 12
                )
                image = face.render(part, False, letter)
                surface.blit(face.render(part, False, shadow), (x0 + 1, y0 + row * step + 1))
                surface.blit(image, (x0, y0 + row * step))
        if arrow is not None and shown >= len(text) and not held:  # held: no key awaited
            aw, ah = settings.get("arrow_size", (8, 16))
            frames = max(1, arrow.get_height() // ah)
            frame = (self.pg.time.get_ticks() // int(settings.get("arrow_frame_ms", 160))) % frames
            ax, ay = settings.get("arrow_at", (220, 24))
            surface.blit(arrow, (ax, ay), (0, frame * ah, aw, ah))
        big = self.pg.transform.scale(surface, (ww * scale, wh * scale))
        self.screen.blit(big, ((self.width - ww * scale) // 2, self.height - wh * scale))

    def _draw_emotes(self):
        """Marks over characters (``game.emotes``: a character that noticed the player...),
        pictures from ``field.emotes`` (``{key: picture}``), drawn above the head."""
        emotes = getattr(self.game, "emotes", None)
        pictures = self.manifest.get("field", {}).get("emotes") or {}
        view = self.tile_view
        if not emotes or not pictures or view is None:
            return
        offset = float(self.manifest.get("field", {}).get("emote_offset", 40))
        for entity_id, (key, _left) in emotes.items():
            entity = self.game.scene.get_entity(entity_id)
            if entity is None or key not in pictures:
                continue
            image = self.load_image(pictures[key])
            zoom = view.camera.zoom
            size = (round(image.get_width() * zoom), round(image.get_height() * zoom))
            cache = self.__dict__.setdefault("_emote_images", {})
            scaled = cache.get((key, size))
            if scaled is None:
                scaled = cache[(key, size)] = self.pg.transform.scale(image, size)
            t = entity.get(Transform)
            x, y = view.world_to_screen(t.x, t.y - offset)
            self.screen.blit(scaled, (round(x - size[0] / 2), round(y)))

    def _area_popup_offset(self, state, settings, now):
        """How far the popup is above its place now (0 = fully shown); moves the popup through
        sliding in, holding and sliding out, and starts a waiting name after it."""
        hidden = state["height"]
        speed = float(settings.get("slide_speed", 119.5))  # world pixels a second
        hold = float(settings.get("show_seconds", 2.0))
        since = now - state["t"]
        if state["phase"] == "in":
            offset = hidden - speed * since
            if offset > 0:
                return offset
            state.update(phase="hold", t=now)
            return 0.0
        if state["phase"] == "hold":
            if since < hold:
                return 0.0
            state.update(phase="out", t=now, start=0.0)
            since = 0.0
        offset = state["start"] + speed * since
        if offset < hidden:
            return offset
        if state.get("next"):
            state.update(title=state.pop("next"), phase="in", t=now)
            return hidden
        state["title"] = None
        return None

    def _draw_area_name(self):
        """``field.area_name``: the name of a map area the player walks into, on a board that
        slides down from the top of the screen, stays ``show_seconds`` (2) and slides back up
        (``slide_speed`` world pixels a second, 119.5). ``window`` is the board's picture,
        ``at`` ``[x, y]`` where it rests, ``text_area`` ``[x, y, width]`` the line the name is
        centred on, ``font`` a bitmap font JSON and ``colours`` ``[letter, shadow]``. A new name
        hurries the shown one away first."""
        requests = self.game.area_title_requests
        settings = self.manifest.get("field", {}).get("area_name")
        if not settings:
            requests.clear()
            return
        cache = self.__dict__.setdefault("_area_popup", {"title": None})
        if "window" not in cache:
            cache["window"] = self.load_image(settings["window"])
            cache["font"] = None
            if settings.get("font"):
                from asteria.graphics.bitmap_font import BitmapFont

                cache["font"] = BitmapFont(self.pg, self.path(settings["font"]))
        window = cache["window"]
        now = self.pg.time.get_ticks() / 1000.0
        if requests:
            title = requests[-1]
            requests.clear()
            if cache["title"] is None:
                cache.update(title=title, phase="in", t=now, height=window.get_height())
            else:
                cache["next"] = title
                if cache["phase"] != "out":
                    offset = self._area_popup_offset(cache, settings, now) or 0.0
                    cache.update(phase="out", t=now, start=offset)
        if cache["title"] is None:
            return
        offset = self._area_popup_offset(cache, settings, now)
        if offset is None:
            return
        surface = window.copy()
        title = cache["title"]
        tx, ty, tw = settings.get("text_area", (8, 11, 80))
        letter, shadow = (
            tuple(c) for c in settings.get("colours", ((255, 255, 255), (41, 49, 90)))
        )
        font = cache["font"]
        if font is not None and font.covers(title):
            font.render(surface, title, tx + (tw - font.width(title)) // 2, ty, letter, shadow)
        else:
            from asteria.platform.pygame_battle_ui import font_for_text

            face = font_for_text(self.pg, self.pg.font.Font(None, 16), title, self._cjk_fonts, 12)
            x = tx + (tw - face.size(title)[0]) // 2
            surface.blit(face.render(title, False, shadow), (x + 1, ty + 1))
            surface.blit(face.render(title, False, letter), (x, ty))
        view = self.tile_view
        scale = max(1, round(view.camera.zoom) if view is not None else self.width // 240)
        ax, ay = settings.get("at", (0, 0))
        big = self.pg.transform.scale(
            surface, (surface.get_width() * scale, surface.get_height() * scale)
        )
        self.screen.blit(big, (round(ax * scale), round((ay - offset) * scale)))

    def _draw_message(self, text, x, y, *, size=22, step=None, color=None, font=None, limit=None):
        """Draw a message whose data codes are expanded: colour and size spans, icons as boxes,
        ``\\n`` starts a new line. A layout (V2) may give the line ``step``, the plain text's
        ``color``, a ``font`` and ``limit`` (how many letters are typed out so far)."""
        from asteria.presentation.message_codes import DEFAULT_PALETTE, parse_message

        left, top = x, y
        step = step or size + 6
        for span in parse_message(text):
            if limit is not None and limit <= 0:
                break
            if span.icon is not None:
                icon_id = self.game.message_icon(span.icon)
                if not (icon_id and self._draw_icon(icon_id, left, top, size)):
                    box = self.pg.Rect(left, top + 2, size - 4, size - 4)  # no icon: a box
                    self.pg.draw.rect(self.screen, span.color, box, 2, 3)
                left += size
                continue
            plain = span.color == DEFAULT_PALETTE[0]  # no colour code: the layout's colour
            tint = color if color is not None and plain else span.color
            for number, part in enumerate(span.text.split("\n")):
                if number:
                    left, top = x, top + step
                if limit is not None:
                    part, limit = part[: max(0, limit)], limit - len(part) - 1
                if part:
                    rect = self.text(
                        part, left, top, size=size + 6 * span.size_steps, color=tint, font=font
                    )
                    left = rect.right

    def _dialogue_input(self, events):
        """Route keys to a waiting dialogue/choice. Returns True when one is open."""
        request = (
            getattr(self, "_network_dialogue", None)
            if self._multiplayer_connected()
            else self.game.pending_dialogue
        )
        if request is None:
            return False
        if getattr(request, "line", None) is not None:
            if self.input.just_pressed("confirm") or self.input.just_pressed("interact"):
                self.game.acknowledge_dialogue()
                sound = self.dialogue_settings().get("confirm_sound")
                self._sound(sound or self.manifest.get("dialogue_confirm_sfx"))
            return True
        choices = getattr(request, "choices", None) or ()
        cursor = self._choice_index(request)
        for event in events:
            if event.type != self.pg.KEYDOWN or not choices:
                continue
            if self.pg.K_1 <= event.key <= self.pg.K_9:
                index = event.key - self.pg.K_1
                if index < len(choices):
                    self.game.choose(index)
                    return True
            elif getattr(request, "columns", 1) > 1 and event.key in self._grid_steps(request):
                # a grid: left / right one option, up / down a row (no wrapping)
                moved = cursor + self._grid_steps(request)[event.key]
                if 0 <= moved < len(choices):
                    self._choice_cursor = cursor = moved
            elif event.key in (self.pg.K_UP, self.pg.K_LEFT):
                self._choice_cursor = cursor = (cursor - 1) % len(choices)
            elif event.key in (self.pg.K_DOWN, self.pg.K_RIGHT):
                self._choice_cursor = cursor = (cursor + 1) % len(choices)
        if choices and (self.input.just_pressed("confirm") or self.input.just_pressed("interact")):
            self.game.choose(cursor)
        elif choices and getattr(request, "cancel", ()) and self.input.just_pressed("cancel"):
            self.game.cancel_choice()  # the choice's own answer to the cancel key
        elif (
            choices
            and self.dialogue_settings().get("cancel_picks_last")
            and self.input.just_pressed("cancel")
        ):
            self.game.choose(len(choices) - 1)  # B on YES / NO answers NO
        return True

    def _field_input(self, events, dt):
        for event in events:  # clicking a picture that has an event
            if event.type == self.pg.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                if self._click_picture(*event.pos) is not None:
                    return False
                if self.game.click_entity(*self._field_world_xy(*event.pos)) is not None:
                    return False
        if self.game.cutscene_active:
            if self.game.cutscene_skippable and self.input.just_pressed("cancel"):
                self.game.skip_cutscene()
                return False
            self._dialogue_input(events)
            return False
        if self._equip_offer_input(events):
            return False
        if self._dialogue_input(events) or (
            getattr(self, "_network_event_busy", False)
            if self._multiplayer_connected()
            else self.game.event_busy
        ):
            if self._multiplayer_connected():
                self._send_multiplayer_input(0, 0, {})
            else:
                self.game.set_field_input(None)
            return False
        if (
            self.multiplayer_bridge is not None
            and not self.multiplayer_bridge.connected
            and any(
                event.type == self.pg.KEYDOWN and event.key == self.pg.K_F3 for event in events
            )
        ):
            if self.multiplayer_bridge.connect():
                self._network_predictor = None
                self._network_input_prediction_sequences.clear()
                self._network_prediction_reconciled_revision = -1
                self.multiplayer_bridge.send_input(
                    {"move_x": 0.0, "move_y": 0.0, "attack": False}, force=True
                )
                self._multiplayer_error = ""
                self._network_revision = -1
            else:
                self._multiplayer_error = self.multiplayer_bridge.error
        if self.game.action_scene:
            return self._action_input(events, dt)
        # Project input map: keyboard and gamepad (stick / d-pad) both drive movement.
        dx, dy = self.input.current.movement_vector()
        moving = bool(dx or dy)
        connected = self._multiplayer_connected()
        if connected:
            self._predict_multiplayer_player(dx, dy, dt)
            self._send_multiplayer_input(dx, dy, dict(self.input.current.actions))
            self._sync_multiplayer_player()
        elif self.manifest.get("field", {}).get("movement") == "grid":
            moving = self._grid_field_step(dx, dy, dt)
        elif moving:
            mag = max(1.0, (dx * dx + dy * dy) ** 0.5)
            speed = 36.0
            pt = self.game.player.get(Transform)
            blocked = CollisionWorld.from_scene(self.game.scene).blocking_query(
                exclude={self.game.player.id}
            )
            x_range, y_range = (-120.0, 120.0), (-52.0, 52.0)
            if self.tile_view is not None:
                # a tile map: its walls block and its edge bounds the walk, the pace is a walk
                # across a screen in a few seconds
                from asteria.runtime.collision import CombinedQuery

                walls = self.game._tile_blocking.get(self.game.scene.id)
                blocked = CombinedQuery(blocked, walls)
                x0, y0, x1, y1 = self.tile_view.bounds
                x_range, y_range, speed = (x0 + 6, x1 - 6), (y0 + 6, y1 - 2), 64.0
            nx = max(x_range[0], min(x_range[1], pt.x + dx / mag * speed * dt))
            if not blocked.collides_world_point(nx, pt.y):
                pt.x = nx
            ny = max(y_range[0], min(y_range[1], pt.y + dy / mag * speed * dt))
            if not blocked.collides_world_point(pt.x, ny):
                pt.y = ny
            self.game.save.player_position = (pt.x, pt.y)
            if abs(dx) > abs(dy):
                self.game.set_player_facing("right" if dx > 0 else "left")
            else:
                self.game.set_player_facing("down" if dy > 0 else "up")
            self._field_step += 1
        if not connected:  # a player with ActionCombat bindings strikes and shoots here too
            self.game.set_field_input(
                dict(self.input.current.actions) if self._field_abilities() else None
            )

        if self.input.just_pressed("menu") and self.settings.developer_menu:
            self._ui_mode = "build"
        if self.input.just_pressed("cancel"):
            if creature_settings(self, "field.creature_menu"):  # the game's own menu
                from asteria.runtime.creature_menu import CreatureMenuScreen

                self._creature_menu = CreatureMenuScreen(self)
                self._ui_mode = "creature_menu"
                return moving
            self._pause_menu.index = 0
            self._ui_mode = "pause"
            return moving
        if any(e.type == self.pg.KEYDOWN and e.key == self.pg.K_i for e in events):
            self.open_status_menu(back="field")
            return moving
        if any(e.type == self.pg.KEYDOWN and e.key == self.pg.K_q for e in events):
            self._quest_return = "field"
            self._ui_mode = "quests"
            return moving
        if moving and not connected and self.game.mode == "field":
            self.game.field_step({})  # doors and other triggers walked into
        # GameSessionRuntime interaction is edge-triggered. Emit release after press.
        if self.input.just_pressed("interact") and not connected:
            self.game.field_step({"interact": 1.0})
            if self.game.mode == "field":
                self.game.field_step({"interact": 0.0})
        return moving

    def _grid_field_step(self, dx, dy, dt):
        """``field.movement: "grid"``: a whole cell a step (runtime/grid_walk.py)."""
        from asteria.runtime.collision import CombinedQuery
        from asteria.runtime.grid_walk import GridWalker

        walker = getattr(self, "_grid_walker", None)
        moves = getattr(self.game, "player_story_moves", 0)  # an event moved / turned the player
        if (
            walker is None
            or getattr(self, "_grid_walker_scene", None) != self.game.scene.id
            or getattr(self, "_grid_walker_moves", moves) != moves
        ):
            walker = self._grid_walker = GridWalker(self.manifest.get("field", {}))
            self._grid_walker_scene = self.game.scene.id
            transform = self.game.player.get(Transform)  # on a whole cell again
            size = walker.size
            transform.x = (transform.x // size) * size + size / 2
            transform.y = (transform.y // size) * size + size / 2
        self._grid_walker_moves = moves
        game = self.game
        blocked = CollisionWorld.from_scene(game.scene).blocking_query(exclude={game.player.id})
        walls = game._tile_blocking.get(game.scene.id)
        if walls is not None:
            blocked = CombinedQuery(blocked, walls)
        running = self.input.held(walker.run_action) if walker.run_action else False
        needs = self.manifest.get("field", {}).get("run_switch")  # running only once allowed
        if running and needs and not game.save.event_context.get_switch(needs):
            running = False
        transform = game.player.get(Transform)
        movers = game._grid_movers.get(game.scene.id)
        held = movers.held_cells() if movers is not None else set()
        size = walker.size

        before = walker.target

        def stopped(x, y):  # a wall, or a cell a grid character stands on or walks into
            return (int(x // size), int(y // size)) in held or blocked.collides_world_point(x, y)

        facing, moving = walker.step(
            transform,
            game.facing,
            dx,
            dy,
            dt,
            stopped,
            running=running,
            ledge=self._grid_ledge(),
        )
        game.player_lift = walker.lift  # the view draws a hopping player raised
        if before is not None and walker.target != before and game.mode == "field":
            # a step ended on a cell: the area there may start a random encounter
            if game.step_arrived():
                transform.x, transform.y = before  # the battle starts on that cell
                walker.target, walker.jump, walker.lift = None, None, 0.0
                game.player_lift = 0.0
        target = walker.target
        game.grid_reserved = (
            ((int(target[0] // size), int(target[1] // size)),) if target is not None else ()
        )
        if facing != game.facing:
            game.set_player_facing(facing)
        game.save.player_position = (transform.x, transform.y)
        if moving:
            self._field_step += 1
        return moving

    def _grid_ledge(self):
        """``ledge(x, y, facing)`` for the grid walk: the tiles there carry the tag
        ``<field.ledge_tag><facing>`` (default ``ledge_down`` ...); ``None`` without a tile map."""
        view = self.tile_view
        if view is None:
            return None
        cache = getattr(self, "_ledge_keys", None)
        if cache is None or cache[0] is not view.tilemap:
            from asteria.runtime.map_rules_field import tile_area_keys

            cache = self._ledge_keys = (view.tilemap, tile_area_keys(view.tilemap, view.tileset))
        keys_at = cache[1]
        prefix = str(self.manifest.get("field", {}).get("ledge_tag", "ledge_"))
        return lambda x, y, facing: f"tag:{prefix}{facing}" in keys_at(x, y)

    def _field_abilities(self):
        """The player carries ActionCombat bindings (a field attack in a turn-based game)."""
        from asteria.runtime.action_combat import ActionCombatComponent

        combat = self.game.player.try_get(ActionCombatComponent)
        return combat is not None and combat.enabled and bool(combat.bindings.strip())
