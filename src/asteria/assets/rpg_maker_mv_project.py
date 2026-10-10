"""Conservative RPG Maker MV to Asteria project conversion."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import ActorDefinition, ClassDefinition, EquipmentDefinition, ItemDefinition

from .local_reference import RPGMakerMVProjectLayout
from .rpg_maker_mv_catalog import RPGMakerMVCatalog
from .rpg_maker_mv_database import MVReferenceIssue, RPGMakerMVDatabase
from .rpg_maker_mv_map import RPGMakerMVMap, discover_mv_maps, to_asteria_scene


def _thaw(value: Any) -> Any:
    if isinstance(value, tuple):
        if all(isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str) for item in value):
            return {key: _thaw(item) for key, item in value}
        return [_thaw(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class RPGMakerMVProjectImport:
    project: Project
    issues: tuple[MVReferenceIssue, ...]
    source_ids: dict[str, dict[int, str]]
    source_metadata: dict[str, dict[int, dict[str, Any]]]


class RPGMakerMVProjectImporter:
    @staticmethod
    def import_project(
        layout: RPGMakerMVProjectLayout, *, map_ids: Iterable[int] | None = None
    ) -> RPGMakerMVProjectImport:
        database = RPGMakerMVDatabase.load(layout)
        catalog = RPGMakerMVCatalog.build(layout, database)
        project = Project(database.system.game_title or layout.root.name)
        issues = list(catalog.issues)
        source_ids: dict[str, dict[int, str]] = {
            key: {} for key in ("actors", "classes", "skills", "items", "equipment", "maps")
        }
        source_metadata: dict[str, dict[int, dict[str, Any]]] = {
            key: {} for key in ("actors", "classes", "skills", "items", "equipment", "maps")
        }

        for asset in catalog.assets:
            project.assets.register(asset)

        for record in database.skills:
            target_id = f"mv.skill.{record.id}"
            project.gameplay_library.add_ability(AbilityDefinition(target_id, tags=("source.mv",)))
            source_ids["skills"][record.id] = target_id
            icon = catalog.icon(record.icon_index)
            metadata = _thaw(record.metadata)
            source_metadata["skills"][record.id] = {
                "name": record.name,
                "icon_index": record.icon_index,
                "icon_box": None if icon is None else icon.box,
                "mv_metadata": metadata,
            }
            if metadata:
                issues.append(
                    MVReferenceIssue(
                        "skill.unsupported_semantics",
                        "Skills.json",
                        f"skill {record.id} retains MV-only semantics as metadata",
                    )
                )

        for record in database.classes:
            target_id = f"mv.class.{record.id}"
            metadata = _thaw(record.metadata)
            learnings = metadata.get("learnings", []) if isinstance(metadata, dict) else []
            abilities = []
            for learning in learnings:
                skill_id = int(learning.get("skillId", 0)) if isinstance(learning, dict) else 0
                target = source_ids["skills"].get(skill_id)
                if target:
                    abilities.append(target)
                elif skill_id:
                    issues.append(
                        MVReferenceIssue(
                            "class.unknown_skill", "Classes.json", f"class {record.id} references skill {skill_id}"
                        )
                    )
            project.rpg_database.add_class(ClassDefinition(target_id, record.name, granted_abilities=abilities))
            source_ids["classes"][record.id] = target_id
            source_metadata["classes"][record.id] = {"mv_metadata": metadata}

        for record in database.actors:
            target_id = f"mv.actor.{record.id}"
            class_id = source_ids["classes"].get(record.class_id)
            project.rpg_database.add_actor(
                ActorDefinition(target_id, record.name, class_id=class_id, tags=("source.mv",))
            )
            source_ids["actors"][record.id] = target_id
            character = catalog.resolve_image("characters", record.character_name) if record.character_name else None
            face = catalog.resolve_image("faces", record.face_name) if record.face_name else None
            battler = catalog.resolve_image("sv_actors", record.battler_name) if record.battler_name else None
            source_metadata["actors"][record.id] = {
                "character": None if character is None else str(character),
                "character_index": record.character_index,
                "face": None if face is None else str(face),
                "face_index": record.face_index,
                "battler": None if battler is None else str(battler),
                "mv_metadata": _thaw(record.metadata),
            }

        for record in database.items:
            target_id = f"mv.item.{record.id}"
            project.rpg_database.add_item(ItemDefinition(target_id, record.name, tags=("source.mv",)))
            source_ids["items"][record.id] = target_id
            icon = catalog.icon(record.icon_index)
            source_metadata["items"][record.id] = {
                "icon_index": record.icon_index,
                "icon_box": None if icon is None else icon.box,
                "mv_metadata": _thaw(record.metadata),
            }

        system_metadata = _thaw(database.system.metadata)
        weapon_types = system_metadata.get("weaponTypes", ())
        for record in (*database.weapons, *database.armors):
            target_id = f"mv.{record.equipment_kind}.{record.id}"
            record_metadata = _thaw(record.metadata)
            type_id = int(record_metadata.get("wtypeId", 0)) if record.equipment_kind == "weapon" else 0
            weapon_type = weapon_types[type_id] if 0 <= type_id < len(weapon_types) else ""
            tags = ("source.mv", record.equipment_kind)
            if weapon_type:
                tags += (f"mv-weapon-type:{weapon_type.lower()}",)
            project.rpg_database.add_equipment(
                EquipmentDefinition(
                    target_id,
                    record.name,
                    slot=record.equipment_kind,
                    tags=tags,
                )
            )
            source_ids["equipment"][record.id if record.equipment_kind == "weapon" else 100000 + record.id] = target_id
            icon = catalog.icon(record.icon_index)
            source_metadata["equipment"][record.id if record.equipment_kind == "weapon" else 100000 + record.id] = {
                "kind": record.equipment_kind,
                "icon_index": record.icon_index,
                "weapon_type": weapon_type,
                "icon_box": None if icon is None else icon.box,
                "mv_metadata": record_metadata,
            }

        entries = discover_mv_maps(layout)
        selected = {entry.map_id for entry in entries} if map_ids is None else {int(value) for value in map_ids}
        for entry in entries:
            if entry.map_id not in selected:
                continue
            mv_map = RPGMakerMVMap.load(entry.path, map_id=entry.map_id, name=entry.name)
            scene = project.add_scene(to_asteria_scene(mv_map, catalog))
            source_ids["maps"][entry.map_id] = scene.id
            source_metadata["maps"][entry.map_id] = {
                "tileset_id": mv_map.tileset_id,
                "display_name": mv_map.display_name,
                "parallax_name": mv_map.parallax_name,
            }

        issues.extend(catalog.issues[len(database.issues) :])
        return RPGMakerMVProjectImport(project, tuple(issues), source_ids, source_metadata)
