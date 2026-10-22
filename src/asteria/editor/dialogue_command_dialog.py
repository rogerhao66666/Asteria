"""The Dialogue command's editor: who speaks, the text and the portrait shown with it, beside a
preview of the game's message window (the project's Message Settings decide face or bust)."""

from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .game_systems_widget import _IconPicker
from .image_tools import PortraitLibrary, project_root

DIALOGUE_KEYS = ("speaker", "text", "portrait_asset_id", "portrait_side")


def portrait_pixmap(document, portrait_id):
    """The whole picture ``portrait_id`` names (a project path, an image asset or a sheet cell),
    or a null QPixmap."""
    from asteria.runtime.menu_icons import icon_source

    portrait_id = str(portrait_id or "").strip()
    project = getattr(document, "project", None)
    if not portrait_id or project is None:
        return QPixmap()
    root = project_root(document)
    path = Path(portrait_id) if Path(portrait_id).is_absolute() else root / portrait_id
    region = None
    if not path.is_file():
        try:
            source = icon_source(project, portrait_id)
        except (KeyError, ValueError):
            source = None
        if source is None:
            return QPixmap()
        uri, region = source
        path = Path(uri) if Path(uri).is_absolute() else root / uri
    pixmap = QPixmap(str(path)) if path.is_file() else QPixmap()
    if not pixmap.isNull() and region:
        pixmap = pixmap.copy(*region)
    return pixmap


def fitted_size(pixmap, width, height):
    """``pixmap``'s size fitted inside ``width`` x ``height`` with its proportions kept."""
    scale = min(width / max(1, pixmap.width()), height / max(1, pixmap.height()))
    return max(1, round(pixmap.width() * scale)), max(1, round(pixmap.height() * scale)), scale


def fit_pixmap(pixmap, width, height):
    """As the game fits a portrait: made larger with sharp pixels, made smaller smoothed."""
    if pixmap.isNull():
        return pixmap
    w, h, scale = fitted_size(pixmap, width, height)
    mode = Qt.FastTransformation if scale >= 1 else Qt.SmoothTransformation
    return pixmap.scaled(w, h, Qt.IgnoreAspectRatio, mode)


class _PortraitPicker(_IconPicker):
    """The icon field's list and Browse…, for portraits: a bigger preview of the picture."""

    PREVIEW = 64

    def __init__(self, library, parent=None):
        super().__init__(library, parent)
        self.preview.setFixedSize(self.PREVIEW, self.PREVIEW)
        self.browse.setToolTip("Use a picture file of your own as the portrait")
        self._shown()

    def _shown(self, *_):
        document = getattr(self.library, "document", None)
        pixmap = portrait_pixmap(document, self.text())
        side = self.PREVIEW - 8  # inside its frame
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("None")  # the frame says there is no picture yet
        else:
            self.preview.setPixmap(fit_pixmap(pixmap, side, side))
        self.combo.setToolTip(self.text())
        self.changed.emit()

    def _browse(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a portrait", "", "Images (*.png *.jpg *.jpeg *.webp)"
        )
        if path and self.library is not None:
            portrait_id = self.library.import_file(path)
            self._fill()
            self.setText(portrait_id)


class _MessagePreview(QWidget):
    """The game's message window drawn small: the same places the game uses on a 960 x 540
    screen (face in a square at the window's end, or a bust standing on the window)."""

    STAGE = (960.0, 540.0)
    BOX_HEIGHT = 130
    BUST_SHARE = 0.55

    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setMinimumSize(300, 190)

    def _settings(self):
        project = getattr(self.owner.document, "project", None)
        values = getattr(getattr(project, "rpg_database", None), "message_settings", None) or {}
        settings = values[sorted(values)[0]] if values else None
        style = getattr(settings, "portrait_style", "face")
        return style, int(getattr(settings, "portrait_size", 0) or 0)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 26, 30))
        stage_w, stage_h = self.STAGE
        s = min(self.width() / stage_w, self.height() / stage_h)
        ox, oy = (self.width() - stage_w * s) / 2, (self.height() - stage_h * s) / 2
        painter.setPen(QPen(QColor(78, 82, 92), 1))
        painter.drawRect(QRectF(ox, oy, stage_w * s, stage_h * s))

        def rect(x, y, w, h):  # stage pixels -> widget
            return QRectF(ox + x * s, oy + y * s, w * s, h * s)

        def draw(target, scale):  # as the game: enlarged pixels stay sharp, shrunk ones smooth
            painter.setRenderHint(QPainter.SmoothPixmapTransform, scale * s < 1)
            painter.drawPixmap(target, pixmap, QRectF(pixmap.rect()))

        style, size = self._settings()
        pixmap = portrait_pixmap(self.owner.document, self.owner.portrait.text())
        left = self.owner.side.currentData() != "right"
        height, face = self.BOX_HEIGHT, None
        if not pixmap.isNull() and style == "face":
            side = size or self.BOX_HEIGHT - 24
            height = max(height, side + 24)
        box = (60, stage_h - 100 - height, stage_w - 120, height)
        x, y, w, h = box
        if not pixmap.isNull() and style == "bust":
            tall = size or round(stage_h * self.BUST_SHARE)
            pw, ph, scale = fitted_size(pixmap, w // 2, tall)
            at = x + 24 if left else x + w - 24 - pw
            draw(rect(at, y + h - ph, pw, ph), scale)
        elif not pixmap.isNull():
            side = size or h - 24
            pw, ph, scale = fitted_size(pixmap, side, side)
            cell_x = x + 12 if left else x + w - 12 - side
            cell_y = y + (h - side) // 2
            face = (cell_x, cell_y, side)
            target = rect(cell_x + (side - pw) // 2, cell_y + (side - ph) // 2, pw, ph)
        painter.setPen(QPen(QColor(240, 201, 93), max(1.0, 2 * s)))
        painter.setBrush(QColor(10, 14, 24, 235))
        painter.drawRoundedRect(rect(*box), 6 * s, 6 * s)
        text_x = x + 24
        if face is not None:
            draw(target, scale)
            if left:
                text_x = face[0] + face[2] + 18
        font = QFont(self.font())
        font.setPixelSize(max(6, round(20 * s)))
        painter.setFont(font)
        speaker = self.owner.speaker.text().strip()
        if speaker:
            painter.setPen(QColor(255, 220, 124))
            painter.drawText(rect(text_x, y + 12, w, 28), Qt.AlignLeft | Qt.AlignTop, speaker)
        font.setPixelSize(max(6, round(18 * s)))
        painter.setFont(font)
        painter.setPen(QColor(245, 245, 250))
        lines = self.owner.text.toPlainText().split("\n")[:3]
        for row, line in enumerate(lines):
            painter.drawText(
                rect(text_x, y + 46 + row * 26, x + w - text_x - 12, 26),
                Qt.AlignLeft | Qt.AlignTop,
                line,
            )
        painter.end()


class DialogueCommandDialog(QDialog):
    """Edit a DIALOGUE instruction: who speaks, the text, and the portrait shown with it."""

    def __init__(self, args=None, *, document=None, parent=None):
        super().__init__(parent)
        self.document = document
        self._initial_args = dict(args or {})
        self.setWindowTitle("Dialogue")
        root = QVBoxLayout(self)
        content = QHBoxLayout()
        form_box = QWidget(self)
        form = QFormLayout(form_box)
        self.speaker = QLineEdit(self._text("speaker"), form_box)
        self.speaker.setPlaceholderText("Nobody (narration)")
        self.text = QPlainTextEdit(self._text("text"), form_box)
        self.text.setTabChangesFocus(True)
        self.text.setMinimumHeight(self.text.fontMetrics().lineSpacing() * 4 + 16)
        self.portrait = _PortraitPicker(PortraitLibrary(document), form_box)
        self.portrait.setText(self._text("portrait_asset_id"))
        self.portrait.setToolTip(
            "Shown with the line in the message window. Pictures in a portraits or faces "
            "folder of the project are listed; Browse… copies one in."
        )
        self.side = QComboBox(form_box)
        self.side.addItem("Left", "left")
        self.side.addItem("Right", "right")
        side = self._text("portrait_side").strip().lower() or "left"
        self.side.setCurrentIndex(max(0, self.side.findData(side)))
        form.addRow("Speaker", self.speaker)
        form.addRow("Text", self.text)
        form.addRow("Portrait", self.portrait)
        form.addRow("Portrait side", self.side)
        self.preview = _MessagePreview(self)
        content.addWidget(form_box, 1)
        content.addWidget(self.preview, 1)
        root.addLayout(content)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        for signal in (
            self.speaker.textChanged,
            self.text.textChanged,
            self.portrait.changed,
            self.side.currentIndexChanged,
        ):
            signal.connect(self._changed)
        self._changed()

    def _text(self, key):
        value = self._initial_args.get(key, "")
        return str(value if value is not None else "")

    def _changed(self, *_):
        save = self.buttons.button(QDialogButtonBox.Save)
        ready = bool(self.text.toPlainText().strip())  # a line needs words
        save.setEnabled(ready)
        save.setToolTip("" if ready else "Write the line's text first")
        self.preview.update()

    def result_args(self):
        """The instruction's arguments: any this dialog does not edit are kept; the portrait
        keys are written only when set."""
        args = {k: v for k, v in self._initial_args.items() if k not in DIALOGUE_KEYS}
        args["speaker"] = self.speaker.text().strip()
        args["text"] = self.text.toPlainText().rstrip()
        if self.portrait.text():
            args["portrait_asset_id"] = self.portrait.text()
        if self.side.currentData() == "right":
            args["portrait_side"] = "right"
        return args
