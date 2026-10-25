"""Presentation ▸ Menu Screens ▸ Layout ▸ Creature screens…: a creature game's own screens
(V5, ``presentation.creature_screens``) edited without writing JSON.

Each screen (battle, start menu, shop, name entry, picture choices) shows every setting as a
tree: a picture or sound gets a file chooser, a colour a colour button, a place two number
boxes, a number a number box, yes / no a tick box, words a text box (``\\n`` for a new line).
Tables (the menu rows, bag pockets, badges, options...) are rows under their name: right-click
adds a row (a copy of the last), removes one, or adds a setting of your own. The battle's
``layout`` points and ``colours`` are listed with the engine's values, so they can be changed
without knowing their names. Every place of the screen is a dot on its picture at the screen's
own 240 x 160 pixels: drag a dot to move it. "From the game folder's manifest" turns an older
game's ``playable_test_manifest.json`` screens into these settings in one step.
"""

from __future__ import annotations

import copy
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.presentation.creature_screens import RESOLUTION, SCREENS, CreatureScreenSettings

from .i18n import translate

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
SOUND_EXT = (".ogg", ".wav", ".mp3")
SCALE = 3  # the preview's pixels per screen pixel


def _listed(places):
    return {k: (list(v) if v is not None else None) for k, v in places.items()}


def engine_defaults(screen_id):
    """The settings a screen draws with when the project says nothing: listed so an author
    can change them by name (the battle's places and text colours, the start menu's summary
    and trainer card places, the shop's windows, the name screen's letter pages)."""
    if screen_id == "battle.creature_screen":
        from asteria.runtime.creature_battle import COLOURS, LAYOUT

        return {
            "layout": {k: list(v) for k, v in LAYOUT.items()},
            "colours": {k: [list(a), list(b)] for k, (a, b) in COLOURS.items()},
        }
    if screen_id == "field.creature_menu":
        from asteria.runtime.creature_menu import CARD_PLACES, SUMMARY_PLACES

        return {
            "summary": {"places": _listed(SUMMARY_PLACES)},
            "card": {"places": _listed(CARD_PLACES)},
        }
    if screen_id == "field.creature_shop":
        from asteria.runtime.creature_shop import PLACES

        return {"places": _listed(PLACES)}
    if screen_id == "field.name_input":
        from asteria.runtime.name_input import DEFAULT_PAGES

        return {"pages": [{"label": p["label"], "rows": list(p["rows"])} for p in DEFAULT_PAGES]}
    return {}


MODULES = {  # where each screen's settings are described (the help shown in the editor)
    "battle.creature_screen": "asteria.runtime.creature_battle",
    "field.creature_menu": "asteria.runtime.creature_menu",
    "field.creature_shop": "asteria.runtime.creature_shop",
    "field.name_input": "asteria.runtime.name_input",
    "field.picture_choices": "asteria.runtime.picture_choice",
}


def _names(sentence, key):
    """``key`` as a setting (``key``) or as a field of a row (``{"key", ...}``)."""
    return f"``{key}``" in sentence or f'"{key}"' in sentence


def help_for(screen_id, path):
    """What the screen's own description says about the setting at ``path`` (the sentence
    naming it as ``key``, the nearest named key upwards for a row) in the editor's language,
    or ""."""
    import importlib
    import re

    module = MODULES.get(screen_id)
    if module is None:
        return ""
    words = " ".join((importlib.import_module(module).__doc__ or "").split())
    keys = [k for k in path if isinstance(k, str)]
    sentences = re.split(r"(?<=\.)\s+|;\s+|\s\*\s", words)  # sentences, clauses, bullets
    for depth in range(len(keys) - 1, -1, -1):  # the deepest key first
        key, parents = keys[depth], keys[:depth]
        named = [t for t in sentences if _names(t, key)]
        if named:  # one naming its table too first, then one naming it as a setting
            best = min(
                named,
                key=lambda t: (not any(_names(t, k) for k in parents), f"``{key}``" not in t),
            )
            return translate(best.strip(" -;*").replace("``", ""))  # without its code marks
    return ""


def merged(data, defaults):
    """``data`` with the defaults it does not set filled in (a deep copy)."""
    out = copy.deepcopy(data)
    for key, value in defaults.items():
        if isinstance(value, dict):
            out[key] = merged(out.get(key, {}) if isinstance(out.get(key), dict) else {}, value)
        else:
            out.setdefault(key, copy.deepcopy(value))
    return out


def stripped(data, defaults):
    """``data`` without what equals the defaults (and tables left empty by that)."""
    out = {}
    for key, value in data.items():
        default = defaults.get(key)
        if isinstance(value, dict) and isinstance(default, dict):
            value = stripped(value, default)
            if not value:
                continue
        elif value == default:
            continue
        out[key] = value
    return out


def is_point(key, value, parent_key=""):
    """A place: ``[x, y]`` named ``at`` / ``*_at`` / ``*_box`` or in ``layout`` / ``places``;
    ``[x, y, w, h]`` (a window's inside) in ``places`` too."""
    numbers = isinstance(value, list) and len(value) in (2, 4)
    numbers = numbers and all(isinstance(v, (int, float)) for v in value)
    if numbers and len(value) == 4:
        return parent_key == "places"
    named = str(key) == "at" or str(key).endswith(("_at", "_box"))
    return numbers and (named or parent_key in ("layout", "places"))


def is_colour(key, value, parent_key=""):
    if not (isinstance(value, list) and len(value) in (3, 4)):
        return False
    if not all(isinstance(v, int) and 0 <= v <= 255 for v in value):
        return False
    words = f"{key} {parent_key}".lower()
    return "colour" in words or "color" in words or "shadow" in words


def is_colour_pair(key, value, parent_key=""):
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(is_colour("colour", v) for v in value)
        and ("colour" in f"{key} {parent_key}".lower() or "color" in str(parent_key).lower())
    )


def file_kind(key, value):
    """``image``, ``sound``, ``file`` (a font or a font table) or "" for plain words."""
    text = str(value).lower()
    if text.endswith(IMAGE_EXT):
        return "image"
    if text.endswith(SOUND_EXT) or str(key).endswith("_sound"):
        return "sound"
    if text.endswith((".json", ".ttf", ".otf")) or str(key) in ("font", "font_small"):
        return "file"
    from .image_tools import picture_field

    return "image" if picture_field(str(key)) and "{" not in text else ""


class PointField(QWidget):
    changed = Signal()

    def __init__(self, value, parent=None):
        super().__init__(parent)
        names = ("x", "y", "w", "h")[: len(value)]  # a place, or a window's inside
        self.boxes = [QSpinBox() for _ in names]
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for name, box in zip(names, self.boxes, strict=True):
            box.setRange(-2000, 4000)
            box.setMinimumWidth(64)
            if len(names) == 4:  # four in a row: typed or wheeled, no arrows taking the room
                box.setButtonSymbols(QSpinBox.NoButtons)
                box.setMinimumWidth(48)
            layout.addWidget(QLabel(name))
            layout.addWidget(box)
            box.valueChanged.connect(self.changed)
        layout.addStretch(1)
        self.set(value)

    def value(self):
        return [box.value() for box in self.boxes]

    def set(self, value):
        for box, v in zip(self.boxes, value, strict=False):
            box.blockSignals(True)
            box.setValue(int(v))
            box.blockSignals(False)


class FileField(QWidget):
    """A project file of any kind (a font table, a font): typed or chosen."""

    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.edit = QLineEdit()
        choose = QPushButton("Choose…")
        choose.clicked.connect(self._choose)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit, 1)
        layout.addWidget(choose)
        self.edit.editingFinished.connect(self.changed)

    def text(self):
        return self.edit.text().strip()

    def setText(self, value):  # noqa: N802 - Qt-style
        self.edit.setText(str(value or ""))

    def _choose(self):
        from PySide6.QtWidgets import QFileDialog

        from .menu_layout_widget import _project_root, import_ui_file

        root = str(_project_root(self.document))
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a file", root, "Fonts and font tables (*.json *.ttf *.otf);;All (*)"
        )
        if path:
            self.setText(import_ui_file(self.document, path))
            self.changed.emit()


class PointCanvas(QWidget):
    """The screen's picture at 240 x 160 (x3) with a dot for every place; drag to move."""

    moved = Signal(object, object)  # path, [x, y]
    picked = Signal(object)  # path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(RESOLUTION[0] * SCALE, RESOLUTION[1] * SCALE)
        self.picture = QPixmap()
        self.points = []  # (path, label, [x, y])
        self.chosen = None
        self.dragging = None
        self.setMouseTracking(True)  # a dot's name shows under the pointer

    def show_points(self, picture, points, chosen=None):
        self.picture = picture or QPixmap()
        self.points = list(points)
        self.chosen = chosen
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 28, 40))
        if not self.picture.isNull():
            painter.drawPixmap(0, 0, self.picture.scaled(self.size(), Qt.IgnoreAspectRatio))
        for path, label, xy in self.points:
            x, y = xy[0], xy[1]
            hot = path == self.chosen
            colour = QColor(255, 210, 90) if hot else QColor(120, 200, 255)
            if len(xy) == 4:  # a window's inside: its outline too
                painter.setPen(QPen(colour, 2 if hot else 1, Qt.DashLine))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(int(x * SCALE), int(y * SCALE), xy[2] * SCALE, xy[3] * SCALE)
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            painter.setBrush(colour)
            centre = QPoint(int(x * SCALE), int(y * SCALE))
            painter.drawEllipse(centre, 5 if hot else 4, 5 if hot else 4)
            if hot:  # only the chosen dot's name: close places would write over each other
                painter.setPen(colour)
                painter.drawText(centre + QPoint(7, -4), label)
        painter.end()

    def _hit(self, pos):
        best, near = None, 12.0
        for path, _label, (x, y, *_size) in self.points:
            d = ((x * SCALE - pos.x()) ** 2 + (y * SCALE - pos.y()) ** 2) ** 0.5
            if d < near:
                best, near = path, d
        return best

    def mousePressEvent(self, event):  # noqa: N802 - Qt
        self.dragging = self._hit(event.position().toPoint())
        if self.dragging is not None:
            self.chosen = self.dragging
            self.picked.emit(self.dragging)
            self.update()

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt
        pos = event.position().toPoint()
        if self.dragging is None:
            near = self._hit(pos)
            self.setToolTip(next((lb for p, lb, _xy in self.points if p == near), ""))
            return
        value = [round(pos.x() / SCALE), round(pos.y() / SCALE)]
        for i, (path, label, xy) in enumerate(self.points):
            if path == self.dragging:
                value += list(xy[2:])  # a window keeps its size
                self.points[i] = (path, label, value)
        self.moved.emit(self.dragging, value)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt
        self.dragging = None


class SettingsTree(QTreeWidget):
    """Every setting of one screen; ``data`` is kept up to date as fields change."""

    edited = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.setHeaderLabels(["Setting", "Value"])
        self.setColumnWidth(0, 230)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)
        self.data = {}
        self.fields = {}  # path -> widget
        self.screen_id = ""  # whose description the settings' help comes from

    def load(self, data):
        self.data = copy.deepcopy(data)
        self.rebuild()

    def rebuild(self):
        open_paths = {p for p, i in self._items() if i.isExpanded()}
        self.clear()
        self.fields = {}
        self._fill(self.invisibleRootItem(), self.data, ())
        for path, item in self._items():
            item.setExpanded(path in open_paths or len(path) == 1 and path[0] == "layout")

    def _items(self):
        out = []

        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                out.append((child.data(0, Qt.UserRole), child))
                walk(child)

        walk(self.invisibleRootItem())
        return out

    def item_of(self, path):
        return next((i for p, i in self._items() if p == path), None)

    def _fill(self, parent, value, path):
        pairs = value.items() if isinstance(value, dict) else enumerate(value)
        parent_key = str(path[-1]) if path else ""
        for key, child in pairs:
            here = (*path, key)
            label = f"#{key + 1}" if isinstance(key, int) else str(key)
            if isinstance(key, int) and isinstance(child, dict):  # a table row: its name
                name = child.get("id") or child.get("name") or child.get("label")
                label += f"  {name}" if name else ""
            item = QTreeWidgetItem(parent, [label, ""])
            item.setData(0, Qt.UserRole, here)
            item.setToolTip(0, help_for(self.screen_id, here))
            widget = self._field(key, child, here, parent_key)
            if widget is not None:
                self.setItemWidget(item, 1, widget)
                self.fields[here] = widget
            elif isinstance(child, (dict, list)):
                count = "settings" if isinstance(child, dict) else "rows"
                item.setText(1, translate(f"{len(child)} {count}"))
                self._fill(item, child, here)

    def _field(self, key, value, path, parent_key):  # noqa: C901 - one branch per kind
        from .menu_layout_widget import AssetField, ColorField

        def store(new):
            self._set(path, new)

        if isinstance(value, bool):
            box = QCheckBox()
            box.setChecked(value)
            box.toggled.connect(store)
            return box
        if isinstance(value, int):
            box = QSpinBox()
            box.setRange(-100000, 100000)
            box.setValue(value)
            box.valueChanged.connect(store)
            return box
        if isinstance(value, float):
            box = QDoubleSpinBox()
            box.setRange(-100000.0, 100000.0)
            box.setDecimals(3)
            box.setValue(value)
            box.valueChanged.connect(store)
            return box
        if isinstance(value, str):
            kind = file_kind(key, value)
            if kind in ("image", "sound"):
                field = AssetField(self.document, kind)
            elif kind == "file":
                field = FileField(self.document)
            else:
                field = QLineEdit(value.replace("\n", "\\n"))
                field.editingFinished.connect(lambda f=field: store(f.text().replace("\\n", "\n")))
                return field
            field.setText(value)
            field.changed.connect(lambda f=field: store(f.text()))
            return field
        if is_point(key, value, parent_key):
            field = PointField(value)
            field.changed.connect(lambda f=field: store(f.value()))
            return field
        if is_colour(key, value, parent_key):
            field = ColorField()
            field.setColor(value)
            field.changed.connect(lambda f=field: store(list(f.color() or value)[: len(value)]))
            return field
        if is_colour_pair(key, value, parent_key):
            pair = QWidget()
            row = QHBoxLayout(pair)
            row.setContentsMargins(0, 0, 0, 0)
            fields = [ColorField(), ColorField()]
            for colour, field in zip(value, fields, strict=True):
                field.setColor(colour)
                row.addWidget(QLabel("letter" if field is fields[0] else "shadow"))
                row.addWidget(field)

            def both():
                store([list(f.color() or c)[:3] for f, c in zip(fields, value, strict=True)])

            for field in fields:
                field.changed.connect(both)
            return pair
        return None

    def _set(self, path, value):
        target = self.data
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        self.edited.emit()

    def get(self, path):
        value = self.data
        for key in path:
            value = value[key]
        return value

    def set_point(self, path, value):
        self._set(path, list(value))
        field = self.fields.get(path)
        if isinstance(field, PointField):
            field.set(value)

    # --- rows and settings of the author's own ------------------------------------------
    def _menu(self, pos):
        item = self.itemAt(pos)
        path = item.data(0, Qt.UserRole) if item is not None else ()
        value = self.get(path) if path else self.data
        menu = QMenu(self)
        if isinstance(value, list):
            menu.addAction("Add a row", lambda: self._add_row(path))
        if isinstance(value, dict):
            menu.addAction("Add a setting…", lambda: self._add_setting(path))
        if path:
            parent = self.get(path[:-1]) if len(path) > 1 else self.data
            if isinstance(parent, list):
                menu.addAction("Duplicate this row", lambda: self._duplicate(path))
            menu.addAction("Remove", lambda: self._remove(path))
        if menu.actions():
            menu.exec(self.viewport().mapToGlobal(pos))

    def _add_row(self, path):
        rows = self.get(path)
        rows.append(copy.deepcopy(rows[-1]) if rows else "")
        self.rebuild()
        self.edited.emit()

    def _duplicate(self, path):
        rows = self.get(path[:-1])
        rows.insert(path[-1] + 1, copy.deepcopy(rows[path[-1]]))
        self.rebuild()
        self.edited.emit()

    def _remove(self, path):
        parent = self.get(path[:-1]) if len(path) > 1 else self.data
        del parent[path[-1]]
        self.rebuild()
        self.edited.emit()

    KINDS = {
        "Words": "",
        "Number": 0,
        "Yes / no": False,
        "Picture": "ui/picture.png",
        "Place (x, y)": [0, 0],
        "Colour": [255, 255, 255],
        "Table of settings": {},
        "List of rows": [],
    }

    def _add_setting(self, path):
        name, ok = QInputDialog.getText(self, "Add a setting", "Name")
        if not ok or not name.strip():
            return
        kind, ok = QInputDialog.getItem(self, "Add a setting", "Kind", list(self.KINDS), 0, False)
        if not ok:
            return
        target = self.get(path) if path else self.data
        name = name.strip()
        if kind == "Place (x, y)" and not name.endswith("_at"):
            name += "_at"  # a place's name says so (the screens read "..._at")
        if kind == "Colour" and "colour" not in name:
            name += "_colour"
        target[name] = copy.deepcopy(self.KINDS[kind])
        self.rebuild()
        self.edited.emit()

    def points(self):
        """Every place in the settings: ``(path, label, [x, y])``."""
        out = []

        def walk(value, path):
            pairs = value.items() if isinstance(value, dict) else enumerate(value)
            parent_key = str(path[-1]) if path else ""
            for key, child in pairs:
                here = (*path, key)
                if is_point(key, child, parent_key):
                    out.append((here, ".".join(str(k) for k in here[-2:]), list(child)))
                elif isinstance(child, (dict, list)):
                    walk(child, here)

        walk(self.data, ())
        return out


class CreatureScreensDialog(QDialog):
    """``changes()`` after OK: ``{screen_id: CreatureScreenSettings | None}``."""

    def __init__(self, document, current, parent=None, *, convert=None, render=None):
        super().__init__(parent)
        self.setWindowTitle("Creature Screens")
        self.resize(1500, 860)
        self.document = document
        self.convert = convert  # () -> {screen_id: CreatureScreenSettings} (the manifest's)
        # (screen_id, settings) -> QPixmap of the screen drawn by the game, or None
        self.render = render
        self.drawn = QPixmap()
        self.redraw = QTimer(self)
        self.redraw.setSingleShot(True)
        self.redraw.setInterval(150)  # typing in a field: drawn once it pauses
        self.redraw.timeout.connect(self._draw_screen)
        self.help = QLabel()
        self.help.setObjectName("SettingHelp")
        self.help.setWordWrap(True)
        self.work = {k: v for k, v in dict(current).items() if v is not None}
        self.original = dict(self.work)
        self.screen_id = ""
        self.screens = QListWidget()
        for screen_id, title in SCREENS.items():
            item = QListWidgetItem(translate(title))
            item.setData(Qt.UserRole, screen_id)
            self.screens.addItem(item)
        self.enabled = QCheckBox("Use these settings (off: the game folder's manifest is used)")
        self.tree = SettingsTree(document)
        self.canvas = PointCanvas()
        self.status = QLabel()
        self.status.setWordWrap(True)
        convert_button = QPushButton("From the game folder's manifest")
        convert_button.setToolTip(
            "Turn every creature screen of playable_test_manifest.json into these settings"
        )
        convert_button.setEnabled(convert is not None)
        convert_button.clicked.connect(self._convert)
        start = QPushButton("Start this screen's settings")
        start.clicked.connect(self._start)
        remove = QPushButton("Remove this screen's settings")
        remove.setObjectName("DangerButton")
        remove.clicked.connect(self._remove)
        tools = QHBoxLayout()
        for button in (convert_button, start, remove):
            tools.addWidget(button)
        tools.addStretch(1)
        middle = QWidget()
        column = QVBoxLayout(middle)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(self.enabled)
        column.addWidget(self.tree, 1)
        column.addWidget(self.help)
        right = QWidget()
        side = QVBoxLayout(right)
        side.setContentsMargins(0, 0, 0, 0)
        side.addWidget(QLabel("The screen as the game draws it (240 × 160): drag a dot"))
        side.addWidget(self.canvas)
        side.addWidget(self.status)
        side.addStretch(1)
        split = QSplitter()
        split.addWidget(self.screens)
        split.addWidget(middle)
        split.addWidget(right)
        split.setSizes([200, 560, 740])
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addWidget(split, 1)
        layout.addWidget(buttons)
        self.screens.currentRowChanged.connect(self._chosen)
        self.tree.edited.connect(self._edited)
        self.tree.currentItemChanged.connect(self._tree_picked)
        self.enabled.toggled.connect(self._edited)
        self.canvas.moved.connect(self.tree.set_point)
        self.canvas.picked.connect(self._canvas_picked)
        self._mark()
        self.screens.setCurrentRow(0)

    # --- choosing ---------------------------------------------------------------------
    def _mark(self):
        for row in range(self.screens.count()):
            item = self.screens.item(row)
            screen_id = item.data(Qt.UserRole)
            mark = "● " if screen_id in self.work else "   "
            item.setText(mark + translate(SCREENS[screen_id]))

    def _chosen(self, row):
        self._keep()
        item = self.screens.item(row)
        self.screen_id = item.data(Qt.UserRole) if item is not None else ""
        settings = self.work.get(self.screen_id)
        has = settings is not None
        self.enabled.blockSignals(True)
        self.enabled.setChecked(settings.enabled if has else False)
        self.enabled.setEnabled(has)
        self.enabled.blockSignals(False)
        defaults = engine_defaults(self.screen_id)
        self.tree.screen_id = self.screen_id
        self.drawn = QPixmap()  # another screen: drawn again
        self.help.setText("")
        self.tree.setEnabled(has)
        self.tree.load(merged(settings.data, defaults) if has else {})
        self.status.setText(
            ""
            if has
            else "No settings yet: the manifest's are used. Start this screen's "
            "settings, or bring them from the manifest."
        )
        self._points()

    def _keep(self):
        """The tree's settings back into the screen's record."""
        if not self.screen_id or self.screen_id not in self.work:
            return
        data = stripped(self.tree.data, engine_defaults(self.screen_id))
        self.work[self.screen_id] = CreatureScreenSettings(
            self.screen_id, data, self.enabled.isChecked()
        )

    def _edited(self):
        self._keep()
        self._points()

    def _points(self):
        chosen = self.tree.currentItem()
        chosen = chosen.data(0, Qt.UserRole) if chosen is not None else None
        self.canvas.show_points(self._picture(), self.tree.points(), chosen)
        if self.render is not None:
            self.redraw.start()

    def _picture(self):
        """The screen drawn by the game, else its ``background`` picture, else nothing."""
        if not self.drawn.isNull():
            return self.drawn
        from .menu_layout_widget import _project_root

        background = self.tree.data.get("background")
        if isinstance(background, str) and background:
            path = _project_root(self.document) / background
            if Path(path).is_file():
                return QPixmap(str(path))
        return QPixmap()

    def _draw_screen(self):
        """The game's own drawing of the screen with the settings as they are now."""
        if self.render is None or not self.screen_id:
            return
        settings = self.work.get(self.screen_id)
        try:
            drawn = self.render(self.screen_id, settings)
        except Exception as error:  # noqa: BLE001 - a half-typed setting: the dots stay
            drawn = None
            self.status.setText(f"Could not draw the screen: {error}")
        self.drawn = drawn if drawn is not None else QPixmap()
        self.canvas.picture = self._picture()
        self.canvas.update()

    def _tree_picked(self, item, _old):
        path = item.data(0, Qt.UserRole) if item is not None else None
        self.canvas.chosen = path
        self.canvas.update()
        self.help.setText(help_for(self.screen_id, path) if path else "")

    def _canvas_picked(self, path):
        item = self.tree.item_of(path)
        if item is not None:
            self.tree.blockSignals(True)
            self.tree.setCurrentItem(item)
            self.tree.blockSignals(False)
            self.tree.scrollToItem(item)

    # --- whole screens ------------------------------------------------------------------
    def _start(self):
        if self.screen_id and self.screen_id not in self.work:
            self.work[self.screen_id] = CreatureScreenSettings(self.screen_id, {})
            self._mark()
            self.screen_id, row = "", self.screens.currentRow()
            self._chosen(row)

    def _remove(self):
        if self.screen_id in self.work:
            del self.work[self.screen_id]
            self._mark()
            self.screen_id, row = "", self.screens.currentRow()
            self._chosen(row)
            self.status.setText("OK removes these settings: the manifest's are used again.")

    def _convert(self):
        found = self.convert() if self.convert is not None else {}
        if not found:
            self.status.setText("The game folder's manifest has no creature screens.")
            return
        self.work.update(found)
        self._mark()
        self.screen_id, row = "", self.screens.currentRow()
        self._chosen(row)
        names = ", ".join(translate(SCREENS[k]) for k in found)
        self.status.setText(f"Read from the manifest: {names}.")

    def _accept(self):
        self._keep()
        self.accept()

    def changes(self):
        out = {}
        for screen_id in SCREENS:
            new, old = self.work.get(screen_id), self.original.get(screen_id)
            if new != old:
                out[screen_id] = new
        return out


__all__ = ["CreatureScreensDialog", "engine_defaults", "merged", "stripped"]
