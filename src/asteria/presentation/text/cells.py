"""How much room a line of text needs before a font is chosen, in cells.

The battle screen and a few runtime panels lay text out by counting characters. A Chinese,
Japanese or Korean character (or a full-width letter) is drawn about twice as wide as a Latin
letter, so it counts as two cells; every other character counts as one. Plain ASCII text keeps
its length, so English layouts come out exactly as they did when characters were counted.
"""

from __future__ import annotations

from unicodedata import east_asian_width

# full-width marks that never start a line: they stay with the character before them
_CLOSING = frozenset("，。、！？：；）」』》〉】〕”’…・～")


def _width(char):
    return 2 if east_asian_width(char) in ("W", "F") else 1


def cells(text):
    """The room ``text`` takes: one cell per character, two per full-width one."""
    text = str(text)
    if text.isascii():
        return len(text)
    return sum(_width(c) for c in text)


def cut(text, room):
    """The longest start of ``text`` that fits in ``room`` cells."""
    text, room = str(text), int(room)
    if text.isascii():
        return text[: max(0, room)]
    used = 0
    for index, char in enumerate(text):
        used += _width(char)
        if used > room:
            return text[:index]
    return text


def _parts(word):
    """A word split where a line may break inside it: before and after each full-width
    character (Chinese and Japanese put no spaces between words), never before a closing
    mark."""
    if word.isascii():
        return [word]
    parts = []
    for char in word:
        # a run of narrow characters stays one piece; a closing mark joins the one before
        narrow_run = _width(char) == 1 and _width(parts[-1][-1]) == 1 if parts else False
        if parts and (char in _CLOSING or narrow_run):
            parts[-1] += char
        else:
            parts.append(char)
    return parts


def wrap(text, room):
    """``text`` in lines of at most ``room`` cells, broken at spaces and between full-width
    characters. A word wider than a line keeps a line of its own (English text wraps exactly
    as it did by counting characters)."""
    lines, line = [], ""
    for word in str(text).split():
        for index, part in enumerate(_parts(word)):
            gap = " " if index == 0 and line else ""
            if line and cells(line) + len(gap) + cells(part) > room:
                lines.append(line)
                line = part
            else:
                line += gap + part
    lines.append(line)
    return lines
