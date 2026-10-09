"""Transactional creation of a playable character from a generated bundle."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable
from uuid import NAMESPACE_URL, uuid5

from asteria.assets.character_bundle import GeneratedCharacterBundle
from asteria.assets.scene_placement import character_cell_position
from asteria.core import Entity, Transform
from asteria.graphics import SpriteClip, SpriteKeyframe
from asteria.project import Project
from asteria.rpg import ActorDefinition
from asteria.runtime import AnimationClipSet, Animator2DComponent, SpriteRenderer2D


@dataclass(frozen=True, slots=True)
class CreatedCharacter:
    actor_id: str
    entity_id: str
    clip_set_id: str
    actor: ActorDefinition
    entity: Entity
    clip_set: AnimationClipSet
    assets: tuple[object, ...]


def _directional_clips() -> AnimationClipSet:
    clips = {}
    for row, direction in enumerate(("down", "left", "right", "up")):
        base = row * 3
        clips[f"idle_{direction}"] = SpriteClip(
            f"idle_{direction}", [SpriteKeyframe(base + 1, 0.4)], True
        )
        # MV's middle cell is the standing pose. Repeat it between the two
        # alternating step poses so the loop matches the native 3-frame gait.
        clips[f"walk_{direction}"] = SpriteClip(
            f"walk_{direction}",
            [SpriteKeyframe(base + pattern, 0.12) for pattern in (1, 2, 1, 0)],
            True,
        )
    return AnimationClipSet(clips)


class CreateCharacterCommand:
    """Apply files, assets, RPG actor, and scene entity as one reversible unit."""

    def __init__(
        self,
        bundle: GeneratedCharacterBundle,
        project: Project,
        scene,
        cell: tuple[int, int],
        *,
        display_name: str | None = None,
        failure_injector: Callable[[str], None] | None = None,
    ):
        if project.scene(scene.id) is not scene:
            raise ValueError("target scene does not belong to project")
        self.bundle = bundle
        self.project = project
        self.scene = scene
        self.cell = (int(cell[0]), int(cell[1]))
        self.failure_injector = failure_injector
        actor_id = f"actor.generated.{bundle.recipe_id}"
        entity_id = str(uuid5(NAMESPACE_URL, f"asteria:{project.id}:{scene.id}:{bundle.recipe_id}:entity"))
        clip_set_id = f"animation.generated.{bundle.recipe_id}"
        actor = ActorDefinition(actor_id, display_name or bundle.recipe_id, tags=("generated", "playable"))
        clip_set = _directional_clips()
        entity = Entity(display_name or bundle.recipe_id, entity_id=entity_id)
        x, y = character_cell_position(*self.cell)
        entity.add_component(Transform(x, y))
        sprite = entity.add_component(SpriteRenderer2D())
        sprite.sprite_sheet_asset_id = bundle.canonical_assets[0].asset_id
        animator = entity.add_component(Animator2DComponent())
        animator.clip_set_id = clip_set_id
        animator.default_clip = "idle_down"

        assets = list(bundle.canonical_assets)
        walking = assets[0]
        animation_metadata = (
            ("anchor", bundle.anchor),
            ("clip_set_id", clip_set_id),
            ("clips", tuple(clip_set.clips)),
            ("frame_size", (48, 48)),
        )
        assets[0] = replace(walking, metadata=tuple(walking.metadata) + animation_metadata)
        self.created = CreatedCharacter(actor_id, entity_id, clip_set_id, actor, entity, clip_set, tuple(assets))
        self._paths = bundle.all_visual_paths + (bundle.metadata_path,) if bundle.files_owned else ()
        self._file_bytes: dict[Path, bytes] | None = None
        self._registered_asset_ids: list[str] = []
        self._actor_added = False
        self._entity_added = False
        self._files_claimed = False
        self._applied = False

    @property
    def label(self):
        return f"Create Character {self.created.actor.display_name}"

    def _fail(self, boundary: str):
        if self.failure_injector is not None:
            self.failure_injector(boundary)

    def _preflight(self):
        for asset in self.created.assets:
            try:
                self.project.assets.resolve(asset.asset_id)
            except KeyError:
                pass
            else:
                raise ValueError(f"asset already exists: {asset.asset_id}")
        if self.created.actor_id in self.project.rpg_database.actors:
            raise ValueError(f"actor already exists: {self.created.actor_id}")
        if self.scene.get_entity(self.created.entity_id) is not None:
            raise ValueError(f"entity already exists: {self.created.entity_id}")

    def _capture_or_restore_files(self):
        if self._file_bytes is None:
            missing = [path for path in self._paths if not path.is_file()]
            if missing:
                raise FileNotFoundError(missing[0])
            self._file_bytes = {path: path.read_bytes() for path in self._paths}
        else:
            for path, payload in self._file_bytes.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                handle, temporary_name = tempfile.mkstemp(prefix=f".{path.name}-", dir=path.parent)
                try:
                    with os.fdopen(handle, "wb") as stream:
                        stream.write(payload)
                    os.replace(temporary_name, path)
                except Exception:
                    try: os.unlink(temporary_name)
                    except FileNotFoundError: pass
                    raise
        self._files_claimed = True

    def _remove_owned_files(self):
        if not self._files_claimed:
            return
        for path in self._paths:
            try: path.unlink()
            except FileNotFoundError: pass
        self._files_claimed = False

    def _rollback(self):
        if self._entity_added and self.created.entity.scene is self.scene:
            self.scene.detach_entity(self.created.entity)
        self._entity_added = False
        if self._actor_added and self.project.rpg_database.actors.get(self.created.actor_id) is self.created.actor:
            self.project.rpg_database.actors.pop(self.created.actor_id)
        self._actor_added = False
        for asset_id in reversed(self._registered_asset_ids):
            try: self.project.assets.remove(asset_id)
            except KeyError: pass
        self._registered_asset_ids.clear()
        self._remove_owned_files()
        self._applied = False

    def execute(self) -> CreatedCharacter:
        return self.redo()

    def redo(self) -> CreatedCharacter:
        if self._applied:
            raise RuntimeError("command is already applied")
        self._preflight()
        try:
            self._capture_or_restore_files()
            self._fail("files")
            for asset in self.created.assets:
                self.project.assets.register(asset)
                self._registered_asset_ids.append(asset.asset_id)
            self._fail("assets")
            self.project.rpg_database.add_actor(self.created.actor)
            self._actor_added = True
            self._fail("actor")
            self.scene.add_entity(self.created.entity)
            self._entity_added = True
            self._fail("entity")
            self._applied = True
            return self.created
        except Exception:
            self._rollback()
            raise

    def undo(self):
        if not self._applied:
            raise RuntimeError("command is not applied")
        self._rollback()
