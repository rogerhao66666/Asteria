import json
from pathlib import Path

from asteria.assets import AssetRef
from asteria.graphics import (
    SpriteClip,
    SpriteFrame,
    SpriteKeyframe,
    SpriteSheet,
    TileDef,
    Tileset,
)
from asteria.graphics.serialization import tilemap_from_data
from asteria.runtime import AnimationClipSet


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_sprite_sheet(path):
    data = _read(path)
    return SpriteSheet(
        AssetRef(data["texture_asset_id"], "texture"),
        [SpriteFrame(**frame) for frame in data["frames"]],
        scaling=str(data.get("scaling", "pixel")),
    )


def load_tileset(path):
    data = _read(path)
    return Tileset(
        AssetRef(data["sprite_sheet_asset_id"], "sprite_sheet"),
        int(data["tile_width"]),
        int(data["tile_height"]),
        {
            int(tile_id): TileDef(
                int(td["frame_index"]),
                td["collision"],
                td["terrain"],
                tuple(td["tags"]),
                tuple(int(f) for f in td.get("animation", ())),
                float(td.get("frame_ms", 0.0)),
            )
            for tile_id, td in data["tiles"].items()
        },
    )


def load_animation_set(path):
    data = _read(path)
    clips = {}
    for name, cd in data["clips"].items():
        clips[name] = SpriteClip(
            name,
            [
                SpriteKeyframe(
                    int(k["frame_index"]), float(k["duration"]), tuple(k.get("events", ()))
                )
                for k in cd["keyframes"]
            ],
            bool(cd["loop"]),
        )
    machine = None
    if "state_machine" in data:
        from asteria.runtime.animation_state_machine import AnimationStateMachineDefinition

        machine = AnimationStateMachineDefinition.from_data(data["state_machine"])
    return AnimationClipSet(clips, machine)


def load_tilemap(path):
    return tilemap_from_data(_read(path))
