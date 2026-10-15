"""Native Asteria JSON serialization for editable skeletal rigs."""

from __future__ import annotations

import json
from pathlib import Path

from .skeleton import Bone, Key, Skeleton, SkeletonClip, Slot


def skeleton_to_data(skeleton):
    """Return the versioned project format, preserving every supported rig field."""
    return {
        "schema": "asteria.skeleton",
        "version": 1,
        "skeleton_id": skeleton.skeleton_id,
        "bones": [
            {
                "bone_id": b.bone_id,
                "parent": b.parent,
                "x": b.x,
                "y": b.y,
                "rotation": b.rotation,
                "scale_x": b.scale_x,
                "scale_y": b.scale_y,
                "length": b.length,
            }
            for b in skeleton.bones
        ],
        "slots": [
            {
                "slot_id": s.slot_id,
                "bone_id": s.bone_id,
                "sheet_asset_id": s.sheet_asset_id,
                "frame": s.frame,
                "offset_x": s.offset_x,
                "offset_y": s.offset_y,
                "rotation": s.rotation,
                "z": s.z,
                "visible": s.visible,
            }
            for s in skeleton.slots
        ],
        "clips": [
            {
                "name": clip.name,
                "duration": clip.duration,
                "loop": clip.loop,
                "tracks": [
                    {
                        "bone_id": bone_id,
                        "channel": channel,
                        "keys": [
                            {"time": key.time, "value": key.value, "easing": key.easing}
                            for key in keys
                        ],
                    }
                    for (bone_id, channel), keys in clip.tracks
                ],
                "frames": {
                    slot_id: [[time, frame] for time, frame in rows]
                    for slot_id, rows in clip.frames
                },
            }
            for clip in skeleton.clips.values()
        ],
    }


def skeleton_from_data(data):
    """Load a native rig document. Importer formats stay handled by their own adapters."""
    if data.get("schema") != "asteria.skeleton" or data.get("version") != 1:
        raise ValueError("Unsupported Asteria skeleton schema/version")
    bones = tuple(Bone(**row) for row in data.get("bones", ()))
    slots = tuple(Slot(**row) for row in data.get("slots", ()))
    clips = {}
    for row in data.get("clips", ()):
        tracks = {
            (track["bone_id"], track["channel"]): tuple(Key(**key) for key in track["keys"])
            for track in row.get("tracks", ())
        }
        frames = {
            slot_id: tuple((float(time), int(frame)) for time, frame in values)
            for slot_id, values in row.get("frames", {}).items()
        }
        clip = SkeletonClip(
            row["name"],
            row["duration"],
            loop=row.get("loop", True),
            tracks=tracks,
            frames=frames,
        )
        clips[clip.name] = clip
    return Skeleton(str(data["skeleton_id"]), bones, slots, clips)


def save_skeleton(path, skeleton):
    Path(path).write_text(
        json.dumps(skeleton_to_data(skeleton), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_skeleton(path):
    return skeleton_from_data(json.loads(Path(path).read_text(encoding="utf-8")))
