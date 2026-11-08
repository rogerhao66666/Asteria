"""What reads every stat and carries every property, found in one walk of the project (D108).

A Usage card (``stat_usage``, ``tag_usage``) used to walk the whole project for the one stat or
property it shows: every skill's formulas, every rule table, every record's tags. The index
walks it once and keeps, for each stat and each property, the records that name it; a card then
looks its own up. It holds ids, raw names and field keys only (no editor words), so a language
switch needs no new index.

``usage_index(project, stamp)`` keeps the last one while ``stamp`` (the document's revision:
every edit, undo and authoring script changes it) and the project stay the same; without a
stamp it is built fresh (a test, a project changed outside the editor's commands).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from asteria.rpg.text.data_text import words

# rules fields that name a stat (the card's words are ``stat_usage.RULE_FIELDS``)
RULE_KEYS = ("initiative_stat", "penetration_stat", "lifesteal_stat", "opponent_stat")
RULE_TABLES = (  # read for rules fields, formula terms and formulas naming a stat
    "battle_session_rules", "battle_extension_rules", "battle_options", "reactions",
    "interaction_rules",
)  # fmt: skip
TERM_TABLES_DONE = {  # tables the stat card words on its own; the rest: ``other``
    "derived_stats", "outcome_checks", "interaction_rules", "battle_state_policies",
    "actors", "enemies", "classes", "equipment", "attachments", "passives",
}  # fmt: skip
_WORD = re.compile(r"(?<![\w.])([A-Za-z_]\w*)")
_QUOTED = re.compile(r"['\"](\w+)['\"]")


def named_in(text):
    """Every stat a formula may read: its variables (``source.dex``, ``self.current("hp")``)
    and every word or quoted name in it."""
    from asteria.gameplay.expressions import ExpressionError, variables

    try:
        stats, resources = variables(text)
    except ExpressionError:
        stats, resources = (), ()
    return {*stats, *resources, *_WORD.findall(text), *_QUOTED.findall(text)}


def scan(value, found):
    """``found[stat]`` gains, in the order they stand, ``("term", side, coefficient)`` for a
    formula term (``side`` 0 the user's, 1 the target's), ``("rule", key)`` for a rules field
    naming the stat and ``("formula", key)`` for a formula reading it."""
    if isinstance(value, dict):
        source = value.get("source")
        if source in ("source_stat", "target_stat") and isinstance(value.get("key"), str):
            side = 0 if source == "source_stat" else 1
            coefficient = float(value.get("coefficient", 1.0))
            found.setdefault(value["key"], []).append(("term", side, coefficient))
        for k, v in value.items():
            if isinstance(v, str) and k in RULE_KEYS:
                found.setdefault(v, []).append(("rule", k))
            elif isinstance(v, str) and k.endswith("expression"):
                for stat in named_in(v):
                    found.setdefault(stat, []).append(("formula", k))
            else:
                scan(v, found)
    elif isinstance(value, list):
        for v in value:
            scan(v, found)


def _term_keys(value, found):
    """``found[stat]`` gains the words of every ``…terms`` map naming it."""
    if isinstance(value, dict):
        for k, v in value.items():
            if "terms" in k and isinstance(v, dict):
                for stat in v:
                    found.setdefault(stat, []).append(words(k))
            else:
                _term_keys(v, found)
    elif isinstance(value, list):
        for v in value:
            _term_keys(v, found)


@dataclass
class UsageIndex:
    """``tags``: ``project_tags``; ``rules[stat]``: the facts (``scan``) of the rule tables;
    ``skills[stat]``: ``(ability_id, name, fact)`` by ability id; ``other[stat]``: ``(table,
    record_id, name, term words)`` of the remaining tables."""

    tags: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    skills: dict = field(default_factory=dict)
    other: dict = field(default_factory=dict)

    @classmethod
    def build(cls, project):
        from asteria.editor.rpg.tag_usage import project_tags

        data = project.rpg_database.to_data()
        library = project.gameplay_library
        index = cls(tags=project_tags(project, (data, library.to_data())))
        for table in RULE_TABLES:
            for record in data.get(table, ()):
                scan(record, index.rules)
        for ability_id in sorted(library.abilities.ids()):
            ability = library.abilities.get(ability_id)
            found = {}
            scan(ability.to_data(), found)
            name = getattr(ability, "display_name", "") or ability_id
            for stat, facts in found.items():
                index.skills.setdefault(stat, []).extend((ability_id, name, x) for x in facts)
        for table, records in data.items():
            if table in TERM_TABLES_DONE or not isinstance(records, list):
                continue
            for record in records:
                found = {}
                _term_keys(record, found)
                if not found:
                    continue
                rid = next((v for k, v in record.items() if k.endswith("_id")), "")
                name = record.get("display_name") or rid
                for stat, keys in found.items():
                    index.other.setdefault(stat, []).append((table, rid, name, keys))
        return index


_last = {}  # "entry": (project, stamp, index) - the one kept


def usage_index(project, stamp=None):
    """The project's index: the kept one while ``project`` and ``stamp`` are the same, else
    built (and kept when there is a stamp)."""
    kept = _last.get("entry")
    if stamp is not None and kept is not None and kept[0] is project and kept[1] == stamp:
        return kept[2]
    index = UsageIndex.build(project)
    if stamp is not None:
        _last["entry"] = (project, stamp, index)
    return index


__all__ = ["RULE_KEYS", "TERM_TABLES_DONE", "UsageIndex", "named_in", "scan", "usage_index"]
