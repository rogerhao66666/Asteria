"""The ordinary message window drawn through its layout (V2): ``dialogue`` for a line,
``dialogue_choice`` for a choice (``presentation/menu_layout.py``).

Every piece is an element the author can move, resize, reskin or hide on Presentation ▸ Menu
Screens ▸ Layout: the window, the speaker's name (and a name box behind it), the portrait's
place, the line (its text area, size, colour, bitmap font, line height and letters a second),
the "continue" words and a "next" arrow (a strip of frames); the prompt, the options (columns,
cell width, row height, the chosen option's frame) and a box behind them. Without a layout the
window draws exactly as before (``tests/test_dialogue_portraits.py``).
"""

from __future__ import annotations

LINE_FIELDS = ("speaker", "text")


def _shift_portrait(portrait, old, new, left):
    """The portrait moved with its window (left side: the window's left edge; right side:
    its right edge; a face keeps its height in the window, a bust stands on its bottom)."""
    picture, at, style, room = portrait
    if tuple(old) == tuple(new):
        return portrait
    if left:
        dx = new[0] - old[0]
    else:
        dx = new[0] + new[2] - old[0] - old[2]
    if style == "bust":
        dy = new[1] + new[3] - old[1] - old[3]
    else:
        dy = new[1] + new[3] // 2 - old[1] - old[3] // 2
    at = (at[0] + dx, at[1] + dy)
    room = (room[0] + dx, room[1] + dy, room[2], room[3])
    return picture, at, style, room


def _typed(rt, line, speed):
    """How many letters of ``line`` are shown (``speed`` letters a second; 0: all)."""
    if speed <= 0:
        return None
    state = rt.__dict__.setdefault("_typed_line", {})
    if state.get("line") is not line:
        state["line"], state["start"] = line, rt.pg.time.get_ticks()
    return int((rt.pg.time.get_ticks() - state["start"]) / 1000 * speed)


def draw_message_window(rt, request, line):
    """The ordinary message window for ``request`` (a line, or a choice when ``line`` is
    None)."""
    if line is None:
        _draw_choice(rt, request)
        return
    game = rt.game
    speaker = game.expand_message(game.speaker_of(line), plain=True) if line.speaker else ""
    c = rt.menu_canvas("dialogue", {"speaker": speaker, "text": lambda: game.line_text(line)})
    c.begin()
    box, portrait = rt._dialogue_layout(line)
    left = line.portrait_side == "left"
    moved = c.rect("window", box)
    if portrait is not None:
        portrait = _shift_portrait(portrait, box, moved, left)
        room = c.rect("portrait", portrait[3])
        if tuple(room) != tuple(portrait[3]):  # the author's own place for it
            picture = rt.dialogue_portrait(line.portrait_asset_id, room[2], room[3])
            if picture is not None:
                at = (
                    room[0] + (room[2] - picture.get_width()) // 2,
                    room[1] + room[3] - picture.get_height()
                    if portrait[2] == "bust"
                    else room[1] + (room[3] - picture.get_height()) // 2,
                )
                portrait = (picture, at, portrait[2], room)
        if not c.shown("portrait"):
            portrait = None
    box = moved
    if portrait is not None and portrait[2] == "bust":  # stands behind the window
        rt.screen.blit(portrait[0], portrait[1])
    c.panel("window", box, fill=(10, 14, 24, 235), border=(240, 201, 93))
    x, y, w, h = box
    text_x = x + 24
    hint_x, hint_anchor = rt.width - 250, None
    if portrait is not None and portrait[2] == "face":
        picture, at, _, room = portrait
        rt.screen.blit(picture, at)
        if left:
            text_x = room[0] + room[2] + 18  # the text starts after the face's square
        else:  # the hint ends before the face
            hint_x, hint_anchor = room[0] - 14, "topright"
    if speaker:
        width = rt.text_size(speaker, c.size("speaker", 24), c.font_of(c.element("speaker")))[0]
        c.picture("name_box", (text_x - 10, y + 6, width + 20, 36))
        c.text("speaker", speaker, text_x, y + 12, size=24, color=(255, 220, 124))
    element = c.element("text")
    message = game.expand_message(game.line_text(line))
    shown = _typed(rt, line, element.fps if element is not None else 0)
    if element is None:
        c._box("text", (text_x, y + 46, w - (text_x - x) - 24, h - 58))
        rt._draw_message(message, text_x, y + 46)
    else:
        if element.visible:
            tx, ty, _tw, _th = c.rect("text", (text_x, y + 46, w - (text_x - x) - 24, h - 58))
            size = element.size or 22
            rt._draw_message(
                message, tx, ty, size=size, step=element.row_height or None,
                color=element.color, font=c.font_of(element), limit=shown,
            )  # fmt: skip
    done = shown is None or shown >= len(message)
    c.text(
        "continue",
        game.tr("dialogue.continue", "Enter / E: continue"),
        hint_x,
        y + h - 28,
        size=18,
        color=(170, 210, 240),
        anchor=hint_anchor,
    )
    if done:
        c.picture("arrow", (x + w - 44, y + h - 40, 24, 24))
    c.finish()


def _draw_choice(rt, request):
    game = rt.game
    prompt = game.prompt_of(request) or game.tr("dialogue.choose", "Choose")
    c = rt.menu_canvas("dialogue_choice", {"prompt": prompt})
    c.begin()
    choices = request.choices[:9]
    columns = c.number("choices", "columns", 3)
    cell = c.number("choices", "cell", 270)
    row = c.row_height("choices", 26)
    rows = max(1, -(-len(choices) // max(1, columns)))
    area = (84, rt.height - 184, cell * columns, row * rows)
    box, _portrait = rt._dialogue_layout(None)  # the message window, as for a line
    place = c.place("choices", area, row)
    if c.element("box") is None or c.element("box").rect is None:
        box = _grown(c, box, place, rows, row)  # taller rows or more of them: room for all
    c.panel("box", box, fill=(10, 14, 24, 235), border=(240, 201, 93))
    c.text("prompt", prompt, 84, rt.height - 218, size=22, color=(255, 220, 124))
    element = c.element("choices")
    look = element is not None and (element.selection_skin or element.selection_fill)
    cursor = rt._choice_index(request)
    size = c.size("choices", 20)
    color = c.color("choices", (245, 245, 250))
    font = c.font_of(element)
    for i, choice in enumerate(choices, 1):
        cx = place.x(84 + ((i - 1) % columns) * cell)
        cy = place.y(rt.height - 184 + ((i - 1) // columns) * row)
        if look and i - 1 == cursor:
            c.selection("choices", (cx - 6, cy - 2, cell - 12, row), lambda: None)
        mark = "> " if i - 1 == cursor and not look else "   "
        rt.text(f"{mark}{i}. {game.line_text(choice)}", cx, cy, size=size, color=color,
                font=font)  # fmt: skip
    c.finish()


def _grown(c, box, place, rows, row):
    """The window behind a choice made tall enough for the prompt and every row of options
    (the engine's own sizes fit as they are: 12 pixels above the prompt, 6 under the last
    row). A box the author placed keeps its size."""
    from asteria.presentation.menu_layout import resolve_rect

    height = c.rt.height
    prompt = c.element("prompt")
    prompt_y = height - 218
    if prompt is not None and prompt.rect is not None:
        prompt_y = resolve_rect(prompt.rect, prompt.anchor, c.area)[1]
    first = place.y(height - 184)
    top = min(box[1], prompt_y - 12, first - 12)
    bottom = min(height, max(box[1] + box[3], first + rows * row + 6))
    return box[0], top, box[2], bottom - top


__all__ = ["draw_message_window"]
