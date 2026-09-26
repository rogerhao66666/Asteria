"""Typed, read-only boundary for RPG Maker MV database JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .local_reference import RPGMakerMVProjectLayout


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple((str(key), _freeze(item)) for key, item in sorted(value.items()))
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _metadata(record: Mapping[str, Any], known: set[str]) -> tuple[tuple[str, Any], ...]:
    return tuple(
        (key, _freeze(value))
        for key, value in sorted(record.items())
        if key not in known
    )


@dataclass(frozen=True, slots=True)
class MVReferenceIssue:
    code: str
    source: str
    message: str


@dataclass(frozen=True, slots=True)
class MVRecord:
    id: int
    name: str
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class MVActorRecord(MVRecord):
    class_id: int = 0
    character_name: str = ""
    character_index: int = 0
    face_name: str = ""
    face_index: int = 0
    battler_name: str = ""


@dataclass(frozen=True, slots=True)
class MVSkillRecord(MVRecord):
    icon_index: int = 0


@dataclass(frozen=True, slots=True)
class MVItemRecord(MVRecord):
    icon_index: int = 0


@dataclass(frozen=True, slots=True)
class MVEquipmentRecord(MVRecord):
    icon_index: int = 0
    equipment_kind: str = ""


@dataclass(frozen=True, slots=True)
class MVSystemRecord:
    game_title: str
    start_map_id: int
    start_x: int
    start_y: int
    party_members: tuple[int, ...]
    metadata: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RPGMakerMVDatabase:
    actors: tuple[MVActorRecord, ...]
    classes: tuple[MVRecord, ...]
    skills: tuple[MVSkillRecord, ...]
    items: tuple[MVItemRecord, ...]
    weapons: tuple[MVEquipmentRecord, ...]
    armors: tuple[MVEquipmentRecord, ...]
    tilesets: tuple[MVRecord, ...]
    system: MVSystemRecord
    issues: tuple[MVReferenceIssue, ...] = ()

    @classmethod
    def load(cls, layout: RPGMakerMVProjectLayout) -> "RPGMakerMVDatabase":
        issues: list[MVReferenceIssue] = []

        def load_json_array(name: str) -> tuple[Mapping[str, Any], ...]:
            path = layout.data / name
            if not path.is_file():
                issues.append(MVReferenceIssue("missing_file", name, f"missing {name}"))
                return ()
            try:
                value = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid RPG Maker MV JSON: {name}") from exc
            if not isinstance(value, list):
                raise ValueError(f"invalid RPG Maker MV array: {name}")
            records = []
            for index, item in enumerate(value):
                if item is None:
                    continue
                if not isinstance(item, dict):
                    raise ValueError(f"invalid RPG Maker MV record: {name}[{index}]")
                records.append(item)
            return tuple(records)

        def generic(name: str) -> tuple[MVRecord, ...]:
            return tuple(
                MVRecord(
                    int(raw.get("id", 0)),
                    str(raw.get("name", "")),
                    _metadata(raw, {"id", "name"}),
                )
                for raw in load_json_array(name)
            )

        actor_known = {
            "id", "name", "classId", "characterName", "characterIndex",
            "faceName", "faceIndex", "battlerName",
        }
        actors = tuple(
            MVActorRecord(
                int(raw.get("id", 0)), str(raw.get("name", "")),
                _metadata(raw, actor_known), int(raw.get("classId", 0)),
                str(raw.get("characterName", "")), int(raw.get("characterIndex", 0)),
                str(raw.get("faceName", "")), int(raw.get("faceIndex", 0)),
                str(raw.get("battlerName", "")),
            )
            for raw in load_json_array("Actors.json")
        )
        classes = generic("Classes.json")

        def icons(name: str, record_type):
            return tuple(
                record_type(
                    int(raw.get("id", 0)), str(raw.get("name", "")),
                    _metadata(raw, {"id", "name", "iconIndex"}),
                    int(raw.get("iconIndex", 0)),
                )
                for raw in load_json_array(name)
            )

        skills = icons("Skills.json", MVSkillRecord)
        items = icons("Items.json", MVItemRecord)

        def equipment(name: str, kind: str):
            return tuple(
                MVEquipmentRecord(
                    int(raw.get("id", 0)), str(raw.get("name", "")),
                    _metadata(raw, {"id", "name", "iconIndex"}),
                    int(raw.get("iconIndex", 0)), kind,
                )
                for raw in load_json_array(name)
            )

        weapons = equipment("Weapons.json", "weapon")
        armors = equipment("Armors.json", "armor")
        tilesets = generic("Tilesets.json")

        system_path = layout.data / "System.json"
        try:
            system_raw = json.loads(system_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid RPG Maker MV JSON: System.json") from exc
        if not isinstance(system_raw, dict):
            raise ValueError("invalid RPG Maker MV object: System.json")
        system_known = {"gameTitle", "startMapId", "startX", "startY", "partyMembers"}
        system = MVSystemRecord(
            str(system_raw.get("gameTitle", "")), int(system_raw.get("startMapId", 0)),
            int(system_raw.get("startX", 0)), int(system_raw.get("startY", 0)),
            tuple(int(item) for item in system_raw.get("partyMembers", ())),
            _metadata(system_raw, system_known),
        )

        class_ids = {record.id for record in classes}
        for actor in actors:
            if actor.class_id and actor.class_id not in class_ids:
                issues.append(MVReferenceIssue(
                    "actor.unknown_class", "Actors.json",
                    f"actor {actor.id} references class {actor.class_id}",
                ))
        return cls(actors, classes, skills, items, weapons, armors, tilesets, system, tuple(issues))
