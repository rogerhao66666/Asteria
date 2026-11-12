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


def needs_anything(data):
    return any(data.get(k) for k in ("required_capabilities", "any_capabilities",
                                     "forbidden_capabilities"))  # fmt: skip


__all__ = ["actor_capabilities", "needs_anything", "who_can_wear"]
