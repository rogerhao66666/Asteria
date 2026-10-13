from __future__ import annotations

from pathlib import Path

from asteria.events import EventContext
from asteria.rpg import ProgressionRuntime, RpgRuntimeState
from asteria.runtime.game_save import GameRuntimeSave

from .playmode import create_play_session


class RuntimeStateIntegrationError(RuntimeError):
    pass


class RuntimeStateIntegrationController:
    def __init__(self, document):
        self.document = document
        self.loaded_save = None
        self.loaded_save_path = None

    @property
    def project(self):
        if self.document.project is None:
            raise RuntimeStateIntegrationError("project required")
        return self.document.project

    def new_save(
        self,
        *,
        scene_id=None,
        player_entity_id="",
        player_facing="down",
        player_position=None,
        party_actor_ids=(),
    ):
        p = self.project
        scene_id = scene_id or p.startup_scene_id
        state = RpgRuntimeState(
            progression=ProgressionRuntime(p.rpg_database.progression_tracks.values()),
            party_actor_ids=party_actor_ids,
        )
        value = GameRuntimeSave(
            p.id,
            scene_id,
            player_entity_id=player_entity_id,
            player_facing=player_facing,
            player_position=player_position,
            rpg_state=state,
            event_context=EventContext(),
        )
        value.validate(p)
        self.loaded_save = value
        self.loaded_save_path = None
        return value

    def load_save(self, path):
        value = GameRuntimeSave.load_json(path, self.project)
        self.loaded_save = value
        self.loaded_save_path = Path(path)
        return value

    def save(self, path=None):
        if self.loaded_save is None:
            raise RuntimeStateIntegrationError("no runtime save loaded")
        target = Path(path) if path is not None else self.loaded_save_path
        if target is None:
            raise RuntimeStateIntegrationError("save path required")
        self.loaded_save.validate(self.project)
        self.loaded_save.save_json(target)
        self.loaded_save_path = target
        return target

    def run(self):
        return create_play_session(self.document, runtime_save=self.loaded_save)

    def capture_from_session(self, session):
        if session.runtime_save is None:
            raise RuntimeStateIntegrationError("session has no runtime save")
        session.runtime_save.validate(session.runtime_project)
        self.loaded_save = GameRuntimeSave.from_data(session.runtime_save.to_data(), self.project)
        return self.loaded_save
