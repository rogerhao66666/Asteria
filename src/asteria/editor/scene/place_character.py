"""Placing a character the way a map editor does: press the tool, carry the picture to a
cell, click. The new character looks like the scene's player (its sprite sheet and walking
animations) - the project's own look, until the author picks another in the Database - and is
an actor, a map entity linked to it, and nothing else, in one undoable step.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.assets.scene_placement import character_cell_position
from asteria.core import Entity, Transform
from asteria.editor.project.commands import AddEntityCommand, CommandTransaction
from asteria.rpg import ActorDefinition
from asteria.runtime import (
    ActorLinkComponent,
    Animator2DComponent,
    Camera2DComponent,
    CharacterController2D,
    SpriteRenderer2D,
)


@dataclass(frozen=True, slots=True)
class DefaultAppearance:
    """What a newly placed character looks like: a sprite sheet the project already has."""

    sprite_sheet_asset_id: str
    clip_set_id: str = ""
    default_clip: str = ""
    frame_index: int = 0
    flip_x: bool = False


def default_appearance(document, scene):
    """The scene's player's look (the entity a camera follows, else one with a character
    controller), else the first drawn and animated entity's, else the first sprite sheet the
    project has; None when the project has no sprite sheet at all."""
    candidates = []
    if scene is not None:
        followed = {
            camera.follow_entity_id
            for camera in (entity.try_get(Camera2DComponent) for entity in scene.entities())
            if camera is not None and camera.follow_entity_id
        }
        for entity in scene.entities():
            sprite = entity.try_get(SpriteRenderer2D)
            if sprite is None or not sprite.sprite_sheet_asset_id:
                continue
            animator = entity.try_get(Animator2DComponent)
            rank = (
                0 if entity.id in followed else 1,
                0 if entity.try_get(CharacterController2D) is not None else 1,
                0 if animator is not None else 1,
            )
            candidates.append(
                (
                    rank,
                    DefaultAppearance(
                        str(sprite.sprite_sheet_asset_id),
                        str(getattr(animator, "clip_set_id", "") or ""),
                        str(getattr(animator, "default_clip", "") or ""),
                        int(sprite.frame_index),
                        bool(sprite.flip_x),
                    ),
                )
            )
    if candidates:
        return min(candidates, key=lambda pair: pair[0])[1]
    views = getattr(document, "asset_views", None)
    ids = views.sprite_sheet_ids() if views is not None else ()
    return DefaultAppearance(ids[0]) if ids else None


def shown_frame(document, appearance):
    """The frame index the character stands in: the default clip's first keyframe when the
    clip set is known, else the appearance's own frame."""
    views = getattr(document, "asset_views", None)
    clip_set = views.clip_set(appearance.clip_set_id) if views and appearance.clip_set_id else None
    clip = getattr(clip_set, "clips", {}).get(appearance.default_clip) if clip_set else None
    keyframes = getattr(clip, "keyframes", None) or ()
    if keyframes:
        return int(keyframes[0].frame_index)
    return int(appearance.frame_index)


def free_actor_id(project, base="actor.new_character"):
    actors = project.rpg_database.actors
    candidate, counter = base, 2
    while candidate in actors:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def free_display_name(project, base="New Character"):
    names = {a.display_name for a in project.rpg_database.actors.values()}
    candidate, counter = base, 2
    while candidate in names:
        candidate = f"{base} {counter}"
        counter += 1
    return candidate


class _ActorCommand:
    """An actor added to the database (undo removes it)."""

    def __init__(self, actors, actor):
        self.actors = actors
        self.actor = actor

    @property
    def label(self):
        return f"Add actor {self.actor.actor_id}"

    def redo(self):
        self.actors[self.actor.actor_id] = self.actor

    def undo(self):
        if self.actors.get(self.actor.actor_id) is self.actor:
            self.actors.pop(self.actor.actor_id)


def build_place_character_command(
    project, scene, cell, appearance, *, display_name=None, tile_size=(48, 48)
):
    """A transaction that adds a playable actor and its map entity at ``cell``, looking like
    ``appearance``; ``command.created`` has the actor and the entity."""
    if project is None or scene is None:
        raise ValueError("a project and a scene are needed to place a character")
    actor_id = free_actor_id(project)
    name = str(display_name or free_display_name(project))
    actor = ActorDefinition(actor_id, name, tags=("playable",))
    entity = Entity(name)
    x, y = character_cell_position(int(cell[0]), int(cell[1]), tuple(tile_size))
    entity.add_component(Transform(float(x), float(y)))
    sprite = entity.add_component(SpriteRenderer2D())
    sprite.sprite_sheet_asset_id = appearance.sprite_sheet_asset_id
    sprite.frame_index = int(appearance.frame_index)
    sprite.flip_x = bool(appearance.flip_x)
    if appearance.clip_set_id:
        animator = entity.add_component(Animator2DComponent())
        animator.clip_set_id = appearance.clip_set_id
        if appearance.default_clip:
            animator.default_clip = appearance.default_clip
    link = entity.add_component(ActorLinkComponent())
    link.actor_id = actor_id
    command = CommandTransaction(
        f"Place Character {name}",
        [_ActorCommand(project.rpg_database.actors, actor), AddEntityCommand(scene, entity)],
    )
    command.created = _Created(actor_id, actor, entity)
    return command


@dataclass(frozen=True, slots=True)
class _Created:
    actor_id: str
    actor: object
    entity: object
