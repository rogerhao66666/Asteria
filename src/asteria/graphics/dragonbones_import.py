"""Import the supported DragonBones 5.x JSON subset into Asteria's Skeleton model."""

from __future__ import annotations

import math
from collections.abc import Mapping

from .skeleton import Bone, Key, Skeleton, SkeletonClip, Slot


class DragonBonesImportError(ValueError):
    """A DragonBones file is malformed or requires an explicit selection."""


def _armature(data, armature_name):
    if not isinstance(data, Mapping):
        raise DragonBonesImportError("DragonBones data must be a JSON object")
    version = str(data.get("version", "5"))
    if version.split(".", 1)[0] != "5":
        raise DragonBonesImportError("only DragonBones 5.x JSON is supported")
    armatures = data.get("armature")
    if not isinstance(armatures, list) or not armatures:
        raise DragonBonesImportError("DragonBones data needs an armature list")
    if armature_name is None:
        if len(armatures) != 1:
            raise DragonBonesImportError("select an armature with armature_name")
        selected = armatures[0]
    else:
        selected = next((item for item in armatures if item.get("name") == armature_name), None)
        if selected is None:
            raise DragonBonesImportError(f"unknown armature {armature_name!r}")
    if not isinstance(selected, Mapping) or not selected.get("bone"):
        raise DragonBonesImportError("the selected armature needs a bone list")
    return selected


def _skin(armature, skin_name):
    skins = armature.get("skin", ())
    if not skins:
        return {"name": "default", "slot": []}
    if not isinstance(skins, list):
        raise DragonBonesImportError("armature skin must be a list")
    if skin_name is not None:
        selected = next((item for item in skins if item.get("name") == skin_name), None)
    else:
        selected = next((item for item in skins if item.get("name") == "default"), None)
        if selected is None and len(skins) == 1:
            selected = skins[0]
    if selected is None:
        raise DragonBonesImportError("select a skin with skin_name")
    return selected


def _number(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DragonBonesImportError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise DragonBonesImportError(f"{label} must be a finite number")
    return number


def _transform(value):
    return value if isinstance(value, Mapping) else {}


def _bone_rows(armature, scale, flip_y):
    sign = -1.0 if flip_y else 1.0
    bones = []
    for raw in armature.get("bone", ()):
        if not isinstance(raw, Mapping) or not raw.get("name"):
            raise DragonBonesImportError("every DragonBones bone needs a name")
        transform = _transform(raw.get("transform"))
        bones.append(
            Bone(
                str(raw["name"]),
                str(raw.get("parent", "")),
                _number(transform.get("x", 0), "bone x") * scale,
                _number(transform.get("y", 0), "bone y") * scale * sign,
                _number(transform.get("skY", 0), "bone rotation") * sign,
                _number(transform.get("scX", 1), "bone scale x"),
                _number(transform.get("scY", 1), "bone scale y"),
                _number(raw.get("length", 0), "bone length") * scale,
            )
        )
    return tuple(bones)


def _display_rows(armature, skin, sheet_asset_id, frames, scale, flip_y):
    sign = -1.0 if flip_y else 1.0
    skin_slots = {
        row.get("name"): row.get("display", [])
        for row in skin.get("slot", ())
        if isinstance(row, Mapping)
    }
    slots, display_frames = [], {}
    for z, raw in enumerate(armature.get("slot", ())):
        if not isinstance(raw, Mapping) or not raw.get("name") or not raw.get("parent"):
            raise DragonBonesImportError("every DragonBones slot needs a name and parent")
        slot_id = str(raw["name"])
        displays = skin_slots.get(slot_id, [])
        if not isinstance(displays, list):
            raise DragonBonesImportError(f"slot {slot_id!r} displays must be a list")
        display_frames[slot_id] = []
        for display in displays:
            if not isinstance(display, Mapping) or display.get("type", "image") != "image":
                display_frames[slot_id].append(None)
                continue
            identity = str(display.get("path") or display.get("name") or "")
            display_frames[slot_id].append(int(frames.get(identity, 0)))
        index = raw.get("displayIndex", 0)
        if isinstance(index, bool) or not isinstance(index, int):
            raise DragonBonesImportError(f"slot {slot_id!r} displayIndex must be an integer")
        visible = 0 <= index < len(display_frames[slot_id])
        selected = display_frames[slot_id][index] if visible else None
        visible = visible and selected is not None
        display = displays[index] if visible else {}
        transform = _transform(display.get("transform"))
        _number(transform.get("skX", 0), "display rotation x")
        sk_y = _number(transform.get("skY", 0), "display rotation y")
        slots.append(
            Slot(
                slot_id,
                str(raw["parent"]),
                sheet_asset_id,
                frame=selected or 0,
                offset_x=_number(transform.get("x", 0), "display x") * scale,
                offset_y=_number(transform.get("y", 0), "display y") * scale * sign,
                rotation=sk_y * sign,
                z=z,
                visible=visible,
            )
        )
    return tuple(slots), display_frames


def _frame_time(frames, frame_index, frame_rate):
    return sum(_frame_length(frame) for frame in frames[:frame_index]) / frame_rate


def _frame_length(frame):
    duration = _number(frame.get("duration", 1), "keyframe duration")
    if duration <= 0:
        raise DragonBonesImportError("keyframe duration must be positive")
    return duration


def _has_unsupported_tween(frame):
    return (
        frame.get("tweenType", 0) not in (0, None)
        or frame.get("tweenEasing", 0) not in (0, None)
        or frame.get("curve") is not None
    )


def _animation_rows(armature, data, display_frames, scale, flip_y):
    global_rate = _number(data.get("frameRate", 24), "frameRate")
    frame_rate = _number(armature.get("frameRate", global_rate), "armature frameRate")
    if frame_rate <= 0:
        raise DragonBonesImportError("frameRate must be positive")
    sign = -1.0 if flip_y else 1.0
    clips = {}
    for animation in armature.get("animation", ()):
        if not isinstance(animation, Mapping) or not animation.get("name"):
            raise DragonBonesImportError("every animation needs a name")
        name = str(animation["name"])
        duration = _number(animation.get("duration", 1), "animation duration") / frame_rate
        if duration <= 0:
            raise DragonBonesImportError("animation duration must be positive")
        tracks, switches = {}, {}
        for timeline in animation.get("bone", ()):
            if not isinstance(timeline, Mapping):
                continue
            bone_id = str(timeline.get("name", ""))
            rows = timeline.get("frame", ())
            if not bone_id or not isinstance(rows, list):
                continue
            if any(_has_unsupported_tween(frame) for frame in rows):
                continue
            values = {channel: [] for channel in ("x", "y", "rotation", "scale_x", "scale_y")}
            for index, frame in enumerate(rows):
                if not isinstance(frame, Mapping):
                    raise DragonBonesImportError("bone animation frames must be objects")
                time = _frame_time(rows, index, frame_rate)
                transform = _transform(frame.get("transform"))
                for channel, source, factor in (
                    ("x", "x", scale),
                    ("y", "y", scale * sign),
                    ("rotation", "skY", sign),
                    ("scale_x", "scX", 1.0),
                    ("scale_y", "scY", 1.0),
                ):
                    if source in transform:
                        values[channel].append(
                            Key(time, _number(transform[source], source) * factor)
                        )
            for channel, keys in values.items():
                if keys:
                    tracks[(bone_id, channel)] = tuple(keys)
        for timeline in animation.get("slot", ()):
            if not isinstance(timeline, Mapping):
                continue
            slot_id = str(timeline.get("name", ""))
            rows = timeline.get("frame", ())
            available = display_frames.get(slot_id, [])
            if (
                not slot_id
                or not isinstance(rows, list)
                or any(_has_unsupported_tween(frame) for frame in rows)
            ):
                continue
            frames_for_slot = []
            for index, frame in enumerate(rows):
                if not isinstance(frame, Mapping):
                    raise DragonBonesImportError("slot animation frames must be objects")
                display_index = frame.get("displayIndex", 0)
                if isinstance(display_index, bool) or not isinstance(display_index, int):
                    raise DragonBonesImportError("displayIndex keyframes must be integers")
                if 0 <= display_index < len(available) and available[display_index] is not None:
                    frames_for_slot.append(
                        (_frame_time(rows, index, frame_rate), available[display_index])
                    )
            if frames_for_slot:
                switches[slot_id] = tuple(frames_for_slot)
        clips[name] = SkeletonClip(
            name,
            duration,
            loop=animation.get("playTimes", 1) == 0,
            tracks=tracks,
            frames=switches,
        )
    return clips


def import_dragonbones_json(
    data,
    *,
    sheet_asset_id="",
    frames=None,
    armature_name=None,
    skin_name=None,
    flip_y=True,
    scale=1.0,
):
    """Import DragonBones 5.x bones, image slots, transform keys and display switches.

    ``frames`` maps display path/name to the sprite-sheet frame. Multiple armatures or skins
    require an explicit selection when no unique/default skin is available.
    """
    armature = _armature(data, armature_name)
    skin = _skin(armature, skin_name)
    scale = _number(scale, "scale")
    if scale <= 0:
        raise DragonBonesImportError("scale must be positive")
    bones = _bone_rows(armature, scale, flip_y)
    slots, display_frames = _display_rows(
        armature, skin, str(sheet_asset_id), dict(frames or {}), scale, flip_y
    )
    skeleton = Skeleton(str(armature.get("name", "skeleton")), bones, slots)
    skeleton.clips = _animation_rows(armature, data, display_frames, scale, flip_y)
    return skeleton


def unsupported_parts(data, *, armature_name=None, skin_name=None):
    """List DragonBones features that the Asteria skeleton model cannot preserve."""
    armatures = data.get("armature", ()) if isinstance(data, Mapping) else ()
    if not isinstance(armatures, list):
        return ()
    selected = (
        next(
            (
                item
                for item in armatures
                if isinstance(item, Mapping) and item.get("name") == armature_name
            ),
            None,
        )
        if armature_name is not None
        else armatures[0]
        if len(armatures) == 1
        else None
    )
    if selected is None:
        return ("select one armature before importing",)
    found = []
    if selected.get("ik"):
        found.append("ik constraints")
    animations = selected.get("animation", ())
    if any(animation.get("ffd") for animation in animations if isinstance(animation, Mapping)):
        found.append("FFD deformation")
    if any(animation.get("zOrder") for animation in animations if isinstance(animation, Mapping)):
        found.append("animated z-order")
    if any(
        animation.get("frame") for animation in animations if isinstance(animation, Mapping)
    ) or selected.get("defaultActions"):
        found.append("animation events and actions")
    if any(
        _has_unsupported_tween(frame)
        for animation in animations
        if isinstance(animation, Mapping)
        for key in ("bone", "slot")
        for timeline in animation.get(key, ())
        if isinstance(timeline, Mapping)
        for frame in timeline.get("frame", ())
        if isinstance(frame, Mapping)
    ):
        found.append("custom animation easing")
    if any(
        frame.get("displayIndex", 0) < 0 or frame.get("color")
        for animation in animations
        if isinstance(animation, Mapping)
        for timeline in animation.get("slot", ())
        if isinstance(timeline, Mapping)
        for frame in timeline.get("frame", ())
        if isinstance(frame, Mapping)
    ):
        found.append("slot visibility and color animation")
    skins = selected.get("skin", ())
    if isinstance(skins, list) and len(skins) > 1:
        found.append("alternate skins")
    if not isinstance(skins, list):
        skins = []
    skin = (
        next(
            (
                item
                for item in skins
                if isinstance(item, Mapping) and item.get("name") == skin_name
            ),
            None,
        )
        if skin_name is not None
        else next(
            (
                item
                for item in skins
                if isinstance(item, Mapping) and item.get("name") == "default"
            ),
            skins[0] if len(skins) == 1 and isinstance(skins[0], Mapping) else None,
        )
    )
    if skin is not None and any(
        display.get("type", "image") != "image"
        for slot in skin.get("slot", ())
        if isinstance(slot, Mapping)
        for display in slot.get("display", ())
        if isinstance(display, Mapping)
    ):
        found.append("mesh, child armature, and bounding-box displays")
    if skin is not None and any(
        (display.get("transform") or {}).get("scX", 1) != 1
        or (display.get("transform") or {}).get("scY", 1) != 1
        for slot in skin.get("slot", ())
        if isinstance(slot, Mapping)
        for display in slot.get("display", ())
        if isinstance(display, Mapping)
    ):
        found.append("display scaling")
    if skin is not None and any(
        "skX" in (display.get("transform") or {})
        and "skY" in (display.get("transform") or {})
        and abs(
            float((display.get("transform") or {})["skX"])
            - float((display.get("transform") or {})["skY"])
        )
        > 1e-6
        for slot in skin.get("slot", ())
        if isinstance(slot, Mapping)
        for display in slot.get("display", ())
        if isinstance(display, Mapping)
    ):
        found.append("display skew")
    if any(
        "skX" in (bone.get("transform") or {})
        and "skY" in (bone.get("transform") or {})
        and abs(
            float((bone.get("transform") or {})["skX"])
            - float((bone.get("transform") or {})["skY"])
        )
        > 1e-6
        for bone in selected.get("bone", ())
        if isinstance(bone, Mapping)
    ):
        found.append("bone skew")
    if (
        any(
            "skX" in (frame.get("transform") or {})
            and "skY" in (frame.get("transform") or {})
            and abs(
                float((frame.get("transform") or {})["skX"])
                - float((frame.get("transform") or {})["skY"])
            )
            > 1e-6
            for animation in animations
            if isinstance(animation, Mapping)
            for timeline in animation.get("bone", ())
            if isinstance(timeline, Mapping)
            for frame in timeline.get("frame", ())
            if isinstance(frame, Mapping)
        )
        and "bone skew" not in found
    ):
        found.append("bone skew")
    return tuple(found)
