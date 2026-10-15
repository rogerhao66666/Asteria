"""Import a Spine-style skeleton JSON as a ``Skeleton``.

Supported (the common subset every Spine-compatible exporter writes): ``bones`` (``name``,
``parent``, ``x``, ``y``, ``rotation``, ``scaleX``, ``scaleY``, ``length``), ``slots`` (``name``,
``bone``, ``attachment``) and ``animations`` with per-bone ``rotate`` / ``translate`` / ``scale``
timelines (also the split ``translatex`` / ``translatey`` / ``scalex`` / ``scaley`` of newer
files) and per-slot ``attachment`` timelines (which switch the slot's sprite frame). Curves:
missing = linear, ``"stepped"`` = hold, a bezier list is approximated with ease-in-out.

Not supported (it is skipped, never guessed): meshes, skins, IK / transform / path constraints,
deform, shear, colour timelines, events. Spine's y axis points up; ``flip_y`` (default) turns the
rig into Asteria's y-down world.
"""

from __future__ import annotations

from .skeleton import Bone, Key, Skeleton, SkeletonClip, Slot

SKIPPED = ("skins", "ik", "transform", "path", "events", "deform", "shear")


class SkeletonImportError(ValueError):
    pass


def _easing(curve):
    if curve == "stepped":
        return "step"
    if isinstance(curve, list | tuple | float | int) and curve is not None:
        return "ease_in_out"
    return "linear"


def _value(frame, *names, default=0.0):
    for name in names:
        if name in frame:
            return float(frame[name])
    return default


def _keys(frames, getter, sign=1.0):
    keys = [
        Key(float(f.get("time", 0.0)), sign * getter(f), _easing(f.get("curve"))) for f in frames
    ]
    return keys or None


def import_spine_json(data, *, sheet_asset_id="", frames=None, flip_y=True, scale=1.0):
    """Build a ``Skeleton`` from parsed Spine JSON.

    ``sheet_asset_id``: the sprite sheet the slots draw from. ``frames``: ``{attachment name:
    frame index}`` (an attachment not listed uses frame 0). ``scale`` multiplies every length.
    """
    if not isinstance(data, dict) or not data.get("bones"):
        raise SkeletonImportError("a skeleton needs a list of bones")
    frames = dict(frames or {})
    y = -1.0 if flip_y else 1.0
    k = float(scale)
    bones = []
    for raw in data["bones"]:
        name = raw.get("name")
        if not name:
            raise SkeletonImportError("every bone needs a name")
        bones.append(
            Bone(
                name,
                raw.get("parent", ""),
                float(raw.get("x", 0.0)) * k,
                y * float(raw.get("y", 0.0)) * k,
                y * float(raw.get("rotation", 0.0)),
                float(raw.get("scaleX", 1.0)),
                float(raw.get("scaleY", 1.0)),
                float(raw.get("length", 0.0)) * k,
            )
        )
    slots = []
    for z, raw in enumerate(data.get("slots", ())):
        attachment = raw.get("attachment") or ""
        slots.append(
            Slot(
                raw["name"],
                raw["bone"],
                sheet_asset_id,
                frame=int(frames.get(attachment, 0)),
                z=z,
                visible=bool(attachment),
            )
        )
    clips = {}
    for name, animation in dict(data.get("animations", {})).items():
        tracks, slot_frames, duration = {}, {}, 0.0
        for bone_id, timelines in dict(animation.get("bones", {})).items():
            for kind, frames_ in timelines.items():
                times = [float(f.get("time", 0.0)) for f in frames_]
                duration = max(duration, *times) if times else duration
                if kind == "rotate":
                    tracks[(bone_id, "rotation")] = _keys(
                        frames_, lambda f: _value(f, "value", "angle"), y
                    )
                elif kind == "translate":
                    tracks[(bone_id, "x")] = _keys(frames_, lambda f: _value(f, "x") * k)
                    tracks[(bone_id, "y")] = _keys(frames_, lambda f: _value(f, "y") * k, y)
                elif kind == "translatex":
                    tracks[(bone_id, "x")] = _keys(frames_, lambda f: _value(f, "value", "x") * k)
                elif kind == "translatey":
                    tracks[(bone_id, "y")] = _keys(
                        frames_, lambda f: _value(f, "value", "y") * k, y
                    )
                elif kind == "scale":
                    tracks[(bone_id, "scale_x")] = _keys(
                        frames_, lambda f: _value(f, "x", default=1.0)
                    )
                    tracks[(bone_id, "scale_y")] = _keys(
                        frames_, lambda f: _value(f, "y", default=1.0)
                    )
                elif kind == "scalex":
                    tracks[(bone_id, "scale_x")] = _keys(
                        frames_, lambda f: _value(f, "value", "x", default=1.0)
                    )
                elif kind == "scaley":
                    tracks[(bone_id, "scale_y")] = _keys(
                        frames_, lambda f: _value(f, "value", "y", default=1.0)
                    )
        for slot_id, timelines in dict(animation.get("slots", {})).items():
            rows = []
            for frame in timelines.get("attachment", ()):
                time = float(frame.get("time", 0.0))
                duration = max(duration, time)
                rows.append((time, int(frames.get(frame.get("name") or "", 0))))
            if rows:
                slot_frames[slot_id] = tuple(rows)
        clips[name] = SkeletonClip(
            name,
            max(duration, 1e-3),
            tracks={key: keys for key, keys in tracks.items() if keys},
            frames=slot_frames,
        )
    skeleton = Skeleton(
        str(data.get("skeleton", {}).get("name", "skeleton")), tuple(bones), tuple(slots)
    )
    skeleton.clips = clips
    return skeleton


def unsupported_parts(data):
    """Names of the parts of ``data`` this importer skips (so a tool can warn the author)."""
    found = [name for name in SKIPPED if data.get(name)]
    if any(
        any(
            key in ("deform", "shear", "color", "twoColor")
            for key in anim.get("slots", {}).get(s, {})
        )
        for anim in dict(data.get("animations", {})).values()
        for s in anim.get("slots", {})
    ):
        found.append("slot colour / deform timelines")
    return tuple(found)
