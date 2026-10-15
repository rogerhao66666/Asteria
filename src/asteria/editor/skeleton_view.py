"""Previewing a 2D skeleton rig: bone lines for a clip at a time (Qt-free part)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from asteria.graphics.skeleton_import import import_spine_json, unsupported_parts


@dataclass(frozen=True, slots=True)
class BoneSegment:
    bone_id: str
    x0: float
    y0: float
    x1: float
    y1: float


def load_rig(path, **options):
    """Import a Spine-style JSON file; returns ``(skeleton, notes)``, ``notes`` naming whatever
    the importer skips (meshes, IK, ...). Raises ``OSError`` / ``ValueError`` (which includes
    ``SkeletonImportError``)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return import_spine_json(data, **options), tuple(unsupported_parts(data))


def bone_segments(skeleton, clip_name=None, time=0.0):
    """The line (origin to tip) of every bone for ``clip_name`` at ``time``."""
    pose = skeleton.pose(clip_name or None, time)
    segments = []
    for bone in skeleton.bones:
        world = pose[bone.bone_id]
        tip = skeleton.tip(pose, bone.bone_id)
        segments.append(BoneSegment(bone.bone_id, world.x, world.y, tip[0], tip[1]))
    return tuple(segments)


def bounds(segments, margin=8.0):
    """``(min_x, min_y, max_x, max_y)`` around the segments, padded by ``margin``."""
    xs = [v for s in segments for v in (s.x0, s.x1)] or [0.0]
    ys = [v for s in segments for v in (s.y0, s.y1)] or [0.0]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)
