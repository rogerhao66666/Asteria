"""Who carries a tag and what reads it (D91), for Game Systems ▸ Tags.

A tag means nothing on its own: a record carries it (gear's ``tags``, a job's ``granted_tags``,
a state's ``contributed_tags``) and a rule reads it (a damage rule's ``target_tags_all``, gear's
``required_capabilities``). ``tag_usage`` walks the project and writes both down, with what the
engine itself does with the tag (``rpg.tag_definitions.BUILT_IN``); a family (``rune.*``)
lists every tag it covers.

``project_tags`` gives every tag the project names, for the Problems list.
"""

from __future__ import annotations

from asteria.rpg.data_text import words
from asteria.rpg.tag_definitions import built_in

from .stat_usage import t

# fields whose tags a record carries; every other field naming tags or capabilities reads them
CARRY = {"tags", "granted_tags", "contributed_tags", "success_tags", "failure_tags"}
CARRY |= {"outcome_tags", "equipment_tags"}
SHOWN = 8  # records listed per line before "and N more"


def _reads(key):
    key = key.lower()
    return key not in CARRY and ("tag" in key or "capabilit" in key)


def _walk(value, key, record, found, groups=False):
    """``found[tag]`` gains ``(carries, field, record)`` for every tag under ``value``;
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
                found.setdefault(v.lower(), []).append((carries, field, record))
            else:
                _walk(v, key, record, found, groups)


def _record_name(table, record):
    rid = next((v for k, v in record.items() if k.endswith("_id") and isinstance(v, str)), "")
    return f"{words(table)} {rid}".strip()


def project_tags(project):
    """``{tag: [(carries, field, "Table record_id"), ...]}`` over the whole project."""
    found = {}
    tables = dict(project.rpg_database.to_data())
    tables.update({f"lib.{k}": v for k, v in project.gameplay_library.to_data().items()})
    for table, records in tables.items():
        if not isinstance(records, list):
            continue
        name = table.removeprefix("lib.")
        for record in records:
            if isinstance(record, dict):
                _walk(record, "", _record_name(name, record), found)
    return found


def _listed(records):
    records = list(dict.fromkeys(records))
    more = t(" and {0} more", len(records) - SHOWN) if len(records) > SHOWN else ""
    return ", ".join(records[:SHOWN]) + more


def tag_usage(project, tag_id):
    """Lines of words: what the engine does with ``tag_id``, who carries it, what reads it."""
    tag_id = str(tag_id).lower()
    family = tag_id[:-1] if tag_id.endswith("*") else None
    every = project_tags(project)
    tags = sorted(x for x in every if x.startswith(family)) if family is not None else [tag_id]
    lines = []
    engine = built_in(tag_id if family is None else (tags[0] if tags else tag_id))
    if engine:
        lines.append(t("Engine: {0}", t(engine)))
    if family is not None:
        lines.append(t("Covers {0} tags: {1}", len(tags), _listed(tags) or t("none yet")))
    uses = [u for x in tags for u in every.get(x, ())]
    carriers = [record for carries, _key, record in uses if carries]
    readers = [f"{record} ({words(key)})" for carries, key, record in uses if not carries]
    lines.append(t("Carried by: {0}", _listed(carriers) if carriers else t("nothing yet")))
    if readers:
        lines.append(t("Read by: {0}", ""))
        lines += [f"  • {line}" for line in _bullets(readers)]
    elif not engine:
        lines.append(t("Read by: nothing reads it yet"))
    return "\n".join(lines)


def _bullets(records):
    """One line each, the first ``SHOWN``, then "and N more"."""
    records = list(dict.fromkeys(records))
    shown = records[:SHOWN]
    if len(records) > SHOWN:
        shown.append(t(" and {0} more", len(records) - SHOWN).strip())
    return shown


__all__ = ["CARRY", "project_tags", "tag_usage"]
