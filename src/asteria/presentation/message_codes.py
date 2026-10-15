"""Message text codes (YEP MessageCore): ``\\V[n]``, ``\\N[id]``, ``\\C[n]``, macros and more.

Two steps. ``expand_message`` replaces the *data* codes with their values (variables, names,
currency, macros, translations) and leaves the formatting codes in place; ``parse_message`` turns
the result into spans a renderer draws one after another (colour, icon, size, pauses).

Data codes:  ``\\V[name]`` variable, ``\\S[name]`` switch (on/off), ``\\N[id]`` actor name,
``\\P[n]`` nth party member (1-based), ``\\G`` currency label, ``\\$`` currency amount,
``\\M[name]`` project macro, ``\\T[key]`` translation, ``\\\\`` a backslash.
Formatting:  ``\\C[n]`` colour (0 = normal), ``\\I[n]`` icon, ``\\{`` / ``\\}`` larger / smaller,
``\\.`` short pause, ``\\|`` long pause, ``\\!`` wait for a key, ``\\^`` do not wait at the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CODE = re.compile(r"\\(?:([VSNPMTCI])\[([^\]\n]*)\]|([G$\\{}.|!^]))")
MAX_MACRO_DEPTH = 5

# Colour table for ``\C[n]`` (RPG Maker's window colours); a project may pass its own.
DEFAULT_PALETTE = (
    (255, 255, 255),
    (32, 160, 214),
    (255, 120, 76),
    (102, 204, 64),
    (153, 204, 255),
    (204, 192, 255),
    (255, 255, 160),
    (128, 128, 128),
    (192, 192, 192),
    (32, 128, 204),
    (255, 56, 16),
    (0, 160, 16),
    (62, 154, 222),
    (160, 152, 255),
    (255, 204, 32),
    (0, 0, 0),
)
PAUSES = {".": 0.25, "|": 1.0}


@dataclass(frozen=True, slots=True)
class MessageContext:
    """What data codes read. Every part is optional; a missing value leaves the code visible."""

    variable: object = None  # name -> value
    switch: object = None  # name -> bool
    actor_name: object = None  # actor id -> name
    party_name: object = None  # 1-based index -> name
    currency_label: str = ""
    currency_amount: object = None  # () -> number
    macros: object = None  # dict name -> text
    translate: object = None  # key -> text or None


def expand_message(text, context=None, *, _depth=0):
    """Replace the data codes in ``text``; formatting codes are kept for ``parse_message``."""
    context = context or MessageContext()
    if _depth > MAX_MACRO_DEPTH:
        return text

    def replace(match):
        kind, arg, single = match.group(1), match.group(2), match.group(3)
        code = match.group(0)
        if single == "\\":
            return "\\\\"  # a literal backslash survives as an escaped one
        if single == "G":
            return context.currency_label or code
        if single == "$":
            amount = context.currency_amount() if context.currency_amount else None
            return code if amount is None else f"{amount:g}"
        if single:
            return code  # formatting
        value = None
        if kind == "V" and context.variable:
            value = context.variable(arg)
        elif kind == "S" and context.switch:
            value = "ON" if context.switch(arg) else "OFF"
        elif kind == "N" and context.actor_name:
            value = context.actor_name(arg)
        elif kind == "P" and context.party_name and arg.strip().isdigit():
            value = context.party_name(int(arg))
        elif kind == "M" and context.macros:
            macro = context.macros.get(arg)
            value = None if macro is None else expand_message(macro, context, _depth=_depth + 1)
        elif kind == "T" and context.translate:
            value = context.translate(arg)
        elif kind in "CI":
            return code  # formatting
        return code if value is None else str(value)

    return _CODE.sub(replace, text)


@dataclass(frozen=True, slots=True)
class Span:
    """A run of text drawn the same way, or a control (``pause`` seconds, ``wait`` for a key)."""

    text: str = ""
    color: tuple = DEFAULT_PALETTE[0]
    icon: int | None = None
    size_steps: int = 0  # \{ and \} steps (each one changes the size by 6 points)
    pause: float = 0.0
    wait: bool = False


def parse_message(text, palette=DEFAULT_PALETTE):
    """Split an expanded message into spans; unknown codes are kept as plain text."""
    spans, color, size, pos = [], palette[0], 0, 0
    buffer = []

    def flush():
        if buffer:
            spans.append(Span("".join(buffer), color, None, size))
            buffer.clear()

    for match in _CODE.finditer(text):
        buffer.append(text[pos : match.start()])
        pos = match.end()
        kind, arg, single = match.group(1), match.group(2), match.group(3)
        if single == "\\":
            buffer.append("\\")
        elif single == "{":
            flush()
            size += 1
        elif single == "}":
            flush()
            size -= 1
        elif single in PAUSES:
            flush()
            spans.append(Span(pause=PAUSES[single]))
        elif single == "!":
            flush()
            spans.append(Span(wait=True))
        elif single == "^":
            pass  # "no wait at the end" is a property of the whole message
        elif kind == "C" and arg.strip().isdigit():
            flush()
            index = int(arg)
            color = palette[index] if 0 <= index < len(palette) else palette[0]
        elif kind == "I" and arg.strip().isdigit():
            flush()
            spans.append(Span(icon=int(arg), color=color, size_steps=size))
        else:
            buffer.append(match.group(0))  # a data code that had no value: shown as it was
    buffer.append(text[pos:])
    flush()
    return tuple(s for s in spans if s.text or s.icon is not None or s.pause or s.wait)


def plain_message(text, context=None):
    """The message as plain text (codes expanded, formatting removed): for logs and backlogs."""
    return "".join(s.text for s in parse_message(expand_message(text, context)))


def auto_wait(text):
    """True unless the message ends with ``\\^`` (show the next one without waiting)."""
    return not text.rstrip().endswith("\\^")
