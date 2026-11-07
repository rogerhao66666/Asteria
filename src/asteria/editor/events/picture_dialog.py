"""Structured editor and screen-space preview for picture world commands."""

from pathlib import Path

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.assets.image_tools import PictureLibrary, movie_first_frame
from asteria.editor.events.dialogue_dialog import _PortraitPicker, fit_pixmap
from asteria.editor.events.picture_preview import (
    WHITE,
    PicturePreview,
    cycled_frame,
    moved,
    parse_rgb,
    sheet_words,
    system_words,
    tinted,
)
from asteria.editor.events.world_command_form import _Color, command_words
from asteria.editor.menus.layout_authoring import MenuLayoutAuthoringController
from asteria.editor.records.vocabulary import vocabulary_for, words
from asteria.editor.scene.render import resolve_texture_source
from asteria.editor.ui.fit import ValueCombo

PICTURE_COMMANDS = (
    "SHOW_PICTURE",
    "MOVE_PICTURE",
    "SET_PICTURE_FRAME",
    "ERASE_PICTURE",
)


class _Name(ValueCombo):
    """A name or record picked from a list; ``text`` / ``setText`` as a line has them."""

    def __init__(self, pairs, value, parent, *, none=None, new=None):
        super().__init__(parent)
        self.setEditable(new is not None)
        self.setProperty("i18n_choices", True)
        if new is not None:
            self.offer_new(*new)
        self.set_choices(pairs, none=none)
        self.setCurrentText(value)

    def text(self):
        return self.currentText().strip()

    def setText(self, value):  # noqa: N802 - Qt-style
        self.setCurrentText(value)


class _PicturePick(_PortraitPicker):
    """The picture shown, chosen as every picture is: a double-click opens them."""

    TITLE = "Choose a Picture"

    def __init__(self, document, parent=None):
        super().__init__(PictureLibrary(document), parent)
        self.preview.setToolTip("Double-click to choose a picture")

    def _icon_of(self, _picture):  # drawn from its file below: no need for the whole list
        return None

    def _shown(self, *_):
        document = self.library.document
        path = resolve_texture_source(document, self.text()) if document else None
        if path is not None:
            pixmap = QPixmap(str(path))
        else:  # a movie shows its first frame
            pixmap = movie_first_frame(document, self.text()) if document else QPixmap()
        side = self.PREVIEW - 8  # inside its frame
        if pixmap.isNull():
            self.preview.setPixmap(QPixmap())
            self.preview.setText("None")
        else:
            self.preview.setPixmap(fit_pixmap(pixmap, side, side))
        self._show_name()
        self.changed.emit()


class _ColorField(_Color):
    """A colour ticked and picked; ``text``: "r,g,b", empty while it isn't ticked. One the
    button can't show stays as it was written until another is picked."""

    def __init__(self, value, tip, parent):
        super().__init__()
        self.setParent(parent)
        self.tick.setToolTip(tip)
        self._held = ""
        self.changed.connect(self._picked)
        if isinstance(value, (list, tuple)):
            value = ",".join(str(c) for c in value)
        plain = "".join(str(value or "").split())
        if plain and not self.set_value(plain):
            self.tick.setChecked(True)
            self._held = str(value)

    def _picked(self):
        self._held = ""

    def text(self):
        return self._held or self.value() or ""


class PictureCommandDialog(QDialog):
    """Edit the exact argument shape consumed by one of the four picture commands."""

    stage_size = (816.0, 624.0)
    _fields = {
        "SHOW_PICTURE": {
            "picture_id",
            "asset_id",
            "x",
            "y",
            "scale",
            "opacity",
            "frame",
            "columns",
            "rows",
            "layer",
            "click_event",
            "tint",
            "tint_color",
            "frame_rate",
            "frame_loop",
            "scroll_x",
            "scroll_y",
            "wave_amplitude",
            "wave_length",
            "wave_speed",
            "blend",
            "text",
            "font",
            "text_color",
            "shadow_color",
            "text_align",
        },
        "MOVE_PICTURE": {
            "picture_id",
            "x",
            "y",
            "scale",
            "opacity",
            "tint",
            "tint_color",
            "duration",
            "easing",
            "delay",
        },
        "SET_PICTURE_FRAME": {"picture_id", "frame"},
        "ERASE_PICTURE": {"picture_id"},
    }

    def __init__(self, command, args=None, *, document=None, parent=None):
        super().__init__(parent)
        self.document = document
        self._initial_args = dict(args or {})
        self.setWindowTitle("Picture Command")
        root = QVBoxLayout(self)
        content = QHBoxLayout()
        form_box = QWidget(self)
        form = QFormLayout(form_box)
        self.command = _Name(
            [(c, command_words(c)) for c in PICTURE_COMMANDS], str(command).upper(), form_box
        )
        vocabulary = vocabulary_for(document) if document is not None else None
        used = vocabulary.values_for("picture_id") if vocabulary is not None else ()
        self.picture_id = _Name(
            [(name, words(name)) for name in used if name],
            self._text("picture_id", "picture_1"),
            form_box,
            new=("New Picture", "picture"),
        )
        self.asset_id = _PicturePick(document, form_box)
        self.asset_id.setText(self._text("asset_id", ""))
        self.x = self._float("x", 0, form_box)
        self.y = self._float("y", 0, form_box)
        self.picture_scale = self._float("scale", 1, form_box, maximum=100)
        self.opacity = self._float("opacity", 1, form_box, maximum=1)
        self.tint = self._float("tint", 0, form_box, maximum=1)
        self.tint_color = self._color("tint_color", "Not ticked: white", form_box)
        self.frame = self._int("frame", 0, form_box)
        self.columns = self._int("columns", 1, form_box, minimum=1)
        self.rows = self._int("rows", 1, form_box, minimum=1)
        self.frame_rate = self._float("frame_rate", 0, form_box, maximum=240)
        self.frame_loop = QCheckBox(form_box)
        self.frame_loop.setChecked(
            str(self._initial_args.get("frame_loop", True)).lower() not in ("false", "0", "no")
        )
        self.scroll_x = self._float("scroll_x", 0, form_box)
        self.scroll_y = self._float("scroll_y", 0, form_box)
        self.wave_amplitude = self._float("wave_amplitude", 0, form_box)
        self.wave_length = self._float("wave_length", 64, form_box)
        self.wave_speed = self._float("wave_speed", 0, form_box)
        self.blend = _Name(
            (("normal", "Normal"), ("add", "Add (A Glow)")),
            self._text("blend", "normal"),
            form_box,
        )
        self.words = QLineEdit(self._text("text", ""), form_box)
        fonts = () if document is None else MenuLayoutAuthoringController(document).fonts()
        self.font = _Name(
            [(key, words(key)) for key, _font in fonts],
            self._text("font", ""),
            form_box,
            none="The Message Window's",
        )
        self.text_color = self._color("text_color", "Not ticked: white", form_box)
        self.shadow_color = self._color("shadow_color", "Not ticked: no shadow", form_box)
        self.text_align = _Name(
            (("left", "Left End"), ("right", "Right End"), ("center", "Middle")),
            self._text("text_align", "left"),
            form_box,
        )
        self.layer = self._int("layer", 0, form_box, minimum=-1000)
        project = getattr(document, "project", None)
        programs = project.event_programs.ids() if project is not None else ()
        self.click_event = _Name(
            [(key, words(key)) for key in programs],
            self._text("click_event", ""),
            form_box,
            none="Nothing",
        )
        self.duration = self._float("duration", 0, form_box, maximum=3600)
        self.delay = self._float("delay", 0, form_box, maximum=3600)
        self.easing = _Name(
            [(e, words(e)) for e in ("linear", "ease_in", "ease_out", "ease_in_out")],
            self._text("easing", "linear"),
            form_box,
        )
        self._form_fields = {
            "command": self.command,
            "picture_id": self.picture_id,
            "asset_id": self.asset_id,
            "x": self.x,
            "y": self.y,
            "scale": self.picture_scale,
            "opacity": self.opacity,
            "tint": self.tint,
            "tint_color": self.tint_color,
            "frame": self.frame,
            "columns": self.columns,
            "rows": self.rows,
            "frame_rate": self.frame_rate,
            "frame_loop": self.frame_loop,
            "scroll_x": self.scroll_x,
            "scroll_y": self.scroll_y,
            "wave_amplitude": self.wave_amplitude,
            "wave_length": self.wave_length,
            "wave_speed": self.wave_speed,
            "blend": self.blend,
            "text": self.words,
            "font": self.font,
            "text_color": self.text_color,
            "shadow_color": self.shadow_color,
            "text_align": self.text_align,
            "layer": self.layer,
            "click_event": self.click_event,
            "duration": self.duration,
            "easing": self.easing,
            "delay": self.delay,
        }
        labels = {
            "command": "Command",
            "picture_id": "Picture",
            "asset_id": "Image",
            "x": "X",
            "y": "Y",
            "scale": "Scale",
            "opacity": "Opacity",
            "tint": ("Tint", "0 = own colours, 1 = all tint colour"),
            "tint_color": "Tint colour",
            "frame": "Frame",
            "columns": "Sheet columns",
            "rows": "Sheet rows",
            "frame_rate": ("Cells a second", "0 = still; a movie: its frames a second"),
            "frame_loop": ("Cells start again", "Off: play once and keep the last"),
            "scroll_x": ("Scroll right", "Image pixels a second; it wraps round"),
            "scroll_y": ("Scroll down", "Image pixels a second; it wraps round"),
            "wave_amplitude": ("Wave height", "Rows are shifted by up to this, in image pixels"),
            "wave_length": ("Wave length", "Rows to a whole wave"),
            "wave_speed": ("Wave speed", "Rows a second it travels up"),
            "blend": ("Blend", "Add: its colours are added, a glow"),
            "text": ("Words", "Words instead of an image; \\V[name] fills in a variable"),
            "font": "Bitmap font",
            "text_color": "Letter colour",
            "shadow_color": "Shadow colour",
            "text_align": ("Words' X is their", "Which part of the words stands at X"),
            "layer": "Layer",
            "click_event": "Click event",
            "duration": "Move duration (seconds)",
            "easing": "Easing",
            "delay": "Start after (seconds)",
        }
        self._form = form
        for name, field in self._form_fields.items():
            label, tip = (labels[name], "") if isinstance(labels[name], str) else labels[name]
            caption = QLabel(label, form_box)
            if tip:
                caption.setToolTip(tip)
                field.setToolTip(tip)
            form.addRow(caption, field)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(form_box)
        self.preview = PicturePreview(self)
        content.addWidget(scroll, 1)
        content.addWidget(self.preview, 1)
        root.addLayout(content)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.command.currentIndexChanged.connect(self._sync_command_fields)
        self._sheet_fonts = {}
        for field in self._form_fields.values():  # whatever is changed shows at once
            for signal in ("valueChanged", "textChanged", "currentIndexChanged", "toggled"):
                if hasattr(field, signal):
                    getattr(field, signal).connect(self.preview.refresh)
            if hasattr(field, "changed"):
                field.changed.connect(self.preview.refresh)
        self._sync_command_fields()
        self.resize(900, 680)

    def _text(self, key, default):
        value = self._initial_args.get(key, default)
        return str(value if value is not None else default)

    def _color(self, key, tip, parent):
        return _ColorField(self._initial_args.get(key), tip, parent)

    def _float(self, key, default, parent, *, maximum=1000000):
        field = QDoubleSpinBox(parent)
        field.setRange(-1000000, maximum)
        field.setDecimals(3)
        field.setValue(float(self._initial_args.get(key, default)))
        return field

    def _int(self, key, default, parent, *, minimum=0):
        field = QSpinBox(parent)
        field.setRange(minimum, 1000000)
        try:
            field.setValue(int(self._initial_args.get(key, default)))
        except (TypeError, ValueError):  # the game reads a number: another word never worked
            field.setValue(default)
        return field

    def _sync_command_fields(self):
        active = self._fields[self.command.currentText()]
        for name, field in self._form_fields.items():
            self._form.setRowVisible(field, name == "command" or name in active)
        self.preview.update()

    def _applies(self, name):
        return name in self._fields[self.command.currentText()]

    def moves(self):
        """Whether anything in this picture changes as time goes by."""
        fields = ("frame_rate", "scroll_x", "scroll_y", "wave_amplitude")
        return any(self._applies(name) and getattr(self, name).value() for name in fields)

    def adds_light(self):
        return self._applies("blend") and self.blend.text() == "add"

    def _word_font(self):
        """The bitmap font for the words: the one picked, else the message window's."""
        project = getattr(self.document, "project", None)
        if project is None:
            return None
        font_id = self.font.text()
        if not font_id:
            records = getattr(project.battle_presentation_library, "_records", {})
            style = records.get("dialogue_window", {}).get("default")
            settings = style.settings() if style is not None else None
            font_id = (settings or {}).get("font_id", "")
        if font_id not in self._sheet_fonts:
            spec = MenuLayoutAuthoringController(self.document).font(font_id)
            self._sheet_fonts[font_id] = sheet_words(self.document, spec)
        return self._sheet_fonts[font_id]

    def _words_image(self, words):
        lines = words.split("\n")
        color = parse_rgb(self.text_color.text(), WHITE)
        shadow = parse_rgb(self.shadow_color.text())
        font = self._word_font()
        if font is not None and font.covers(lines):
            return font.words(lines, color, shadow)
        return system_words(lines, color, shadow)

    def picture_image(self, age=0.0):
        """(what this command shows now, whether that's words); (None, False) for nothing yet.
        Words win over the picture, as they do in the game."""
        words = self.words.text() if self._applies("text") else ""
        if words:
            image = self._words_image(words)
        else:
            pixmap = self.frame_pixmap(age)
            if pixmap.isNull():
                return None, False
            image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32_Premultiplied)
        if self._applies("scroll_x"):
            shift = self.scroll_x.value() * age, self.scroll_y.value() * age
            wave = self.wave_amplitude.value(), self.wave_length.value(), self.wave_speed.value()
            image = moved(image, shift, wave, age)
        if self._applies("tint"):
            color = parse_rgb(self.tint_color.text(), WHITE)
            image = tinted(image, self.tint.value(), color)
        return image, bool(words)

    def frame_pixmap(self, age=0.0):
        if self.document is None or self.document.project is None:
            return QPixmap()
        path = resolve_texture_source(self.document, self.asset_id.text().strip())
        if path is None:  # a movie: its first frame
            return movie_first_frame(self.document, self.asset_id.text().strip())
        if not Path(path).is_file():
            return QPixmap()
        pixmap = QPixmap(str(path))
        columns, rows = self.columns.value(), self.rows.value()
        frame = self.frame.value()
        if self._applies("frame_rate"):
            loop = self.frame_loop.isChecked()
            frame = cycled_frame(frame, self.frame_rate.value(), columns * rows, loop, age)
        if pixmap.isNull() or frame >= columns * rows:
            return pixmap if frame == 0 else QPixmap()
        width, height = pixmap.width() // columns, pixmap.height() // rows
        if width <= 0 or height <= 0:
            return QPixmap()
        return pixmap.copy((frame % columns) * width, (frame // columns) * height, width, height)

    def result_args(self):
        command = self.command.currentText()
        all_values = {
            "picture_id": self.picture_id.text(),
            "asset_id": self.asset_id.text(),
            "x": self.x.value(),
            "y": self.y.value(),
            "scale": self.picture_scale.value(),
            "opacity": self.opacity.value(),
            "tint": self.tint.value(),
            "tint_color": self.tint_color.text(),
            "frame": self.frame.value(),
            "columns": self.columns.value(),
            "rows": self.rows.value(),
            "frame_rate": self.frame_rate.value(),
            "frame_loop": self.frame_loop.isChecked(),
            "scroll_x": self.scroll_x.value(),
            "scroll_y": self.scroll_y.value(),
            "wave_amplitude": self.wave_amplitude.value(),
            "wave_length": self.wave_length.value(),
            "wave_speed": self.wave_speed.value(),
            "blend": self.blend.currentText(),
            "text": self.words.text(),
            "font": self.font.text(),
            "text_color": self.text_color.text(),
            "shadow_color": self.shadow_color.text(),
            "text_align": self.text_align.currentText(),
            "layer": self.layer.value(),
            "click_event": self.click_event.text(),
            "duration": self.duration.value(),
            "easing": self.easing.currentText(),
            "delay": self.delay.value(),
        }
        return {name: all_values[name] for name in self._fields[command]}
