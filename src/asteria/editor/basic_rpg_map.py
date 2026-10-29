"""Reuse the tile-painted ARPG field without its action RPG systems."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

# Boulder pieces of the overworld atlas (tiles 29-34 and 40-42). Each is a fragment of a bigger
# rock, so on the grass they read as stray grey blocks; the starter map leaves them out.
ROCK_TILES = frozenset({29, 30, 31, 32, 33, 34, 40, 41, 42})


def remove_rocks(map_path):
    """Clear the rock fragments (and any blocking tile under them) from a saved tile map."""
    path = Path(map_path)
    data = json.loads(path.read_text())
    cleared = {}
    for layer in data["layers"]:
        for chunk in layer["chunks"]:
            for index, tile in enumerate(chunk["tiles"]):
                if tile in ROCK_TILES:
                    chunk["tiles"][index] = -1
                    cleared.setdefault((chunk["chunk_x"], chunk["chunk_y"]), set()).add(index)
    for layer in data["layers"]:
        if not layer.get("collision_enabled"):
            continue
        for chunk in layer["chunks"]:
            for index in cleared.get((chunk["chunk_x"], chunk["chunk_y"]), ()):
                chunk["tiles"][index] = -1
    path.write_text(json.dumps(data, indent=2) + "\n")


def add_editable_field(folder, source):
    folder, source = Path(folder), Path(source)
    path = folder / "project.asteria.json"
    project = json.loads(path.read_text())
    donor = json.loads((source / "project.asteria.json").read_text())
    shutil.copytree(source / "playable_assets", folder / "editable_map_assets")
    remove_rocks(folder / "editable_map_assets" / "field_map.json")
    for asset in donor["assets"]["assets"]:
        asset["source_path"] = asset["source_path"].replace(
            "playable_assets/", "editable_map_assets/", 1
        )
    project["assets"]["assets"].extend(donor["assets"]["assets"])
    town, field = donor["scenes"][:2]
    scene = copy.deepcopy(field)
    scene["name"] = "Training Meadow"
    scene["entities"] = [
        e for e in scene["entities"] if e["name"] in ("Map", "Camera", "Combat Scene")
    ]
    player = copy.deepcopy(next(e for e in town["entities"] if e["name"] == "Player"))
    player["components"] = [
        c
        for c in player["components"]
        if c["type"]
        in (
            "asteria.Transform",
            "asteria.SpriteRenderer2D",
            "asteria.Animator2D",
            "asteria.CharacterController2D",
            "asteria.PlayerInput2D",
            "asteria.ActorLink",
        )
    ]
    for component in player["components"]:
        if component["type"] == "asteria.Transform":
            component["fields"].update(x=64.0, y=232.0)
        if component["type"] == "asteria.ActorLink":
            component["fields"]["actor_id"] = project["rpg_database"]["actors"][0]["actor_id"]
    scene["entities"].append(player)
    for entity in scene["entities"]:
        for component in entity["components"]:
            if component["type"] == "asteria.CombatScene":
                component["fields"]["combat_mode"] = "encounter"
            if component["type"] == "asteria.Camera2D":
                component["fields"]["follow_entity_id"] = player["id"]
    for name, encounter in (("Slime 1", "slime_pit"), ("Skeleton 1", "old_crypt")):
        enemy = copy.deepcopy(next(e for e in field["entities"] if e["name"] == name))
        enemy["components"] = [
            c
            for c in enemy["components"]
            if c["type"]
            in (
                "asteria.Transform",
                "asteria.SpriteRenderer2D",
                "asteria.Animator2D",
            )
        ]
        enemy["components"].append(
            {
                "type": "asteria.VisibleEncounter",
                "version": 1,
                "fields": {
                    "encounter_id": encounter,
                    "remove_on_start": True,
                    "touch_radius": 14.0,
                },
            }
        )
        scene["entities"].append(enemy)
    project["scenes"] = [scene]
    project["startup_scene_id"] = scene["id"]
    project["game_start"].update(
        scene_id=scene["id"],
        player_entity_id=player["id"],
        player_position=[64.0, 232.0],
        player_facing="right",
    )
    from .scene_cameras import center

    center(project)  # the camera on the hero; the Player's place is the start
    path.write_text(json.dumps(project, indent=2) + "\n")
    manifest_path = folder / "playable_test_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["field"]["entity_sprites"] = {}
    manifest["field"]["player_start"] = [64, 232]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
