import json
from pathlib import Path

from asteria.assets import (
    AssetRegistry,
    deserialize_asset_registry,
    serialize_asset_registry,
)
from asteria.core.ids import new_id, validate_id
from asteria.core.serialization import deserialize_scene, serialize_scene
from asteria.events import EventProgram, EventProgramRegistry, SceneEventBindings
from asteria.events.lifecycle_bridge import LifecycleEventBinding
from asteria.gameplay import GameplayLibrary
from asteria.rpg import RpgDatabase


class Project:
    SCHEMA = "asteria.project"
    VERSION = 6

    def __init__(
        self,
        name,
        *,
        project_id=None,
        startup_scene_id=None,
        assets=None,
        event_programs=None,
        scene_event_bindings=None,
        rpg_database=None,
        lifecycle_event_bindings=None,
        gameplay_library=None,
    ):
        self.id = validate_id(project_id) if project_id else new_id()
        self.name = str(name)
        self.startup_scene_id = startup_scene_id
        self.assets = assets or AssetRegistry()
        self.event_programs = event_programs or EventProgramRegistry()
        self.scene_event_bindings = dict(scene_event_bindings or {})
        if rpg_database is not None and not isinstance(rpg_database, RpgDatabase):
            raise TypeError("rpg_database must be RpgDatabase")
        self.rpg_database = rpg_database or RpgDatabase()
        if gameplay_library is not None and not isinstance(
            gameplay_library, GameplayLibrary
        ):
            raise TypeError("gameplay_library must be GameplayLibrary")
        self.gameplay_library = gameplay_library or GameplayLibrary()
        self.lifecycle_event_bindings = list(lifecycle_event_bindings or ())
        if any(
            not isinstance(x, LifecycleEventBinding)
            for x in self.lifecycle_event_bindings
        ):
            raise TypeError(
                "lifecycle_event_bindings must contain LifecycleEventBinding values"
            )
        self._scenes = {}

    def add_scene(self, scene):
        if scene.id in self._scenes:
            raise ValueError("duplicate scene id")
        self._scenes[scene.id] = scene
        if self.startup_scene_id is None:
            self.startup_scene_id = scene.id
        return scene

    def scenes(self):
        return tuple(self._scenes.values())

    def scene(self, scene_id):
        return self._scenes.get(scene_id)

    def scene_index(self, scene):
        if scene.id not in self._scenes:
            raise ValueError("Scene does not belong to project")
        return list(self._scenes).index(scene.id)

    def move_scene(self, scene, new_index):
        if scene.id not in self._scenes:
            raise ValueError("Scene does not belong to project")
        items = list(self._scenes.items())
        count = len(items)
        if count <= 1:
            return 0
        old = self.scene_index(scene)
        new_index = max(0, min(int(new_index), count - 1))
        if old == new_index:
            return old
        item = items.pop(old)
        items.insert(new_index, item)
        self._scenes = dict(items)
        return old

    def detach_scene(self, scene):
        if scene.id not in self._scenes:
            raise ValueError("Scene does not belong to project")
        if len(self._scenes) <= 1:
            raise ValueError("Project must keep at least one scene")
        idx = self.scene_index(scene)
        del self._scenes[scene.id]
        if self.startup_scene_id == scene.id:
            self.startup_scene_id = next(iter(self._scenes))
        return idx

    def validate(self, *, validate_gameplay_refs=True):
        if not self._scenes:
            raise ValueError("project requires scene")
        if self.startup_scene_id not in self._scenes:
            raise ValueError("invalid startup scene")
        self.assets.validate()
        self.rpg_database.validate()
        for scene_id in self.scene_event_bindings:
            if scene_id not in self._scenes:
                raise ValueError("event bindings reference unknown scene")
        for binding in self.lifecycle_event_bindings:
            if binding.event_program_id not in self.event_programs.ids():
                raise ValueError("lifecycle binding references unknown event program")
        if validate_gameplay_refs:
            known = set(self.gameplay_library.abilities.ids())
            refs = []
            for actor in self.rpg_database.actors.values():
                refs.extend((f"actor {actor.actor_id}", x) for x in actor.abilities)
            for cls in self.rpg_database.classes.values():
                refs.extend((f"class {cls.class_id}", x) for x in cls.granted_abilities)
            for equipment in self.rpg_database.equipment.values():
                refs.extend(
                    (f"equipment {equipment.equipment_id}", x)
                    for x in equipment.granted_abilities
                )
            for attachment in self.rpg_database.attachments.values():
                refs.extend(
                    (f"attachment {attachment.attachment_id}", x)
                    for x in attachment.granted_abilities
                )
            for enemy in self.rpg_database.enemies.values():
                refs.extend((f"enemy {enemy.enemy_id}", x) for x in enemy.abilities)
            for track in self.rpg_database.progression_tracks.values():
                for milestone in track.milestones:
                    refs.extend(
                        (f"progression {track.track_id} rank {milestone.rank}", x)
                        for x in milestone.granted_abilities
                    )
            missing = [
                f"{owner} references unknown ability {ability_id}"
                for owner, ability_id in refs
                if ability_id not in known
            ]
            if missing:
                raise ValueError(
                    "invalid RPG gameplay references: " + "; ".join(sorted(missing))
                )
        return True

    def to_data(self):
        self.validate()
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "id": self.id,
            "name": self.name,
            "startup_scene_id": self.startup_scene_id,
            "assets": serialize_asset_registry(self.assets),
            "scenes": [serialize_scene(s) for s in self.scenes()],
            "event_programs": {
                program_id: self.event_programs.require(program_id).to_data()
                for program_id in self.event_programs.ids()
            },
            "scene_event_bindings": {
                scene_id: bindings.to_data()
                for scene_id, bindings in self.scene_event_bindings.items()
            },
            "rpg_database": self.rpg_database.to_data(),
            "gameplay_library": self.gameplay_library.to_data(),
            "lifecycle_event_bindings": [
                binding.to_data() for binding in self.lifecycle_event_bindings
            ],
        }

    @classmethod
    def from_data(cls, data, registry):
        version = data.get("version")
        if data.get("schema") != cls.SCHEMA or version not in {2, 3, 4, 5, 6}:
            raise ValueError("unsupported project")

        expected_v2 = {
            "schema",
            "version",
            "id",
            "name",
            "startup_scene_id",
            "assets",
            "scenes",
        }
        expected_v3 = expected_v2 | {"event_programs", "scene_event_bindings"}
        expected_v4 = expected_v3 | {"rpg_database"}
        expected_v5 = expected_v4 | {"lifecycle_event_bindings"}
        expected_v6 = expected_v5 | {"gameplay_library"}
        expected = (
            expected_v6
            if version == 6
            else expected_v5
            if version == 5
            else expected_v4
            if version == 4
            else expected_v3
            if version == 3
            else expected_v2
        )
        if set(data) != expected:
            raise ValueError("invalid project record")

        programs = EventProgramRegistry()
        bindings_by_scene = {}
        if version >= 3:
            if not isinstance(data["event_programs"], dict):
                raise TypeError("event_programs must be a dict")
            if not isinstance(data["scene_event_bindings"], dict):
                raise TypeError("scene_event_bindings must be a dict")
            for program_id, raw in data["event_programs"].items():
                programs.register(program_id, EventProgram.from_data(raw))
            for scene_id, raw in data["scene_event_bindings"].items():
                bindings_by_scene[scene_id] = SceneEventBindings.from_data(raw)

        p = cls(
            data["name"],
            project_id=data["id"],
            startup_scene_id=data["startup_scene_id"],
            assets=deserialize_asset_registry(data["assets"]),
            event_programs=programs,
            scene_event_bindings=bindings_by_scene,
            rpg_database=RpgDatabase.from_data(data["rpg_database"])
            if version >= 4
            else RpgDatabase(),
            gameplay_library=GameplayLibrary.from_data(data["gameplay_library"])
            if version >= 6
            else GameplayLibrary(),
            lifecycle_event_bindings=[
                LifecycleEventBinding.from_data(x)
                for x in data["lifecycle_event_bindings"]
            ]
            if version >= 5
            else (),
        )
        for sd in data["scenes"]:
            p.add_scene(deserialize_scene(sd, registry))
        # Pre-v6 projects had no canonical GameplayLibrary ownership, so they
        # remain readable without inventing missing ability definitions. Saving
        # them as v6 requires the references to be resolved explicitly.
        p.validate(validate_gameplay_refs=(version >= 6))
        return p

    def save_json(self, path):
        Path(path).write_text(
            json.dumps(self.to_data(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def load_json(cls, path, registry):
        return cls.from_data(
            json.loads(Path(path).read_text(encoding="utf-8")), registry
        )
