"""Editor-only field-appearance-per-actor store, kept beside a Project.

Mirrors PlaytestProfileLibrary: never part of canonical Project data, never
read by the runtime. The Editor applies a stored appearance directly onto
every linked entity's SpriteRenderer2D fields (see SceneEditingController and
AdapterFamilyWidget's "actors" appearance panel), so the shipped game never
needs to know this file exists.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class ActorAppearanceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ActorAppearance:
    actor_id: str
    sprite_sheet_asset_id: str
    frame_index: int = 0
    flip_x: bool = False

    def to_data(self):
        return {
            "sprite_sheet_asset_id": self.sprite_sheet_asset_id,
            "frame_index": self.frame_index,
            "flip_x": self.flip_x,
        }

    @classmethod
    def from_data(cls, actor_id, data):
        return cls(
            str(actor_id),
            str(data["sprite_sheet_asset_id"]),
            int(data.get("frame_index", 0)),
            bool(data.get("flip_x", False)),
        )


class ActorAppearanceLibrary:
    SCHEMA = "asteria.editor.actor_appearances"
    VERSION = 1

    def __init__(self, project_dir):
        self.project_dir = Path(project_dir)
        self.path = self.project_dir / "actor_appearances.json"
        self._items = {}
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ActorAppearanceError(str(exc)) from exc
        if raw.get("schema") != self.SCHEMA or raw.get("version") != self.VERSION:
            raise ActorAppearanceError("unsupported actor appearance store")
        self._items = {
            actor_id: ActorAppearance.from_data(actor_id, data)
            for actor_id, data in raw.get("actors", {}).items()
        }

    def get(self, actor_id):
        self._ensure_loaded()
        return self._items.get(str(actor_id))

    def set(self, actor_id, sprite_sheet_asset_id, frame_index=0, flip_x=False):
        self._ensure_loaded()
        actor_id = str(actor_id)
        value = ActorAppearance(
            actor_id, str(sprite_sheet_asset_id), int(frame_index), bool(flip_x)
        )
        self._items[actor_id] = value
        self._save()
        return value

    def remove(self, actor_id):
        self._ensure_loaded()
        if self._items.pop(str(actor_id), None) is not None:
            self._save()

    def _save(self):
        self.project_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "actors": {k: v.to_data() for k, v in sorted(self._items.items())},
        }
        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


def get_actor_appearance(document, actor_id):
    """Current field appearance for an Actor, or None if it has none yet.

    An unsaved project has no sidecar to read, so the linked map entity's
    SpriteRenderer2D is the fallback source of truth — it is what
    apply_actor_appearance wrote, and what the map is actually drawing.
    """
    if document.file_path is not None:
        stored = ActorAppearanceLibrary(document.file_path.parent).get(actor_id)
        if stored is not None:
            return stored
    session = getattr(document, "session_appearances", {}).get(str(actor_id))
    if session is not None:
        return session
    return _appearance_from_map(document, actor_id)


def _appearance_from_map(document, actor_id):
    from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

    if document.project is None:
        return None
    for scene in document.project.scenes():
        for entity in scene.entities():
            link = entity.try_get(ActorLinkComponent)
            if link is None or link.actor_id != str(actor_id):
                continue
            sprite = entity.try_get(SpriteRenderer2D)
            if sprite is not None and sprite.sprite_sheet_asset_id:
                return ActorAppearance(
                    str(actor_id), sprite.sprite_sheet_asset_id,
                    sprite.frame_index, sprite.flip_x,
                )
    return None


def apply_actor_appearance(document, actor_id, sprite_sheet_asset_id, frame_index=0, flip_x=False):
    """Persist an Actor's field appearance/name and push both onto every map
    Entity linked to it via ActorLinkComponent — one undoable step.

    Shared by the main window (menu-driven edits) and the Character tab's
    Actors panel (AdapterFamilyWidget), neither of which should duplicate
    this sync logic.
    """
    from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

    from .commands import AddComponentCommand, CommandTransaction, SetAttributeCommand
    from .structure import build_rename_command

    if document.project is None:
        return False

    actor = document.project.rpg_database.actors.get(str(actor_id))
    # Remembered for this session either way: an unsaved project has no folder
    # for the sidecar, and a character that has not been put on a map yet has
    # no entity to read the appearance back from.
    if not hasattr(document, "session_appearances"):
        document.session_appearances = {}
    document.session_appearances[str(actor_id)] = ActorAppearance(
        str(actor_id), str(sprite_sheet_asset_id), int(frame_index), bool(flip_x)
    )
    if document.file_path is not None:
        ActorAppearanceLibrary(document.file_path.parent).set(
            actor_id, sprite_sheet_asset_id, frame_index, flip_x
        )
    target_fields = {
        "sprite_sheet_asset_id": str(sprite_sheet_asset_id),
        "frame_index": int(frame_index),
        "flip_x": bool(flip_x),
    }
    tx = CommandTransaction("Sync Actor to Map")
    for scene in document.project.scenes():
        for entity in scene.entities():
            link = entity.try_get(ActorLinkComponent)
            if link is None or link.actor_id != str(actor_id):
                continue
            if actor is not None and entity.name != actor.display_name:
                tx.add(build_rename_command(entity, actor.display_name))
            sprite = entity.try_get(SpriteRenderer2D)
            if sprite is None:
                new_sprite = SpriteRenderer2D()
                for field_name, value in target_fields.items():
                    setattr(new_sprite, field_name, value)
                tx.add(AddComponentCommand(entity, new_sprite))
            else:
                for field_name, new_value in target_fields.items():
                    old_value = getattr(sprite, field_name)
                    if old_value != new_value:
                        tx.add(
                            SetAttributeCommand(
                                sprite, field_name, new_value, old_value,
                                f"Set {field_name}",
                            )
                        )
    if tx.commands:
        document.execute(tx)
    return True
