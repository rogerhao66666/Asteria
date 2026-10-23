"""What the Translations page lists of the project's own data (D60), without Qt.

``data_groups(project)`` gives ``[(title, [(key, english)])]``: one group per kind of record
(actors, classes, skills, items...), each record's name and - for the kinds that have one - its
description, keyed ``data.<kind>.<id>.<field>`` (``rpg/data_text.py``); then the maps, the
currencies, who speaks in the events, and every dialogue line, choice and choice prompt that has
a ``text_key``. Records with no text of their own are left out (nothing to translate).

``dialogue_without_keys(project)`` counts the lines that have no key yet; ``keyed_programs``
gives each event program with keys added to those lines (``dlg.<program>.<index>``, choices
``...<index>.<n>``, the prompt ``...<index>.prompt``), for the page's button to put in place as
one undoable step.
"""

from __future__ import annotations

import re

from asteria.events.program import EventInstruction, EventProgram
from asteria.rpg.data_text import key, kind_of

# (title, the RpgDatabase tables or gameplay libraries it lists, nested records)
DATA_GROUPS = (
    ("Data: actors", ("actors",)),
    ("Data: classes", ("classes",)),
    ("Data: skills", ("gameplay:abilities",)),
    ("Data: passives", ("passives",)),
    ("Data: states", ("gameplay:states",)),
    ("Data: items", ("items",)),
    ("Data: equipment", ("equipment",)),
    ("Data: socketed items", ("attachments",)),
    ("Data: equipment sets", ("equipment_sets",)),
    ("Data: equipment growth", ("equipment_growth",)),
    ("Data: rarities and affixes", ("rarities", "affixes")),
    ("Data: enemies", ("enemies",)),
    ("Data: pet species", ("pet_species",)),
    ("Data: quests", ("quests",)),
    ("Data: shops", ("shops",)),
    ("Data: crafting recipes", ("composition_recipes",)),
    ("Data: skill trees", ("progression_graphs",)),
    ("Data: progression tracks", ("progression_tracks",)),
    ("Data: stats", ("derived_stats",)),
    ("Data: factions and achievements", ("factions", "achievements")),
    ("Data: world interactions", ("world_interactions",)),
    ("Data: party setups and drop tables", ("party_setups", "drop_tables")),
)
MAPS_GROUP = "Data: map names"
CURRENCY_GROUP = "Data: currencies"
SLOTS_GROUP = "Data: equipment slots"
SPEAKERS_GROUP = "Dialogue: who speaks"
LINES_GROUP = "Dialogue: lines and choices"
NESTED = ("objectives", "nodes")  # quest objectives, skill-tree / growth nodes
# a text that is only \\T[key] codes already comes from the locale tables: it needs no key
_ONLY_TABLE_CODES = re.compile(r"^(\s*\\T\[[^\]]+\]\s*)+$")


def _translatable(text):
    text = str(text or "")
    return bool(text.strip()) and not _ONLY_TABLE_CODES.match(text)


def _records(project, table):
    if table.startswith("gameplay:"):
        library = getattr(getattr(project, "gameplay_library", None), table[9:], None)
        if library is None:
            return []
        values = library.values() if isinstance(library, dict) else ()
        if not values and hasattr(library, "ids"):
            values = [library.get(i) for i in library.ids()]
        return [v for v in values if v is not None]
    values = getattr(getattr(project, "rpg_database", None), table, None) or {}
    return list(values.values()) if isinstance(values, dict) else list(values)


def _rows_of(record):
    known = kind_of(record)
    if known is None:
        return []
    rows = []
    name = str(getattr(record, "display_name", "") or "")
    if name:
        rows.append((key(*known, "name"), name))
    description = str(getattr(record, "description", "") or "")
    if description:
        rows.append((key(*known, "description"), description))
    for attribute in NESTED:
        for child in getattr(record, attribute, ()) or ():
            rows += _rows_of(child)
    return rows


def _instructions(project):
    programs = getattr(project, "event_programs", None)
    if programs is None:
        return
    for program_id in programs.ids():
        program = programs.require(program_id)
        for index, instruction in enumerate(program.instructions):
            yield program_id, index, instruction


def currency_ids(project):
    db = getattr(project, "rpg_database", None)
    ids = set()
    for settings in (getattr(db, "message_settings", None) or {}).values():
        if getattr(settings, "currency_id", ""):
            ids.add(settings.currency_id)
    for enemy in (getattr(db, "enemies", None) or {}).values():
        ids.update(getattr(getattr(enemy, "reward", None), "currencies", None) or {})
    for shop in (getattr(db, "shops", None) or {}).values():
        for entry in getattr(shop, "entries", ()):
            ids.update(getattr(entry, "prices", None) or {})
    return sorted(ids)


def data_groups(project):
    """``[(title, [(key, english)])]`` of the project's own data, groups without rows left
    out."""
    if project is None:
        return []
    groups = []
    for title, tables in DATA_GROUPS:
        rows = {}
        for table in tables:
            for record in _records(project, table):
                for row_key, english in _rows_of(record):
                    rows.setdefault(row_key, english)
        if rows:
            groups.append((title, list(rows.items())))
    listed = getattr(project, "scenes", None)
    listed = listed() if callable(listed) else (listed or ())
    scenes = [(key("map", s.id), s.name) for s in listed if s.name]
    if scenes:
        groups.append((MAPS_GROUP, scenes))
    equipment = (getattr(getattr(project, "rpg_database", None), "equipment", None) or {}).values()
    slots = sorted({str(getattr(e, "slot", "") or "") for e in equipment} - {""})
    if slots:
        groups.append((SLOTS_GROUP, [(key("slot", s), s) for s in slots]))
    currencies = [(key("currency", c), c) for c in currency_ids(project)]
    if currencies:
        groups.append((CURRENCY_GROUP, currencies))
    speakers, lines = {}, {}
    for _program_id, _index, instruction in _instructions(project):
        args = instruction.args
        if instruction.opcode == "DIALOGUE":
            speaker = str(args.get("speaker", "") or "")
            if speaker:
                speakers.setdefault(key("speaker", speaker), speaker)
            if args.get("text_key"):
                lines.setdefault(str(args["text_key"]), str(args.get("text", "")))
        elif instruction.opcode == "CHOICE":
            if args.get("prompt_key"):
                lines.setdefault(str(args["prompt_key"]), str(args.get("prompt", "")))
            for choice in args.get("choices") or ():
                if isinstance(choice, dict) and choice.get("text_key"):
                    lines.setdefault(str(choice["text_key"]), str(choice.get("text", "")))
    if speakers:
        groups.append((SPEAKERS_GROUP, sorted(speakers.items(), key=lambda kv: kv[1])))
    if lines:
        groups.append((LINES_GROUP, list(lines.items())))
    return groups


def _needs_keys(instruction):
    args = instruction.args
    if instruction.opcode == "DIALOGUE":
        return _translatable(args.get("text")) and not args.get("text_key")
    if instruction.opcode == "CHOICE":
        missing = [
            c
            for c in args.get("choices") or ()
            if isinstance(c, dict) and _translatable(c.get("text"))
        ]
        prompt = _translatable(args.get("prompt")) and not args.get("prompt_key")
        return prompt or any(not c.get("text_key") for c in missing)
    return False


def dialogue_without_keys(project):
    """How many DIALOGUE / CHOICE instructions still have text without a key."""
    return sum(1 for _p, _i, ins in _instructions(project) if _needs_keys(ins))


def _short(program_id):
    text = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(program_id))
    return text[:8] if len(text) > 8 else text


def keyed_programs(project):
    """``[(program_id, new_program, old_program)]``: every event program with a key put on
    each dialogue line, choice and prompt that has none (keys already there are kept)."""
    programs = getattr(project, "event_programs", None)
    if programs is None:
        return []
    used = set()
    for _program_id, _index, instruction in _instructions(project):
        args = instruction.args
        used.update(str(args[k]) for k in ("text_key", "prompt_key") if args.get(k))
        for choice in args.get("choices") or ():
            if isinstance(choice, dict) and choice.get("text_key"):
                used.add(str(choice["text_key"]))

    def fresh(base):
        name, number = base, 2
        while name in used:
            name, number = f"{base}_{number}", number + 1
        used.add(name)
        return name

    changed = []
    for program_id in programs.ids():
        old = programs.require(program_id)
        if not any(_needs_keys(i) for i in old.instructions):
            continue
        short = _short(program_id)
        instructions = []
        for index, instruction in enumerate(old.instructions):
            if not _needs_keys(instruction):
                instructions.append(instruction)
                continue
            args = dict(instruction.args)
            base = f"dlg.{short}.{index}"
            if instruction.opcode == "DIALOGUE":
                args["text_key"] = fresh(base)
            else:
                if _translatable(args.get("prompt")) and not args.get("prompt_key"):
                    args["prompt_key"] = fresh(f"{base}.prompt")
                choices = []
                for number, choice in enumerate(args.get("choices") or (), 1):
                    if (
                        isinstance(choice, dict)
                        and _translatable(choice.get("text"))
                        and not choice.get("text_key")
                    ):
                        choice = {**choice, "text_key": fresh(f"{base}.{number}")}
                    choices.append(choice)
                args["choices"] = choices
            instructions.append(EventInstruction(instruction.opcode, args))
        changed.append((program_id, EventProgram(instructions, name=old.name), old))
    return changed
