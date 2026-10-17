"""Animation editor API (EDT-05, ANI-04, AST-02).

Edits the project's canonical ``sprite_sheet`` assets — frame grid, pivot,
clips (frames, timing, loop) and keyframe events — the same data the
runtime battle presentation resolves (``asteria.runtime.battle_visuals``).
Every change is an undoable document command; ``preview_frame`` plays a
clip with the runtime ``AnimatorState`` so the editor shows exactly what
the game will show.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from pathlib import Path

SHEET_KIND = "sprite_sheet"


class AnimationAuthoringError(ValueError):
    pass


@dataclass(slots=True)
class _ReplaceAssetCommand:
    registry: object
    before: object
    after: object
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        self.registry.register(self.after, replace=True)

    def undo(self):
        self.registry.register(self.before, replace=True)


class AnimationAuthoringController:
    def __init__(self, document, *, resource_root=None):
        self.document = document
        self._resource_root = None if resource_root is None else Path(resource_root)

    # -- lookup ------------------------------------------------------------------
    @property
    def project(self):
        if self.document.project is None:
            raise AnimationAuthoringError("project required")
        return self.document.project

    @property
    def resource_root(self):
        if self._resource_root is not None:
            return self._resource_root
        path = getattr(self.document, "file_path", None)
        return Path(path).parent if path else Path.cwd()

    def sheets(self):
        return tuple(sorted(a.asset_id for a in self.project.assets.query(kind=SHEET_KIND)))

    def asset(self, asset_id):
        try:
            asset = self.project.assets.resolve(str(asset_id))
        except KeyError:
            raise AnimationAuthoringError(f"unknown sprite sheet {asset_id}") from None
        if asset.kind != SHEET_KIND:
            raise AnimationAuthoringError(f"{asset_id} is not a sprite sheet")
        return asset

    def data(self, asset_id):
        meta = self.asset(asset_id).meta()
        return {
            "frame_size": list(meta.get("frame_size", (16, 16))),
            "pivot": list(meta.get("pivot", (0.5, 1.0))),
            "clips": copy.deepcopy(dict(meta.get("clips", {}))),
            # battle use: the character's real height in the frame (0 = the whole frame) and
            # where an effect sheet appears on its target (None = the engine defaults)
            "body_height": float(meta.get("body_height", 0) or 0),
            "vfx": copy.deepcopy(dict(meta["vfx"])) if meta.get("vfx") else None,
        }

    def image_path(self, asset_id):
        return self.resource_root / self.asset(asset_id).source.uri

    def image_size(self, asset_id):
        from PIL import Image

        path = self.image_path(asset_id)
        if not path.is_file():
            return None
        with Image.open(path) as image:
            return image.size

    def grid(self, asset_id):
        size = self.image_size(asset_id)
        fw, fh = self.data(asset_id)["frame_size"]
        if size is None:
            return (0, 0)
        return (size[0] // fw, size[1] // fh)

    def frame_rect(self, asset_id, index):
        fw, fh = self.data(asset_id)["frame_size"]
        columns, _ = self.grid(asset_id)
        if columns <= 0:
            raise AnimationAuthoringError("sheet image is missing")
        return ((index % columns) * fw, (index // columns) * fh, fw, fh)

    # -- validation ---------------------------------------------------------------
    def problems(self, asset_id, data=None):
        data = data or self.data(asset_id)
        found = []
        fw, fh = data["frame_size"]
        if fw <= 0 or fh <= 0:
            return [f"{asset_id}: frame size must be positive"]
        size = self.image_size(asset_id)
        if size is None:
            found.append(f"{asset_id}: image {self.asset(asset_id).source.uri} not found")
            count = None
        else:
            if size[0] % fw or size[1] % fh:
                found.append(f"{asset_id}: image {size} is not a whole grid of {fw}x{fh}")
            count = (size[0] // fw) * (size[1] // fh)
        px, py = data["pivot"]
        if not (0 <= px <= 1 and 0 <= py <= 1):
            found.append(f"{asset_id}: pivot must be inside the frame (0..1)")
        for name, clip in sorted(data["clips"].items()):
            frames = clip.get("frames", [])
            if not frames:
                found.append(f"{asset_id}.{name}: clip has no frames")
            if count is not None and any(not 0 <= int(f) < count for f in frames):
                found.append(f"{asset_id}.{name}: frame outside the {count}-frame sheet")
            if float(clip.get("frame_duration", 0)) <= 0:
                found.append(f"{asset_id}.{name}: frame duration must be > 0")
            for position in dict(clip.get("events", {})):
                if not 0 <= int(position) < len(frames):
                    found.append(f"{asset_id}.{name}: event on missing keyframe {position}")
        return found

    # -- edits (undoable) ---------------------------------------------------------
    def _commit(self, asset_id, data, label):
        problems = self.problems(asset_id, data)
        if problems:
            raise AnimationAuthoringError("; ".join(problems))
        before = self.asset(asset_id)
        meta = dict(before.metadata)
        meta.update(
            frame_size=list(data["frame_size"]), pivot=list(data["pivot"]), clips=data["clips"]
        )
        after = replace(before, metadata=tuple(sorted(meta.items())))
        self.document.execute(_ReplaceAssetCommand(self.project.assets, before, after, label))
        return self.data(asset_id)

    def set_frame_size(self, asset_id, width, height):
        data = self.data(asset_id)
        data["frame_size"] = [int(width), int(height)]
        return self._commit(asset_id, data, f"Frame size {asset_id}")

    def set_body_height(self, asset_id, height):
        """Source pixels of the character's body (health bars and menus sit on it); 0 clears."""
        height = float(height)
        if height < 0:
            raise AnimationAuthoringError("body height cannot be negative")
        before = self.asset(asset_id)
        meta = dict(before.metadata)
        if height:
            meta["body_height"] = height
        else:
            meta.pop("body_height", None)
        self._replace_meta(before, meta, f"Body height {asset_id}")
        return self.data(asset_id)

    def set_vfx(self, asset_id, anchor=None, *, offset=(0.0, 0.0), scale=0.6):
        """Where this sheet shows when used as an effect; ``anchor=None`` clears the setting."""
        before = self.asset(asset_id)
        meta = dict(before.metadata)
        if anchor is None:
            meta.pop("vfx", None)
        else:
            if anchor not in ("feet", "center", "head"):
                raise AnimationAuthoringError("anchor must be feet, center or head")
            if float(scale) <= 0:
                raise AnimationAuthoringError("effect scale must be > 0")
            meta["vfx"] = {
                "anchor": anchor,
                "offset": [float(offset[0]), float(offset[1])],
                "scale": float(scale),
            }
        self._replace_meta(before, meta, f"Effect placement {asset_id}")
        return self.data(asset_id)

    def _replace_meta(self, before, meta, label):
        after = replace(before, metadata=tuple(sorted(meta.items())))
        self.document.execute(_ReplaceAssetCommand(self.project.assets, before, after, label))

    def set_pivot(self, asset_id, x, y):
        data = self.data(asset_id)
        data["pivot"] = [round(float(x), 4), round(float(y), 4)]
        return self._commit(asset_id, data, f"Pivot {asset_id}")

    def add_clip(self, asset_id, name, frames, frame_duration=0.12, loop=True):
        data = self.data(asset_id)
        name = str(name).strip()
        if not name or name in data["clips"]:
            raise AnimationAuthoringError(f"clip name {name!r} is empty or taken")
        data["clips"][name] = {
            "frames": [int(f) for f in frames],
            "frame_duration": float(frame_duration),
            "loop": bool(loop),
        }
        return self._commit(asset_id, data, f"Add clip {name}")

    def set_clip(self, asset_id, name, *, frames=None, frame_duration=None, loop=None):
        data = self.data(asset_id)
        clip = data["clips"].get(name)
        if clip is None:
            raise AnimationAuthoringError(f"unknown clip {name}")
        if frames is not None:
            clip["frames"] = [int(f) for f in frames]
            events = {
                k: v
                for k, v in dict(clip.get("events", {})).items()
                if int(k) < len(clip["frames"])
            }
            clip.pop("events", None)
            if events:
                clip["events"] = events
        if frame_duration is not None:
            clip["frame_duration"] = float(frame_duration)
        if loop is not None:
            clip["loop"] = bool(loop)
        return self._commit(asset_id, data, f"Edit clip {name}")

    def rename_clip(self, asset_id, name, new_name):
        data = self.data(asset_id)
        new_name = str(new_name).strip()
        if name not in data["clips"] or not new_name or new_name in data["clips"]:
            raise AnimationAuthoringError(f"cannot rename {name} to {new_name!r}")
        data["clips"][new_name] = data["clips"].pop(name)
        return self._commit(asset_id, data, f"Rename clip {name}")

    def remove_clip(self, asset_id, name):
        data = self.data(asset_id)
        if data["clips"].pop(name, None) is None:
            raise AnimationAuthoringError(f"unknown clip {name}")
        return self._commit(asset_id, data, f"Remove clip {name}")

    def set_events(self, asset_id, name, position, names):
        data = self.data(asset_id)
        clip = data["clips"].get(name)
        if clip is None:
            raise AnimationAuthoringError(f"unknown clip {name}")
        events = dict(clip.get("events", {}))
        cleaned = [str(n).strip() for n in names if str(n).strip()]
        if cleaned:
            events[str(int(position))] = cleaned
        else:
            events.pop(str(int(position)), None)
        clip.pop("events", None)
        if events:
            clip["events"] = dict(sorted(events.items(), key=lambda kv: int(kv[0])))
        return self._commit(asset_id, data, f"Events {name}")

    # -- preview (runtime animation path) -----------------------------------------
    def _clip(self, asset_id, name):
        from asteria.graphics import SpriteClip, SpriteKeyframe

        clip = self.data(asset_id)["clips"].get(name)
        if clip is None:
            raise AnimationAuthoringError(f"unknown clip {name}")
        events = {int(k): tuple(v) for k, v in dict(clip.get("events", {})).items()}
        keyframes = [
            SpriteKeyframe(int(f), float(clip["frame_duration"]), events.get(i, ()))
            for i, f in enumerate(clip["frames"])
        ]
        return SpriteClip(name, keyframes, bool(clip.get("loop", True)))

    def preview_frame(self, asset_id, name, time):
        """Sheet frame index the runtime shows ``time`` seconds into the clip."""
        from asteria.runtime.animation import AnimatorState

        animator = AnimatorState(self._clip(asset_id, name))
        animator.update(max(0.0, float(time)))
        return animator.frame_index

    def preview_events(self, asset_id, name, until):
        """``[(time, event)]`` fired from 0 to ``until`` seconds at their authored keyframe
        times."""
        clip = self._clip(asset_id, name)
        fired, time = [], 0.0
        while time <= until + 1e-9:
            for keyframe in clip.keyframes:
                if time > until + 1e-9:
                    break
                fired.extend((round(time, 4), event) for event in keyframe.events)
                time += keyframe.duration
            if not clip.loop:
                break
        return fired
