"""What a Game Systems "Usage" card shows (D108), without Qt: a short summary, then sections of
rows - one row per kind of thing (the actors' starting values, the gear that adds to it, the
rules that read it) with how many there are, the range of their numbers and the page they are
set on - and every record behind a row, by name, with a target to open it.

``stat_usage`` and ``tag_usage`` build a ``Usage``; ``editor/rpg/usage_panel.py`` draws it;
``Usage.text()`` is the same in plain lines (tests, search).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asteria.editor.ui.i18n import translate

# where a record of a database table opens: ``navigate_to_problem`` targets (problems.py)
RPG_TABLES = {
    "actors": "actors", "classes": "classes", "passives": "passives", "items": "items",
    "equipment": "equipment", "attachments": "attachments", "equipment_growth": "growth",
    "composition_recipes": "recipes", "party_setups": "parties", "formations": "formations",
    "enemies": "enemies", "encounters": "encounters", "progression_graphs": "graphs",
    "progression_tracks": "tracks", "ability_evolutions": "evolutions", "affixes": "affixes",
    "rarities": "rarities", "lib.abilities": "abilities", "lib.states": "states",
}  # fmt: skip
BATTLE_TABLES = {
    "interaction_rules": "interactions", "outcome_checks": "outcome_checks",
    "reactions": "reactions", "battle_state_policies": "states",
    "action_sequences": "sequences", "gauge_compositions": "gauges",
    "battle_session_rules": "session",
}  # fmt: skip


def t(template, *values):
    """``template`` in the editor's language, ``{0}``... filled in."""
    return translate(template).format(*values)


def target_for(table, record_id):
    """The jump to a record of ``table`` (``navigate_to_problem``'s target), or ``()``."""
    from asteria.editor.rpg.game_systems_authoring import KINDS

    record_id = str(record_id)
    if table in RPG_TABLES:
        return ("record", "rpg", RPG_TABLES[table], record_id)
    if table in BATTLE_TABLES:
        return ("record", "battle", BATTLE_TABLES[table], record_id)
    if table == "lib.attacks":
        return ("combat", "attacks", record_id)
    kind = next((k.kind_id for k in KINDS if table in (k.store, k.kind_id)), None)
    return ("game_system", kind, record_id) if kind else ()


def number(value, sign=False):
    """``12``, ``+1.8`` (``sign``), never ``12.0``."""
    text = f"{value:g}"
    return f"+{text}" if sign and value >= 0 else text


@dataclass(frozen=True, slots=True)
class Link:
    """One record named by a row: its name, its number there (``+10``, ``×18``), the amount
    the row's range is worked out from, and where it opens."""

    name: str
    value: str = ""
    amount: float | None = None
    target: tuple = ()

    def text(self):
        return f"{self.name} {self.value}".strip()


@dataclass(frozen=True, slots=True)
class UsageRow:
    """One kind of thing: ``what`` it is, the ``page`` it is set on (words), the records
    behind it, the ``noun`` they are counted as ("actor"), ``sign`` when the numbers add (+10)
    and ``mark`` before each number (×). ``short``: the row in the card's summary ("Gear").
    ``target``: the page to open when the row names no record of its own."""

    what: str
    page: str = ""
    links: tuple[Link, ...] = ()
    noun: str = ""
    sign: bool = False
    mark: str = ""
    short: str = ""
    target: tuple = ()

    def count(self):
        """ "5 actors" - empty when the row has no noun to count by."""
        if not self.noun or not self.links:
            return ""
        return count(len(self.links), self.noun)

    def span(self):
        """The range of the records' numbers: ``12 – 32``, ``+10``; empty without numbers."""
        amounts = [x.amount for x in self.links if x.amount is not None]
        if not amounts:
            return ""
        low, high = (f"{self.mark}{number(x, self.sign)}" for x in (min(amounts), max(amounts)))
        return low if low == high else f"{low} – {high}"

    def opens(self):
        """Where the row's "open" button goes: its own target, else its first record's when
        every record is on the same page (the jobs, not a job and a weapon)."""
        if self.target:
            return self.target
        pages = {x.target[:-1] for x in self.links if x.target}
        return next((x.target for x in self.links if x.target), ()) if len(pages) == 1 else ()

    def text(self):
        head = " · ".join(x for x in (self.what, self.count(), self.span()) if x)
        page = f"  ({self.page})" if self.page else ""
        listed = translate("; ").join(x.text() for x in self.links)
        return f"{head}{page}" + (f": {listed}" if listed else "")


@dataclass(frozen=True, slots=True)
class UsageSection:
    title: str
    rows: tuple[UsageRow, ...] = ()
    empty: str = ""  # said when there are no rows ("Nothing reads it yet.")
    numbered: bool = False  # the rows are steps in order (where a stat comes from)


@dataclass(frozen=True, slots=True)
class Usage:
    """A card: ``summary`` (a line or two said first), then its sections."""

    summary: tuple[str, ...] = ()
    sections: tuple[UsageSection, ...] = field(default=())

    def text(self):
        lines = list(self.summary)
        for section in self.sections:
            lines.append(section.title)
            if not section.rows and section.empty:
                lines.append(f"  {section.empty}")
            for number_, row in enumerate(section.rows, 1):
                mark = f"{number_}." if section.numbered else "•"
                lines.append(f"  {mark} {row.text()}")
        return "\n".join(lines)

    def __str__(self):
        return self.text()


NOUNS = {  # (one, many), counted in the editor's language
    "actor": ("{0} actor", "{0} actors"),
    "enemy": ("{0} enemy", "{0} enemies"),
    "job": ("{0} job", "{0} jobs"),
    "gear": ("{0} piece of gear", "{0} pieces of gear"),
    "attachment": ("{0} attachment", "{0} attachments"),
    "passive": ("{0} passive", "{0} passives"),
    "skill": ("{0} skill", "{0} skills"),
    "node": ("{0} skill tree node", "{0} skill tree nodes"),
    "track": ("{0} rank reward", "{0} rank rewards"),
    "record": ("{0} record", "{0} records"),
    "rule": ("{0} rule", "{0} rules"),
    "property": ("{0} property", "{0} properties"),
}


def count(n, noun):
    one, many = NOUNS[noun]
    return t(one if n == 1 else many, n)


__all__ = [
    "Link",
    "NOUNS",
    "Usage",
    "UsageRow",
    "UsageSection",
    "count",
    "number",
    "t",
    "target_for",
]
