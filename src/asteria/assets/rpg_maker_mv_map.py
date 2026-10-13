"""RPG Maker MV map boundary models and Asteria scene conversion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from asteria.core import Entity, Scene, Transform
from asteria.runtime import SpriteRenderer2D, TileMap2DComponent

from .local_reference import RPGMakerMVProjectLayout
from .rpg_maker_mv_catalog import RPGMakerMVCatalog

_MV_ID_NAMESPACE = UUID("adabcfcb-dd74-4dc5-870b-55dd5efb7184")


def _stable_id(kind: str, source_id: int) -> str:
    return str(uuid5(_MV_ID_NAMESPACE, f"{kind}:{int(source_id)}"))


@dataclass(frozen=True, slots=True)
class MVMapEntry:
    map_id: int
    name: str
    path: Path
    parent_id: int = 0
    order: int = 0


@dataclass(frozen=True, slots=True)
class MVEncounter:
    troop_id: int
    weight: int
    regions: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class MVEventImage:
    character_name: str = ""
    character_index: int = 0
    direction: int = 2
    pattern: int = 1
    tile_id: int = 0


@dataclass(frozen=True, slots=True)
class MVMapEvent:
    id: int
    name: str
    x: int
    y: int
    image: MVEventImage
    raw: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RPGMakerMVMap:
    map_id: int
    name: str
    display_name: str
    width: int
    height: int
    tileset_id: int
    parallax_name: str
    scroll_type: int
    layers: tuple[tuple[int, ...], ...]
    encounters: tuple[MVEncounter, ...]
    events: tuple[MVMapEvent, ...]

    @classmethod
    def load(cls, path: Path, *, map_id: int, name: str = "") -> RPGMakerMVMap:
        source = Path(path)
        try:
            raw = json.loads(source.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid RPG Maker MV map JSON: {source.name}") from exc
        if not isinstance(raw, dict):
            raise ValueError(f"invalid RPG Maker MV map object: {source.name}")
        width, height = int(raw.get("width", 0)), int(raw.get("height", 0))
        if width <= 0 or height <= 0:
            raise ValueError("invalid map dimensions")
        data = raw.get("data")
        layer_size = width * height
        if not isinstance(data, list) or len(data) != layer_size * 6:
            raise ValueError("map data must contain exactly six layers")
        if any(not isinstance(tile, int) or tile < 0 for tile in data):
            raise ValueError("invalid tile id")
        layers = tuple(tuple(data[i * layer_size : (i + 1) * layer_size]) for i in range(6))
        encounters = tuple(
            MVEncounter(
                int(item.get("troopId", 0)),
                int(item.get("weight", 0)),
                tuple(int(region) for region in item.get("regionSet", ())),
            )
            for item in raw.get("encounterList", ())
            if isinstance(item, dict)
        )
        events = []
        for item in raw.get("events", ()):
            if not isinstance(item, dict):
                continue
            pages = item.get("pages") or ()
            image = pages[0].get("image", {}) if pages and isinstance(pages[0], dict) else {}
            events.append(
                MVMapEvent(
                    int(item.get("id", 0)),
                    str(item.get("name", "")),
                    int(item.get("x", 0)),
                    int(item.get("y", 0)),
                    MVEventImage(
                        str(image.get("characterName", "")),
                        int(image.get("characterIndex", 0)),
                        int(image.get("direction", 2)),
                        int(image.get("pattern", 1)),
                        int(image.get("tileId", 0)),
                    ),
                    tuple(
                        (key, value)
                        for key, value in sorted(item.items())
                        if key not in {"id", "name", "x", "y"}
                    ),
                )
            )
        return cls(
            int(map_id),
            str(name or raw.get("displayName") or f"Map{int(map_id):03d}"),
            str(raw.get("displayName", "")),
            width,
            height,
            int(raw.get("tilesetId", 0)),
            str(raw.get("parallaxName", "")),
            int(raw.get("scrollType", 0)),
            layers,
            encounters,
            tuple(events),
        )


def discover_mv_maps(layout: RPGMakerMVProjectLayout) -> tuple[MVMapEntry, ...]:
    path = layout.data / "MapInfos.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid RPG Maker MV JSON: MapInfos.json") from exc
    if not isinstance(raw, list):
        raise ValueError("invalid RPG Maker MV map index")
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        map_id = int(item.get("id", 0))
        map_path = layout.data / f"Map{map_id:03d}.json"
        if map_path.is_file():
            entries.append(
                MVMapEntry(
                    map_id,
                    str(item.get("name", f"Map{map_id:03d}")),
                    map_path.resolve(),
                    int(item.get("parentId", 0)),
                    int(item.get("order", 0)),
                )
            )
    return tuple(sorted(entries, key=lambda item: (item.order, item.map_id)))


_MV_DIRECTION_ROW = {2: 0, 4: 1, 6: 2, 8: 3}
_MV_FACING = {2: "down", 4: "left", 6: "right", 8: "up"}


def _first_page(event: MVMapEvent):
    pages = dict(event.raw).get("pages") or ()
    return pages[0] if pages and isinstance(pages[0], dict) else None


def _vanish_page(event: MVMapEvent, channel: str):
    """True when turning self switch ``channel`` on selects an empty page (no image, no commands):
    the
    common "talk once, then the event is gone" idiom."""
    for page in (dict(event.raw).get("pages") or ())[1:]:
        c = page.get("conditions") or {}
        only_self = c.get("selfSwitchValid") and c.get("selfSwitchCh") == channel
        others = any(
            c.get(k)
            for k in ("switch1Valid", "switch2Valid", "variableValid", "itemValid", "actorValid")
        )
        image = page.get("image") or {}
        empty = not image.get("characterName") and not image.get("tileId")
        commands = [cmd for cmd in page.get("list") or () if cmd.get("code") != 0]
        if only_self and not others:
            return empty and not commands
    return False


def npc_id_for(mv_map: RPGMakerMVMap, event: MVMapEvent) -> str:
    return f"mv.map{mv_map.map_id:03d}.event{event.id:03d}"


def convert_event_page(mv_map: RPGMakerMVMap, event: MVMapEvent):
    """``(trigger, instructions, unsupported)`` for the event's first page.

    Supported: Show Text (101/401) -> DIALOGUE, Transfer Player with direct coordinates
    (201) -> WORLD TRANSFER to the imported scene, Wait (230) -> WAIT, Control Self Switch ON
    (123) whose page is empty -> WORLD SET_NPC visible=false (the event's NPC state). Triggers:
    action
    button -> ``action``; player/event touch -> ``touch``; autorun / parallel -> ``None``
    (not converted). Every other command is listed in ``unsupported`` (never dropped silently).
    """
    from asteria.events import EventInstruction

    page = _first_page(event)
    if page is None:
        return None, (), ()
    trigger = {0: "action", 1: "touch", 2: "touch"}.get(int(page.get("trigger", 0)))
    instructions, unsupported, text = [], [], []

    def flush():
        if text:
            instructions.append(
                EventInstruction("DIALOGUE", {"speaker": "", "text": "\n".join(text)})
            )
            text.clear()

    for command in page.get("list") or ():
        code, params = int(command.get("code", 0)), command.get("parameters") or []
        if code == 401:
            text.append(str(params[0]) if params else "")
            continue
        flush()
        if code in (0, 101):
            continue
        if code == 201 and params and int(params[0]) == 0:
            target, x, y, direction = (
                int(params[1]),
                int(params[2]),
                int(params[3]),
                int(params[4]),
            )
            args = {
                "scene_id": _stable_id("map", target),
                "x": float(x * 48 + 24),
                "y": float(y * 48 + 40),
            }
            if direction in _MV_FACING:
                args["facing"] = _MV_FACING[direction]
            instructions.append(EventInstruction("WORLD", {"command": "TRANSFER", "args": args}))
        elif code == 230 and params:
            instructions.append(EventInstruction("WAIT", {"seconds": int(params[0]) / 60.0}))
        elif (
            code == 123
            and len(params) >= 2
            and int(params[1]) == 0
            and _vanish_page(event, str(params[0]))
        ):
            args = {"npc": npc_id_for(mv_map, event), "key": "visible", "value": False}
            instructions.append(EventInstruction("WORLD", {"command": "SET_NPC", "args": args}))
        else:
            unsupported.append(code)
    flush()
    return trigger, tuple(instructions), tuple(unsupported)


def to_asteria_scene(
    mv_map: RPGMakerMVMap,
    catalog: RPGMakerMVCatalog,
    *,
    baked=None,
    characters=None,
    start=None,
    event_programs=None,
    issues=None,
) -> Scene:
    """Scene for an MV map. ``baked`` (``BakedMap``) binds the canonical tilemap; ``characters``
    maps
    ``(character_name, index)`` to ``BakedCharacter``; ``start`` = ``(x, y, character_key)`` adds
    the
    player (feet in its start cell, MV walking speed) and a follow camera. With ``event_programs``
    (the
    project's library) each event's first page becomes an event program on an ``Interaction2D``;
    anything not converted is appended to ``issues`` as ``(code, message)``.

    Without ``baked`` the tile map binding stays empty (never a dangling asset id).
    """
    from asteria.runtime import Animator2DComponent, Camera2DComponent
    from asteria.runtime.character_control import CharacterController2DComponent

    characters = characters or {}
    scene = Scene(mv_map.display_name or mv_map.name, scene_id=_stable_id("map", mv_map.map_id))
    host = scene.add_entity(Entity("Tile Map", entity_id=_stable_id("map-tiles", mv_map.map_id)))
    host.add_component(Transform())
    tilemap = host.add_component(TileMap2DComponent())
    tilemap.tilemap_asset_id = "" if baked is None else baked.tilemap_id
    for event in mv_map.events:
        entity = scene.add_entity(
            Entity(
                event.name or f"Event {event.id}",
                entity_id=str(uuid5(_MV_ID_NAMESPACE, f"map:{mv_map.map_id}:event:{event.id}")),
            )
        )
        entity.add_component(
            Transform(event.x * 48 + 24, event.y * 48 + 40)
        )  # feet: same as the player
        if event.image.character_name:
            sprite = entity.add_component(SpriteRenderer2D())
            baked_character = characters.get(
                (event.image.character_name, event.image.character_index)
            )
            sprite.sprite_sheet_asset_id = (
                "" if baked_character is None else baked_character.sprite_sheet_id
            )
            row = _MV_DIRECTION_ROW.get(event.image.direction, 0)
            sprite.frame_index = row * 3 + max(0, min(2, event.image.pattern))
        entity.rpg_maker_mv_event = event
        from asteria.runtime.npc_state import NpcIdentity2DComponent

        entity.add_component(NpcIdentity2DComponent()).npc_id = npc_id_for(
            mv_map, event
        )  # saved event state
        page = _first_page(event)
        if (
            page is not None
            and int(page.get("priorityType", 0)) == 1
            and not page.get("through", False)
        ):
            from asteria.runtime.collision import Collider2DComponent

            solid = entity.add_component(
                Collider2DComponent()
            )  # "same as characters": blocks the player
            solid.width = solid.height = 46.0
            solid.offset_y = -16.0  # centred on the event's cell (feet are 40 px into it)
        if event_programs is not None:
            from asteria.events import EventProgram
            from asteria.runtime import Interaction2DComponent

            trigger, instructions, unsupported = convert_event_page(mv_map, event)
            where = f"map {mv_map.map_id} event {event.id} ({event.name})"
            if unsupported and issues is not None:
                issues.append(
                    (
                        "event.unsupported_commands",
                        f"{where}: commands {sorted(set(unsupported))} kept out",
                    )
                )
            pages = dict(event.raw).get("pages") or ()
            vanishes = any(_vanish_page(event, ch) for ch in "ABCD")
            if len(pages) > (2 if vanishes else 1) and issues is not None:
                issues.append(
                    (
                        "event.extra_pages",
                        f"{where}: only the first of {len(pages)} pages is converted",
                    )
                )
            if trigger is None and instructions and issues is not None:
                issues.append(
                    ("event.trigger", f"{where}: autorun / parallel pages are not converted")
                )
            if trigger is not None and instructions:
                program_id = npc_id_for(mv_map, event)
                event_programs.register(program_id, EventProgram(instructions))
                interaction = entity.add_component(Interaction2DComponent())
                interaction.event_program_id = program_id
                interaction.trigger = trigger
                interaction.require_facing = trigger == "action"
                interaction.range = 56.0 if trigger == "action" else 20.0
    if start is not None and characters.get(start[2]) is not None:
        x, y, key = start
        baked_character = characters[key]
        player = scene.add_entity(
            Entity("Player", entity_id=_stable_id("map-player", mv_map.map_id))
        )
        player.add_component(
            Transform(x * 48 + 24, y * 48 + 40)
        )  # collision box stays inside the cell
        sprite = player.add_component(SpriteRenderer2D())
        sprite.sprite_sheet_asset_id = baked_character.sprite_sheet_id
        sprite.frame_index = 1
        sprite.layer = 5
        animator = player.add_component(Animator2DComponent())
        animator.clip_set_id = baked_character.animation_id
        animator.default_clip = "idle_down"
        controller = player.add_component(CharacterController2DComponent())
        controller.speed = 180.0  # MV move speed 4: 1/16 tile per frame at 60 fps
        controller.half_width = 14.0
        controller.half_height = (
            19.0  # the box stands on the feet: most of the cell, like an MV character
        )
        camera_entity = scene.add_entity(
            Entity("Camera", entity_id=_stable_id("map-camera", mv_map.map_id))
        )
        camera_entity.add_component(Transform(x * 48 + 24, y * 48 + 24))
        camera = camera_entity.add_component(Camera2DComponent())
        camera.width, camera.height = 816, 624  # the MV screen
        camera.follow_entity_id = player.id
        camera.smoothing = 12.0
    return scene
