"""VFX tool API (EDT-08): battle VFX sheets — import, placement, preview, usage.

A VFX is a ``sprite_sheet`` asset tagged ``vfx`` whose ``play`` clip the
battle plays on a member when an action timeline beat cues it. This API
edits what the battle renderer reads (``asteria.runtime.battle_visuals``:
``vfx_placement``, ``vfx_rect``, ``vfx_keyframe``) and the preview uses
those same functions, so the editor shows the in-game placement and timing.
Frames and clip timing are edited with the Animation Editor API.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from asteria.assets.canonical import AssetSource, CanonicalAsset
from asteria.runtime.battle_visuals import (
    VFX_ALIGNS,
    VFX_ANCHORS,
    VFX_BLENDS,
    VFX_DEFAULTS,
    vfx_content_center,
    vfx_keyframe,
    vfx_placement,
    vfx_rect,
)

from .animation_authoring import SHEET_KIND, AnimationAuthoringController, _ReplaceAssetCommand

VFX_TAG = "vfx"
PLAY_CLIP = "play"
PREVIEW_BODY_HEIGHT = 96.0  # stand-in member height for the preview (world pixels)


class VFXAuthoringError(ValueError):
    pass


@dataclass(slots=True)
class _AddAssetCommand:
    registry: object
    asset: object
    description: str

    @property
    def label(self):
        return self.description

    def redo(self):
        self.registry.register(self.asset)

    def undo(self):
        self.registry.remove(self.asset.asset_id)


@dataclass(frozen=True, slots=True)
class VFXPreview:
    keyframe: int
    frame_index: int
    source: tuple  # (x, y, width, height) in the sheet image
    rect: tuple  # (centre_x, centre_y, width, height) relative to the member's feet
    placement: dict
    duration: float


class VFXAuthoringController:
    def __init__(self, document, *, resource_root=None):
        self.document = document
        self.animation = AnimationAuthoringController(document, resource_root=resource_root)

    @property
    def project(self):
        if self.document.project is None:
            raise VFXAuthoringError("project required")
        return self.document.project

    def vfx_ids(self):
        return tuple(
            sorted(
                a.asset_id for a in self.project.assets.query(kind=SHEET_KIND) if VFX_TAG in a.tags
            )
        )

    def other_sheets(self):
        """Sprite sheets not marked as VFX (candidates for 'Use as VFX')."""
        return tuple(
            sorted(
                a.asset_id
                for a in self.project.assets.query(kind=SHEET_KIND)
                if VFX_TAG not in a.tags
            )
        )

    def asset(self, asset_id):
        return self.animation.asset(asset_id)

    def placement(self, asset_id):
        return vfx_placement(self.asset(asset_id).meta())

    def duration(self, asset_id):
        clip = self.animation.data(asset_id)["clips"].get(PLAY_CLIP)
        if not clip:
            return 0.0
        return max(0.05, len(clip["frames"]) * float(clip["frame_duration"]))

    # -- edits (undoable) ---------------------------------------------------------
    def _replace(self, before, label, *, metadata=None, tags=None):
        meta = before.meta() if metadata is None else metadata
        after = replace(
            before,
            metadata=tuple(sorted(meta.items())),
            tags=before.tags if tags is None else frozenset(tags),
        )
        self.document.execute(_ReplaceAssetCommand(self.project.assets, before, after, label))
        return after

    def set_placement(self, asset_id, **changes):
        unknown = set(changes) - set(VFX_DEFAULTS)
        if unknown:
            raise VFXAuthoringError(f"unknown VFX settings: {sorted(unknown)}")
        if "anchor" in changes and changes["anchor"] not in VFX_ANCHORS:
            raise VFXAuthoringError(f"anchor must be one of {VFX_ANCHORS}")
        if "blend" in changes and changes["blend"] not in VFX_BLENDS:
            raise VFXAuthoringError(f"blend must be one of {VFX_BLENDS}")
        if "align" in changes and changes["align"] not in VFX_ALIGNS:
            raise VFXAuthoringError(f"align must be one of {VFX_ALIGNS}")
        if "scale" in changes and not float(changes["scale"]) > 0:
            raise VFXAuthoringError("scale must be greater than 0")
        if "opacity" in changes and not 0.0 <= float(changes["opacity"]) <= 1.0:
            raise VFXAuthoringError("opacity must be between 0 and 1")
        if "offset" in changes:
            changes["offset"] = [
                round(float(changes["offset"][0]), 2),
                round(float(changes["offset"][1]), 2),
            ]
        before = self.asset(asset_id)
        meta = before.meta()
        placement = {**dict(meta.get("vfx", {})), **changes}
        meta["vfx"] = {k: placement[k] for k in VFX_DEFAULTS if k in placement}
        self._replace(before, f"VFX placement {asset_id}", metadata=meta)
        return self.placement(asset_id)

    def mark_as_vfx(self, asset_id, enabled=True):
        before = self.asset(asset_id)
        tags = set(before.tags) | {VFX_TAG} if enabled else set(before.tags) - {VFX_TAG}
        meta = before.meta()
        if enabled and PLAY_CLIP not in meta.get("clips", {}):
            raise VFXAuthoringError(f"{asset_id} needs a '{PLAY_CLIP}' clip to be used as a VFX")
        if not enabled and self.usages(asset_id):
            raise VFXAuthoringError(
                f"{asset_id} is cued by action timelines: {self._usage_text(asset_id)}"
            )
        return self._replace(
            before, f"{'Use' if enabled else 'Stop using'} {asset_id} as VFX", tags=tags
        )

    def import_sheet(
        self, asset_id, image_path, frame_width, frame_height, *, frame_duration=0.06
    ):
        """Copy ``image_path`` into the project's ``assets/vfx`` folder and add it as a VFX playing
        every frame once."""
        asset_id = str(asset_id).strip()
        if not asset_id:
            raise VFXAuthoringError("asset id is required")
        try:
            self.project.assets.resolve(asset_id)
        except KeyError:
            pass
        else:
            raise VFXAuthoringError(f"asset {asset_id} already exists")
        source = Path(image_path)
        if not source.is_file():
            raise VFXAuthoringError(f"image not found: {source}")
        fw, fh = int(frame_width), int(frame_height)
        if fw <= 0 or fh <= 0:
            raise VFXAuthoringError("frame size must be positive")
        from PIL import Image

        with Image.open(source) as image:
            width, height = image.size
        if width % fw or height % fh:
            raise VFXAuthoringError(
                f"image {width}x{height} is not a whole grid of {fw}x{fh} frames"
            )
        root = self.animation.resource_root
        if source.resolve().is_relative_to(root.resolve()):
            uri = (
                source.resolve().relative_to(root.resolve()).as_posix()
            )  # already inside the project
        else:
            target = root / "assets" / "vfx" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise VFXAuthoringError(f"a different {target.name} already exists in assets/vfx")
            shutil.copyfile(source, target)
            uri = target.relative_to(root).as_posix()
        count = (width // fw) * (height // fh)
        meta = {
            "frame_size": [fw, fh],
            "pivot": [0.5, 0.5],
            "clips": {
                PLAY_CLIP: {
                    "frames": list(range(count)),
                    "frame_duration": float(frame_duration),
                    "loop": False,
                }
            },
            "vfx": dict(VFX_DEFAULTS),
        }
        asset = CanonicalAsset(
            asset_id,
            SHEET_KIND,
            AssetSource(uri),
            tags=frozenset({"battle", VFX_TAG}),
            metadata=tuple(sorted(meta.items())),
        )
        self.document.execute(
            _AddAssetCommand(self.project.assets, asset, f"Import VFX {asset_id}")
        )
        return asset

    # -- usage, checks, preview ------------------------------------------------------
    def usages(self, asset_id):
        """``[(sequence_id, beat_id)]`` of action timeline beats that cue this VFX."""
        library = self.project.battle_presentation_library
        found = []
        for sequence_id in library.ids("motion_sequences"):
            for beat in library.require("motion_sequences", sequence_id).beats:
                if beat.channel == "vfx" and beat.cue == asset_id:
                    found.append((sequence_id, beat.beat_id))
        return found

    def _usage_text(self, asset_id):
        return ", ".join(f"{s}.{b}" for s, b in self.usages(asset_id))

    def problems(self, asset_id):
        found = list(self.animation.problems(asset_id))
        if PLAY_CLIP not in self.animation.data(asset_id)["clips"]:
            found.append(f"{asset_id}: no '{PLAY_CLIP}' clip — the battle has nothing to play")
        raw = dict(self.asset(asset_id).meta().get("vfx", {}))
        if raw.get("anchor", "center") not in VFX_ANCHORS:
            found.append(f"{asset_id}: unknown anchor {raw.get('anchor')}")
        if raw.get("blend", "normal") not in VFX_BLENDS:
            found.append(f"{asset_id}: unknown blend {raw.get('blend')}")
        if raw.get("align", "content") not in VFX_ALIGNS:
            found.append(f"{asset_id}: unknown align {raw.get('align')}")
        return found

    def content_center(self, asset_id, frames, fw, fh, columns):
        """Where the clip's picture sits in its frames (the battle centres it on the member)."""
        from PIL import Image

        path = self.animation.image_path(asset_id)
        if not path.is_file():
            return 0.0, 0.0
        boxes = []
        with Image.open(path) as image:
            image = image.convert("RGBA")
            for index in frames:
                x, y = (int(index) % columns) * fw, (int(index) // columns) * fh
                boxes.append(image.crop((x, y, x + fw, y + fh)).getbbox())
        return vfx_content_center(boxes, fw, fh)

    def preview(self, asset_id, age, *, duration=None):
        """What the battle draws ``age`` seconds into the effect, relative to a member's feet at
        (0, 0)."""
        data = self.animation.data(asset_id)
        clip = data["clips"].get(PLAY_CLIP)
        if not clip or not clip["frames"]:
            raise VFXAuthoringError(f"{asset_id} has no '{PLAY_CLIP}' frames")
        duration = self.duration(asset_id) if duration is None else float(duration)
        keyframe = vfx_keyframe(age, duration, len(clip["frames"]))
        frame_index = int(clip["frames"][keyframe])
        fw, fh = data["frame_size"]
        columns = max(1, (self.animation.image_size(asset_id) or (fw, fh))[0] // fw)
        source = ((frame_index % columns) * fw, (frame_index // columns) * fh, fw, fh)
        placement = self.placement(asset_id)
        content = self.content_center(asset_id, clip["frames"], fw, fh, columns)
        rect = vfx_rect(placement, 0.0, 0.0, PREVIEW_BODY_HEIGHT, fw, fh, content)
        return VFXPreview(keyframe, frame_index, source, rect, placement, duration)
