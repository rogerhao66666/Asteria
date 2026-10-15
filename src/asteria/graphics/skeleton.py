"""2D skeletal animation: bones, keyframed clips, blending, two-bone IK and drawable sprites.

A ``Skeleton`` is a bone tree (each bone has a local position, rotation in degrees and scale
against its parent) plus ``Slot`` sprites attached to bones. A ``SkeletonClip`` keys bone channels
over time (with easing) and can switch a slot's frame. ``Skeleton.pose`` samples one clip - or a
blend of two - into world transforms; ``solve_two_bone`` bends a limb to reach a point;
``Skeleton.draws`` returns ready-to-draw ``SpriteDraw`` rows (position, rotation, scale, frame).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import acos, atan2, cos, degrees, hypot, isfinite, radians, sin

EASINGS = ("linear", "step", "ease_in", "ease_out", "ease_in_out")
CHANNELS = ("x", "y", "rotation", "scale_x", "scale_y")


def _ease(kind, t):
    if kind == "step":
        return 0.0
    if kind == "ease_in":
        return t * t
    if kind == "ease_out":
        return 1.0 - (1.0 - t) * (1.0 - t)
    if kind == "ease_in_out":
        return 3 * t * t - 2 * t * t * t
    return t


def _blend_angle(a, b, t):
    """Interpolate degrees along the short way round."""
    delta = (b - a + 180.0) % 360.0 - 180.0
    return a + delta * t


@dataclass(frozen=True, slots=True)
class Bone:
    bone_id: str
    parent: str = ""
    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    length: float = 0.0

    def __post_init__(self):
        if not self.bone_id:
            raise ValueError("bone_id is required")
        for name in ("x", "y", "rotation", "scale_x", "scale_y", "length"):
            if not isfinite(getattr(self, name)):
                raise ValueError(f"bone {name} must be finite")


@dataclass(frozen=True, slots=True)
class Slot:
    """A sprite carried by a bone: a frame of a sprite sheet, offset from the bone, drawn by
    ``z`` (higher on top)."""

    slot_id: str
    bone_id: str
    sheet_asset_id: str = ""
    frame: int = 0
    offset_x: float = 0.0
    offset_y: float = 0.0
    rotation: float = 0.0
    z: int = 0
    visible: bool = True

    def __post_init__(self):
        if not self.slot_id or not self.bone_id:
            raise ValueError("a slot needs an id and a bone")


@dataclass(frozen=True, slots=True)
class Key:
    time: float
    value: float
    easing: str = "linear"  # how to move from this key to the next

    def __post_init__(self):
        if self.easing not in EASINGS:
            raise ValueError(f"easing must be one of {EASINGS}")


@dataclass(frozen=True, slots=True)
class SkeletonClip:
    """``tracks``: ``{(bone id, channel): keys}`` where a channel is an offset from the bone's
    rest pose (``x``, ``y``, ``rotation`` add; ``scale_x`` / ``scale_y`` multiply).
    ``frames``: ``{slot id: ((time, frame), ...)}`` switches a slot's frame."""

    name: str
    duration: float
    loop: bool = True
    tracks: tuple = ()
    frames: tuple = ()

    def __init__(self, name, duration, *, loop=True, tracks=None, frames=None):
        if not name:
            raise ValueError("a clip needs a name")
        if not duration > 0:
            raise ValueError("duration must be positive")
        parsed = []
        for (bone_id, channel), keys in dict(tracks or {}).items():
            if channel not in CHANNELS:
                raise ValueError(f"channel must be one of {CHANNELS}")
            keys = tuple(sorted(keys, key=lambda k: k.time))
            if not keys or any(k.time < 0 or k.time > duration for k in keys):
                raise ValueError("keys must lie inside the clip")
            parsed.append(((bone_id, channel), keys))
        switches = tuple(
            sorted((slot, tuple(sorted(rows))) for slot, rows in dict(frames or {}).items())
        )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "duration", float(duration))
        object.__setattr__(self, "loop", bool(loop))
        object.__setattr__(self, "tracks", tuple(sorted(parsed)))
        object.__setattr__(self, "frames", switches)

    def local_time(self, time):
        return time % self.duration if self.loop else max(0.0, min(self.duration, time))

    def sample(self, bone_id, channel, time, default):
        """The key value at ``time`` (``default`` when the bone is not keyed on that channel)."""
        for (bone, name), keys in self.tracks:
            if bone == bone_id and name == channel:
                return self._interpolate(keys, self.local_time(time))
        return default

    @staticmethod
    def _interpolate(keys, time):
        if time <= keys[0].time:
            return keys[0].value
        for before, after in zip(keys, keys[1:], strict=False):
            if time <= after.time:
                span = after.time - before.time
                t = 0.0 if span <= 0 else (time - before.time) / span
                return before.value + (after.value - before.value) * _ease(before.easing, t)
        return keys[-1].value

    def frame_for(self, slot_id, time, default):
        for slot, rows in self.frames:
            if slot == slot_id:
                frame = default
                for when, value in rows:
                    if when <= self.local_time(time):
                        frame = value
                return frame
        return default


@dataclass(frozen=True, slots=True)
class WorldBone:
    x: float
    y: float
    rotation: float
    scale_x: float
    scale_y: float


@dataclass(frozen=True, slots=True)
class SpriteDraw:
    slot_id: str
    sheet_asset_id: str
    frame: int
    x: float
    y: float
    rotation: float
    scale_x: float
    scale_y: float
    z: int


@dataclass(slots=True)
class Skeleton:
    skeleton_id: str
    bones: tuple = ()
    slots: tuple = ()
    clips: dict = field(default_factory=dict)

    def __post_init__(self):
        ids = [b.bone_id for b in self.bones]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate bone id")
        known = set()
        for bone in self.bones:  # parents must come first, which also rules out cycles
            if bone.parent and bone.parent not in known:
                raise ValueError(
                    f"bone {bone.bone_id}: parent {bone.parent!r} must be listed first"
                )
            known.add(bone.bone_id)
        for slot in self.slots:
            if slot.bone_id not in known:
                raise ValueError(f"slot {slot.slot_id}: unknown bone {slot.bone_id}")
        self.clips = (
            {c.name: c for c in self.clips.values()}
            if isinstance(self.clips, dict)
            else {c.name: c for c in self.clips}
        )

    def bone(self, bone_id):
        return next(b for b in self.bones if b.bone_id == bone_id)

    # -- posing --------------------------------------------------------------------------------
    def _local(self, bone, clip, time):
        if clip is None:
            return bone.x, bone.y, bone.rotation, bone.scale_x, bone.scale_y
        return (
            bone.x + clip.sample(bone.bone_id, "x", time, 0.0),
            bone.y + clip.sample(bone.bone_id, "y", time, 0.0),
            bone.rotation + clip.sample(bone.bone_id, "rotation", time, 0.0),
            bone.scale_x * clip.sample(bone.bone_id, "scale_x", time, 1.0),
            bone.scale_y * clip.sample(bone.bone_id, "scale_y", time, 1.0),
        )

    def pose(self, clip_name=None, time=0.0, *, blend=None, blend_time=0.0, weight=0.0):
        """World transforms of every bone. With ``blend`` (a second clip name) the local values
        are mixed: ``weight`` 0 is all the first clip, 1 all the second."""
        first = self.clips.get(clip_name) if clip_name else None
        second = self.clips.get(blend) if blend else None
        if clip_name and first is None or blend and second is None:
            raise KeyError(clip_name if first is None and clip_name else blend)
        weight = max(0.0, min(1.0, float(weight)))
        world = {}
        for bone in self.bones:
            a = self._local(bone, first, time)
            if second is not None and weight > 0:
                b = self._local(bone, second, blend_time)
                x, y, r, sx, sy = (
                    a[0] + (b[0] - a[0]) * weight,
                    a[1] + (b[1] - a[1]) * weight,
                    _blend_angle(a[2], b[2], weight),
                    a[3] + (b[3] - a[3]) * weight,
                    a[4] + (b[4] - a[4]) * weight,
                )
            else:
                x, y, r, sx, sy = a
            if bone.parent:
                p = world[bone.parent]
                px, py = x * p.scale_x, y * p.scale_y
                c, s = cos(radians(p.rotation)), sin(radians(p.rotation))
                world[bone.bone_id] = WorldBone(
                    p.x + px * c - py * s,
                    p.y + px * s + py * c,
                    p.rotation + r,
                    p.scale_x * sx,
                    p.scale_y * sy,
                )
            else:
                world[bone.bone_id] = WorldBone(x, y, r, sx, sy)
        return world

    def tip(self, pose, bone_id):
        """World position of the end of a bone (its origin plus ``length`` along its angle)."""
        bone, w = self.bone(bone_id), pose[bone_id]
        angle = radians(w.rotation)
        return (
            w.x + cos(angle) * bone.length * w.scale_x,
            w.y + sin(angle) * bone.length * w.scale_x,
        )

    def draws(self, pose, clip_name=None, time=0.0, *, origin=(0.0, 0.0), scale=1.0):
        """``SpriteDraw`` rows sorted by ``z``, positioned from ``origin``."""
        clip = self.clips.get(clip_name) if clip_name else None
        rows = []
        for slot in self.slots:
            if not slot.visible:
                continue
            w = pose[slot.bone_id]
            c, s = cos(radians(w.rotation)), sin(radians(w.rotation))
            ox, oy = slot.offset_x * w.scale_x, slot.offset_y * w.scale_y
            frame = clip.frame_for(slot.slot_id, time, slot.frame) if clip else slot.frame
            rows.append(
                SpriteDraw(
                    slot.slot_id,
                    slot.sheet_asset_id,
                    frame,
                    origin[0] + (w.x + ox * c - oy * s) * scale,
                    origin[1] + (w.y + ox * s + oy * c) * scale,
                    w.rotation + slot.rotation,
                    w.scale_x * scale,
                    w.scale_y * scale,
                    slot.z,
                )
            )
        return sorted(rows, key=lambda r: (r.z, r.slot_id))


def solve_two_bone(root, upper_length, lower_length, target, *, bend=1):
    """Angles (degrees) for a two-bone limb whose root is at ``root`` and whose end reaches
    ``target``: ``(upper_angle, lower_angle_relative_to_upper)``. Out of reach the limb straightens
    toward the target. ``bend`` +1 / -1 chooses which way the middle joint points."""
    if not (upper_length > 0 and lower_length > 0):
        raise ValueError("limb lengths must be positive")
    dx, dy = target[0] - root[0], target[1] - root[1]
    distance = hypot(dx, dy)
    base = degrees(atan2(dy, dx))
    reach = upper_length + lower_length
    if distance >= reach:
        return base, 0.0
    near = abs(upper_length - lower_length)
    distance = max(distance, near + 1e-9, 1e-9)
    cos_root = (upper_length**2 + distance**2 - lower_length**2) / (2 * upper_length * distance)
    cos_mid = (upper_length**2 + lower_length**2 - distance**2) / (2 * upper_length * lower_length)
    root_offset = degrees(acos(max(-1.0, min(1.0, cos_root))))
    mid = degrees(acos(max(-1.0, min(1.0, cos_mid))))
    sign = 1 if bend >= 0 else -1
    return base - sign * root_offset, sign * (180.0 - mid)
