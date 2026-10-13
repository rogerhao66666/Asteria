"""Deterministic sprite auto-fixes and runtime atlas packing (ASTERIA_ASSET_PIPELINE §17, §21).

Safe fixes (SPEC §21): crop transparent border, pad frame, resize with
nearest-neighbour, align pivot, shift frame, normalize alpha, remove empty
outer rows/columns, repack atlas. Each fix returns the new image plus a
``FixReport``. Fixes that can lose visible pixels (downscaling resize,
shift/pad that pushes content off the frame, alpha normalization) are
*destructive*: ``apply_fix`` refuses them unless ``confirmed=True``, and
``preview_fix`` shows the result without committing it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageChops

FIXES = (
    "crop_transparent_border",
    "pad_frame",
    "resize_nearest",
    "align_pivot",
    "shift_frame",
    "normalize_alpha",
    "remove_empty_outer",
    "repack_atlas",
)


@dataclass(frozen=True, slots=True)
class FixReport:
    fix: str
    before_size: tuple[int, int]
    after_size: tuple[int, int]
    destructive: bool
    details: tuple = ()


class ConfirmationRequired(ValueError):
    """A destructive fix was applied without ``confirmed=True``."""


def _opaque_count(image):
    alpha = image.getchannel("A").histogram()
    return image.width * image.height - alpha[0]


def _rgba(image):
    return image if image.mode == "RGBA" else image.convert("RGBA")


def crop_transparent_border(image):
    image = _rgba(image)
    box = image.getchannel("A").getbbox()
    out = image.crop(box) if box else image.copy()
    return out, FixReport("crop_transparent_border", image.size, out.size, False, (("box", box),))


def remove_empty_outer(image):
    """Remove fully transparent outer rows/columns (alias kept for the SPEC wording)."""
    out, report = crop_transparent_border(image)
    return out, FixReport(
        "remove_empty_outer", report.before_size, report.after_size, False, report.details
    )


def pad_frame(image, size, *, anchor=(0.5, 1.0)):
    """Place the image on a transparent canvas of ``size`` (feet-anchored by default)."""
    image = _rgba(image)
    width, height = size
    x = round((width - image.width) * anchor[0])
    y = round((height - image.height) * anchor[1])
    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    out.alpha_composite(image, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))
    lost = _opaque_count(image) - _opaque_count(out)
    return out, FixReport(
        "pad_frame", image.size, out.size, lost > 0, (("offset", (x, y)), ("lost_pixels", lost))
    )


def resize_nearest(image, size):
    image = _rgba(image)
    out = image.resize(tuple(size), Image.NEAREST)
    downscale = size[0] < image.width or size[1] < image.height
    return out, FixReport(
        "resize_nearest",
        image.size,
        out.size,
        downscale,
        (("scale", (size[0] / image.width, size[1] / image.height)),),
    )


def shift_frame(image, dx, dy):
    image = _rgba(image)
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    out.alpha_composite(image, (max(0, dx), max(0, dy)), (max(0, -dx), max(0, -dy)))
    lost = _opaque_count(image) - _opaque_count(out)
    return out, FixReport(
        "shift_frame", image.size, out.size, lost > 0, (("shift", (dx, dy)), ("lost_pixels", lost))
    )


def content_pivot(image):
    """Current pivot of the opaque content: (centre x, bottom y) in 0..1."""
    image = _rgba(image)
    box = image.getchannel("A").getbbox()
    if not box:
        return (0.5, 1.0)
    return ((box[0] + box[2]) / 2 / image.width, box[3] / image.height)


def align_pivot(image, pivot=(0.5, 1.0)):
    """Shift the opaque content so its centre-bottom sits on ``pivot``."""
    image = _rgba(image)
    box = image.getchannel("A").getbbox()
    if not box:
        return image.copy(), FixReport(
            "align_pivot", image.size, image.size, False, (("shift", (0, 0)),)
        )
    dx = round(pivot[0] * image.width - (box[0] + box[2]) / 2)
    dy = round(pivot[1] * image.height - box[3])
    out, report = shift_frame(image, dx, dy)
    return out, FixReport("align_pivot", image.size, out.size, report.destructive, report.details)


def normalize_alpha(image, threshold=128):
    """Snap alpha to fully transparent / opaque (pixel art); RGB of transparent pixels is
    cleared."""
    image = _rgba(image)
    mask = image.getchannel("A").point(lambda a: 255 if a >= threshold else 0)
    out = Image.new("RGBA", image.size, (0, 0, 0, 0))
    solid = image.copy()
    solid.putalpha(mask)
    out.paste(solid, (0, 0), mask)
    difference = ImageChops.difference(image, out).convert("L").histogram()
    changed = image.width * image.height - difference[0]
    return out, FixReport(
        "normalize_alpha", image.size, out.size, changed > 0, (("changed_pixels", changed),)
    )


@dataclass
class Atlas:
    image: Image.Image
    regions: dict = field(default_factory=dict)  # name -> (x, y, w, h)


def repack_atlas(frames, *, padding=1, max_width=1024):
    """Shelf-pack ``{name: image}`` deterministically (tallest first, then name) into one atlas."""
    items = sorted(
        ((name, _rgba(img)) for name, img in frames.items()), key=lambda kv: (-kv[1].height, kv[0])
    )
    x = y = shelf = width = 0
    regions = {}
    for name, img in items:
        if img.width + padding > max_width:
            raise ValueError(f"{name} is wider than the atlas")
        if x + img.width + padding > max_width:
            x, y, shelf = 0, y + shelf + padding, 0
        regions[name] = (x, y, img.width, img.height)
        x += img.width + padding
        shelf = max(shelf, img.height)
        width = max(width, x)
    height = y + shelf
    atlas = Image.new("RGBA", (max(1, width), max(1, height)), (0, 0, 0, 0))
    for name, img in items:
        rx, ry, _, _ = regions[name]
        atlas.alpha_composite(img, (rx, ry))
    before = (sum(i.width for _, i in items), max((i.height for _, i in items), default=0))
    return Atlas(atlas, regions), FixReport(
        "repack_atlas", before, atlas.size, False, (("regions", len(regions)),)
    )


def preview_fix(name, image, *args, **kwargs):
    """Run a fix without committing anything: returns (before, after, report)."""
    if name not in FIXES or name == "repack_atlas":
        raise ValueError(f"unknown image fix {name}")
    after, report = globals()[name](image, *args, **kwargs)
    return image, after, report


def apply_fix(name, image, *args, confirmed=False, **kwargs):
    """Apply a fix; destructive results require ``confirmed=True`` (see ``preview_fix``)."""
    _, after, report = preview_fix(name, image, *args, **kwargs)
    if report.destructive and not confirmed:
        raise ConfirmationRequired(
            f"{name} would lose pixels: preview it and confirm ({report.details})"
        )
    return after, report
