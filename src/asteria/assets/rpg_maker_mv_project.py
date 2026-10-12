"""Conservative RPG Maker MV to Asteria project conversion."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import ActorDefinition, ClassDefinition, EquipmentDefinition, ItemDefinition

from .canonical import AssetSource, CanonicalAsset
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
        layout: RPGMakerMVProjectLayout, *, map_ids: Iterable[int] | None = None, output_root=None
    ) -> RPGMakerMVProjectImport:
        """Convert an MV project. With ``output_root`` (the new Asteria project folder) every map is baked
        into canonical tile assets there, the party leader becomes the player at the MV start position and
        the game starts on the MV start map (W-18)."""
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

        def menu_icon(icon):
            """An ``mv.icon.<index>`` icon asset (one IconSet cell) for menus; "" for none (MV index 0)."""
            if icon is None or icon.index <= 0:
                return ""
            asset_id = f"mv.icon.{icon.index}"
            if all(a.asset_id != asset_id for a in project.assets.query(kind="icon")):
                x0, y0, x1, y1 = icon.box
                project.assets.register(
                    CanonicalAsset(
                        asset_id,
                        "icon",
                        AssetSource(
                            str(icon.source), provider="rpg_maker_mv", provenance=(("development_fixture", True),)
                        ),
                        tags=frozenset({"source:rpg-maker-mv", "mv:icon"}),
                        metadata=(("region", (x0, y0, x1 - x0, y1 - y0)),),
                    )
                )
            return asset_id

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
            icon = catalog.icon(record.icon_index)
            project.rpg_database.add_item(
                ItemDefinition(target_id, record.name, tags=("source.mv",), icon_id=menu_icon(icon))
            )
            source_ids["items"][record.id] = target_id
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
            icon = catalog.icon(record.icon_index)
            project.rpg_database.add_equipment(
                EquipmentDefinition(
                    target_id,
                    record.name,
                    slot=record.equipment_kind,
                    tags=tags,
                    icon_id=menu_icon(icon),
                )
            )
            source_ids["equipment"][record.id if record.equipment_kind == "weapon" else 100000 + record.id] = target_id
            source_metadata["equipment"][record.id if record.equipment_kind == "weapon" else 100000 + record.id] = {
                "kind": record.equipment_kind,
                "icon_index": record.icon_index,
                "weapon_type": weapon_type,
                "icon_box": None if icon is None else icon.box,
                "mv_metadata": record_metadata,
            }

        entries = discover_mv_maps(layout)
        selected = {entry.map_id for entry in entries} if map_ids is None else {int(value) for value in map_ids}
        system = database.system
        leader = next((a for a in database.actors if system.party_members and a.id == system.party_members[0]), None)
        leader_key = (
            None
            if leader is None or not leader.character_name
            else (
                leader.character_name,
                leader.character_index,
            )
        )
        characters = {}

        def character(key):
            if output_root is None or key in characters:
                return
            from .rpg_maker_mv_map_bake import bake_character

            baked_character = bake_character(catalog, key[0], key[1], output_root)
            characters[key] = baked_character
            if baked_character is None:
                issues.append(MVReferenceIssue("character.missing", "characters", f"character {key} not found"))
            else:
                for record in baked_character.records:
                    project.assets.add(record)

        start_scene = None
        player_entity = None
        for entry in entries:
            if entry.map_id not in selected:
                continue
            mv_map = RPGMakerMVMap.load(entry.path, map_id=entry.map_id, name=entry.name)
            baked = None
            start = None
            if output_root is not None:
                from .rpg_maker_mv_map_bake import bake_map

                baked = bake_map(layout, catalog, mv_map, output_root)
                for record in baked.records:
                    project.assets.add(record)
                for tile_id in baked.unsupported_tiles:
                    issues.append(
                        MVReferenceIssue("map.unsupported_tile", entry.path.name, f"tile {tile_id} has no image")
                    )
                for event in mv_map.events:
                    if event.image.character_name:
                        character((event.image.character_name, event.image.character_index))
                if leader_key is not None and entry.map_id == system.start_map_id:
                    character(leader_key)
                    start = (system.start_x, system.start_y, leader_key)
            else:
                issues.append(
                    MVReferenceIssue("map.not_baked", entry.path.name, "map tiles need an output folder to be baked")
                )
            event_issues = []
            scene = project.add_scene(
                to_asteria_scene(
                    mv_map,
                    catalog,
                    baked=baked,
                    characters=characters,
                    start=start,
                    event_programs=project.event_programs if output_root is not None else None,
                    issues=event_issues,
                )
            )
            issues.extend(MVReferenceIssue(code, entry.path.name, message) for code, message in event_issues)
            if start is not None:
                start_scene = scene
                player_entity = next((e for e in scene.entities() if e.name == "Player"), None)
            source_ids["maps"][entry.map_id] = scene.id
            source_metadata["maps"][entry.map_id] = {
                "tileset_id": mv_map.tileset_id,
                "display_name": mv_map.display_name,
                "parallax_name": mv_map.parallax_name,
                "tilemap_asset_id": None if baked is None else baked.tilemap_id,
                "blocked_cells": None if baked is None else baked.blocked_cells,
            }
        if output_root is not None:  # a door to a map that was not imported would fail at runtime: say so now
            for program_id in project.event_programs.ids():
                for instruction in project.event_programs.get(program_id).instructions:
                    args = instruction.args.get("args", {}) if instruction.opcode == "WORLD" else {}
                    if instruction.args.get("command") == "TRANSFER" and project.scene(args.get("scene_id")) is None:
                        issues.append(
                            MVReferenceIssue(
                                "event.transfer_target_missing",
                                program_id,
                                "transfer to a map that was not imported (import it too, or edit the event)",
                            )
                        )
        if start_scene is not None:
            from asteria.core import Transform
            from asteria.runtime.game_start import GameStartDefinition

            project.startup_scene_id = start_scene.id
            position = None
            if player_entity is not None:
                t = player_entity.get(Transform)
                position = (t.x, t.y)
            project.game_start = GameStartDefinition(
                start_scene.id, "" if player_entity is None else player_entity.id, "down", position
            )

        issues.extend(catalog.issues[len(database.issues) :])
        return RPGMakerMVProjectImport(project, tuple(issues), source_ids, source_metadata)


def import_mv_project(source, output, *, map_ids=None, name=None):
    """Import the MV project folder ``source`` (with ``data/System.json``) as a new Asteria project in ``output``.

    Returns ``(project_path, RPGMakerMVProjectImport)``.
    """
    from pathlib import Path

    from .local_reference import RPGMakerMVProjectLayout

    source, output = Path(source).expanduser().resolve(), Path(output).expanduser().resolve()
    if not (source / "data" / "System.json").is_file():
        raise ValueError(f"{source} is not an RPG Maker MV project (no data/System.json)")
    layout = RPGMakerMVProjectLayout.from_root(source)
    output.mkdir(parents=True, exist_ok=True)
    result = RPGMakerMVProjectImporter.import_project(layout, map_ids=map_ids, output_root=output)
    if name:
        result.project.name = name
    project_path = output / "project.asteria.json"
    result.project.save_json(project_path)
    return project_path, result


def import_mv_main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Import an RPG Maker MV project as a new Asteria project")
    parser.add_argument("source", help="MV project folder (contains data/System.json)")
    parser.add_argument("output", help="new Asteria project folder")
    parser.add_argument("--maps", type=int, nargs="*", help="map ids to import (default: all)")
    args = parser.parse_args(argv)
    project_path, result = import_mv_project(args.source, args.output, map_ids=args.maps)
    print(f"Imported {len(result.project.scenes())} maps into {project_path}")
    for issue in result.issues:
        print(f"  {issue.code}: {issue.message}")
    print(f"Run: asteria-preview {project_path}")
    return 0
