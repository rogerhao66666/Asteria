"""Where a stat comes from and what reads it (D91), for Game Systems ▸ Stats.

A stat's meaning is spread over the project: a stat formula works it out, gear adds to it, a
battle check turns it into a chance, a skill's damage multiplies it, a battle rule orders the
turns by it. ``stat_usage`` walks the project's data and writes all of that down, so a stat
nobody reads shows as such ("nothing reads it yet").

Every sentence is a template the editor's language table translates (``{0}`` the values).
"""

from __future__ import annotations

import re

from asteria.rpg.battle_session_rules import BattleSessionRules
from asteria.rpg.data_text import words

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
    pattern = rf"(?<![\w.]){re.escape(stat_id)}(?!\w)|['\"]{re.escape(stat_id)}['\"]"
    return re.search(pattern, text) is not None


def _sources(db, data, stat_id):
    found = []
    rule = db.derived_stats.get(stat_id)
    if rule is not None:
        parts = [f"{c:g} x {_name(db, k)}" for k, c in rule.terms.items()]
        if rule.base or not parts:
            parts.insert(0, f"{rule.base:g}")
        found.append(t("Stat Formulas: + {0} (for {1})", " + ".join(parts), t(rule.applies_to)))
        if rule.maximum:
            found.append(t("at most {0}", f"{rule.maximum:g}"))
    places = (
        ("actors", "actor", lambda r: r.base_stats),
        ("enemies", "enemy", lambda r: r.stats),
        ("classes", "job", lambda r: {**r.stat_bonuses, **r.level_growth}),
    )
    for table, noun, stats in places:
        n = sum(1 for r in getattr(db, table).values() if stat_id in (stats(r) or {}))
        if n:
            found.append(t("Base Stats of {0}", _count(n, noun)))
    gear = (*db.equipment.values(), *db.attachments.values())
    n = sum(1 for r in gear if any(m.stat == stat_id for m in r.modifiers))
    if n:
        found.append(t("added by {0}", _count(n, "gear")))
    n = sum(1 for p in data.get("passives", ()) if stat_id in str(p))
    if n:
        found.append(t("changed by {0}", _count(n, "passive")))
    return found


def _effects(project, db, data, stat_id):
    found = []
    for other in sorted(db.derived_stats.values(), key=lambda r: (r.order, r.stat_id)):
        if stat_id in other.terms:
            amount = f"{other.terms[stat_id]:+g}"
            found.append(t("{0} {1} per point (Stat Formulas)", _name(db, other.stat_id), amount))
    for check in sorted(db.outcome_checks.values(), key=lambda c: c.check_id):
        sides = ((SIDES[0], check.source_stat_terms), (SIDES[1], check.target_stat_terms))
        for side, terms in sides:
            if stat_id in (terms or {}):
                per = f"{terms[stat_id] * 100:+g}%"
                found.append(t("{0} chance {1} per point of {2}", words(check.check_id), per,
                               t(side)))  # fmt: skip
        if check.chance_expression and _mentions(check.chance_expression, stat_id):
            found.append(t("{0} chance (its expression)", words(check.check_id)))
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


def stat_usage(project, stat_id):
    """Lines of words: where ``stat_id`` comes from, what reads it and where it is shown."""
    db = project.rpg_database
    stat_id = str(stat_id)
    data = db.to_data()
    source = _sources(db, data, stat_id)
    effect = _effects(project, db, data, stat_id)
    shown = []
    for menu in db.menu_rules.values():
        if stat_id in menu.stat_rows:
            shown.append(t("Status page: the stat table"))
        groups = [ln.group or "other" for ln in menu.stat_lines if ln.stat_id == stat_id]
        if groups:
            shown.append(t("Status page: details ({0})", ", ".join(groups)))
    lines = [t("Comes from: {0}", "; ".join(source) if source else t("nothing sets it yet"))]
    if effect:
        lines.append(t("What it does:"))
        lines += [f"  • {line}" for line in effect]
    else:
        lines.append(t("What it does: nothing reads it yet"))
    if shown:
        lines.append(t("Shown on: {0}", "; ".join(dict.fromkeys(shown))))
    return "\n".join(lines)


__all__ = ["RULE_FIELDS", "stat_usage"]
