"""What a character wears when they first come in (D110): the actor's own
``starting_equipment``. Every character puts it on at New Game (the starting party and those
who join later, as Game Start's own loadouts did); one who joins with no loadout yet (a save
from before) puts it on when joining. A character with a loadout already keeps theirs.
"""

from __future__ import annotations

from asteria.rpg.items.definitions import (
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
)


def starting_slot(database, slot_id, equipment_id):
    """The slot a starting piece goes in: the one named, else the gear's own."""
    return str(slot_id or database.equipment[equipment_id].slot)


def starting_loadout(database, actor):
    """The loadout ``actor`` comes in wearing, or ``None`` when they name no gear."""
    if not actor.starting_equipment:
        return None
    slots = dict(getattr(database, "equipment_slots", {}))
    for slot_id, equipment_id in actor.starting_equipment:  # no slot records: the gear's own
        slot = starting_slot(database, slot_id, equipment_id)
        slots.setdefault(slot, EquipmentSlotDefinition(slot))
    sets = tuple(database.equipment_sets.values())
    loadout = EquipmentLoadout(tuple(slots.values()), set_definitions=sets)
    taken = set()
    for slot_id, equipment_id in actor.starting_equipment:
        serial, instance_id = 1, f"{equipment_id}:{actor.actor_id}"
        while instance_id in taken:  # two of the same piece: each its own
            serial += 1
            instance_id = f"{equipment_id}:{actor.actor_id}{serial}"
        taken.add(instance_id)
        piece = EquippedItem(database.equipment[equipment_id], instance_id=instance_id)
        slot = starting_slot(database, slot_id, equipment_id)
        loadout.equip(slot, piece, validate_requirements=False)
    return loadout


def put_on_starting_gear(state, database, actor_ids):
    """Each of ``actor_ids`` with no loadout yet puts on their starting gear. Returns the ids
    that did."""
    dressed = []
    for actor_id in actor_ids:
        actor = database.actors.get(str(actor_id))
        if actor is None or actor.actor_id in state.loadouts:
            continue
        loadout = starting_loadout(database, actor)
        if loadout is not None:
            state.loadouts[actor.actor_id] = loadout
            dressed.append(actor.actor_id)
    return tuple(dressed)


def starting_gear_errors(database):
    """A message per starting piece the database cannot put on: gear it does not define, a
    slot it does not define, gear that does not go in its slot."""
    errors = []
    slots = getattr(database, "equipment_slots", {})
    for actor in database.actors.values():
        for slot_id, equipment_id in actor.starting_equipment:
            where = f"actor {actor.actor_id} starting equipment"
            gear = database.equipment.get(equipment_id)
            if gear is None:
                errors.append(f"{where} references unknown equipment {equipment_id}")
                continue
            slot_id = slot_id or gear.slot
            if slots and slot_id not in slots:
                errors.append(f"{where} references unknown equipment slot {slot_id}")
            elif slots and not slots[slot_id].takes(gear):
                errors.append(f"{where}: {equipment_id} does not go in the {slot_id} slot")
    return errors


__all__ = [
    "put_on_starting_gear",
    "starting_gear_errors",
    "starting_loadout",
    "starting_slot",
]
