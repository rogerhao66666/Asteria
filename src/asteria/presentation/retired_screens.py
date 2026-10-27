"""The six runtime screen records retired in D98 (the editor's old "Menu Records" tab).

A project file from before D98 may still hold ``rpg_character_screen``,
``rpg_equipment_screen``, ``rpg_ability_screen``, ``rpg_progression_screen``,
``rpg_inventory_screen`` and ``rpg_party_screen`` in its presentation library. Of all their
fields the game read only these, and they move where the rest of the data is:

* the character screen's stat and resource names and their order -> the Stats
  (``rpg_database.stat_definitions``: a name only where the definition has none of its own,
  a definition made for a stat that has none);
* the character and equipment screens' slot names -> the Equipment Slots (a defined slot's
  name where it has none; a slot without a definition keeps the engine's name, since a
  definition made for it would change what it holds).

Everything else was never drawn (section order, hidden sections, bar styles, groups, visible
limits, the party and progression screens) or only repeated a record's own name (item,
equipment, ability and passive names), and is dropped.
"""

from __future__ import annotations

RETIRED_CATEGORIES = (
    "rpg_character_screen",
    "rpg_equipment_screen",
    "rpg_ability_screen",
    "rpg_progression_screen",
    "rpg_inventory_screen",
    "rpg_party_screen",
)


def _first(retired, category):
    """The record the game read: the category's first by id, as plain data (or {})."""
    records = retired.get(category) or {}
    return records[sorted(records)[0]] if records else {}


def _pairs(raw):
    return dict(raw.items() if isinstance(raw, dict) else (tuple(x) for x in raw or ()))


def move_retired(retired, database):
    """Move what the game read of ``retired`` (``{category: {id: data}}``) into ``database``
    (an ``RpgDatabase``); returns the ids of the stats and slots it changed."""
    from dataclasses import replace

    from asteria.rpg.stat_definitions import SET_ON, StatDefinition

    character = _first(retired, "rpg_character_screen")
    equipment = _first(retired, "rpg_equipment_screen")
    changed = []
    names = {**_pairs(character.get("resource_labels")), **_pairs(character.get("stat_labels"))}
    order = [*character.get("stat_order", ()), *character.get("resource_order", ())]
    order += [k for k in names if k not in order]
    definitions = database.stat_definitions
    had_definitions = bool(definitions)
    after = max((d.order for d in definitions.values()), default=-1) + 1
    for stat_id in order:
        name = str(names.get(stat_id, "") or "")
        found = definitions.get(stat_id)
        if found is None:
            made = StatDefinition(
                stat_id,
                name or stat_id,
                order=after,
                set_on=() if had_definitions else SET_ON,  # none before: still offered
            )
            database.add_stat_definition(made)
            changed.append(stat_id)
            after += 1
        elif name and found.display_name == stat_id:
            definitions[stat_id] = replace(found, display_name=name)
            changed.append(stat_id)
    slots = {**_pairs(character.get("slot_labels")), **_pairs(equipment.get("slot_labels"))}
    for slot_id, name in slots.items():
        found = database.equipment_slots.get(slot_id)  # a new definition would change it
        if found is not None and not found.display_name:
            database.equipment_slots[slot_id] = replace(found, display_name=str(name))
            changed.append(slot_id)
    return changed


__all__ = ["RETIRED_CATEGORIES", "move_retired"]
