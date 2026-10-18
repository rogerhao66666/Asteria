"""Scene cameras on the main character, and the Player's place as the game start (project data).

``center(data)`` edits saved project data: each Camera2D follows the game start's player entity
and stands where the player is in that scene (else where a TRANSFER brings them, else unchanged);
a game start position that only repeats where the Player entity stands is cleared, so moving the
Player in the editor moves the start. Running it twice changes nothing.
"""

from __future__ import annotations


def _transform(entity):
    for component in entity.get("components", ()):
        if component["type"] == "asteria.Transform":
            return component["fields"]
    return None


def _arrivals(data):
    """``{scene_id: (x, y)}``: the first place a TRANSFER puts the player in each scene."""
    found = {}

    def walk(value):
        if isinstance(value, dict):
            if value.get("command") == "TRANSFER" and isinstance(value.get("args"), dict):
                args = value["args"]
                if args.get("scene_id") and "x" in args and "y" in args:
                    found.setdefault(args["scene_id"], (float(args["x"]), float(args["y"])))
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(data.get("event_programs", {}))
    return found


def add_missing_cameras(data, *, width=320, height=180):
    """Give every scene without a Camera2D entity one (named "Camera"), active, at the default
    size; ``center`` then aims it at the player. Returns how many were added."""
    import uuid

    from asteria.core import Entity, Transform
    from asteria.core.serialization import serialize_entity
    from asteria.runtime.components2d import Camera2DComponent

    added = 0
    for scene in data.get("scenes", ()):
        entities = scene.setdefault("entities", [])
        if any(c["type"] == "asteria.Camera2D" for e in entities for c in e.get("components", ())):
            continue
        entity_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"asteria-camera:{scene['id']}"))
        entity = Entity("Camera", entity_id=entity_id)
        entity.add_component(Transform(0.0, 0.0))
        camera = entity.add_component(Camera2DComponent())
        camera.width, camera.height = int(width), int(height)
        entities.append(serialize_entity(entity))
        added += 1
    return added


def center(data):
    """Edit project data in place; returns how many cameras were moved or re-aimed."""
    start = data.get("game_start") or {}
    player_id = start.get("player_entity_id") or ""
    arrivals = _arrivals(data)
    changed = 0
    for scene in data.get("scenes", ()):
        entities = scene.get("entities", ())
        player = next((e for e in entities if e.get("id") == player_id), None)
        spot = None
        if player is not None and _transform(player) is not None:
            t = _transform(player)
            spot = (float(t["x"]), float(t["y"]))
            if start.get("player_position") is not None and start.get("scene_id") == scene["id"]:
                if [float(v) for v in start["player_position"]] == list(spot):
                    start["player_position"] = None  # the Player's own place is the start
        if spot is None:
            spot = arrivals.get(scene["id"])
        for entity in entities:
            camera = next(
                (c for c in entity.get("components", ()) if c["type"] == "asteria.Camera2D"), None
            )
            transform = _transform(entity)
            if camera is None or transform is None:
                continue
            before = (camera["fields"].get("follow_entity_id"), transform["x"], transform["y"])
            if player_id:
                camera["fields"]["follow_entity_id"] = player_id
            if spot is not None:
                transform["x"], transform["y"] = spot
            if before != (
                camera["fields"].get("follow_entity_id"),
                transform["x"],
                transform["y"],
            ):
                changed += 1
    return changed
