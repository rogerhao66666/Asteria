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

    What the map draws comes first - the linked entity's (or, for the party
    leader, the player's) SpriteRenderer2D, which apply_actor_appearance wrote
    and undo puts back - then this session's choice, then the sidecar, which
    remembers the look of an actor not on any map yet.
    """
    on_map = _appearance_from_map(document, actor_id)
    if on_map is not None:
        return on_map
    session = getattr(document, "session_appearances", {}).get(str(actor_id))
    if session is not None:
        return session
    if document.file_path is not None:
        return ActorAppearanceLibrary(document.file_path.parent).get(actor_id)
    return None


def party_leader_entity(document, actor_id):
    """The map entity the player walks as, when ``actor_id`` leads the starting party (the
    first active member of Game Start's party) - the leader looks like the player on the
    map, as in RPG Maker; else None."""
    project = document.project
    start = getattr(project, "game_start", None) if project is not None else None
    if start is None or not start.player_entity_id:
        return None
    state = start.rpg_state_data or {}
    party = list(state.get("party_active_actor_ids") or state.get("party_actor_ids") or ())
    if not party or party[0] != str(actor_id):
        return None
    for scene in project.scenes():
        entity = scene.get_entity(start.player_entity_id)
        if entity is not None:
            return entity
    return None


def linked_entities(document, actor_id):
    """``(entity, renamed)`` for every map entity that looks like the actor: those linked to
    it (named after it too), then the player's entity when it leads the party (its name is
    the scene's own)."""
    from asteria.runtime import ActorLinkComponent

    if document.project is None:
        return []
    found = []
    for scene in document.project.scenes():
        for entity in scene.entities():
            link = entity.try_get(ActorLinkComponent)
            if link is not None and link.actor_id == str(actor_id):
                found.append((entity, True))
    leader = party_leader_entity(document, actor_id)
    if leader is not None and all(entity is not leader for entity, _ in found):
        found.append((leader, False))
    return found


def _appearance_from_map(document, actor_id):
    from asteria.runtime import SpriteRenderer2D

    for entity, _renamed in linked_entities(document, actor_id):
        sprite = entity.try_get(SpriteRenderer2D)
        if sprite is not None and sprite.sprite_sheet_asset_id:
            return ActorAppearance(
                str(actor_id),
                sprite.sprite_sheet_asset_id,
                sprite.frame_index,
                sprite.flip_x,
            )
    return None


def apply_actor_appearance(document, actor_id, sprite_sheet_asset_id, frame_index=0, flip_x=False):
    """Persist an Actor's field appearance/name and push both onto every map
    Entity that looks like it (linked via ActorLinkComponent, or the player's
    when it leads the party) — one undoable step. A sheet with its own walking
    animations brings them along.

    Shared by the main window (menu-driven edits) and the Character tab's
    Actors panel (AdapterFamilyWidget), neither of which should duplicate
    this sync logic.
    """
    from asteria.runtime import Animator2DComponent, SpriteRenderer2D

    from .commands import AddComponentCommand, CommandTransaction
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
    clip_set_id, clips = _walking_clips(document, sprite_sheet_asset_id)
    for entity, renamed in linked_entities(document, actor_id):
        if renamed and actor is not None and entity.name != actor.display_name:
            tx.add(build_rename_command(entity, actor.display_name))
        sprite = entity.try_get(SpriteRenderer2D)
        if sprite is None:
            new_sprite = SpriteRenderer2D()
            for field_name, value in target_fields.items():
                setattr(new_sprite, field_name, value)
            tx.add(AddComponentCommand(entity, new_sprite))
        else:
            _set_fields(tx, sprite, target_fields)
        animator = entity.try_get(Animator2DComponent)
        if animator is not None and clip_set_id:  # the new sheet walks with its own clips
            fields = {"clip_set_id": clip_set_id}
            if animator.default_clip not in clips:
                fields["default_clip"] = _standing_clip(clips)
            _set_fields(tx, animator, fields)
    if tx.commands:
        document.execute(tx)
    return True


def _set_fields(tx, target, fields):
    from .commands import SetAttributeCommand

    for field_name, new_value in fields.items():
        old_value = getattr(target, field_name)
        if old_value != new_value:
            label = f"Set {field_name}"
            tx.add(SetAttributeCommand(target, field_name, new_value, old_value, label))


def _walking_clips(document, sheet_id):
    """``(clip set id, clip names)`` of the animations that go with a sprite sheet (the
    animation file beside it), or ``(None, ())``."""
    from .picture_categories import paired_clip_set_id

    project = document.project
    clip_set_id = paired_clip_set_id(project, project.assets.get(str(sheet_id)))
    views = getattr(document, "asset_views", None)
    clip_set = views.clip_set(clip_set_id) if views is not None and clip_set_id else None
    if clip_set is None:
        return None, ()
    return clip_set_id, tuple(clip_set.clips)


def _standing_clip(clips):
    for name in ("idle_down", "idle", *clips):
        if name in clips:
            return name
    return ""


def standing_frame(document, sheet_id):
    """The frame a sheet's character stands in (its idle clip's first frame), else 0."""
    clip_set_id, clips = _walking_clips(document, sheet_id)
    if not clip_set_id:
        return 0
    clip = document.asset_views.clip_set(clip_set_id).clips.get(_standing_clip(clips))
    keyframes = getattr(clip, "keyframes", None) or ()
    return int(keyframes[0].frame_index) if keyframes else 0
