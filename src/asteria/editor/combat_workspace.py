"""Real-Time Combat workspace (D22 A9): attacks, projectiles, loot rarities and affixes, designed
side by side.

Layout: a kind switcher and a searchable record list on the left; the selected record in titled
cards (dense,
multi-column) in the middle; a live preview on the right that redraws as values change — the
knockback and timing of
an attack, the flight of a projectile (simulated with the engine's projectile kernel), a rarity's
name colour and
affix count, an affix's value range across item levels. Apply records the edit as one undo step.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .combat_authoring import KINDS, CombatAuthoringController, CombatAuthoringError
from .icons import icon
from .responsive_form import ResponsiveForm

SOURCES = (
    ("constant", "Constant"),
    ("source_stat", "Attacker stat"),
    ("target_stat", "Target stat"),
    ("source_resource_current", "Attacker resource"),
    ("source_resource_max", "Attacker resource max"),
    ("target_resource_current", "Target resource"),
    ("target_resource_max", "Target resource max"),
)
OPERATIONS = ("add", "multiply", "override")


class _CellCombo(QComboBox):
    """A list in a table cell: as wide as its column, never wider. (``fit_combo_boxes`` widens
    a page's lists to their longest entry - in a narrow column that spilled over the next.)"""

    def __init__(self):
        super().__init__()
        # tighter padding than a form's lists: the text keeps the room in a narrow column
        self.setStyleSheet("QComboBox { padding-left: 6px; padding-right: 16px; }")

    def setMinimumWidth(self, width):  # noqa: N802 - Qt API
        super().setMinimumWidth(0)


def _double(value=0.0, *, minimum=-1_000_000.0, maximum=1_000_000.0, step=1.0, decimals=2):
    box = QDoubleSpinBox()
    box.setRange(minimum, maximum)
    box.setDecimals(decimals)
    box.setSingleStep(step)
    box.setValue(float(value))
    return box


def _int(value=0, *, minimum=0, maximum=1_000_000):
    box = QSpinBox()
    box.setRange(int(minimum), int(min(maximum, 2_147_483_647)))
    box.setValue(int(value))
    return box


def _small_button(text, tip):
    button = QToolButton()
    button.setText(text)
    button.setToolTip(tip)
    button.setAutoRaise(True)
    return button


class _Table(QWidget):
    """A compact editable table with + / − buttons; ``columns`` = ((title, kind, options), ...)."""

    changed = Signal()

    def _emit(self, *_args):
        self.changed.emit()

    def __init__(self, columns, parent=None):
        super().__init__(parent)
        self.columns = columns
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([c[0] for c in columns])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setMinimumSectionSize(46)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._fit()
        add, remove = (
            _small_button("+", "Add a line"),
            _small_button("−", "Remove the selected line"),
        )
        add.clicked.connect(lambda: (self.add_row(), self.changed.emit()))
        remove.clicked.connect(self._remove)
        buttons = QVBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table, 1)
        layout.addLayout(buttons)

    ROW = 30  # row height until a row's own fields ask for more

    def _fit(self):
        """As tall as its rows (one empty row at least, six at most - then it scrolls)."""
        count = self.table.rowCount()
        heights = [self.table.rowHeight(r) for r in range(min(6, count))] or [self.ROW]
        header = self.table.horizontalHeader().sizeHint().height()
        self.table.setFixedHeight(header + sum(heights) + 4)

    def _remove(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self._fit()
            self.changed.emit()

    def add_row(self, values=None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, (_title, kind, options) in enumerate(self.columns):
            value = None if values is None else values[column]
            if kind == "choice":
                widget = _CellCombo()
                widget.setEditable(bool(options.get("editable")))
                for key, label in options.get("items", ()):
                    widget.addItem(label, key)
                index = widget.findData(value) if value is not None else 0
                if index >= 0:
                    widget.setCurrentIndex(index)
                elif value is not None:
                    widget.setEditText(str(value))
                widget.currentIndexChanged.connect(self._emit)
                widget.editTextChanged.connect(self._emit)
            elif kind == "float":
                widget = _double(
                    value or options.get("default", 0.0), step=options.get("step", 1.0)
                )
                # a narrow cell: no arrows (typing and the wheel still change it), so the
                # number itself has the room
                widget.setButtonSymbols(QDoubleSpinBox.NoButtons)
                widget.valueChanged.connect(self._emit)
            elif kind == "bool":
                widget = QCheckBox()
                widget.setChecked(bool(value))
                widget.toggled.connect(self._emit)

            else:
                widget = QLineEdit("" if value is None else str(value))
                widget.setPlaceholderText(options.get("placeholder", ""))
                widget.textChanged.connect(self._emit)
            # each field sits in its cell with a little room around it (they touched before);
            # a checkbox is centred
            cell = QWidget()
            room = QHBoxLayout(cell)
            room.setContentsMargins(3, 3, 3, 3)
            if kind == "bool":
                room.addWidget(widget, 0, Qt.AlignCenter)
            else:
                # a field never wider than its column (a list asks for more on macOS and
                # spilled over the next column)
                widget.setMinimumWidth(0)
                widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
                if isinstance(widget, QComboBox):
                    widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
                    widget.setMinimumContentsLength(2)
                room.addWidget(widget)
            cell.field = widget
            self.table.setCellWidget(row, column, cell)
        # every field of the row as tall as the tallest (a text box was shorter than a number)
        fields = [self.table.cellWidget(row, c).field for c in range(len(self.columns))]
        tallest = max((f.sizeHint().height() for f in fields), default=self.ROW - 6)
        for field, (_title, kind, _options) in zip(fields, self.columns, strict=True):
            if kind != "bool":
                field.setFixedHeight(tallest)
        self.table.setRowHeight(row, max(self.ROW, tallest + 6))
        self._fit()

    def rows(self):
        result = []
        for row in range(self.table.rowCount()):
            values = []
            for column, (_title, kind, _options) in enumerate(self.columns):
                widget = self.table.cellWidget(row, column)
                widget = getattr(widget, "field", widget)
                if kind == "choice":
                    text = widget.currentText()
                    index = widget.findText(text)
                    values.append(widget.itemData(index) if index >= 0 else text.strip())
                elif kind == "float":
                    values.append(widget.value())
                elif kind == "bool":
                    values.append(widget.isChecked())
                else:
                    values.append(widget.text().strip())
            result.append(values)
        return result

    def set_rows(self, rows):
        self.table.setRowCount(0)
        for values in rows:
            self.add_row(values)
        self._fit()


class FormulaEditor(QWidget):
    """Terms (source, key, ×) summed; tag multipliers; optional minimum / maximum."""

    changed = Signal()

    def _emit(self, *_args):
        self.changed.emit()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.terms = _Table(
            (
                ("Source", "choice", {"items": SOURCES}),
                ("Stat", "text", {"placeholder": "power"}),
                ("×", "float", {"default": 1.0, "step": 0.1}),
            )
        )
        self.multipliers = _Table(
            (
                ("×", "float", {"default": 2.0, "step": 0.1}),
                ("Attacker tags", "text", {"placeholder": "Element.Fire"}),
                ("Target tags", "text", {"placeholder": "Creature.Plant"}),
            )
        )
        self.use_min, self.use_max = QCheckBox("Minimum"), QCheckBox("Maximum")
        self.minimum, self.maximum = _double(1.0), _double(9999.0)
        for box in (self.minimum, self.maximum):
            box.setMinimumWidth(96)
        bounds = QHBoxLayout()
        bounds.setSpacing(8)
        for check, box in ((self.use_min, self.minimum), (self.use_max, self.maximum)):
            bounds.addWidget(check)
            bounds.addWidget(box)
            check.toggled.connect(self._emit)
            box.valueChanged.connect(self._emit)
        bounds.addStretch(1)
        self.summary = QLabel()
        self.summary.setObjectName("CardHint")
        self.summary.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.terms)
        multipliers = QLabel("Tag multipliers")
        multipliers.setToolTip(
            "Weaknesses and resistances: × when the attacker and the target carry tags"
        )
        multipliers.setObjectName("FieldLabel")
        layout.addWidget(multipliers)
        layout.addWidget(self.multipliers)
        layout.addLayout(bounds)
        layout.addWidget(self.summary)
        for table in (self.terms, self.multipliers):
            table.changed.connect(self._emit)
        self.changed.connect(self._describe)

    def set_value(self, data):
        data = data or {"terms": [], "multipliers": [], "minimum": None, "maximum": None}
        self.terms.set_rows([[t["source"], t["key"], t["coefficient"]] for t in data["terms"]])
        self.multipliers.set_rows(
            [
                [
                    m["multiplier"],
                    ", ".join(m["condition"]["required_source_tags"]),
                    ", ".join(m["condition"]["required_target_tags"]),
                ]
                for m in data["multipliers"]
            ]
        )
        self.use_min.setChecked(data["minimum"] is not None)
        self.use_max.setChecked(data["maximum"] is not None)
        self.minimum.setValue(data["minimum"] or 0.0)
        self.maximum.setValue(data["maximum"] or 9999.0)
        self._describe()

    def value(self):
        terms = []
        for source, key, coefficient in self.terms.rows():
            key = "" if source == "constant" else key
            terms.append({"source": source, "key": key, "coefficient": coefficient})
        multipliers = []
        for multiplier, attacker, target in self.multipliers.rows():
            tags = lambda text: [t.strip() for t in text.replace(";", ",").split(",") if t.strip()]  # noqa: E731
            multipliers.append(
                {
                    "multiplier": multiplier,
                    "condition": {
                        "required_source_tags": tags(attacker),
                        "blocked_source_tags": [],
                        "required_target_tags": tags(target),
                        "blocked_target_tags": [],
                    },
                }
            )
        if not terms and not multipliers:
            return None
        return {
            "schema": "asteria.value_formula",
            "version": 1,
            "terms": terms,
            "multipliers": multipliers,
            "minimum": self.minimum.value() if self.use_min.isChecked() else None,
            "maximum": self.maximum.value() if self.use_max.isChecked() else None,
        }

    def _describe(self):
        parts = []
        for source, key, coefficient in self.terms.rows():
            label = dict(SOURCES).get(source, source)
            parts.append(
                f"{coefficient:g}"
                if source == "constant"
                else f"{coefficient:g} × {label.lower()} {key}"
            )
        text = " + ".join(parts) or "no damage"
        if self.use_min.isChecked():
            text = f"at least {self.minimum.value():g} of " + text
        self.summary.setText(f"= {text}")


class _ColorButton(QPushButton):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.color = "#ffffff"
        self.clicked.connect(self._pick)

    def set_color(self, value):
        self.color = value
        c = QColor(value)
        text = (
            "#111111"
            if (c.red() * 299 + c.green() * 587 + c.blue() * 114) / 1000 > 140
            else "#ffffff"
        )
        self.setText(value)
        self.setStyleSheet(
            f"background: {value}; color: {text}; border-radius: 6px; font-weight: 700;"
        )

    def _pick(self):
        chosen = QColorDialog.getColor(QColor(self.color), self, "Rarity colour")
        if chosen.isValid():
            self.set_color(chosen.name())
            self.changed.emit()


# -- previews -------------------------------------------------------------------------------------
class _Preview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.record = None
        self.setMinimumSize(190, 260)

    def show_record(self, record):
        self.record = record
        self.update()

    def _start(self):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(20, 22, 30))
        return painter

    @staticmethod
    def _caption(painter, x, y, text, color=QColor(170, 178, 196), size=10, bold=False):
        font = QFont()
        font.setPointSize(size)
        font.setBold(bold)
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(QPointF(x, y), text)


class AttackPreview(_Preview):
    """Attacker, target and the knockback push; a time line of hit-stop, hitstun, down time and
    i-frames."""

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = self._start()
        a = self.record
        if a is None:
            painter.end()
            return
        w, h = self.width(), self.height()
        ground = h * 0.46
        ax, tx = w * 0.28, w * 0.58
        painter.setPen(QPen(QColor(60, 66, 84), 1, Qt.DashLine))
        painter.drawLine(QPointF(16, ground + 22), QPointF(w - 16, ground + 22))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(90, 170, 255))
        painter.drawEllipse(QPointF(ax, ground), 16, 16)
        painter.setBrush(QColor(224, 92, 100))
        painter.drawEllipse(QPointF(tx, ground), 16, 16)
        self._caption(painter, ax - 26, ground + 40, "attacker")
        self._caption(painter, tx - 16, ground + 40, "target")
        angle = math.radians(
            a.knockback_angle
        )  # "fixed": a world angle; "away" / "facing": turned from the right
        length = min(w * 0.3, 18 + abs(a.knockback) * 0.25)
        dx, dy = (
            math.cos(angle) * length,
            math.sin(angle) * length - min(60, a.knockback_lift * 0.2),
        )
        if a.knockback or a.knockback_lift:
            pen = QPen(QColor(255, 196, 90), 3)
            painter.setPen(pen)
            end = QPointF(tx + dx, ground + dy)
            painter.drawLine(QPointF(tx, ground), end)
            head = math.atan2(dy, dx)
            for side in (-0.5, 0.5):
                painter.drawLine(
                    end,
                    QPointF(
                        end.x() - 10 * math.cos(head + side), end.y() - 10 * math.sin(head + side)
                    ),
                )
            self._caption(
                painter, end.x() - 20, end.y() - 10, f"{a.knockback:g}/s", QColor(255, 196, 90)
            )
        chips = []
        if a.knockdown:
            chips.append(("knocks down", QColor(255, 140, 90)))
        if a.armor_break:
            chips.append((f"breaks armor ≤ {a.armor_break}", QColor(200, 140, 255)))
        if a.poise_damage:
            chips.append((f"poise −{a.poise_damage:g}", QColor(120, 200, 255)))
        if a.tags:
            chips.append((", ".join(a.tags), QColor(140, 220, 160)))
        x = 16
        for text, color in chips:
            width = 14 + len(text) * 6.4
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color.red(), color.green(), color.blue(), 50))
            painter.drawRoundedRect(QRectF(x, 14, width, 20), 9, 9)
            self._caption(painter, x + 7, 28, text, color)
            x += width + 6
        # time line
        top = h * 0.66
        scale = (w - 120) / max(
            1.2,
            a.hitstop
            + a.hitstun
            + (a.knockdown_time or (1.0 if a.knockdown else 0.0))
            + a.target_iframes
            + 0.2,
        )
        rows = (
            ("hit-stop", a.hitstop, QColor(255, 220, 120)),
            ("hitstun", a.hitstun, QColor(255, 140, 120)),
            ("down", (a.knockdown_time or 1.0) if a.knockdown else 0.0, QColor(255, 110, 90)),
            ("i-frames", a.target_iframes, QColor(120, 200, 255)),
        )
        for index, (label, seconds, color) in enumerate(rows):
            y = top + index * 20
            self._caption(painter, 16, y + 11, label)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(44, 48, 62))
            painter.drawRoundedRect(QRectF(92, y, w - 112, 12), 4, 4)
            if seconds:
                painter.setBrush(color)
                painter.drawRoundedRect(QRectF(92, y, max(3.0, seconds * scale), 12), 4, 4)
                self._caption(painter, 96 + seconds * scale, y + 11, f"{seconds:g}s", color)
        painter.end()


class ProjectilePreview(_Preview):
    """A shot fired to the right (and one with a target above, for homing), simulated by the
    projectile kernel."""

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = self._start()
        p = self.record
        if p is None:
            painter.end()
            return
        from asteria.kernels import _python

        w, h = self.width(), self.height()
        origin = QPointF(30, h * 0.62)
        target = (w * 0.62, -h * 0.30) if p.homing_turn > 0 else None
        store = _python.ProjectileStore()
        store.add(
            [
                (
                    0.0,
                    0.0,
                    p.speed,
                    0.0,
                    p.gravity,
                    0.0,
                    max(p.lifetime, 0.01),
                    p.width / 2,
                    p.height / 2,
                    math.radians(p.homing_turn),
                    1,
                )
            ]
        )
        zoom = min(1.0, (w - 60) / max(1.0, p.speed * max(p.lifetime, 0.01)))
        path = QPainterPath(origin)
        dt = max(0.01, p.lifetime / 90)
        points = []
        for _ in range(90):
            if target is not None:
                tx, ty = target[0] / zoom, target[1] / zoom
                in_range = (
                    math.hypot(tx - store.x[0], ty - store.y[0]) <= p.homing_range
                )  # world units
                store.step(
                    dt, [tx if in_range else float("nan")], [ty if in_range else float("nan")]
                )
            else:
                store.step(dt)
            points.append(QPointF(origin.x() + store.x[0] * zoom, origin.y() + store.y[0] * zoom))
        for point in points:
            path.lineTo(point)
        painter.setPen(QPen(QColor(255, 196, 90), 2, Qt.DashLine))
        painter.drawPath(path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(255, 230, 150))
        end = points[-1]
        bw, bh = max(3.0, p.width * zoom * 2), max(3.0, p.height * zoom * 2)
        painter.drawRoundedRect(QRectF(end.x() - bw / 2, end.y() - bh / 2, bw, bh), 2, 2)
        painter.setBrush(QColor(90, 170, 255))
        painter.drawEllipse(origin, 9, 9)
        if target is not None:
            painter.setBrush(QColor(224, 92, 100))
            spot = QPointF(origin.x() + target[0], origin.y() + target[1])
            painter.drawEllipse(spot, 10, 10)
            painter.setPen(QPen(QColor(224, 92, 100, 90), 1, Qt.DotLine))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(spot, p.homing_range * zoom, p.homing_range * zoom)
        lines = [
            f"{p.speed:g}/s for {p.lifetime:g}s  ·  range ≈ {p.speed * p.lifetime:.0f}",
            f"on a wall: {p.wall}"
            + (f" (≤ {p.bounce_limit} bounces)" if p.wall == "bounce" and p.bounce_limit else ""),
            "pierces every target" if p.pierce < 0 else f"pierces {p.pierce} extra target(s)",
            f"hits with: {p.attack_id or '— reports hits only'}",
        ]
        for index, text in enumerate(lines):
            self._caption(painter, 16, 22 + index * 16, text)
        painter.end()


class RarityPreview(_Preview):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all = {}

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = self._start()
        r = self.record
        if r is None:
            painter.end()
            return
        w = self.width()
        color = QColor(r.color)
        for index, (bg, label) in enumerate(
            ((QColor(20, 22, 30), "dark"), (QColor(236, 238, 244), "light"))
        ):
            y = 18 + index * 52
            painter.setPen(Qt.NoPen)
            painter.setBrush(bg)
            painter.drawRoundedRect(QRectF(16, y, w - 32, 40), 8, 8)
            if index:  # on a light surface a pale colour needs a shadow to be read
                for ox, oy in ((1, 1),):  # one soft shadow: an outline blurs small text
                    self._caption(
                        painter,
                        28 + ox,
                        y + 26 + oy,
                        f"{r.display_name} Blade of the Bear",
                        QColor(40, 44, 56),
                        size=13,
                        bold=True,
                    )
            self._caption(
                painter,
                28,
                y + 26,
                f"{r.display_name} Blade of the Bear",
                color,
                size=13,
                bold=True,
            )
            self._caption(painter, w - 60, y + 26, label, QColor(130, 136, 150))
        y = 140
        self._caption(painter, 16, y, "Random affixes", QColor(200, 206, 220), bold=True)
        for i in range(max(6, r.max_affixes)):
            filled = i < r.min_affixes
            maybe = r.min_affixes <= i < r.max_affixes
            painter.setPen(QPen(color, 1.5))
            painter.setBrush(
                color
                if filled
                else QColor(color.red(), color.green(), color.blue(), 70)
                if maybe
                else Qt.NoBrush
            )
            painter.drawEllipse(QPointF(28 + i * 22, y + 18), 7, 7)
        self._caption(
            painter, 16, y + 46, f"{r.min_affixes}–{r.max_affixes} affixes", QColor(150, 158, 176)
        )
        total = sum(x.weight for x in self.all.values()) or 1.0
        share = r.weight / total
        self._caption(
            painter,
            16,
            y + 74,
            f"Rolled {share * 100:.1f}% of the time"
            if r.weight
            else "Never rolled — given by drop tables",
            QColor(200, 206, 220),
            bold=True,
        )
        x = 16
        for other in sorted(self.all.values(), key=lambda v: v.order):
            width = (w - 32) * other.weight / total
            painter.setPen(Qt.NoPen)
            painter.setBrush(
                QColor(other.color)
                if other.rarity_id == r.rarity_id
                else QColor(
                    QColor(other.color).red(),
                    QColor(other.color).green(),
                    QColor(other.color).blue(),
                    90,
                )
            )
            painter.drawRect(QRectF(x, y + 84, max(0.0, width), 14))
            x += width
        painter.end()


class AffixPreview(_Preview):
    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = self._start()
        a = self.record
        if a is None:
            painter.end()
            return
        w = self.width()
        name = f"{a.display_name} Sword" if a.position == "prefix" else f"Sword {a.display_name}"
        self._caption(painter, 16, 30, name, QColor(130, 180, 255), size=14, bold=True)
        levels = (max(1, a.min_level), max(1, a.max_level or a.min_level + 20))
        self._caption(
            painter,
            16,
            52,
            f"item levels {levels[0]}–{a.max_level or '∞'}  ·  weight {a.weight:g}"
            + (f"  ·  group {a.group}" if a.group else ""),
            QColor(150, 158, 176),
        )
        top = 78
        for index, m in enumerate(a.modifiers):
            y = top + index * 54
            lo1, hi1 = (
                m.minimum + m.per_level * (levels[0] - 1),
                m.maximum + m.per_level * (levels[0] - 1),
            )
            lo2, hi2 = (
                m.minimum + m.per_level * (levels[1] - 1),
                m.maximum + m.per_level * (levels[1] - 1),
            )
            top_value = max(abs(hi2), abs(hi1), 1e-9)
            sign = "×" if m.operation == "multiply" else "+" if m.operation == "add" else "="
            self._caption(
                painter,
                16,
                y + 12,
                f"{m.stat}  {sign}{lo1:g}–{hi1:g}"
                + (f"  →  {lo2:g}–{hi2:g} at lv {levels[1]}" if m.per_level else ""),
                QColor(220, 224, 236),
            )
            for row, (lo, hi, color) in enumerate(
                ((lo1, hi1, QColor(130, 180, 255)), (lo2, hi2, QColor(200, 150, 255)))
            ):
                if row and not m.per_level:
                    continue
                bar_y = y + 20 + row * 12
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(44, 48, 62))
                painter.drawRoundedRect(QRectF(16, bar_y, w - 32, 8), 4, 4)
                painter.setBrush(color)
                x0 = 16 + (w - 32) * max(0.0, lo) / top_value
                x1 = 16 + (w - 32) * max(0.0, hi) / top_value
                painter.drawRoundedRect(QRectF(x0, bar_y, max(4.0, x1 - x0), 8), 4, 4)
        if not a.modifiers:
            self._caption(
                painter,
                16,
                top + 12,
                "No modifiers yet — add a line in Rolled values.",
                QColor(150, 158, 176),
            )
        painter.end()


EMPTY_HINTS = {
    "attacks": "An attack is what one landed hit does: damage, poise, knockback, hit-stop, "
    "super armor and "
    "knockdown. Hitboxes name it in their hit tag.",
    "projectiles": "A projectile flies, homes, bounces or pierces, and applies an attack to "
    "what it hits. "
    "Action timelines fire it.",
    "rarities": "Rarities name how rare loot is, its label colour and how many random affixes "
    "it rolls. "
    "Without any, the five defaults are used.",
    "affixes": "Affixes are the random prefixes and suffixes rolled on dropped equipment — each "
    "adds stats "
    "within a range.",
}

PREVIEWS = {
    "attacks": AttackPreview,
    "projectiles": ProjectilePreview,
    "rarities": RarityPreview,
    "affixes": AffixPreview,
}


# -- the workspace --------------------------------------------------------------------------------
class CombatWorkspace(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.api = CombatAuthoringController(document)
        self.kind_id = KINDS[0].kind_id
        self.record_id = None
        self.inputs = {}
        self._loading = False

        # left: kind switcher, search, list, actions
        self.kind_buttons = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        kinds = QVBoxLayout()
        kinds.setSpacing(4)
        for spec in KINDS:
            button = QToolButton()
            button.setObjectName("KindButton")
            button.setCheckable(True)
            button.setIcon(icon(spec.icon, spec.accent))
            button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda _checked=False, k=spec.kind_id: self.show_kind(k))
            group.addButton(button)
            kinds.addWidget(button)
            self.kind_buttons[spec.kind_id] = button
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search…")
        self.search.textChanged.connect(self._fill_list)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(
            lambda current, _old: self.select(current.data(Qt.UserRole) if current else None)
        )
        # short labels: the left column can be narrow; the tooltips carry the full wording
        self.new_button = QPushButton("New")
        self.new_button.setProperty("role", "primary")
        self.new_button.clicked.connect(self.new_record)
        self.duplicate_button = QPushButton("Duplicate")
        self.duplicate_button.clicked.connect(self.duplicate_record)
        self.delete_button = QPushButton("Delete")
        self.delete_button.setProperty("role", "danger")
        self.delete_button.clicked.connect(self.delete_record)
        # two rows: "New" across the column, "Duplicate" and "Delete" side by side; the left
        # column can be narrow, and this never clips or wraps whatever the icons add
        actions = QGridLayout()
        actions.setHorizontalSpacing(6)
        actions.setVerticalSpacing(6)
        actions.addWidget(self.new_button, 0, 0, 1, 2)
        actions.addWidget(self.duplicate_button, 1, 0)
        actions.addWidget(self.delete_button, 1, 1)
        for button in (self.new_button, self.duplicate_button, self.delete_button):
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left = QVBoxLayout()
        left.addLayout(kinds)
        left.addSpacing(6)
        left.addWidget(self.search)
        left.addWidget(self.list, 1)
        left.addLayout(actions)
        left_panel = QWidget()
        left_panel.setLayout(left)
        left_panel.setMinimumWidth(240)

        # middle: heading + cards + apply bar
        self.heading = QLabel()
        self.heading.setObjectName("RecordHeading")
        self.record_label = QLabel()
        self.record_label.setObjectName("RecordId")
        self.cards = QVBoxLayout()
        self.cards.setSpacing(10)
        holder = QWidget()
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 6, 0)
        holder_layout.addLayout(self.cards)
        holder_layout.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(holder)
        self.status = QLabel()
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        self.apply_button = QPushButton("Apply")
        self.apply_button.setProperty("role", "success")
        self.apply_button.clicked.connect(self.apply)
        self.revert_button = QPushButton("Revert")
        self.revert_button.clicked.connect(lambda: self.select(self.record_id))
        bar = QHBoxLayout()
        bar.addWidget(self.status, 1)
        bar.addWidget(self.revert_button)
        bar.addWidget(self.apply_button)
        self.form_area = scroll
        self.empty = QFrame()
        self.empty.setObjectName("Card")
        empty_layout = QVBoxLayout(self.empty)
        empty_layout.setContentsMargins(28, 28, 28, 28)
        empty_layout.addStretch(1)
        self.empty_icon = QLabel()
        self.empty_icon.setAlignment(Qt.AlignCenter)
        self.empty_title = QLabel()
        self.empty_title.setObjectName("EmptyStateTitle")
        self.empty_title.setAlignment(Qt.AlignCenter)
        self.empty_hint = QLabel()
        self.empty_hint.setObjectName("EmptyStateHint")
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setWordWrap(True)
        self.empty_button = QPushButton()
        self.empty_button.setProperty("role", "primary")
        self.empty_button.clicked.connect(lambda: self.new_record())
        for widget in (self.empty_icon, self.empty_title, self.empty_hint):
            empty_layout.addWidget(widget)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.empty_button)
        row.addStretch(1)
        empty_layout.addSpacing(8)
        empty_layout.addLayout(row)
        empty_layout.addStretch(2)
        # the live preview folds away in a narrow window (the form needs the room); the button
        # shows or hides it by hand, and a hand-set choice is kept
        self.preview_toggle = QToolButton()
        self.preview_toggle.setText("Preview")
        self.preview_toggle.setCheckable(True)
        self.preview_toggle.setChecked(True)
        self.preview_toggle.setToolTip("Show or hide the live preview")
        self.preview_toggle.clicked.connect(self._preview_toggled)
        self._preview_by_hand = False
        head = QHBoxLayout()
        head.addWidget(self.heading, 1)
        head.addWidget(self.preview_toggle)
        middle = QVBoxLayout()
        middle.addLayout(head)
        middle.addWidget(self.record_label)
        middle.addWidget(scroll, 1)
        middle.addWidget(self.empty, 1)
        middle.addLayout(bar)
        middle_panel = QWidget()
        middle_panel.setLayout(middle)
        middle_panel.setMinimumWidth(340)

        # right: preview
        self.preview_frame = QFrame()
        self.preview_frame.setObjectName("PreviewFrame")
        self.preview_layout = QVBoxLayout(self.preview_frame)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_title = QLabel("Preview")
        self.preview_title.setObjectName("AuthoringSidebarTitle")
        self.usage = QLabel()
        self.usage.setObjectName("CardHint")
        self.usage.setWordWrap(True)
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(10)
        right.addWidget(self.preview_title)
        right.addWidget(self.preview_frame, 1)
        right.addWidget(self.usage)
        right_panel = QFrame()
        right_panel.setObjectName("AuthoringPreviewCard")
        right_panel.setLayout(right)
        right_panel.setMinimumWidth(210)
        self.right_panel = right_panel
        self.preview = None

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(middle_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([250, 700, 380])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.addWidget(splitter)
        self.show_kind(self.kind_id)

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        """The three panels' real minimum (the cards scroll inside, so the page itself needs
        no more width than that), at least 520 high."""
        base = super().minimumSizeHint()
        return QSize(base.width(), max(base.height(), 520))

    PREVIEW_MIN_PAGE_WIDTH = 1000  # narrower than this the preview is folded away

    def _preview_toggled(self, checked):
        self._preview_by_hand = True
        self._sync_preview()

    def _sync_preview(self):
        wanted = (
            self.preview_toggle.isChecked()
            if self._preview_by_hand
            else self.width() >= self.PREVIEW_MIN_PAGE_WIDTH
        )
        self.right_panel.setVisible(wanted)
        if not self._preview_by_hand:
            self.preview_toggle.setChecked(wanted)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._sync_preview()

    def showEvent(self, event):  # noqa: N802 - Qt API: pick up edits made elsewhere (undo, other tools)
        super().showEvent(event)
        self.refresh()

    # -- kinds and records ------------------------------------------------------------------------
    def refresh(self):
        for spec in KINDS:
            self.kind_buttons[spec.kind_id].setText(
                f"{spec.label}   {len(self.api.ids(spec.kind_id))}"
            )
        self._fill_list()

    def show_kind(self, kind_id):
        self.kind_id = kind_id
        self.kind_buttons[kind_id].setChecked(True)
        spec = self.api.kind(kind_id)
        self.new_button.setToolTip(f"New {spec.noun}…")
        self.duplicate_button.setToolTip(f"Duplicate this {spec.noun.lower()}…")
        self.delete_button.setToolTip(f"Delete this {spec.noun.lower()}")
        self._build_form()
        if self.preview is not None:
            self.preview.setParent(None)
        self.preview = PREVIEWS[kind_id]()
        self.preview_layout.addWidget(self.preview)
        self.preview_title.setText(f"{spec.noun} preview")
        self.record_id = None
        self.refresh()
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.select(None)

    def _fill_list(self):
        spec = self.api.kind(self.kind_id)
        needle = self.search.text().strip().lower()
        current = self.record_id
        self.list.blockSignals(True)
        self.list.clear()
        for record_id in self.api.ids(self.kind_id):
            record = self.api.get(self.kind_id, record_id)
            name = getattr(record, "display_name", record_id)
            if needle and needle not in record_id.lower() and needle not in name.lower():
                continue
            item = QListWidgetItem(
                icon(spec.icon, getattr(record, "color", None) or spec.accent),
                name,
            )
            item.setData(Qt.UserRole, record_id)
            self.list.addItem(item)
            if record_id == current:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)

    def select_id(self, record_id):
        """Select ``record_id`` in the list (and the form)."""
        for row in range(self.list.count()):
            if self.list.item(row).data(Qt.UserRole) == record_id:
                self.list.setCurrentRow(row)
                return True
        return False

    def select(self, record_id):
        self.record_id = record_id
        data = self.api.data(self.kind_id, record_id) if record_id else None
        enabled = data is not None
        for widget in (
            self.apply_button,
            self.revert_button,
            self.duplicate_button,
            self.delete_button,
        ):
            widget.setEnabled(enabled)
        self.form_area.setVisible(enabled)
        self.empty.setVisible(not enabled)
        for widget in (self.heading, self.record_label, self.apply_button, self.revert_button):
            widget.setVisible(enabled)
        if data is None:
            spec = self.api.kind(self.kind_id)
            self.empty_icon.setPixmap(icon(spec.icon, spec.accent).pixmap(56, 56))
            none = not self.api.ids(self.kind_id)
            self.empty_title.setText(
                f"No {spec.label.lower()} yet" if none else f"Pick a {spec.noun.lower()}"
            )
            self.empty_hint.setText(
                EMPTY_HINTS[self.kind_id] if none else "Choose one from the list on the left."
            )
            self.empty_button.setText(f"New {spec.noun}…")
            self.empty_button.setIcon(icon("plus", "#ffffff"))
            self.status.setText("")
            self.usage.setText("")
            self.preview.show_record(None)
            return
        self._loading = True
        try:
            for name, widget in self.inputs.items():
                self._set(widget, data.get(name))
        finally:
            self._loading = False
        self.heading.setText(data.get("display_name") or record_id)
        self.record_label.setText(f"id  {record_id}")
        used = self.api.usage(self.kind_id, record_id)
        self.usage.setText(("Used by: " + ", ".join(used)) if used else "Not used yet.")
        self._edited()

    # -- the form ---------------------------------------------------------------------------------
    def _build_form(self):
        while self.cards.count():  # the previous kind's cards go now, not at the next event loop
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self.inputs = {}
        spec = self.api.kind(self.kind_id)
        for title, hint, fields in spec.sections:
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            card_layout.setSpacing(4)
            heading = QLabel(title)
            heading.setObjectName("CardTitle")
            card_layout.addWidget(heading)
            if hint:
                note = QLabel(hint)
                note.setObjectName("CardHint")
                note.setWordWrap(True)
                card_layout.addWidget(note)
            form = ResponsiveForm(column_width=210, max_columns=3)
            for field in fields:
                widget = self._widget(field)
                self.inputs[field.name] = widget
                if field.kind in ("formula", "states", "modifiers"):
                    form.add_row(field.label, widget, span=True)
                else:
                    form.add_row(field.label, widget)
                if field.hint:
                    widget.setToolTip(field.hint)
            card_layout.addWidget(form)
            self.cards.addWidget(card)

    def _widget(self, field):
        kind = field.kind
        if kind == "float":
            widget = _double(0.0, minimum=field.minimum, maximum=field.maximum, step=field.step)
            widget.valueChanged.connect(self._edited)
        elif kind == "int":
            widget = _int(0, minimum=field.minimum, maximum=field.maximum)
            widget.valueChanged.connect(self._edited)
        elif kind == "bool":
            widget = QCheckBox()
            widget.toggled.connect(self._edited)
        elif kind == "choice":
            widget = QComboBox()
            widget.addItems(field.choices)
            widget.setEditable(field.name == "position")
            widget.currentTextChanged.connect(self._edited)
        elif kind == "attack":
            widget = QComboBox()
            widget.setEditable(True)
            widget.currentTextChanged.connect(self._edited)
        elif kind == "mask":
            widget = QLineEdit()
            widget.setPlaceholderText("0xFFFFFFFF = every layer")
            widget.textChanged.connect(self._edited)
        elif kind == "color":
            widget = _ColorButton()
            widget.changed.connect(self._edited)
        elif kind == "formula":
            widget = FormulaEditor()
            widget.changed.connect(self._edited)
        elif kind == "states":
            widget = _Table(
                (
                    (
                        "State",
                        "choice",
                        {"items": [(s, s) for s in self.api.choices("states")], "editable": True},
                    ),
                    ("Chance", "float", {"default": 1.0, "step": 0.05}),
                    ("Seconds", "float", {"step": 0.5}),
                )
            )
            widget.changed.connect(self._edited)
        elif kind == "modifiers":
            widget = _Table(
                (
                    ("Stat", "text", {"placeholder": "power"}),
                    ("Op", "choice", {"items": [(o, o) for o in OPERATIONS]}),
                    ("Min", "float", {"step": 1.0}),
                    ("Max", "float", {"step": 1.0}),
                    ("Whole", "bool", {}),
                    ("+/level", "float", {"step": 0.5}),
                )
            )
            widget.changed.connect(self._edited)
        else:  # text, tags
            widget = QLineEdit()
            if field.hint:
                widget.setPlaceholderText(field.hint)
            widget.textChanged.connect(self._edited)
        widget.field = field
        return widget

    def _set(self, widget, value):
        kind = widget.field.kind
        if kind == "float":
            widget.setValue(float(value or 0.0))
        elif kind == "int":
            widget.setValue(int(value or 0))
        elif kind == "bool":
            widget.setChecked(bool(value))
        elif kind == "choice":
            widget.setCurrentText(str(value or widget.field.choices[0]))
        elif kind == "attack":
            widget.clear()
            widget.addItem("")
            widget.addItems(self.api.choices("attack"))
            widget.setCurrentText(str(value or ""))
        elif kind == "mask":
            widget.setText(f"0x{int(value or 0):08X}")
        elif kind == "color":
            widget.set_color(str(value or "#ffffff"))
        elif kind == "formula":
            widget.set_value(value)
        elif kind == "states":
            widget.set_rows(
                [[s["state"], s.get("chance", 1.0), s.get("duration") or 0.0] for s in value or ()]
            )
        elif kind == "modifiers":
            widget.set_rows(
                [
                    [
                        m["stat"],
                        m["operation"],
                        m["minimum"],
                        m["maximum"],
                        m["integer"],
                        m["per_level"],
                    ]
                    for m in value or ()
                ]
            )
        elif kind == "tags":
            widget.setText(", ".join(value or ()))
        else:
            widget.setText("" if value is None else str(value))

    def _get(self, widget):
        kind = widget.field.kind
        if kind in ("float", "int"):
            return widget.value()
        if kind == "bool":
            return widget.isChecked()
        if kind in ("choice", "attack"):
            return widget.currentText().strip()
        if kind == "mask":
            text = widget.text().strip() or "0"
            try:
                return int(text, 0)
            except ValueError:
                return text  # the record refuses it with a reason
        if kind == "color":
            return widget.color
        if kind == "formula":
            return widget.value()
        if kind == "states":
            rows = []
            for state, chance, seconds in widget.rows():
                if state:
                    entry = {"state": state, "chance": chance}
                    if seconds:
                        entry["duration"] = seconds
                    rows.append(entry)
            return rows
        if kind == "modifiers":
            return [
                {
                    "stat": stat,
                    "operation": operation,
                    "minimum": lo,
                    "maximum": hi,
                    "integer": integer,
                    "per_level": per,
                }
                for stat, operation, lo, hi, integer, per in widget.rows()
                if stat
            ]
        if kind == "tags":
            return [t.strip() for t in widget.text().replace(";", ",").split(",") if t.strip()]
        return widget.text().strip()

    def form_data(self):
        data = dict(self.api.data(self.kind_id, self.record_id) or {})
        for name, widget in self.inputs.items():
            data[name] = self._get(widget)
        return data

    def _edited(self, *_args):
        if self._loading or self.record_id is None:
            return
        try:
            record = self.api.build(self.kind_id, self.form_data())
        except CombatAuthoringError as exc:
            self.status.setText(f"⚠  {exc}")
            self.status.setObjectName("ErrorLabel")
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)
            return
        changed = record != self.api.get(self.kind_id, self.record_id)
        self.status.setText("Changed — Apply to keep it (one undo step)." if changed else "Saved.")
        self.status.setObjectName("MutedLabel")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        if isinstance(self.preview, RarityPreview):
            rarities = (
                dict(self.document.project.rpg_database.loot_rarities())
                if self.document.project
                else {}
            )
            rarities[record.rarity_id] = record
            self.preview.all = rarities
        self.heading.setText(getattr(record, "display_name", self.record_id))
        self.preview.show_record(record)

    # -- actions ----------------------------------------------------------------------------------
    def apply(self):
        try:
            self.api.apply(self.kind_id, self.record_id, self.form_data())
        except CombatAuthoringError as exc:
            QMessageBox.warning(self, "Cannot apply", str(exc))
            return
        self.refresh()
        self._edited()
        self.changed.emit()

    def _ask_id(self, title, default=""):
        text, ok = QInputDialog.getText(self, title, "Id (letters, numbers, _):", text=default)
        return text.strip() if ok and text.strip() else None

    def new_record(self, record_id=None):
        spec = self.api.kind(self.kind_id)
        record_id = record_id or self._ask_id(f"New {spec.noun}")
        if not record_id:
            return None
        try:
            self.api.create(self.kind_id, record_id)
        except CombatAuthoringError as exc:
            QMessageBox.warning(self, f"New {spec.noun}", str(exc))
            return None
        self.record_id = record_id
        self.refresh()
        self.select(record_id)
        self.changed.emit()
        return record_id

    def duplicate_record(self, record_id=None):
        if self.record_id is None:
            return None
        spec = self.api.kind(self.kind_id)
        record_id = record_id or self._ask_id(f"Duplicate {spec.noun}", f"{self.record_id}_copy")
        if not record_id:
            return None
        try:
            self.api.create(self.kind_id, record_id, source=self.record_id)
        except CombatAuthoringError as exc:
            QMessageBox.warning(self, f"Duplicate {spec.noun}", str(exc))
            return None
        self.record_id = record_id
        self.refresh()
        self.select(record_id)
        self.changed.emit()
        return record_id

    def delete_record(self, confirm=True):
        if self.record_id is None:
            return
        used = self.api.usage(self.kind_id, self.record_id)
        if confirm:
            text = f"Delete {self.record_id}?" + (
                f"\nStill used by: {', '.join(used)}" if used else ""
            )
            if QMessageBox.question(self, "Delete", text) != QMessageBox.Yes:
                return
        self.api.delete(self.kind_id, self.record_id)
        self.record_id = None
        self.refresh()
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.select(None)
        self.changed.emit()


__all__ = [
    "AffixPreview",
    "AttackPreview",
    "CombatWorkspace",
    "FormulaEditor",
    "ProjectilePreview",
    "RarityPreview",
]
