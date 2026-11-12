"""Who can wear a piece of gear: the characters whose own properties and jobs give what it
needs (its ``required_capabilities``, one of its ``any_capabilities``, none of its
``forbidden_capabilities``), for the gear page's "Who can wear it" line.

The engine checks the same rule when a character equips it (``EquipmentDefinition
.eligibility`` over the character's tags, which hold their jobs' ``granted_tags``). What a
character gains later (a skill tree, a level reward, another piece of gear) may let more wear
it; the line says who can from the start.
"""

from __future__ import annotations

from asteria.rpg.characters.actors import build_actor
from asteria.rpg.items.definitions import EquipmentDefinition


def actor_capabilities(db, actor):
    """The properties a character starts with: their own and their jobs' (none when a job is
    missing from the project)."""
    try:
        return set(build_actor(actor, class_definitions=db.classes).tags.values())
    except ValueError:
        return set(actor.tags)


def who_can_wear(project, data):
    """``(actor_id, name)`` of every character who can wear the gear ``data`` (its record as
    saved), in the project's order; all of them when it needs nothing."""
    try:
        gear = EquipmentDefinition.from_data(data)
    except (KeyError, TypeError, ValueError):
        return ()
    db = project.rpg_database
    return tuple(
        (actor_id, actor.display_name or actor_id)
        for actor_id, actor in db.actors.items()
        if gear.eligibility(actor_capabilities(db, actor)).allowed
    )


def starting_wear(project):
    """What every character wears when a new game starts, for Game Start's overview (D110):
    ``(actor_id, name, pieces, kept)`` in the project's order, ``pieces`` as ``(slot_id,
    slot name, equipment_id)`` by the slots' order. ``kept``: the pieces come from a loadout
    Game Start itself holds (an older project), which stays as it is."""
    from asteria.rpg.items.starting_gear import starting_slot

    db = project.rpg_database
    slots = getattr(db, "equipment_slots", {})
    order = {slot_id: (getattr(s, "order", 0), i) for i, (slot_id, s) in enumerate(slots.items())}
    state = project.game_start.rpg_state_data or {}
    loadouts = state.get("loadouts", {}) if isinstance(state, dict) else {}
    out = []
    for actor_id, actor in db.actors.items():
        kept = actor_id in loadouts
        if kept:
            equipped = loadouts[actor_id].get("equipped", {})
            pairs = [(s, p["equipment_id"]) for s, ps in equipped.items() for p in ps]
        else:
            pairs = [
                (starting_slot(db, s, e) if e in db.equipment else s, e)
                for s, e in actor.starting_equipment
            ]
        pairs.sort(key=lambda pair: order.get(pair[0], (1 << 30, 0)))
        pieces = tuple((s, getattr(slots.get(s), "display_name", "") or s, e) for s, e in pairs)
        out.append((actor_id, actor.display_name or actor_id, pieces, kept))
    return tuple(out)


def needs_anything(data):
    return any(data.get(k) for k in ("required_capabilities", "any_capabilities",
                                     "forbidden_capabilities"))  # fmt: skip


__all__ = ["actor_capabilities", "needs_anything", "starting_wear", "who_can_wear"]
