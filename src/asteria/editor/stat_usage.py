"""Where a stat comes from and what reads it (D91), for Game Systems ▸ Stats.

A stat's meaning is spread over the project: a stat formula works it out, gear adds to it, a
battle check turns it into a chance, a skill's damage multiplies it, a battle rule orders the
turns by it. ``stat_usage`` walks the project's data and writes all of that down, so a stat
nobody reads shows as such ("nothing reads it yet").

Every sentence is a template the editor's language table translates (``{0}`` the values).
"""

from __future__ import annotations

import re
from dataclasses import fields
from html import escape

from asteria.rpg.battle_session_rules import BattleSessionRules
from asteria.rpg.data_text import words
from asteria.rpg.menu_pages import menu_pages

from .i18n import translate

# rules fields that name a stat, and what the engine does with it
RULE_FIELDS = {
    "initiative_stat": "Battle Rules: orders the turns (Turn Order Stat)",
    "penetration_stat": "Battle Rules: ignores that % of the target's stats in damage",
    "lifesteal_stat": "Battle Extensions: heals by that % of the damage dealt",
    "opponent_stat": "compared with the opponent's",
}
NOUNS = {  # (one, many)
    "actor": ("{0} actor", "{0} actors"),
    "enemy": ("{0} enemy", "{0} enemies"),
    "job": ("{0} job", "{0} jobs"),
    "gear": ("{0} piece of gear", "{0} pieces of gear"),
    "passive": ("{0} passive", "{0} passives"),
    "skill": ("{0} skill", "{0} skills"),
}
SIDES = ("the user's", "the target's")


def t(template, *values):
    """``template`` in the editor's language, ``{0}``... filled in."""
    return translate(template).format(*values)


def _count(n, noun):
    one, many = NOUNS[noun]
    return t(one if n == 1 else many, n)


def _name(db, stat_id):
    record = getattr(db, "stat_definitions", {}).get(stat_id)
    if record is not None:
        return record.short
    rule = getattr(db, "derived_stats", {}).get(stat_id)
    if rule is not None and rule.display_name != stat_id:
        return rule.display_name
    return words(stat_id)


def _terms(value, stat_id, found):
    """``(side or None, coefficient or words)`` for every formula term (``{"source":
    "source_stat", "key": id, "coefficient": c}``) and rules field naming ``stat_id`` inside
    ``value``."""
    if isinstance(value, dict):
        if value.get("key") == stat_id and value.get("source") in ("source_stat", "target_stat"):
            side = SIDES[0] if value["source"] == "source_stat" else SIDES[1]
            found.append((side, float(value.get("coefficient", 1.0))))
        for k, v in value.items():
            if isinstance(v, str) and v == stat_id and k in RULE_FIELDS:
                found.append((None, t(RULE_FIELDS[k])))
            elif isinstance(v, str) and k.endswith("expression") and _mentions(v, stat_id):
                found.append((None, t("an expression ({0})", words(k))))
            else:
                _terms(v, stat_id, found)
    elif isinstance(value, list):
        for v in value:
            _terms(v, stat_id, found)


def _mentions(text, stat_id):
    """Whether a formula reads ``stat_id`` (``source.dex``, ``self.current("hp")``), or names it
    as a word."""
    from asteria.gameplay.expressions import ExpressionError, variables

    try:
        stats, resources = variables(text)
    except ExpressionError:
        stats, resources = (), ()
    if stat_id in stats or stat_id in resources:
        return True
    pattern = rf"(?<![\w.]){re.escape(stat_id)}(?!\w)|['\"]{re.escape(stat_id)}['\"]"
    return re.search(pattern, text) is not None


def _number(value, sign=""):
    text = f"{value:g}"
    return f"+{text}" if sign and value >= 0 else text


def _record(record):
    """A record's name for the reader: its display name, else its id."""
    if getattr(record, "display_name", ""):
        return str(record.display_name)
    ids = [f.name for f in fields(record) if f.name.endswith("_id")]
    return str(getattr(record, ids[0])) if ids else ""


def _listed(items):
    """``Roger 21, Mira 1`` - every record, in the editor's list separator."""
    return translate(", ").join(items)


def _where(*steps):
    """``Database ▸ Actors ▸ Base Stats``: the page an author opens, in the editor's words."""
    return " ▸ ".join(translate(step) for step in steps)


def _modifier(m):
    if m.operation == "add":
        return _number(m.value, "+")
    if m.operation in ("multiply", "mul"):
        return f"×{m.value:g}"
    return f"{t(m.operation)} {m.value:g}"


def _per_record(table, stats, stat_id, sign=""):
    """``Name value`` for every record of ``table`` whose ``stats(record)`` names the stat."""
    items = []
    for record in table.values():
        value = (stats(record) or {}).get(stat_id)
        if value is not None:
            items.append(f"{_record(record)} {_number(value, sign)}")
    return items


def _changed_by(table, stat_id):
    """``Name +10`` for every gear piece or passive whose stat changes touch the stat."""
    items = []
    for record in table.values():
        changes = [_modifier(m) for m in record.modifiers if m.stat == stat_id]
        if changes:
            items.append(f"{_record(record)} {' '.join(changes)}")
    return items


def _maxima(actor):
    """An actor's starting resources as ``{id: maximum}``."""
    return {k: raw["maximum"] for k, raw in actor.base_resources.items()}


def _milestones(db, stat_id):
    items = []
    for track in db.progression_tracks.values():
        for milestone in track.milestones:
            value = milestone.stat_bonuses.get(stat_id)
            if value:
                rank = t("rank {0}", milestone.rank)
                items.append(f"{_record(track)} {rank} {_number(value, '+')}")
    return items


def _tree_nodes(db, stat_id):
    """``Attributes ▸ STR: +1 a rank, up to 30 ranks`` for every skill tree node
    whose ranks give the stat (or add to the resource's maximum)."""
    items = []
    for graph in db.progression_graphs.values():
        for node in graph.nodes:
            gains = [
                r.stat_bonuses.get(stat_id, 0.0) + r.resource_bonuses.get(stat_id, 0.0)
                for r in node.rewards
            ]
            if not any(gains):
                continue
            name = f"{_record(graph)} ▸ {_record(node)}"
            if len(gains) == 1:
                what = t("{0} (one rank)", _number(gains[0], "+"))
            elif len(set(gains)) == 1:
                what = t("{0} a rank, up to {1} ranks", _number(gains[0], "+"), len(gains))
            else:
                what = t("{0} over {1} ranks", _number(sum(gains), "+"), len(gains))
            items.append(f"{name}: {what}")
    return items


def _sources(db, data, stat_id):
    """``(step, where, items)`` in the order the game adds them up for a party member: what it
    is, the page that sets it (Database ▸ Actors ▸ Base Stats) and every record there with its
    number. A resource (HP, MP) is its maximum, set on the resource fields. Steps nothing sets
    are left out."""
    steps = (
        (
            "Starting value of the actor",
            ("Database", "Actors", "Base Stats"),
            _per_record(db.actors, lambda r: r.base_stats, stat_id),
        ),
        (
            "Starting maximum of the actor",
            ("Database", "Actors", "HP, MP and other resources"),
            _per_record(db.actors, _maxima, stat_id),
        ),
        (
            "Given once by the job",
            ("Database", "Classes / Jobs", "Stat bonuses"),
            _per_record(db.classes, lambda r: r.stat_bonuses, stat_id, "+"),
        ),
        (
            "Added to the maximum once by the job",
            ("Database", "Classes / Jobs", "Resource bonuses"),
            _per_record(db.classes, lambda r: r.resource_bonuses, stat_id, "+"),
        ),
        (
            "Progression ranks",
            ("Database", "Progression Tracks"),
            _milestones(db, stat_id),
        ),
        (
            "Gained every level after the first (× level − 1)",
            ("Database", "Classes / Jobs", "Growth per level"),
            _per_record(db.classes, lambda r: r.level_growth, stat_id, "+"),
        ),
        (
            "Added to the maximum every level after the first (× level − 1)",
            ("Database", "Classes / Jobs", "Resource growth per level"),
            _per_record(db.classes, lambda r: r.resource_growth, stat_id, "+"),
        ),
        (
            "Points the player spends (skill tree ranks)",
            ("Database", "Skill Trees"),
            _tree_nodes(db, stat_id),
        ),
        (
            "Worn equipment",
            ("Database", "Equipment", "Stat changes"),
            _changed_by(db.equipment, stat_id),
        ),
        (
            "Attachments set in the equipment",
            ("Database", "Attachments", "Stat changes"),
            _changed_by(db.attachments, stat_id),
        ),
        (
            "Learned passives",
            ("Database", "Passives", "Stat changes"),
            _changed_by(db.passives, stat_id),
        ),
    )
    found = [(t(step), _where(*where), items) for step, where, items in steps if items]
    rule = db.derived_stats.get(stat_id)
    if rule is not None:  # worked out last, from the stats above
        if rule.expression:  # written as a formula (D94)
            what = rule.expression
        else:
            parts = [f"{c:g} × {_name(db, k)}" for k, c in rule.terms.items()]
            if rule.base or not parts:
                parts.insert(0, f"{rule.base:g}")
            what = " + ".join(parts)
        what = t("+ {0} (for {1})", what, t(rule.applies_to))
        if rule.maximum:
            what += t(", at most {0}", f"{rule.maximum:g}")
        where = _where("Game Systems", "Stat Formulas", rule.display_name)
        found.append((t("Its stat formula, worked out last"), where, [what]))
    return found


def _enemy_sources(db, stat_id):
    return _per_record(db.enemies, lambda r: r.stats, stat_id)


def _effects(project, db, data, stat_id):
    found = []
    for other in sorted(db.derived_stats.values(), key=lambda r: (r.order, r.stat_id)):
        where = _where("Game Systems", "Stat Formulas", other.display_name)
        if other.expression and _mentions(other.expression, stat_id):
            what = t("{0} = {1}", _name(db, other.stat_id), other.expression)
            found.append(f"{what}  ({where})")
        elif stat_id in other.terms:
            amount = f"{other.terms[stat_id]:+g}"
            what = t("{0} {1} for each point of {2}", _name(db, other.stat_id), amount,
                     _name(db, stat_id))  # fmt: skip
            found.append(f"{what}  ({where})")
    for check in sorted(db.outcome_checks.values(), key=lambda c: c.check_id):
        where = _where("Battle Rules", "Chance Checks", words(check.check_id))
        sides = ((SIDES[0], check.source_stat_terms), (SIDES[1], check.target_stat_terms))
        for side, terms in sides:
            if stat_id in (terms or {}):
                per = f"{terms[stat_id] * 100:+g}%"
                what = t("{0} chance {1} for each point of {2}", words(check.check_id), per,
                         t(side))  # fmt: skip
                found.append(f"{what}  ({where})")
        if check.chance_expression and _mentions(check.chance_expression, stat_id):
            what = t("{0} chance = {1}", words(check.check_id), check.chance_expression)
            found.append(f"{what}  ({where})")
    rules = []
    for record in db.battle_session_rules.values() or (BattleSessionRules("default"),):
        if record.initiative_stat == stat_id and not record.initiative_expression:
            rules.append((None, t(RULE_FIELDS["initiative_stat"])))
    tables = ("battle_session_rules", "battle_extension_rules", "battle_options", "reactions")
    for table in (*tables, "interaction_rules"):
        for record in data.get(table, ()):
            _terms(record, stat_id, rules)
    found += list(dict.fromkeys(what for _side, what in rules))
    found += _damage_rules(db, stat_id)
    for policy in sorted(db.battle_state_policies.values(), key=lambda p: p.state_id):
        per = (policy.target_stat_terms or {}).get(stat_id)
        if per:
            found.append(t("State {0} lands {1} per point of the target", policy.state_id,
                           f"{per * 100:+g}%"))  # fmt: skip
    found += _other_terms(data, stat_id)
    skills = {side: [] for side in SIDES}
    library = project.gameplay_library
    for ability_id in sorted(library.abilities.ids()):
        ability = library.abilities.get(ability_id)
        name = getattr(ability, "display_name", "") or ability_id
        terms = []
        _terms(ability.to_data(), stat_id, terms)
        for side, what in terms:
            if side is None:
                found.append(f"{name}: {what}")
            else:
                skills[side].append(f"{name} {abs(what):g}x")
    for side, uses in skills.items():
        uses = list(dict.fromkeys(uses))
        if uses:
            more = t(" and {0} more", len(uses) - 6) if len(uses) > 6 else ""
            listed = ", ".join(uses[:6]) + more
            found.append(t("{0} read {1} in their formulas: {2}", _count(len(uses), "skill"),
                           t(side), listed))  # fmt: skip
    return found


TERM_TABLES_DONE = {  # tables the lines above word on their own; the rest: ``_other_terms``
    "derived_stats", "outcome_checks", "interaction_rules", "battle_state_policies",
    "actors", "enemies", "classes", "equipment", "attachments", "passives",
}  # fmt: skip


def _damage_rules(db, stat_id):
    """Interaction rules (a hit's value) whose multiplier or amount grows with the stat."""
    found = []
    for rule in sorted(db.interaction_rules.values(), key=lambda r: r.rule_id):
        maps = (
            (SIDES[0], rule.multiplier_source_terms, True),
            (SIDES[1], rule.multiplier_target_terms, True),
            (SIDES[0], rule.source_stat_terms, False),
            (SIDES[1], rule.target_stat_terms, False),
        )
        for side, terms, multiplies in maps:
            per = (terms or {}).get(stat_id)
            if not per:
                continue
            when = [*rule.source_tags_all, *rule.source_tags_any]
            when += [f"target {x}" for x in (*rule.target_tags_all, *rule.target_tags_any)]
            condition = t(" when {0}", ", ".join(when)) if when else t(" on every hit")
            if multiplies:
                change = f"x({rule.multiplier:g} {per:+g} x {t(side)})"
            else:
                change = f"{per:+g} x {t(side)}"
            found.append(t("Damage rule {0}: {1}{2}", rule.rule_id, change, condition))
    return found


def _other_terms(data, stat_id):
    """Any other record with a ``…terms`` map naming the stat (D91: nothing goes unlisted)."""
    found = []
    for table, records in data.items():
        if table in TERM_TABLES_DONE or not isinstance(records, list):
            continue
        for record in records:
            keys = []
            _term_keys(record, stat_id, keys)
            if keys:
                name = next((v for k, v in record.items() if k.endswith("_id")), "")
                found.append(f"{words(table)} {name}: {', '.join(dict.fromkeys(keys))}")
    return found


def _term_keys(value, stat_id, keys):
    if isinstance(value, dict):
        for k, v in value.items():
            if "terms" in k and isinstance(v, dict) and stat_id in v:
                keys.append(words(k))
            else:
                _term_keys(v, stat_id, keys)
    elif isinstance(value, list):
        for v in value:
            _term_keys(v, stat_id, keys)


def _section(heading, lines):
    """A bold heading and its lines, one bullet each (rich text for the info box)."""
    body = "".join(f"<br>&nbsp;&nbsp;•&nbsp;{escape(line)}" for line in lines)
    return f"<b>{escape(heading)}</b>{body}"


def _source_section(name, steps, enemies):
    """Where the number comes from, step by step: what each step is, the page to open and every
    record there with its number."""
    out = [f"<b>{escape(t('Where {0} comes from', name))}</b>"]
    if steps:
        out.append(escape(t("A party member's {0} is these added up, in this order:", name)))
        for number, (step, where, items) in enumerate(steps, 1):
            out.append(f"<b>{number}. {escape(step)}</b> &nbsp;({escape(where)})")
            out += [f"&nbsp;&nbsp;&nbsp;&nbsp;{escape(item)}" for item in items]
    if enemies:
        where = _where("Database", "Enemies / Bosses", "Stats")
        out.append(f"<b>{escape(t('Enemies use their own number'))}</b> &nbsp;({escape(where)})")
        out.append(f"&nbsp;&nbsp;&nbsp;&nbsp;{escape(_listed(enemies))}")
    if not steps and not enemies:
        out.append(escape(t("Nothing sets it yet.")))
    return "<br>".join(out)


def stat_usage(project, stat_id):
    """Rich text in three parts - where ``stat_id``'s number comes from (step by step, every
    record with its number), what it changes and where it is shown - each line naming the
    page an author opens."""
    db = project.rpg_database
    stat_id = str(stat_id)
    data = db.to_data()
    name = _name(db, stat_id)
    steps = [
        (step, where, items if ": " in items[0] else [_listed(items)])  # a node a line
        for step, where, items in _sources(db, data, stat_id)
    ]
    effect = _effects(project, db, data, stat_id)
    shown = []
    for page in menu_pages(db).values():  # D96: a menu page's detail tables
        page_name = page.display_name  # not ``name``: that is the stat's, used below
        for block in page.blocks:
            if stat_id in block.stat_rows:
                shown.append(t("Menu page {0}: the detail table", page_name))
            groups = [ln.group or "other" for ln in block.stat_lines if ln.stat_id == stat_id]
            if groups:
                shown.append(t("Menu page {0}: details ({1})", page_name, ", ".join(groups)))
    parts = [
        _source_section(name, steps, _enemy_sources(db, stat_id)),
        _section(t("What {0} changes", name), effect or [t("Nothing reads it yet.")]),
    ]
    if shown:
        parts.append(_section(t("Where {0} is shown", name), list(dict.fromkeys(shown))))
    return "<br><br>".join(parts)


__all__ = ["RULE_FIELDS", "stat_usage"]
