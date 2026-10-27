"""What stat modifiers do, in words (D91): ``MAG +18``, ``DEF x1.6``, ``Crit Rate +3%``.

A passive, a state or a piece of gear is a list of ``StatModifier``; a player reads it as one
line per stat. ``amount`` writes one value the stat's way (Game Systems ▸ Stats: a percent stat
gets its ``%``, a 0..1 share is multiplied by 100); ``modifier_lines`` adds up a list per stat,
operation and condition (``when weapon.sword``).
"""

from __future__ import annotations


def _english(_key, english, **params):
    return english.format(**params) if params else english


def amount(value, operation="add", definition=None):
    """``+18``, ``-5%``, ``x1.6`` or ``= 3``: ``value`` written for ``operation``."""
    operation = getattr(operation, "value", operation)
    if operation == "multiply":
        return f"x{value:g}"

    def text(v):
        return definition.text(v) if definition is not None else f"{v:g}"

    if operation == "override":
        return f"= {text(value)}"
    return ("+" if value >= 0 else "-") + text(abs(value))


def modifier_lines(modifiers, name, definitions=None, tag_name=str, tr=None):
    """One line per stat, operation and condition: ``name(stat_id)`` and the summed amount
    (adds add up, multipliers multiply), ``(when <tags>)`` for a modifier that needs tags."""
    definitions = definitions or {}
    tr = tr or _english
    totals = {}
    for m in modifiers:
        operation = getattr(m.operation, "value", m.operation)
        key = (m.stat, operation, tuple(m.required_tags))
        if key not in totals:
            totals[key] = 1.0 if operation == "multiply" else 0.0
        if operation == "multiply":
            totals[key] *= m.value
        elif operation == "override":
            totals[key] = m.value
        else:
            totals[key] += m.value
    lines = []
    for (stat, operation, needs), value in totals.items():
        line = f"{name(stat)} {amount(value, operation, definitions.get(stat))}"
        if needs:
            tags = ", ".join(tag_name(t) for t in needs)
            line += " " + tr("effect.when", "(when {tags})", tags=tags)
        lines.append(line)
    return lines


__all__ = ["amount", "modifier_lines"]
