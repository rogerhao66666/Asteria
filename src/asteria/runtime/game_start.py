from __future__ import annotations

from dataclasses import dataclass

from asteria.events import EventContext
from asteria.rpg import ProgressionRuntime, RpgRuntimeState

from .game_save import GameRuntimeSave


@dataclass(slots=True)
class GameStartDefinition:
    """Canonical authored New Game state stored inside Project.

    This is design data, not a Player Save. Every Run/New Game materializes a
    fresh GameRuntimeSave from this definition.
    """

    scene_id: str | None = None
    player_entity_id: str = ""
    player_facing: str = "down"
    player_position: tuple[float, float] | None = None
    rpg_state_data: dict | None = None
    event_context_data: dict | None = None

    SCHEMA = "asteria.game_start"
    VERSION = 1

    @classmethod
    def from_runtime_save(cls, save):
        return cls(
            save.scene_id,
            save.player_entity_id,
            save.player_facing,
            save.player_position,
            save.rpg_state.to_data(),
            save.event_context.to_data(),
        )

    def instantiate(self, project):
        scene_id = self.scene_id or project.startup_scene_id
        if self.rpg_state_data is None:
            rpg = RpgRuntimeState(
                progression=ProgressionRuntime(project.rpg_database.progression_tracks.values())
            )
        else:
            rpg = RpgRuntimeState.from_data(self.rpg_state_data, project.rpg_database)
        ctx = (
            EventContext()
            if self.event_context_data is None
            else EventContext.from_data(self.event_context_data)
        )
        value = GameRuntimeSave(
            project.id,
            scene_id,
            player_entity_id=self.player_entity_id,
            player_facing=self.player_facing,
            player_position=self.player_position,
            rpg_state=rpg,
            event_context=ctx,
        )
        value.validate(project)
        return value

    def validate(self, project):
        self.instantiate(project)
        return True

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "scene_id": self.scene_id,
            "player_entity_id": self.player_entity_id,
            "player_facing": self.player_facing,
            "player_position": None
            if self.player_position is None
            else list(self.player_position),
            "rpg_state": self.rpg_state_data,
            "event_context": self.event_context_data,
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "scene_id",
            "player_entity_id",
            "player_facing",
            "player_position",
            "rpg_state",
            "event_context",
        }
        if set(data) != expected or data.get("schema") != cls.SCHEMA or data.get("version") != 1:
            raise ValueError("unsupported game start definition")
        return cls(
            data["scene_id"],
            data["player_entity_id"],
            data["player_facing"],
            None if data["player_position"] is None else tuple(data["player_position"]),
            data["rpg_state"],
            data["event_context"],
        )
