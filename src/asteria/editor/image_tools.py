"""Editor image tools (AST-11): the asset pipeline's safe auto-fixes and atlas packing, from the
Asset list.

* Auto-fix Image... - choose a fix, see the image before and after, apply. The original is kept as
  ``<name>.bak.png``; fixes that would lose visible pixels ask for confirmation first
  (``autofix``).
* Pack into Atlas... - the selected images packed into one PNG plus a JSON of named regions.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QVBoxLayout,
)

from asteria.assets.autofix import ConfirmationRequired, apply_fix, preview_fix, repack_atlas

# fixes that need no extra numbers: the dialog offers these
SIMPLE_FIXES = {
    "crop_transparent_border": "Crop transparent border",
    "remove_empty_outer": "Remove empty outer rows / columns",
    "normalize_alpha": "Normalize alpha (no half-transparent pixels)",
    "align_pivot": "Align content to the bottom-centre pivot",
}


def project_root(document):
    path = getattr(document, "file_path", None)
    return Path(path).parent if path else Path.cwd()


def _pixmap(image, box=220):
    from io import BytesIO

    data = BytesIO()
    image.save(data, "PNG")
    qimage = QImage.fromData(data.getvalue())
    pixmap = QPixmap.fromImage(qimage)
    scale = max(1, min(box // max(1, pixmap.width()), box // max(1, pixmap.height())))
    return pixmap.scaled(
        pixmap.width() * scale, pixmap.height() * scale, Qt.KeepAspectRatio, Qt.FastTransformation
    )


def fix_image_file(path, fix, *, confirmed=False):
    """Apply ``fix`` to the PNG at ``path``; the original is kept beside it. Returns the
    FixReport."""
    from PIL import Image

    path = Path(path)
    with Image.open(path) as source:
        image = source.convert("RGBA")
    after, report = apply_fix(fix, image, confirmed=confirmed)
    backup = path.with_name(path.stem + ".bak" + path.suffix)
    if not backup.exists():
        shutil.copy2(path, backup)
    after.save(path)
    return report


def pack_atlas(paths, output, *, padding=1, max_width=1024):
    """Pack the PNGs at ``paths`` into ``output`` (PNG) and ``output``.json (``{"regions": {name:
    [x,y,w,h]}}``)."""
    from PIL import Image

    frames = {}
    for path in paths:
        path = Path(path)
        with Image.open(path) as image:
            frames[path.stem] = image.convert("RGBA")
    atlas, report = repack_atlas(frames, padding=padding, max_width=max_width)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    atlas.image.save(output)
    regions = {name: list(rect) for name, rect in sorted(atlas.regions.items())}
    meta = output.with_suffix(".json")
    meta.write_text(
        json.dumps({"image": output.name, "regions": regions}, indent=2) + "\n", encoding="utf-8"
    )
    return output, meta, report


class ImageFixDialog(QDialog):
    """Preview a safe fix on one image, then apply it."""

    def __init__(self, path, parent=None):
        from PIL import Image

        super().__init__(parent)
        self.setWindowTitle(f"Auto-fix Image — {Path(path).name}")
        self.path = Path(path)
        with Image.open(self.path) as source:
            self.image = source.convert("RGBA")
        self.fix = QComboBox()
        for key, label in SIMPLE_FIXES.items():
            self.fix.addItem(label, key)
        self.fix.currentIndexChanged.connect(self._preview)
        self.before, self.after = QLabel(), QLabel()
        for label in (self.before, self.after):
            label.setAlignment(Qt.AlignCenter)
            label.setMinimumSize(240, 240)
        self.report = QLabel()
        self.report.setObjectName("MutedLabel")
        self.report.setWordWrap(True)
        images = QHBoxLayout()
        for caption, label in (("Before", self.before), ("After", self.after)):
            column = QVBoxLayout()
            title = QLabel(caption)
            title.setObjectName("FieldLabel")
            column.addWidget(title)
            column.addWidget(label, 1)
            images.addLayout(column)
        buttons = QDialogButtonBox(QDialogButtonBox.Apply | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.fix)
        layout.addLayout(images, 1)
        layout.addWidget(self.report)
        layout.addWidget(buttons)
        self.applied = None
        self._preview()

    @property
    def fix_id(self):
        return self.fix.currentData()

    def _preview(self, *_):
        before, after, report = preview_fix(self.fix_id, self.image)
        self.before.setPixmap(_pixmap(before))
        self.after.setPixmap(_pixmap(after))
        size = (
            f"{report.before_size[0]}x{report.before_size[1]} → "
            f"{report.after_size[0]}x{report.after_size[1]}"
        )
        warning = (
            "  This fix loses visible pixels; you will be asked to confirm."
            if report.destructive
            else ""
        )
        self.report.setText(f"{size}.{warning}")
        self.preview_report = report

    def apply(self, *, confirm=None):
        confirmed = False
        if self.preview_report.destructive:
            answer = (
                confirm
                if confirm is not None
                else QMessageBox.question(self, "Auto-fix Image", self.report.text())
            )
            confirmed = answer in (True, QMessageBox.Yes)
            if not confirmed:
                return None
        try:
            self.applied = fix_image_file(self.path, self.fix_id, confirmed=confirmed)
        except ConfirmationRequired:
            return None
        self.accept()
        return self.applied


_FORGED_ICONS = {}  # (icon id, size) -> QIcon: drawing the built-in library once is enough


def forged_qicon(icon_id, size=32):
    """A QIcon of a built-in (``forged:``) icon id, or ``None``."""
    key = (str(icon_id), int(size))
    if key not in _FORGED_ICONS:
        _FORGED_ICONS[key] = _draw_forged_qicon(icon_id, size)
    return _FORGED_ICONS[key]


def _draw_forged_qicon(icon_id, size):
    from PySide6.QtGui import QIcon, QImage, QPixmap

    from asteria.runtime.menu_icons import forged_surface

    surface = forged_surface(icon_id, size)
    if surface is None:
        return None
    import pygame

    data = pygame.image.tobytes(surface, "RGBA")
    image = QImage(data, size, size, size * 4, QImage.Format_RGBA8888).copy()
    return QIcon(QPixmap.fromImage(image))


_SKIPPED_FOLDERS = {
    "__pycache__",
    "node_modules",
    "venv",
    "site-packages",
    "build",
    "dist",
    "local_reference",
}


def _icon_files(root, limit=600, depth=4, folder_budget=1500):
    """PNG files in folders named ``icons`` under ``root`` (a bounded walk: hidden and build
    folders are skipped, so a project opened from a big folder still lists quickly)."""
    import os

    found = []
    base_depth = len(Path(root).parts)
    for visited, (folder, names, files) in enumerate(os.walk(root)):
        if visited >= folder_budget:  # a very big folder: stop looking
            break
        names[:] = sorted(
            n
            for n in names
            if not n.startswith(".")
            and n not in _SKIPPED_FOLDERS
            and len(Path(folder, n).parts) - base_depth <= depth
        )
        if Path(folder).name == "icons":
            found.extend(Path(folder, f) for f in sorted(files) if f.lower().endswith(".png"))
        if len(found) >= limit:
            break
    return found[:limit]


def icon_pixmap(document, icon_id, size=32):
    """The picture an ``icon_id`` field names (an icon asset, a picture file of the project, or
    a ``forged:`` icon) as a ``size`` QPixmap, or ``None``."""
    from asteria.runtime.menu_icons import icon_source

    icon_id = str(icon_id or "").strip()
    if not icon_id:
        return None
    if icon_id.startswith("forged:"):
        icon = forged_qicon(icon_id, size)
        return None if icon is None else icon.pixmap(size, size)
    project = getattr(document, "project", None)
    root = project_root(document)
    region = None
    path = Path(icon_id) if Path(icon_id).is_absolute() else root / icon_id
    if not path.is_file() and project is not None:  # an icon asset (maybe a sheet cell)
        try:
            uri, region = icon_source(project, icon_id)
        except (KeyError, ValueError):
            return None
        path = Path(uri) if Path(uri).is_absolute() else root / uri
    if not path.is_file():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    if region:
        pixmap = pixmap.copy(*region)
    return pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.FastTransformation)


def icon_choices(document):
    """Every icon an ``icon_id`` field can take, as ``((icon id, QIcon or None), ...)``: the
    project's own picture files (any ``icons`` folder) and ``icon`` assets, then the engine's
    built-in library (``forged:<kind>``)."""
    from PySide6.QtGui import QIcon

    from asteria.graphics.forged_icons import DRAWINGS
    from asteria.runtime.menu_icons import icon_source

    project = getattr(document, "project", None)
    if project is None:
        return ()
    root = project_root(document)
    sheets = {}
    choices, seen = [], set()
    for asset in sorted(project.assets.query(kind="icon"), key=lambda a: a.asset_id):
        uri, region = icon_source(project, asset.asset_id)
        path = Path(uri) if Path(uri).is_absolute() else root / uri
        if path not in sheets:
            sheets[path] = QPixmap(str(path)) if path.is_file() else QPixmap()
        sheet = sheets[path]
        icon = None
        if not sheet.isNull():
            cell = sheet.copy(*region) if region else sheet
            icon = QIcon(cell.scaled(32, 32, Qt.KeepAspectRatio, Qt.FastTransformation))
        choices.append((asset.asset_id, icon))
        seen.add(asset.asset_id)
    if root.is_dir():  # picture files in the project's icon folders
        for path in _icon_files(root):
            rel = path.relative_to(root).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            pixmap = QPixmap(str(path))
            icon = None
            if not pixmap.isNull():
                icon = QIcon(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.FastTransformation))
            choices.append((rel, icon))
    for kind in sorted(DRAWINGS):
        choices.append((f"forged:{kind}", forged_qicon(f"forged:{kind}")))
    return tuple(choices)


class IconLibrary:
    """The icons a project's ``icon_id`` fields can use: ``choices()`` for pickers and
    ``import_file(path)`` to bring a picture of the author's own into the project."""

    FOLDER = "icons"

    def __init__(self, document):
        self.document = document

    CACHE_SECONDS = 3.0  # a form that builds several pickers asks for the list once

    def choices(self):
        import time

        now = time.monotonic()
        cached = getattr(self, "_cache", None)
        if cached is not None and now - cached[0] < self.CACHE_SECONDS:
            return cached[1]
        choices = icon_choices(self.document)
        self._cache = (now, choices)
        return choices

    def import_file(self, path):
        """Use the picture at ``path`` as an icon: a file already inside the project keeps its
        place; any other is copied to ``<project>/icons/``. Returns the ``icon_id`` (a path
        relative to the project folder)."""
        import shutil

        source = Path(path).resolve()
        root = project_root(self.document).resolve()
        try:
            return source.relative_to(root).as_posix()
        except ValueError:
            pass
        folder = root / self.FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / source.name
        counter = 2
        while target.exists() and target.read_bytes() != source.read_bytes():
            target = folder / f"{source.stem}_{counter}{source.suffix}"
            counter += 1
        if not target.exists():
            shutil.copyfile(source, target)
        return target.relative_to(root).as_posix()
