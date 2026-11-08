"""Who carries a property (a tag) and what reads it (D91; a card since D108), for Game Systems ▸
Properties.

A tag means nothing on its own: a record carries it (gear's ``tags``, a job's ``granted_tags``,
a state's ``contributed_tags``) and a rule reads it (a damage rule's ``target_tags_all``, gear's
``required_capabilities``). ``tag_usage`` walks the project and returns a ``Usage`` card
(``usage_model``): what the engine itself does with the tag (``rpg.tag_definitions.BUILT_IN``),
then a row per table and field, in plain words ("Equipment: has it", "Damage interactions: when
the target has it"), with every record by name to open. A family (``rune.*``) covers every tag
it starts.

``project_tags`` gives every tag the project names, for the Problems list.
"""

from __future__ import annotations

from asteria.editor.rpg.usage_model import (
    Link,
    Usage,
    UsageRow,
    UsageSection,
    count,
    t,
    target_for,
)
from asteria.editor.ui.i18n import translate
from asteria.rpg.data.tag_definitions import built_in
from asteria.rpg.text.data_text import words

# what a field does with the tags it lists, in the card's words; fields a record carries its
# tags in first, then the fields that read them (any other field naming tags reads them too)
CARRY = {
    "tags": "has it",
    "granted_tags": "gives it to its owner",
    "contributed_tags": "adds it while it lasts",
    "outcome_tags": "marks the hit's result with it",
    "success_tags": "marks a success with it",
    "failure_tags": "marks a failure with it",
    "equipment_tags": "gives it to the gear",
}
READS = {
    "category": "its tab or category holds what has it",
    "accepted_tags": "accepts what has it",
    "allowed_tags": "allows what has it",
    "required_tags": "needs it",
    "blocked_tags": "is blocked by it",
    "exempt_tags": "leaves out what has it",
    "immune_tags": "has no effect on what has it",
    "reactor_tags": "reacts when the one hit has it",
    "source_tags_all": "when the user has it (with the others listed)",
    "source_tags_any": "when the user has it (or one of the others listed)",
    "required_source_tags": "only when the user has it",
    "blocked_source_tags": "not when the user has it",
    "target_tags_all": "when the target has it (with the others listed)",
    "target_tags_any": "when the target has it (or one of the others listed)",
    "required_target_tags": "only on a target that has it",
    "blocked_target_tags": "not on a target that has it",
    "immune_target_tags": "a target that has it is immune",
    "allowed_ability_tags": "allows skills that have it",
    "blocked_ability_tags": "blocks skills that have it",
    "required_outcome_tags_all": "when the hit's result has it",
    "required_capabilities": "needs the capability",
    "any_capabilities": "needs this or another capability listed",
    "granted_capabilities": "gives the capability",
}


def _reads(key):
    key = key.lower()
    return key not in CARRY and ("tag" in key or "capabilit" in key)


def _walk(value, key, record, found, groups=False):
    """``found[tag]`` gains ``(carries, field, *record)`` for every tag under ``value``;
    ``groups``: inside a menu or workstation category or filter, whose tags pick what it
    holds (they read the tags)."""
    if isinstance(value, dict):
        groups = groups or "category_id" in value or "filter_id" in value
        for k, v in value.items():
            _walk(v, k, record, found, groups)
    elif isinstance(value, list):
        carries = key in CARRY and not groups
        for v in value:
            if isinstance(v, str) and (key in CARRY or _reads(key)):
                field = "category" if groups and key in CARRY else key
                found.setdefault(v.lower(), []).append((carries, field, *record))
            else:
                _walk(v, key, record, found, groups)


def _record(table, record):
    """``(table, record id, name)``: the name the record shows, else its id."""
    rid = next((v for k, v in record.items() if k.endswith("_id") and isinstance(v, str)), "")
    name = record.get("display_name") or record.get("name") or rid
    return table, rid, translate(name) if isinstance(name, str) and name else rid


def project_tags(project, data=None):
    """``{tag: [(carries, field, table, record_id, name), ...]}`` over the whole project
    (``table``: ``lib.abilities`` for the gameplay library's).

    ``data``: the ``(rpg_database.to_data(), gameplay_library.to_data())`` pair when the caller
    has already serialised them."""
    found = {}
    rpg_data, library_data = data if data is not None else _project_data(project)
    tables = dict(rpg_data)
    tables.update({f"lib.{k}": v for k, v in library_data.items()})
    for table, records in tables.items():
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict):
                _walk(record, "", _record(table, record), found)
    return found


def _project_data(project):
    return project.rpg_database.to_data(), project.gameplay_library.to_data()


def _rows(uses, meanings):
    """A row per table and field: "Equipment: has it", every record by name."""
    grouped = {}
    for _carries, field, table, rid, name in uses:
        grouped.setdefault((table, field), {})[rid] = Link(name, target=target_for(table, rid))
    rows = []
    for (table, field), links in sorted(grouped.items(), key=lambda x: words(x[0][0])):
        meaning = meanings.get(field)
        meaning = t(meaning) if meaning else words(field)
        what = t("{0}: {1}", translate(words(table.removeprefix("lib."))), meaning)
        rows.append(
            UsageRow(
                what,
                links=tuple(links.values()),
                noun="record",
                short=translate(words(table.removeprefix("lib."))),
            )
        )
    return rows


SHOWN = 3  # names said in a group member's row before "… (N records)"


def _few(links):
    """``Brave, Knight, Guardian… (7 records)``: the first names, then how many in all."""
    names = translate(", ").join(link.name for link in links[:SHOWN])
    return names if len(links) <= SHOWN else t("{0}… ({1})", names, count(len(links), "record"))


def _member(family, tag, uses):
    """A group member's row: its name (the part after the group's start), who carries it and
    what reads it by name; the records carrying it first, each with its table."""
    carry = [u for u in uses if u[0]]
    reads = [u for u in uses if not u[0]]
    links = {}
    for _carries, _field, table, rid, name in carry + reads:
        table_name = translate(words(table.removeprefix("lib.")))
        links[(table, rid)] = Link(name, f"({table_name})", target=target_for(table, rid))
    carried = list(links.values())[: len({(u[2], u[3]) for u in carry})]
    read = list(links.values())[len(carried) :]
    what = t(
        "{0} · carried by: {1} · read by: {2}",
        translate(words(tag[len(family) :])),
        _few(carried) if carried else t("nothing"),
        _few(read) if read else t("nothing"),
    )
    return UsageRow(what, page=tag, links=tuple(links.values()))


def tag_usage(project, tag_id, index=None):
    """The ``Usage`` card of ``tag_id``: what the engine does with it, who carries it and what
    reads it; a group (``rune.*``) gets a row per member instead. ``index``: the project's
    ``usage_index`` (built here when not given)."""
    from asteria.editor.rpg.usage_index import usage_index

    tag_id = str(tag_id).lower()
    family = tag_id[:-1] if tag_id.endswith("*") else None
    every = (index if index is not None else usage_index(project)).tags
    tags = sorted(x for x in every if x.startswith(family)) if family is not None else [tag_id]
    engine = built_in(tag_id if family is None else (tags[0] if tags else tag_id))
    summary = [t("The engine: {0}", t(engine))] if engine else []
    if family is not None:
        record = project.rpg_database.tag_definitions.get(tag_id)
        name = translate(record.display_name) if record is not None else tag_id
        summary.append(t("{0} is a group of {1}", name, count(len(tags), "property")))
        rows = tuple(_member(family, tag, every.get(tag, ())) for tag in tags)
        section = UsageSection(t("In the group"), rows, t("Nothing in the project uses it yet."))
        return Usage(tuple(summary), (section,))
    uses = every.get(tag_id, ())
    carriers = _rows([u for u in uses if u[0]], CARRY)
    readers = _rows([u for u in uses if not u[0]], READS)
    has = count(sum(len(row.links) for row in carriers), "record")
    read = count(sum(len(row.links) for row in readers), "record")
    summary.append(t("Carried by {0} · read by {1}", has, read))
    sections = (
        UsageSection(t("Who carries it"), tuple(carriers), t("Nothing carries it yet.")),
        UsageSection(
            t("What reads it"),
            tuple(readers),
            t("Only the engine reads it.") if engine else t("Nothing reads it yet."),
        ),
    )
    return Usage(tuple(summary), sections)


__all__ = ["CARRY", "READS", "project_tags", "tag_usage"]
