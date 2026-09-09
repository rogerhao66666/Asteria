from dataclasses import dataclass

from asteria.core import deserialize_entity, serialize_entity
from asteria.core.ids import new_id

from .commands import AddEntityCommand, DuplicateEntityCommand


@dataclass(frozen=True, slots=True)
class EntityClipboardPayload:
    entity_data: dict


class EditorClipboard:
    def __init__(self):
        self.entity_payload = None

    def copy_entity(self, entity):
        self.entity_payload = EntityClipboardPayload(serialize_entity(entity))
        return self.entity_payload

    def has_entity(self):
        return self.entity_payload is not None


def _freshen(data):
    cloned = dict(data)
    cloned["id"] = new_id()
    cloned["name"] = f"{cloned['name']} Copy"
    return cloned


def build_duplicate_entity_command(entity, registry):
    if entity.scene is None:
        raise ValueError("entity must belong to scene")
    duplicate = deserialize_entity(_freshen(serialize_entity(entity)), registry)
    return DuplicateEntityCommand(entity.scene, entity, duplicate)


def build_paste_entity_command(scene, clipboard, registry):
    if scene is None:
        raise ValueError("scene required")
    if not clipboard.has_entity():
        raise ValueError("clipboard has no entity")
    duplicate = deserialize_entity(
        _freshen(clipboard.entity_payload.entity_data), registry
    )
    return AddEntityCommand(scene, duplicate)
