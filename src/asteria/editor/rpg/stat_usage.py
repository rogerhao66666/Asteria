"""Where a stat comes from and what reads it (D91, D95; a card since D108), for Game Systems ▸
Stats.

A stat's meaning is spread over the project: a stat formula works it out, gear adds to it, a
battle check turns it into a chance, a skill's damage multiplies it, a battle rule orders the
turns by it. ``stat_usage`` walks the project's data and returns a ``Usage`` card
(``usage_model``): a summary, the sources in the order the game adds them up (each kind of
source one row: how many, the range of their numbers, every record by name), what reads the
stat and where it is shown. A stat nobody reads says so ("Nothing reads it yet").

Every sentence is a template the editor's language table translates (``{0}`` the values).
"""

from __future__ import annotations

import re
from dataclasses import fields

from asteria.editor.rpg.usage_model import (
    Link,
    Usage,
    UsageRow,
    UsageSection,
    number,
    t,
    target_for,
)
from asteria.editor.ui.i18n import translate
from asteria.rpg.battle.session_rules import BattleSessionRules
from asteria.rpg.menus.pages import menu_pages
from asteria.rpg.text.data_text import words

# rules fields that name a stat, and what the engine does with it
RULE_FIELDS = {
    "initiative_stat": "Orders the turns (Battle Rules ▸ Turn Order Stat)",
    "penetration_stat": "Ignores that % of the target's defence (Battle Rules)",
    "lifesteal_stat": "Heals by that % of the damage dealt (Battle Extensions)",
    "opponent_stat": "Compared with the opponent's",
}
RULE_SHORT = {  # the same, said in the card's summary ("It changes the turn order")
    "initiative_stat": "the turn order",
    "penetration_stat": "how much defence hits ignore",
    "lifesteal_stat": "how much damage heals",
    "opponent_stat": "comparisons with the opponent",
}
SIDES = ("the user's", "the target's")
RESOURCE = "resource"  # an effect row's short: damage and healing change what is left


def _name(db, stat_id):
    """The stat's short name as the game writes it (STR, HP)."""
    record = getattr(db, "stat_definitions", {}).get(stat_id)
    if record is not None:
        return translate(record.short)
    rule = getattr(db, "derived_stats", {}).get(stat_id)
    if rule is not None and rule.display_name != stat_id:
        return translate(rule.display_name)
    return words(stat_id)


def _full_name(db, stat_id):
    """The stat's whole name (Strength), else its short one."""
    record = getattr(db, "stat_definitions", {}).get(stat_id)
    if record is not None and record.display_name:
        return translate(record.display_name)
    return _name(db, stat_id)


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
                found.append((None, t("Read by a formula ({0})", words(k))))
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


def _record_id(record):
    ids = [f.name for f in fields(record) if f.name.endswith("_id")]
    return str(getattr(record, ids[0])) if ids else ""


def _record(record):
    """A record's name for the reader (in the editor's language): its display name, else its
    id."""
    return translate(str(getattr(record, "display_name", "") or _record_id(record)))


def _where(*steps):
    """``Database ▸ Actors ▸ Base Stats``: the page an author opens, in the editor's words."""
    return " ▸ ".join(translate(step) for step in steps)


def _modifier(m):
    if m.operation == "add":
        return number(m.value, sign=True)
    if m.operation in ("multiply", "mul"):
        return f"×{m.value:g}"
    return f"{t(m.operation)} {m.value:g}"


def _per_record(table, name, stats, stat_id):
    """A link for every record of ``table`` (the database table ``name``) whose
    ``stats(record)`` gives the stat a number."""
    links = []
    for record in table.values():
        value = (stats(record) or {}).get(stat_id)
        if value:  # a 0 adds nothing
            target = target_for(name, _record_id(record))
            links.append(Link(_record(record), number(value, sign=True), float(value), target))
    return links


def _starting(table, name, stats, stat_id):
    """Like ``_per_record``, the numbers written as they are (a starting value: 32)."""
    return [
        Link(x.name, number(x.amount), x.amount, x.target)
        for x in _per_record(table, name, stats, stat_id)
    ]


def _changed_by(table, name, stat_id):
    """A link for every gear piece or passive whose stat changes touch the stat; its amount
    is what the "add" changes come to."""
    links = []
    for record in table.values():
        changes = [m for m in record.modifiers if m.stat == stat_id]
        if changes:
            added = [m.value for m in changes if m.operation == "add"]
            value = " ".join(_modifier(m) for m in changes)
            amount = float(sum(added)) if added else None
            links.append(
                Link(_record(record), value, amount, target_for(name, _record_id(record)))
            )
    return links


def _maxima(actor):
    """An actor's starting resources as ``{id: maximum}``."""
    return {k: raw["maximum"] for k, raw in actor.base_resources.items()}


def _milestones(db, stat_id):
    links = []
    for track in db.progression_tracks.values():
        for milestone in track.milestones:
            value = milestone.stat_bonuses.get(stat_id)
            if value:
                name = f"{_record(track)} {t('rank {0}', milestone.rank)}"
                target = target_for("progression_tracks", _record_id(track))
                links.append(Link(name, number(value, sign=True), float(value), target))
    return links


def _tree_nodes(db, stat_id):
    """A link for every skill tree node whose ranks give the stat (or add to the resource's
    maximum): ``Attributes ▸ STR`` ``+1 a rank, 30 ranks``, its amount the whole node."""
    links = []
    for graph in db.progression_graphs.values():
        for node in graph.nodes:
            gains = [
                r.stat_bonuses.get(stat_id, 0.0) + r.resource_bonuses.get(stat_id, 0.0)
                for r in node.rewards
            ]
            if not any(gains):
                continue
            if len(gains) == 1:
                value = number(gains[0], sign=True)
            elif len(set(gains)) == 1:
                value = t("{0} a rank, {1} ranks", number(gains[0], sign=True), len(gains))
            else:
                value = t("{0} over {1} ranks", number(sum(gains), sign=True), len(gains))
            name = f"{_record(graph)} ▸ {_record(node)}"
            target = target_for("progression_graphs", _record_id(graph))
            links.append(Link(name, value, float(sum(gains)), target))
    return links


def _sources(db, stat_id):
    """The rows in the order the game adds them up for a party member: what each is, the page
    that sets it and every record there with its number. A resource (HP, MP) is its maximum,
    set on the resource fields. Steps nothing sets are left out."""
    actors, classes = db.actors, db.classes
    rows = (
        UsageRow(
            t("Starting value of each actor"),
            _where("Database", "Actors", "Base Stats"),
            tuple(_starting(actors, "actors", lambda r: r.base_stats, stat_id)),
            "actor",
            short=t("the starting value"),
        ),
        UsageRow(
            t("Starting maximum of each actor"),
            _where("Database", "Actors", "HP, MP and other resources"),
            tuple(_starting(actors, "actors", _maxima, stat_id)),
            "actor",
            short=t("the starting value"),
        ),
        UsageRow(
            t("Given once by the job"),
            _where("Database", "Classes / Jobs", "Stat bonuses"),
            tuple(_per_record(classes, "classes", lambda r: r.stat_bonuses, stat_id)),
            "job",
            sign=True,
            short=t("the job"),
        ),
        UsageRow(
            t("Added to the maximum once by the job"),
            _where("Database", "Classes / Jobs", "Resource bonuses"),
            tuple(_per_record(classes, "classes", lambda r: r.resource_bonuses, stat_id)),
            "job",
            sign=True,
            short=t("the job"),
        ),
        UsageRow(
            t("Progression rank rewards"),
            _where("Database", "Progression Tracks"),
            tuple(_milestones(db, stat_id)),
            "track",
            sign=True,
            short=t("rank rewards"),
        ),
        UsageRow(
            t("Gained on every level up"),
            _where("Database", "Classes / Jobs", "Growth per level"),
            tuple(_per_record(classes, "classes", lambda r: r.level_growth, stat_id)),
            "job",
            sign=True,
            short=t("level ups"),
        ),
        UsageRow(
            t("Added to the maximum on every level up"),
            _where("Database", "Classes / Jobs", "Resource growth per level"),
            tuple(_per_record(classes, "classes", lambda r: r.resource_growth, stat_id)),
            "job",
            sign=True,
            short=t("level ups"),
        ),
        UsageRow(
            t("Skill tree points the player spends (whole node)"),
            _where("Database", "Skill Trees"),
            tuple(_tree_nodes(db, stat_id)),
            "node",
            sign=True,
            short=t("skill trees"),
        ),
        UsageRow(
            t("Worn equipment"),
            _where("Database", "Equipment", "Stat changes"),
            tuple(_changed_by(db.equipment, "equipment", stat_id)),
            "gear",
            sign=True,
            short=t("gear"),
        ),
        UsageRow(
            t("Attachments set in the equipment"),
            _where("Database", "Attachments", "Stat changes"),
            tuple(_changed_by(db.attachments, "attachments", stat_id)),
            "attachment",
            sign=True,
            short=t("attachments"),
        ),
        UsageRow(
            t("Learned passives"),
            _where("Database", "Passives", "Stat changes"),
            tuple(_changed_by(db.passives, "passives", stat_id)),
            "passive",
            sign=True,
            short=t("passives"),
        ),
    )
    found = [row for row in rows if row.links]
    rule = db.derived_stats.get(stat_id)
    if rule is not None:  # worked out last, from the stats above
        found.append(_formula_row(db, rule))
    return found


def _formula_row(db, rule):
    """The stat's own formula, worked out after everything above (D94)."""
    if rule.expression:
        what = rule.expression
    else:
        parts = [f"{c:g} × {_full_name(db, k)}" for k, c in rule.terms.items()]
        if rule.base or not parts:
            parts.insert(0, f"{rule.base:g}")
        what = " + ".join(parts)
    who = {"actors": "party members", "enemies": "enemies", "all": "everyone"}
    what = t("{0}, for {1}", what, t(who.get(rule.applies_to, rule.applies_to)))
    if rule.maximum:
        what += t(", at most {0}", f"{rule.maximum:g}")
    return UsageRow(
        t("Then its stat formula adds {0}", what),
        _where("Game Systems", "Stat Formulas", rule.display_name),
        short=t("its stat formula"),
        target=("game_system", "derived_stats", rule.stat_id),
    )


def _effects(project, db, data, stat_id):
    """Rows of what reads the stat: formulas, chance checks, battle rules, damage rules,
    states, skills."""
    name = _full_name(db, stat_id)
    rows = []
    for other in sorted(db.derived_stats.values(), key=lambda r: (r.order, r.stat_id)):
        where = _where("Game Systems", "Stat Formulas", other.display_name)
        target = ("game_system", "derived_stats", other.stat_id)
        changed = _full_name(db, other.stat_id)
        if other.expression and _mentions(other.expression, stat_id):
            what = t("{0} = {1}", changed, other.expression)
        elif stat_id in other.terms:
            amount = number(other.terms[stat_id], sign=True)
            what = t("{0} {1} for each point of {2}", changed, amount, name)
        else:
            continue
        rows.append(UsageRow(what, where, short=changed, target=target))
    for check in sorted(db.outcome_checks.values(), key=lambda c: c.check_id):
        where = _where("Battle", "Chance Checks", words(check.check_id))
        target = target_for("outcome_checks", check.check_id)
        chance = t("{0} chance", words(check.check_id))
        sides = ((SIDES[0], check.source_stat_terms), (SIDES[1], check.target_stat_terms))
        for side, terms in sides:
            if stat_id in (terms or {}):
                per = f"{terms[stat_id] * 100:+g}%"
                what = t("{0} {1} for each point of {2} {3}", chance, per, t(side), name)
                rows.append(UsageRow(what, where, short=chance, target=target))
        if check.chance_expression and _mentions(check.chance_expression, stat_id):
            what = t("{0} = {1}", chance, check.chance_expression)
            rows.append(UsageRow(what, where, short=chance, target=target))
    rules = []
    for record in db.battle_session_rules.values() or (BattleSessionRules("default"),):
        if record.initiative_stat == stat_id and not record.initiative_expression:
            rules.append((None, t(RULE_FIELDS["initiative_stat"])))
    tables = ("battle_session_rules", "battle_extension_rules", "battle_options", "reactions")
    for table in (*tables, "interaction_rules"):
        for record in data.get(table, ()):
            _terms(record, stat_id, rules)
    shorts = {t(v): t(RULE_SHORT[k]) for k, v in RULE_FIELDS.items()}
    for what in dict.fromkeys(what for _side, what in rules):
        rows.append(UsageRow(what, short=shorts.get(what, t("a formula"))))
    rows += _damage_rules(db, stat_id, name)
    for policy in sorted(db.battle_state_policies.values(), key=lambda p: p.state_id):
        per = (policy.target_stat_terms or {}).get(stat_id)
        if per:
            what = t(
                "Status {0} lands {1} for each point the target has",
                words(policy.state_id),
                f"{per * 100:+g}%",
            )
            target = target_for("battle_state_policies", policy.state_id)
            rows.append(
                UsageRow(
                    what,
                    _where("Battle", "Status Effects"),
                    target=target,
                    short=words(policy.state_id),
                )
            )
    rows += _other_terms(data, stat_id)
    rows += _skills(project, stat_id, name)
    if any(stat_id in a.base_resources for a in db.actors.values()):  # a pool: HP, MP (D99)
        what = t("Damage and healing change what is left of it; it never goes above this maximum")
        rows.insert(0, UsageRow(what, short=RESOURCE))
    return rows


def _skills(project, stat_id, name):
    """A row per side (the user's, the target's) of the skills whose formulas read the stat,
    each skill with how many times the stat counts (×18); other uses each a row."""
    rows, skills = [], {side: [] for side in SIDES}
    library = project.gameplay_library
    for ability_id in sorted(library.abilities.ids()):
        ability = library.abilities.get(ability_id)
        title = translate(getattr(ability, "display_name", "") or ability_id)
        target = target_for("lib.abilities", ability_id)
        terms = []
        _terms(ability.to_data(), stat_id, terms)
        for side, what in terms:
            if side is None:
                rows.append(UsageRow(f"{title}: {what}", short=title, target=target))
            elif all(link.name != title for link in skills[side]):
                skills[side].append(Link(title, f"×{abs(what):g}", abs(what), target))
    for side, links in skills.items():
        if links:
            what = t("Skill formulas use {0} {1}", t(side), name)
            where = _where("Database", "Abilities", "Formula")
            rows.append(
                UsageRow(what, where, tuple(links), "skill", mark="×", short=t("skill damage"))
            )
    return rows


TERM_TABLES_DONE = {  # tables the rows above word on their own; the rest: ``_other_terms``
    "derived_stats", "outcome_checks", "interaction_rules", "battle_state_policies",
    "actors", "enemies", "classes", "equipment", "attachments", "passives",
}  # fmt: skip


def _damage_rules(db, stat_id, name):
    """Damage rules (a hit's value) whose multiplier or amount grows with the stat."""
    rows = []
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
            when += [t("target {0}", x) for x in (*rule.target_tags_all, *rule.target_tags_any)]
            if multiplies:
                what = t(
                    "Damage × ({0} {1} for each point of {2} {3})",
                    f"{rule.multiplier:g}",
                    f"{per:+g}",
                    t(side),
                    name,
                )
            else:
                what = t("Damage {0} for each point of {1} {2}", f"{per:+g}", t(side), name)
            what += t(", when {0}", ", ".join(when)) if when else t(", on every hit")
            target = target_for("interaction_rules", rule.rule_id)
            rows.append(
                UsageRow(
                    what,
                    _where("Battle", "Damage Interactions", words(rule.rule_id)),
                    short=t("damage"),
                    target=target,
                )
            )
    return rows


def _other_terms(data, stat_id):
    """Any other record with a ``…terms`` map naming the stat (D91: nothing goes unlisted)."""
    rows = []
    for table, records in data.items():
        if table in TERM_TABLES_DONE or not isinstance(records, list):
            continue
        for record in records:
            keys = []
            _term_keys(record, stat_id, keys)
            if keys:
                record_id = next((v for k, v in record.items() if k.endswith("_id")), "")
                name = translate(record.get("display_name") or record_id)
                what = t(
                    "{0} {1} reads it ({2})", words(table), name, ", ".join(dict.fromkeys(keys))
                )
                rows.append(
                    UsageRow(what, short=words(table), target=target_for(table, record_id))
                )
    return rows


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


def _shown(db, stat_id):
    rows = []
    for page in menu_pages(db).values():  # D96: a menu page's detail tables
        target = ("game_system", "menu_pages", page.page_id)
        for block in page.blocks:
            if stat_id in block.stat_rows:
                rows.append(
                    UsageRow(
                        t("{0} page: the stat table", translate(page.display_name)), target=target
                    )
                )
            groups = [ln.group or "other" for ln in block.stat_lines if ln.stat_id == stat_id]
            if groups:
                what = t(
                    "{0} page: details ({1})", translate(page.display_name), ", ".join(groups)
                )
                rows.append(UsageRow(what, target=target))
    return list({row.what: row for row in rows}.values())


def _and(items):
    """``a, b and c`` in the editor's language."""
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return t("{0} and {1}", translate(", ").join(items[:-1]), items[-1])


def _summary(name, sources, effects):
    """Two sentences: what adds up to it, then what it changes (the numbers are in the rows
    below)."""
    added = list(dict.fromkeys(row.short for row in sources))
    if added:
        lines = [t("{0} comes from {1}.", name, _and(added))]
    else:
        lines = [t("Nothing sets {0} yet.", name)]
    if any(row.short == RESOURCE for row in effects):
        lines.append(t("Damage and healing change what is left of it."))
    changed = [x for x in dict.fromkeys(row.short for row in effects) if x and x != RESOURCE]
    if changed:
        lines.append(t("It changes {0}.", _and(changed)))
    elif len(lines) == 1:
        lines.append(t("Nothing reads it yet."))
    return tuple(lines)


def stat_usage(project, stat_id):
    """The ``Usage`` card of ``stat_id``: a summary, where its number comes from (in the order
    the game adds it up), what it changes, and where it is shown."""
    db = project.rpg_database
    stat_id = str(stat_id)
    data = db.to_data()
    name = _full_name(db, stat_id)
    sources = _sources(db, stat_id)
    enemies = _starting(db.enemies, "enemies", lambda r: r.stats, stat_id)
    effects = _effects(project, db, data, stat_id)
    sections = [
        UsageSection(
            t("Where {0} comes from (added up in this order)", name),
            tuple(sources),
            t("Nothing sets it yet."),
            numbered=True,
        )
    ]
    if enemies:
        row = UsageRow(
            t("Each enemy's own number"),
            _where("Database", "Enemies / Bosses", "Stats"),
            tuple(enemies),
            "enemy",
        )
        sections.append(UsageSection(t("Enemies"), (row,)))
    sections.append(
        UsageSection(t("What {0} changes", name), tuple(effects), t("Nothing reads it yet."))
    )
    shown = _shown(db, stat_id)
    if shown:
        sections.append(UsageSection(t("Where {0} is shown", name), tuple(shown)))
    return Usage(_summary(name, sources, effects), tuple(sections))


__all__ = ["RULE_FIELDS", "stat_usage"]
