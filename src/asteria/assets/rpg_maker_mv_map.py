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
    def load(cls, path: Path, *, map_id: int, name: str = "") -> "RPGMakerMVMap":
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
                int(item.get("troopId", 0)), int(item.get("weight", 0)),
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
            events.append(MVMapEvent(
                int(item.get("id", 0)), str(item.get("name", "")),
                int(item.get("x", 0)), int(item.get("y", 0)),
                MVEventImage(
                    str(image.get("characterName", "")), int(image.get("characterIndex", 0)),
                    int(image.get("direction", 2)), int(image.get("pattern", 1)),
                    int(image.get("tileId", 0)),
                ),
                tuple((key, value) for key, value in sorted(item.items()) if key not in {"id", "name", "x", "y"}),
            ))
        return cls(
            int(map_id), str(name or raw.get("displayName") or f"Map{int(map_id):03d}"),
            str(raw.get("displayName", "")), width, height,
            int(raw.get("tilesetId", 0)), str(raw.get("parallaxName", "")),
            int(raw.get("scrollType", 0)), layers, encounters, tuple(events),
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
            entries.append(MVMapEntry(
                map_id, str(item.get("name", f"Map{map_id:03d}")), map_path.resolve(),
                int(item.get("parentId", 0)), int(item.get("order", 0)),
            ))
    return tuple(sorted(entries, key=lambda item: (item.order, item.map_id)))


def to_asteria_scene(mv_map: RPGMakerMVMap, catalog: RPGMakerMVCatalog) -> Scene:
    scene = Scene(mv_map.display_name or mv_map.name, scene_id=_stable_id("map", mv_map.map_id))
    host = scene.add_entity(Entity("Tile Map", entity_id=_stable_id("map-tiles", mv_map.map_id)))
    host.add_component(Transform())
    tilemap = host.add_component(TileMap2DComponent())
    tilemap.tilemap_asset_id = f"mv.tileset.{mv_map.tileset_id}"
    host.rpg_maker_mv_map = mv_map
    for event in mv_map.events:
        entity = scene.add_entity(Entity(
            event.name or f"Event {event.id}",
            entity_id=str(uuid5(_MV_ID_NAMESPACE, f"map:{mv_map.map_id}:event:{event.id}")),
        ))
        entity.add_component(Transform(event.x * 48 + 24, event.y * 48 + 48))
        if event.image.character_name:
            sprite = entity.add_component(SpriteRenderer2D())
            source = catalog.resolve_image("characters", event.image.character_name)
            sprite.sprite_sheet_asset_id = "" if source is None else source.stem
            sprite.frame_index = event.image.pattern
        entity.rpg_maker_mv_event = event
    return scene
