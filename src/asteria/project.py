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
from asteria.presentation.library import BattlePresentationLibrary
from asteria.runtime.game_start import GameStartDefinition
from asteria.runtime.input_map import InputActionMap
from asteria.core.prefab import PrefabLibrary


class Project:
    SCHEMA = "asteria.project"
    VERSION = 10

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
        battle_presentation_library=None,
        game_start=None,
        input_map=None,
        prefabs=None,
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
        if gameplay_library is not None and not isinstance(gameplay_library, GameplayLibrary):
            raise TypeError("gameplay_library must be GameplayLibrary")
        self.gameplay_library = gameplay_library or GameplayLibrary()
        if battle_presentation_library is not None and not isinstance(
            battle_presentation_library, BattlePresentationLibrary
        ):
            raise TypeError("battle_presentation_library must be BattlePresentationLibrary")
        self.battle_presentation_library = battle_presentation_library or BattlePresentationLibrary()
        if game_start is not None and not isinstance(game_start, GameStartDefinition):
            raise TypeError("game_start must be GameStartDefinition")
        self.game_start = game_start or GameStartDefinition(startup_scene_id)
        if input_map is not None and not isinstance(input_map, InputActionMap):
            raise TypeError("input_map must be InputActionMap")
        self.input_map = input_map or InputActionMap.default()
        if prefabs is not None and not isinstance(prefabs, PrefabLibrary):
            raise TypeError("prefabs must be PrefabLibrary")
        self.prefabs = prefabs or PrefabLibrary()
        self.lifecycle_event_bindings = list(lifecycle_event_bindings or ())
        if any(not isinstance(x, LifecycleEventBinding) for x in self.lifecycle_event_bindings):
            raise TypeError("lifecycle_event_bindings must contain LifecycleEventBinding values")
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
        self.battle_presentation_library.validate()
        self.game_start.validate(self)
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
                refs.extend((f"equipment {equipment.equipment_id}", x) for x in equipment.granted_abilities)
            for attachment in self.rpg_database.attachments.values():
                refs.extend((f"attachment {attachment.attachment_id}", x) for x in attachment.granted_abilities)
            for enemy in self.rpg_database.enemies.values():
                refs.extend((f"enemy {enemy.enemy_id}", x) for x in enemy.abilities)
            for track in self.rpg_database.progression_tracks.values():
                for milestone in track.milestones:
                    refs.extend(
                        (f"progression {track.track_id} rank {milestone.rank}", x) for x in milestone.granted_abilities
                    )
            for passive in self.rpg_database.passives.values():
                refs.extend((f"passive {passive.passive_id}", x) for x in passive.granted_abilities)
            for rule in self.rpg_database.ability_evolutions.values():
                refs.append((f"ability evolution {rule.rule_id} source", rule.source_ability_id))
                refs.append((f"ability evolution {rule.rule_id} result", rule.result_ability_id))
            for graph in self.rpg_database.progression_graphs.values():
                for node in graph.nodes:
                    for rank, reward in enumerate(node.rewards, start=1):
                        refs.extend(
                            (f"progression graph {graph.graph_id} node {node.node_id} rank {rank}", x)
                            for x in reward.granted_abilities
                        )
            for growth in self.rpg_database.equipment_growth.values():
                for node in growth.nodes:
                    for rank, reward in enumerate(node.rewards, start=1):
                        refs.extend(
                            (f"equipment growth {growth.growth_id} node {node.node_id} rank {rank}", x)
                            for x in reward.granted_abilities
                        )
            missing = [
                f"{owner} references unknown ability {ability_id}"
                for owner, ability_id in refs
                if ability_id not in known
            ]
            if missing:
                raise ValueError("invalid RPG gameplay references: " + "; ".join(sorted(missing)))
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
                scene_id: bindings.to_data() for scene_id, bindings in self.scene_event_bindings.items()
            },
            "rpg_database": self.rpg_database.to_data(),
            "gameplay_library": self.gameplay_library.to_data(),
            "battle_presentation_library": self.battle_presentation_library.to_data(),
            "game_start": self.game_start.to_data(),
            "input_map": self.input_map.to_data(),
            "prefabs": self.prefabs.to_data(),
            "lifecycle_event_bindings": [binding.to_data() for binding in self.lifecycle_event_bindings],
        }

    @classmethod
    def from_data(cls, data, registry):
        version = data.get("version")
        if data.get("schema") != cls.SCHEMA or version not in {2, 3, 4, 5, 6, 7, 8, 9, 10}:
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
        expected_v7 = expected_v6 | {"battle_presentation_library"}
        expected_v8 = expected_v7 | {"game_start"}
        expected_v9 = expected_v8 | {"input_map"}
        expected_v10 = expected_v9 | {"prefabs"}
        expected = (
            expected_v10
            if version == 10
            else expected_v9
            if version == 9
            else expected_v8
            if version == 8
            else expected_v7
            if version == 7
            else expected_v6
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
            rpg_database=RpgDatabase.from_data(data["rpg_database"]) if version >= 4 else RpgDatabase(),
            gameplay_library=GameplayLibrary.from_data(data["gameplay_library"]) if version >= 6 else GameplayLibrary(),
            battle_presentation_library=BattlePresentationLibrary.from_data(data["battle_presentation_library"])
            if version >= 7
            else BattlePresentationLibrary(),
            game_start=GameStartDefinition.from_data(data["game_start"])
            if version >= 8
            else GameStartDefinition(data["startup_scene_id"]),
            input_map=InputActionMap.from_data(data["input_map"]) if version >= 9 else InputActionMap.default(),
            prefabs=PrefabLibrary.from_data(data["prefabs"]) if version >= 10 else PrefabLibrary(),
            lifecycle_event_bindings=[LifecycleEventBinding.from_data(x) for x in data["lifecycle_event_bindings"]]
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
        return cls.from_data(json.loads(Path(path).read_text(encoding="utf-8")), registry)
