"""Dialogue on the field: portraits, the message and choice windows, emotes, the area name
and reading the player's answers."""

from __future__ import annotations

from asteria.core import Transform
from asteria.platform.pygame_battle_ui import font_for_text
from asteria.presentation.text.message_codes import DEFAULT_PALETTE, parse_message
from asteria.runtime.menus.dialogue import draw_message_window
from asteria.runtime.menus.icons import icon_source


class DialogueUiMixin:
    """Dialogue on the field: portraits, the message and choice windows, emotes, the area name"""

    # defaults until something sets them (code may read them first)
    _choice_request = None
    _network_dialogue = None

    def dialogue_portrait(self, portrait_id, width, height):
        """The picture ``portrait_id`` names (an image asset, a sheet cell or a project path)
        fitted inside ``width`` x ``height`` with its proportions kept, or ``None``. A picture
        made larger keeps sharp pixels (pixel-art faces); one made smaller is smoothed."""

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
        """The message window, and last of all a SCREEN_FADE ``over`` everything."""
        self._draw_dialogue_request()
        effects = self.field_effects
        if effects.fade_alpha > 0 and effects.fade_over == "everything":
            self.dim_screen((*effects.fade_color, int(effects.fade_alpha * 255)))

    def _draw_dialogue_request(self):
        request = (
            self._network_dialogue if self._multiplayer_connected() else self.game.pending_dialogue
        )
        held = False
        if request is None and not self._multiplayer_connected():
            request = self.game.held_dialogue  # shown without waiting for a key
            held = request is not None
        if request is None:
            return
        line = getattr(request, "line", None)
        if not held:  # a click anywhere goes on (a line) or is kept from the map (a choice)
            self.hotspot((0, 0, self.width, self.height), key="return" if line is not None else "")
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

        draw_message_window(self, request, line)  # through the dialogue layouts (V2)

    def _grid_steps(self, request):
        pg = self.pg
        return {pg.K_LEFT: -1, pg.K_RIGHT: 1, pg.K_UP: -request.columns,
                pg.K_DOWN: request.columns}  # fmt: skip

    def _choice_index(self, request):
        """The choice under the cursor (arrow keys move it; a new one starts on its ``cursor``)."""
        if self._choice_request is not request:  # its own start (cursor)
            self._choice_request = request
            self._choice_cursor = getattr(request, "cursor", 0)
        return self._choice_cursor

    def _draw_choice_window(self, request):
        """A choice in the game's own windows: the prompt in the message window, the options in
        a framed box above its right end (``dialogue.choice_frame``: a 3 x 3 grid of 8-pixel
        border pieces; ``choice_fill``: the inside colour; ``choice_right`` / ``choice_bottom``:
        the box's right and bottom edges in window pixels, unless the choice gives ``box_at``,
        its inside's top left; ``choice_line_height``), a pointer at the option under the
        cursor. The box comes once the prompt is written out (``choice_after_text``: false
        shows it at once)."""
        settings = self.dialogue_settings()
        self._draw_dialogue_window(None, text=self.game.prompt_of(request))
        cache = self._dialogue_window_cache
        if not self._choice_ready():
            return
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
        choice_spots = []  # (option, x, y, width, height) in the box's own pixels
        for index, name in enumerate(names):
            tx, ty = 16 + index % columns * column, 8 + index // columns * step
            if font is not None and font.covers(name):
                font.render(box, name, tx, ty, letter, shadow)
            else:
                face = self.pg.font.Font(None, 16)
                box.blit(face.render(name, False, letter), (tx, ty))
            choice_spots.append((index, tx - 8, ty, column, step))
            if index == cursor:  # the pointer (menu.c's arrow)
                tip = [(tx - 7, ty + 3), (tx - 7, ty + 11), (tx - 3, ty + 7)]
                self.pg.draw.polygon(box, shadow, [(x + 1, y + 1) for x, y in tip])
                self.pg.draw.polygon(box, letter, tip)
        scale = max(1, self.width // ww)
        big = self.pg.transform.scale(box, (bw * scale, bh * scale))
        left = (self.width - ww * scale) // 2 + (right - bw) * scale
        top = self.height - wh * scale - (160 - wh - bottom) * scale - bh * scale
        self.screen.blit(big, (left, top))
        for index, x, y, w, h in choice_spots:
            spot = (left + x * scale, top + y * scale, w * scale, h * scale)
            self.hotspot(spot, lambda index=index: setattr(self, "_choice_cursor", index))

    def _draw_dialogue_window(self, line, text=None, held=False):
        """``dialogue.window``: the game's own message window, drawn at its own resolution and
        scaled by whole pixels. ``window`` is the picture (placed at the bottom of the screen),
        ``text_area`` ``[x, y, w, h]`` in it, ``line_height``, ``font`` (a bitmap font JSON;
        text it lacks is drawn in a system face), ``colours`` ``[letter, shadow]``, ``speed``
        (letters a second, 0 = all at once), ``arrow`` (a strip of frames under each other,
        ``arrow_size`` ``[w, h]``) shown at ``arrow_at`` once the line is written out; ``rows``
        lines show at once (2), a longer line scrolls up as it is written."""
        settings = self.dialogue_settings()
        cache = self._dialogue_window_cache
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
        if cache.get("held") and cache.get("text") == text:  # a held line now awaited
            cache["line"] = line  # (waitbuttonpress): written out already, not typed again
        elif cache.get("line") is not line and not (
            isinstance(line, tuple) and cache.get("line") == line  # the same prompt
        ):
            cache["line"], cache["start"] = line, self.pg.time.get_ticks()
        cache["held"], cache["text"] = held, text
        speed = float(settings.get("speed", 40))
        speeds = settings.get("speeds")  # letters a second by the option.text_speed choice
        if speeds:
            chosen = int(self.game.save.event_context.get_variable("option.text_speed", 0) or 0)
            speed = float(speeds[min(chosen, len(speeds) - 1)])
        shown = len(text)
        if speed > 0:
            shown = int((self.pg.time.get_ticks() - cache["start"]) / 1000 * speed)
        cache["written"] = shown >= len(text)  # a choice's box waits for its prompt
        x0, y0, _w, _h = settings.get("text_area", (16, 8, 216, 32))
        step = int(settings.get("line_height", 16))
        letter, shadow = (
            tuple(c) for c in settings.get("colours", ((98, 98, 98), (213, 213, 205)))
        )
        typed, left = [], shown  # lines begun so far; past ``rows`` the window scrolls up
        for words in text.split("\n"):
            if left <= 0 and typed:
                break
            typed.append(words[: max(0, left)])
            left -= len(words) + 1
        for row, part in enumerate(typed[-int(settings.get("rows", 2)) :]):
            if not part:
                continue
            if font is not None and font.covers(part):
                font.render(surface, part, x0, y0 + row * step, letter, shadow)
            else:
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
        effects = self.field_effects
        if effects.fade_alpha > 0 and effects.fade_over == "message_window":
            mix = round(effects.fade_alpha * 255)
            shade = self.pg.Surface(surface.get_size(), self.pg.SRCALPHA)
            shade.fill((*effects.fade_color, mix))
            surface.blit(shade, (0, 0))
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
            cache = self._emote_images
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
        cache = self._area_popup
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

    def _choice_ready(self):
        """Whether a choice in the game's own windows takes keys: once its prompt is written out
        (``dialogue.choice_after_text``, true unless set false; other windows: at once)."""
        settings = self.dialogue_settings()
        if not settings.get("window") or not settings.get("choice_after_text", True):
            return True
        cache = self._dialogue_window_cache
        return cache.get("written", True)

    def _dialogue_input(self, events):
        """Route keys to a waiting dialogue/choice. Returns True when one is open."""
        request = (
            self._network_dialogue if self._multiplayer_connected() else self.game.pending_dialogue
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
        if choices and not self._choice_ready():
            return True  # its box is not up yet: the prompt is still being written
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
        if (
            choices
            and cursor != getattr(self, "_choice_hovered", (None, None))[1]
            and (getattr(self, "_choice_hovered", (None, None))[0] is request)
        ):
            self.game.hover_choice(cursor)  # the pointer moved: the choice's hover commands
        self._choice_hovered = (request, cursor)
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
