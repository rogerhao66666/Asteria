"""What kind of thing an entity is, read from its components, and the colour that kind keeps
everywhere in the Scene workspace: the project tree's icon, the name label on the map and the
badge in the Inspector all use the same one, so a door reads as a door wherever it is listed.

The kinds are the engine's reading of the components, not a field the author sets: a camera is
whatever carries a camera component, a trigger an interaction without a picture, and so on. An
entity nothing fits is simply an entity, in the neutral colour.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityKind:
    kind: str  # a short id (the QSS property value)
    label: str  # the word shown (translated where it is shown)
    colour: str  # ``#rrggbb``
    icon: str  # a drawing in ``icons.DRAWINGS``


KINDS = {
    kind.kind: kind
    for kind in (
        EntityKind("camera", "Camera", "#9a84e0", "camera"),
        EntityKind("map", "Map", "#8f96a3", "tiles"),
        EntityKind("player", "Player", "#46b896", "entity"),
        EntityKind("character", "Character", "#4aa9dc", "entity"),
        EntityKind("trigger", "Trigger", "#e06a5c", "interact"),
        EntityKind("prop", "Prop", "#dca545", "doodad"),
        EntityKind("entity", "Entity", "#a3a5ad", "entity"),
    )
}


def _component_names(entity):
    try:
        return {type(component).__name__ for component in entity.components()}
    except (AttributeError, TypeError):
        return set()


def _has(names, *needles):
    return any(needle in name for name in names for needle in needles)


def kind_of(entity):
    """The ``EntityKind`` of ``entity``: the first rule its components satisfy.

    camera > map > player (a character controller) > character (someone to talk to: an
    interaction with a picture, or an NPC identity) > trigger (an interaction with no picture: a
    door, an exit) > prop (a picture alone) > entity.
    """
    names = _component_names(entity)
    if _has(names, "Camera2D"):
        return KINDS["camera"]
    if _has(names, "TileMap2D"):
        return KINDS["map"]
    if _has(names, "CharacterController2D"):
        return KINDS["player"]
    interactive = _has(names, "Interaction2D")
    pictured = _has(names, "SpriteRenderer2D", "SkeletonAnimation2D")
    if _has(names, "NpcIdentity2D") or (interactive and pictured):
        return KINDS["character"]
    if interactive:
        return KINDS["trigger"]
    if pictured:
        return KINDS["prop"]
    return KINDS["entity"]
