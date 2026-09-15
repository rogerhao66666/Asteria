"""Procedural character sprites, so a new Actor has art immediately.

A new Actor otherwise has no field appearance at all until the author draws or
imports a sheet, which makes it invisible on the map. This draws a sprite in
the same 16x24, two-frame shape as the bundled starter character, with the
palette derived from a seed so the same Actor always regenerates identically
and two different Actors look different.

Pixels are placed directly on a QImage rather than composited from layer art:
there is no layered character atlas in the project to composite from, and a
seeded palette over one body template already distinguishes cast members at
map scale.
"""
from __future__ import annotations

import colorsys
import json
import shutil
import tempfile
import uuid
import zlib
from pathlib import Path

try:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import (
        QBrush, QColor, QImage, QPainter, QPainterPath, QPen,
    )
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover - headless import guard
    QT_AVAILABLE = False

from asteria.assets.types import AssetRecord

# Chibi proportions, like RPG Maker's field sprites: the head is roughly the
# top 45% of the figure with oversized eyes, which is what reads as "an RPG
# character" at map scale. A realistic 1:6 figure at this size just looks like
# a smudge.
WIDTH = 48
HEIGHT = 64
FRAMES = 2

_SKIN_TONES = ((0.08, 0.28, 0.97), (0.07, 0.36, 0.87), (0.06, 0.45, 0.70), (0.05, 0.52, 0.52))


def _rgb(h, s, v):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def character_palette(seed):
    """Deterministic skin/hair/outfit colors for one seed string.

    Every material comes as a base plus a lighter and a darker tone: a flat
    fill reads as a paper cut-out, while a three-tone ramp with a dark outline
    is what makes a small sprite look drawn rather than generated.
    """
    digest = zlib.crc32(str(seed).encode("utf-8"))
    skin = _SKIN_TONES[digest % len(_SKIN_TONES)]
    hair_hue = ((digest >> 4) % 360) / 360.0
    shirt_hue = ((digest >> 12) % 360) / 360.0
    pants_hue = ((digest >> 20) % 360) / 360.0
    # The trim sits opposite the shirt on the wheel so it always reads as a
    # deliberate accent (collar, belt) instead of noise.
    accent_hue = shirt_hue + 0.5
    return {
        "outline": _rgb(hair_hue, 0.45, 0.16),
        "skin": _rgb(*skin),
        "skin_shadow": _rgb(skin[0], skin[1] + 0.14, skin[2] - 0.20),
        "hair": _rgb(hair_hue, 0.62, 0.48),
        "hair_light": _rgb(hair_hue, 0.48, 0.70),
        "hair_dark": _rgb(hair_hue, 0.70, 0.30),
        "eye": _rgb(hair_hue, 0.40, 0.14),
        "eye_white": QColor(248, 248, 252),
        "iris": _rgb(hair_hue + 0.45, 0.72, 0.66),
        "shirt": _rgb(shirt_hue, 0.55, 0.80),
        "shirt_light": _rgb(shirt_hue, 0.38, 0.95),
        "shirt_shadow": _rgb(shirt_hue, 0.66, 0.55),
        "accent": _rgb(accent_hue, 0.62, 0.80),
        "pants": _rgb(pants_hue, 0.45, 0.52),
        "pants_shadow": _rgb(pants_hue, 0.55, 0.34),
        "shoe": _rgb(pants_hue, 0.42, 0.30),
        "shoe_light": _rgb(pants_hue, 0.35, 0.44),
    }


# Drawn as layered shapes rather than a fixed pixel template: at 48x64 there
# is room for a real silhouette (hair styles, a fringe, shaped eyes, armour
# trim), and each layer can vary independently the way RPG Maker's character
# generator composites hair/face/outfit pieces.

HAIR_STYLES = ("short", "long", "spiky", "ponytail")
OUTFITS = ("tunic", "robe", "armour")

# Figure metrics inside the 48x64 frame.
_HEAD = QRectF(12, 3, 24, 25)
_EYE_Y = 17
_FRINGE_BOTTOM = 15
_BODY_TOP = 31
_BODY_BOTTOM = 48


def _outlined(painter, palette, width=1.6):
    painter.setPen(QPen(palette["outline"], width))


def _draw_hair_back(painter, palette, style):
    """The mass that sits behind the head — long hair and ponytails only."""
    painter.setBrush(QBrush(palette["hair_dark"]))
    _outlined(painter, palette)
    if style == "long":
        painter.drawRoundedRect(QRectF(9, 10, 30, 34), 12, 12)
    elif style == "ponytail":
        painter.drawEllipse(QRectF(30, 22, 14, 22))


def _draw_hair_front(painter, palette, style):
    """Cap and side locks only.

    Clipped to the top of the head on purpose: hair drawn over the whole
    skull covers the eyes, and a face with no eyes is the single thing that
    stops a small sprite reading as a character.
    """
    painter.save()
    painter.setClipRect(QRectF(0, 0, WIDTH, _FRINGE_BOTTOM))
    painter.setBrush(QBrush(palette["hair"]))
    _outlined(painter, palette)
    cap = QPainterPath()
    if style == "spiky":
        cap.moveTo(8, 22)
        for index in range(6):
            x = 8 + index * 5.5
            cap.lineTo(x + 2.75, 0 + (4 if index % 2 else 0))
            cap.lineTo(x + 5.5, 11 - (3 if index % 2 else 0))
        cap.lineTo(41, 22)
        cap.closeSubpath()
    else:
        cap.addEllipse(QRectF(9, 2, 30, 22))
    painter.drawPath(cap)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(palette["hair_light"]))
    painter.drawEllipse(QRectF(15, 4, 12, 5))
    painter.restore()

    # Side locks frame the face without crossing it.
    painter.setBrush(QBrush(palette["hair"]))
    _outlined(painter, palette, 1.2)
    lock_bottom = 22 if style in ("short", "spiky") else 32
    painter.drawRoundedRect(QRectF(9.5, 9, 4.0, lock_bottom - 9), 2.0, 2.0)
    painter.drawRoundedRect(QRectF(34.5, 9, 4.0, lock_bottom - 9), 2.0, 2.0)


def _draw_face(painter, palette):
    painter.setBrush(QBrush(palette["skin"]))
    _outlined(painter, palette)
    painter.drawEllipse(_HEAD)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(palette["skin_shadow"]))
    painter.drawEllipse(QRectF(13, 24, 22, 6))

    for eye_x in (17.5, 26.0):
        painter.setBrush(QBrush(palette["eye_white"]))
        _outlined(painter, palette, 1.0)
        painter.drawEllipse(QRectF(eye_x, _EYE_Y - 3, 4.5, 5.5))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(palette["iris"]))
        painter.drawEllipse(QRectF(eye_x + 0.9, _EYE_Y - 2, 2.8, 3.6))
        painter.setBrush(QBrush(palette["eye"]))
        painter.drawEllipse(QRectF(eye_x + 1.6, _EYE_Y - 1.3, 1.4, 2.4))
        painter.setBrush(QBrush(palette["eye_white"]))
        painter.drawEllipse(QRectF(eye_x + 1.2, _EYE_Y - 2.1, 1.1, 1.1))


def _draw_body(painter, palette, outfit):
    painter.setBrush(QBrush(palette["skin_shadow"]))
    _outlined(painter, palette, 1.2)
    painter.drawRect(QRectF(21, _BODY_TOP - 5, 6, 6))
    painter.setBrush(QBrush(palette["skin"]))
    _outlined(painter, palette)
    painter.drawRoundedRect(QRectF(9, _BODY_TOP + 2, 6, 13), 3, 3)
    painter.drawRoundedRect(QRectF(33, _BODY_TOP + 2, 6, 13), 3, 3)

    torso = QPainterPath()
    if outfit == "robe":
        torso.moveTo(15, _BODY_TOP)
        torso.lineTo(33, _BODY_TOP)
        torso.lineTo(38, _BODY_BOTTOM + 6)
        torso.lineTo(10, _BODY_BOTTOM + 6)
    else:
        torso.moveTo(14, _BODY_TOP)
        torso.lineTo(34, _BODY_TOP)
        torso.lineTo(35, _BODY_BOTTOM)
        torso.lineTo(13, _BODY_BOTTOM)
    torso.closeSubpath()
    painter.setBrush(QBrush(palette["shirt"]))
    _outlined(painter, palette)
    painter.drawPath(torso)

    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(palette["shirt_light"]))
    painter.drawRect(QRectF(16, _BODY_TOP + 1, 5, _BODY_BOTTOM - _BODY_TOP - 3))
    painter.setBrush(QBrush(palette["shirt_shadow"]))
    painter.drawRect(QRectF(30, _BODY_TOP + 1, 4, _BODY_BOTTOM - _BODY_TOP - 3))

    collar = QPainterPath()
    collar.moveTo(19, _BODY_TOP)
    collar.lineTo(24, _BODY_TOP + 7)
    collar.lineTo(29, _BODY_TOP)
    collar.closeSubpath()
    painter.setBrush(QBrush(palette["accent"]))
    _outlined(painter, palette, 1.2)
    painter.drawPath(collar)

    if outfit == "armour":
        painter.setBrush(QBrush(palette["accent"]))
        painter.drawEllipse(QRectF(11, _BODY_TOP - 1, 11, 9))
        painter.drawEllipse(QRectF(26, _BODY_TOP - 1, 11, 9))
    painter.setBrush(QBrush(palette["accent"]))
    _outlined(painter, palette, 1.2)
    painter.drawRect(QRectF(14, _BODY_BOTTOM - 6, 20, 5))


def _draw_legs(painter, palette, stride):
    """stride 0 = standing, 1 = mid-step (the second frame)."""
    left_x, right_x = (17.0, 25.0) if stride == 0 else (14.5, 27.0)
    for index, x in enumerate((left_x, right_x)):
        lift = 0.0 if stride == 0 else (2.0 if index == 0 else 0.0)
        painter.setBrush(QBrush(palette["pants"]))
        _outlined(painter, palette)
        painter.drawRoundedRect(QRectF(x, _BODY_BOTTOM - 1, 6.5, 10 - lift), 2, 2)
        painter.setBrush(QBrush(palette["shoe"]))
        painter.drawRoundedRect(QRectF(x - 1, _BODY_BOTTOM + 8 - lift, 8.5, 6), 2, 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(palette["shoe_light"]))
        painter.drawRect(QRectF(x - 0.5, _BODY_BOTTOM + 8.5 - lift, 7.5, 1.6))


def _draw_character(painter, palette, style, outfit, stride):
    painter.setRenderHint(QPainter.Antialiasing, True)
    _draw_hair_back(painter, palette, style)
    _draw_legs(painter, palette, stride)
    _draw_body(painter, palette, outfit)
    _draw_face(painter, palette)
    _draw_hair_front(painter, palette, style)


def character_style(seed):
    """Hair style and outfit for a seed, the way a generator picks parts."""
    digest = zlib.crc32(str(seed).encode("utf-8"))
    return (
        HAIR_STYLES[(digest >> 6) % len(HAIR_STYLES)],
        OUTFITS[(digest >> 16) % len(OUTFITS)],
    )


def generate_character_atlas(seed):
    """A 2-frame (idle, step) character atlas image for `seed`."""
    if not QT_AVAILABLE:
        raise RuntimeError("PySide6 is required")
    palette = character_palette(seed)
    style, outfit = character_style(seed)
    image = QImage(WIDTH * FRAMES, HEIGHT, QImage.Format_RGBA8888)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    for frame in range(FRAMES):
        painter.save()
        painter.translate(frame * WIDTH, 0)
        _draw_character(painter, palette, style, outfit, frame)
        painter.restore()
    painter.end()
    return image


def _sheet_frames():
    return [
        {"x": index * WIDTH, "y": 0, "width": WIDTH, "height": HEIGHT}
        for index in range(FRAMES)
    ]


def _write_dir(document, asset_dir):
    """Where generated files go: the project folder, or a staging dir until saved."""
    if document.file_path is not None:
        target = Path(document.file_path).parent / asset_dir
    else:
        staging = getattr(document, "staging_dir", None)
        if staging is None:
            staging = Path(tempfile.mkdtemp(prefix="asteria-staged-"))
            document.staging_dir = staging
        target = staging / asset_dir
    target.mkdir(parents=True, exist_ok=True)
    return target


def _stage(document, source_path, written):
    if document.file_path is None:
        document.staged_assets[source_path] = written


def generate_actor_appearance(document, actor_id, *, asset_dir="characters", seed=None):
    """Draw, register and apply a generated sprite for one Actor.

    Works on an unsaved project: the image is written to a staging directory
    and copied into the project folder on save. `seed` picks the look — a new
    random one each press, so pressing again re-rolls the character.

    Returns the new sprite-sheet asset id.
    """
    from .actor_appearance import apply_actor_appearance
    from .resource_resolver import resolve_project_resources
    from .storage import EditorStorageError

    actor_id = str(actor_id)
    if seed is None:
        seed = f"{actor_id}:{uuid.uuid4().hex}"
    target_dir = _write_dir(document, asset_dir)

    texture_name = f"{actor_id}_atlas.png"
    sheet_name = f"{actor_id}.sprite_sheet.json"
    image = generate_character_atlas(seed)
    texture_path = target_dir / texture_name
    if not image.save(str(texture_path), "PNG"):
        raise EditorStorageError(f"could not write {texture_name}")

    texture_source = f"{asset_dir}/{texture_name}"
    sheet_source = f"{asset_dir}/{sheet_name}"
    _stage(document, texture_source, texture_path)
    texture = _existing_record(document, texture_source)
    if texture is None:
        texture = AssetRecord.create(kind="texture", source_path=texture_source)
        document.project.assets.add(texture)
    sheet_path = target_dir / sheet_name
    sheet_path.write_text(
        json.dumps(
            {"texture_asset_id": texture.id, "frames": _sheet_frames()},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    _stage(document, sheet_source, sheet_path)
    sheet = _existing_record(document, sheet_source)
    if sheet is None:
        sheet = AssetRecord.create(kind="sprite_sheet", source_path=sheet_source)
        document.project.assets.add(sheet)

    # The new sheet has to become a resolved asset view before anything can
    # render it — records alone are not enough.
    resolve_project_resources(document)
    apply_actor_appearance(document, actor_id, sheet.id, 0, False)
    return sheet.id


def materialize_staged_assets(document, project_dir):
    """Copy staged generated files into a project that now has a folder."""
    staged = getattr(document, "staged_assets", {})
    for source_path, written in list(staged.items()):
        target = Path(project_dir) / source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if Path(written).is_file():
            shutil.copyfile(written, target)
    staged.clear()


def _existing_record(document, source_path):
    return next(
        (r for r in document.project.assets.records() if r.source_path == source_path),
        None,
    )
