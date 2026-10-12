"""Editor image tools (AST-11): the asset pipeline's safe auto-fixes and atlas packing, from the Asset list.

* Auto-fix Image... - choose a fix, see the image before and after, apply. The original is kept as
  ``<name>.bak.png``; fixes that would lose visible pixels ask for confirmation first (``autofix``).
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
    return pixmap.scaled(pixmap.width() * scale, pixmap.height() * scale, Qt.KeepAspectRatio, Qt.FastTransformation)


def fix_image_file(path, fix, *, confirmed=False):
    """Apply ``fix`` to the PNG at ``path``; the original is kept beside it. Returns the FixReport."""
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
    """Pack the PNGs at ``paths`` into ``output`` (PNG) and ``output``.json (``{"regions": {name: [x,y,w,h]}}``)."""
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
    meta.write_text(json.dumps({"image": output.name, "regions": regions}, indent=2) + "\n", encoding="utf-8")
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
        size = f"{report.before_size[0]}x{report.before_size[1]} → {report.after_size[0]}x{report.after_size[1]}"
        warning = "  This fix loses visible pixels; you will be asked to confirm." if report.destructive else ""
        self.report.setText(f"{size}.{warning}")
        self.preview_report = report

    def apply(self, *, confirm=None):
        confirmed = False
        if self.preview_report.destructive:
            answer = (
                confirm if confirm is not None else QMessageBox.question(self, "Auto-fix Image", self.report.text())
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
