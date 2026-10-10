from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from asteria.events import EventContext
from asteria.rpg import RpgRuntimeState


@dataclass(slots=True)
class GameRuntimeSave:
    project_id: str
    scene_id: str
    player_entity_id: str
    player_facing: str
    player_position: tuple[float, float] | None
    rpg_state: RpgRuntimeState
    event_context: EventContext
    active_event: dict | None

    SCHEMA = "asteria.game_runtime_save"
    VERSION = 2

    def __init__(
        self,
        project_id,
        scene_id,
        *,
        player_entity_id="",
        player_facing="down",
        player_position=None,
        rpg_state,
        event_context=None,
        active_event=None,
    ):
        self.project_id = str(project_id)
        self.scene_id = str(scene_id)
        self.player_entity_id = str(player_entity_id)
        self.player_facing = str(player_facing)
        self.player_position = (
            None if player_position is None else (float(player_position[0]), float(player_position[1]))
        )
        self.rpg_state = rpg_state
        self.event_context = event_context or EventContext()
        # Snapshot of the foreground event that was running when saved (EventRunner.snapshot()).
        self.active_event = None if active_event is None else dict(active_event)

    def validate(self, project):
        if self.project_id != project.id:
            raise ValueError("save belongs to another project")
        if project.scene(self.scene_id) is None:
            raise ValueError("save references unknown scene")
        if self.player_entity_id and project.scene(self.scene_id).get_entity(self.player_entity_id) is None:
            raise ValueError("save references unknown player entity")
        self.rpg_state.validate(project.rpg_database)
        return True

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "project_id": self.project_id,
            "scene_id": self.scene_id,
            "player_entity_id": self.player_entity_id,
            "player_facing": self.player_facing,
            "player_position": None if self.player_position is None else list(self.player_position),
            "rpg_state": self.rpg_state.to_data(),
            "event_context": self.event_context.to_data(),
            "active_event": self.active_event,
        }

    @classmethod
    def from_data(cls, data, project):
        if data.get("schema") != cls.SCHEMA or data.get("version") not in {1, 2}:
            raise ValueError("unsupported game runtime save")
        value = cls(
            data["project_id"],
            data["scene_id"],
            player_entity_id=data.get("player_entity_id", ""),
            player_facing=data.get("player_facing", "down"),
            player_position=data.get("player_position"),
            rpg_state=RpgRuntimeState.from_data(data["rpg_state"], project.rpg_database),
            event_context=EventContext.from_data(data["event_context"]),
            active_event=data.get("active_event"),
        )
        value.validate(project)
        return value

    def save_json(self, path):
        Path(path).write_text(json.dumps(self.to_data(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load_json(cls, path, project):
        return cls.from_data(json.loads(Path(path).read_text(encoding="utf-8")), project)
