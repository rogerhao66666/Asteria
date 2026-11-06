"""Growth curves (as RPG Maker's Parameter Curves): a small area chart per stat and resource,
level 1 to the level shown, worked out by the game's own rules (``RpgActorRuntime``: the
job's bonuses and its growth per level). A job's page shows what the job gives, whoever takes
it. The charts follow every edit."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from asteria.rpg.actors import ActorDefinition, ClassAssignment, ClassDefinition, RpgActorRuntime

from .i18n import translate
from .record_vocabulary import label_for

COLOURS = (  # one per chart, in order (RPG Maker's warm-to-cool row)
    "#d9805a",
    "#4f7ee0",
    "#c9445e",
    "#8fb05a",
    "#b64fb8",
    "#3fa44a",
    "#4aa8dc",
    "#d1ad3a",
    "#7c6ad6",
    "#d06a9a",
)


def colour(index):
    """The ``index``-th chart colour: the ten above, then new hues (golden-angle steps), so no
    two charts on a page share one."""
    if index < len(COLOURS):
        return QColor(COLOURS[index])
    return QColor.fromHsvF((0.13 + index * 0.618034) % 1.0, 0.55, 0.85)


def growth_curves(actor_data, class_datas, max_level):
    """``[(kind, key, [value at level 1 … max_level])]`` for every stat and resource maximum of
    the actor (``actor_data``, as saved) with ``class_datas`` as its jobs."""

    data = dict(actor_data)
    classes = {}
    assignments = []
    for index, class_data in enumerate(class_datas):
        definition = ClassDefinition.from_data(class_data)
        classes[definition.class_id] = definition
        role = "primary" if index == 0 else "secondary"
        assignments.append(ClassAssignment(definition.class_id, role=role).to_data())
    data["class_assignments"] = assignments
    runtime = RpgActorRuntime(ActorDefinition.from_data(data), class_definitions=classes)
    levels = range(1, max(1, int(max_level)) + 1)
    stats = [runtime.effective_stats(level=level).to_data()["values"] for level in levels]
    keys = sorted({key for row in stats for key in row})
    curves = [("stat", key, [row.get(key, 0.0) for row in stats]) for key in keys]
    grown_ids = {k for level in levels for k in runtime.level_resource_growth(level)}
    for resource_id in sorted(set(runtime.resources.names()) | grown_ids):
        has = resource_id in runtime.resources.names()
        top = runtime.resources.maximum(resource_id) if has else 0.0
        grown = [runtime.level_resource_growth(level).get(resource_id, 0.0) for level in levels]
        curves.append(("resource", resource_id, [top + extra for extra in grown]))
    order = {"vitality": 0, "technique": 1}  # HP, MP first, as RPG Maker lists them
    curves.sort(key=lambda c: (c[0] != "resource", order.get(c[1], 9), c[1]))
    return curves


class CurveChart(QWidget):
    """One stat: its name, the values at the first and last level, the filled curve; hovering
    reads the value at a level."""

    def __init__(self, title, values, colour, parent=None):
        super().__init__(parent)
        self.setObjectName("GrowthCurveChart")
        self.title, self.values, self.colour = title, list(values), QColor(colour)
        self.setMouseTracking(True)
        self.setMinimumSize(150, 92)
        self._hover = None

    def sizeHint(self):  # noqa: N802 - Qt API
        return QSize(190, 100)

    def _area(self):
        return QRectF(self.rect()).adjusted(6, 24, -6, -6)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())
        painter.setPen(QPen(palette.mid().color(), 1))
        painter.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        painter.setPen(palette.text().color())
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(8, 4, self.width() - 16, 18), Qt.AlignLeft, translate(self.title))
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(palette.placeholderText().color())
        first, last = self.values[0], self.values[-1]
        painter.drawText(
            QRectF(8, 4, self.width() - 16, 18), Qt.AlignRight, f"{first:g} → {last:g}"
        )
        area = self._area()
        count = len(self.values)
        flat = max(self.values) == min(self.values)
        # a value that does not grow: a low band and its words, not a full box
        top = (max(self.values) * 2.5 if flat else max(self.values)) or 1.0

        def point(index, value):
            x = area.left() + area.width() * (index / max(1, count - 1))
            return QPointF(x, area.bottom() - area.height() * max(0.0, value) / top)

        path = QPainterPath(QPointF(area.left(), area.bottom()))
        for index, value in enumerate(self.values):
            path.lineTo(point(index, value))
        path.lineTo(QPointF(area.right(), area.bottom()))
        path.closeSubpath()
        fill = QColor(self.colour)
        fill.setAlpha(90 if flat else 210)
        painter.fillPath(path, fill)
        if flat:
            painter.setPen(palette.placeholderText().color())
            painter.drawText(area, Qt.AlignCenter, translate("No growth"))
        if self._hover is not None:
            x = point(self._hover, 0).x()
            painter.setPen(QPen(palette.text().color(), 1, Qt.DashLine))
            painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        area = self._area()
        share = (event.position().x() - area.left()) / max(1.0, area.width())
        index = round(max(0.0, min(1.0, share)) * (len(self.values) - 1))
        self._hover = index
        self.update()
        QToolTip.showText(
            event.globalPosition().toPoint(),
            translate(f"Lv {index + 1}: {self.values[index]:g}"),
            self,
        )

    def leaveEvent(self, event):  # noqa: N802 - Qt API
        self._hover = None
        self.update()
        super().leaveEvent(event)


class GrowthCurves(QWidget):
    """The charts of the job being edited in ``form`` (a RecordForm): what the job itself
    gives at each level - its bonuses and its growth per level - whoever takes it (an actor's
    own starting stats come on top, and its jobs change in play). Drawn again a moment after
    each edit."""

    COLUMNS = 4  # at most; as many as the width holds
    SPACING = 8
    CHART_WIDTH = 150  # the narrowest a chart goes

    def __init__(self, form, category="classes"):
        super().__init__()
        self.form, self.category = form, category
        self.charts = []
        self.shown_columns = self.COLUMNS
        self.setObjectName("GrowthCurves")
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.max_level = QSpinBox()
        self.max_level.setRange(2, 999)
        self.max_level.setValue(99)
        self.max_level.setToolTip("How far the charts reach (only what is shown here)")
        self.max_level.valueChanged.connect(lambda _v: self.redraw())
        controls.addWidget(QLabel("Up to level"))
        controls.addWidget(self.max_level)
        controls.addStretch(1)
        column.addLayout(controls)
        self.grid = QGridLayout()
        self.grid.setSpacing(self.SPACING)
        column.addLayout(self.grid)
        self.note = QLabel()
        self.note.setObjectName("MutedLabel")
        self.note.setWordWrap(True)
        column.addWidget(self.note)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.redraw)
        form.changed.connect(self._timer.start)
        self.redraw()

    def minimumSizeHint(self):  # noqa: N802 - Qt API: one chart a row is the narrowest it goes
        size = super().minimumSizeHint()
        controls = self.layout().itemAt(0).minimumSize().width()
        size.setWidth(max(self.CHART_WIDTH, controls))
        return size

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        if self._columns_for(event.size().width()) != self.shown_columns:
            self._place_charts()

    def _columns_for(self, width):
        fit = (width + self.SPACING) // (self.CHART_WIDTH + self.SPACING)
        return max(1, min(self.COLUMNS, fit))

    def _place_charts(self):
        """The charts in as many columns as the width holds (all of them before it has one)."""
        sized = self.testAttribute(Qt.WA_Resized)
        self.shown_columns = self._columns_for(self.width()) if sized else self.COLUMNS
        while self.grid.count():
            self.grid.takeAt(0)
        for index, chart in enumerate(self.charts):
            row, column = divmod(index, self.shown_columns)
            self.grid.addWidget(chart, row, column)
        for column in range(self.COLUMNS):
            self.grid.setColumnStretch(column, 1 if column < self.shown_columns else 0)

    def _database(self):
        project = getattr(self.form.document, "project", None)
        return getattr(project, "rpg_database", None)

    def _inputs(self):
        """``(an empty actor, [the job])``: the job's own share, level by level."""

        return ActorDefinition("preview").to_data(), [self.form._data]

    def _charted(self, stat):
        """A stat set to Grow with Level (Game Systems ▸ Stats); every stat that is not a
        Stat Formula's when the project defines none."""
        database = self._database()
        if database is None:
            return True
        if stat in database.derived_stats:  # worked out from others, not grown
            return False
        definitions = database.stat_definitions
        if not definitions:
            return True
        definition = definitions.get(stat)
        return definition is not None and "classes" in definition.set_on

    def redraw(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()  # once: unparented, the item lets go of it
            if widget is not None:
                widget.hide()
                widget.setParent(None)  # gone now (not found among the children)
                widget.deleteLater()
        self.charts = []
        try:
            actor, classes = self._inputs()
            curves = growth_curves(actor, classes, self.max_level.value())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            self.note.setText(f"Cannot draw the curves yet: {exc}")
            self.note.show()
            return
        self.note.hide()
        curves = [c for c in curves if c[0] == "resource" or self._charted(c[1])]
        curves = [c for c in curves if c[2] and max(c[2]) - min(c[2]) > 1e-9]  # flat: hidden
        if not curves:
            self.note.setText("Nothing grows with level in this job.")
            self.note.show()
            return
        vocabulary = getattr(self.form, "vocabulary", None)
        names = {}
        if vocabulary is not None:
            for kind in ("stats", "resources"):
                names.update({c.value: c.label for c in vocabulary.choices(kind)})

        rank = {"vitality": 0, "technique": 1}  # HP, MP first, as RPG Maker lists them
        if vocabulary is not None:  # stats in the game's own order (STR, DEX, INT…)
            for kind in ("resources", "stats"):
                for choice in vocabulary.choices(kind):
                    rank.setdefault(choice.value, len(rank))
        curves.sort(key=lambda c: (c[0] != "resource", rank.get(c[1], 1e9), c[1]))
        for index, (_kind, key, values) in enumerate(curves):
            title = names.get(key) or label_for(key)
            chart = CurveChart(title, values, colour(index))
            chart.setToolTip("")
            self.charts.append(chart)
        self._place_charts()


class StatBar(QWidget):
    """One stat beside the others of its kind: a bar to the strongest record's value, a tick
    at the average, the value."""

    def __init__(self, title, value, others, colour, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCompareBar")
        self.title, self.value, self.colour = title, float(value), QColor(colour)
        values = [self.value, *(float(v) for v in others)]  # this record and the rest
        self.top = max([*values, 0.0]) or 1.0
        self.average = sum(values) / len(values)
        self.setMinimumHeight(22)
        self.setToolTip(f"Average {self.average:g} · strongest {self.top:g}")

    def sizeHint(self):  # noqa: N802 - Qt API
        return QSize(260, 22)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        name_width, tail = 70, 64
        painter.setPen(palette.text().color())
        painter.drawText(
            QRectF(0, 0, name_width - 6, self.height()),
            Qt.AlignVCenter | Qt.AlignRight,
            translate(self.title),
        )
        track = QRectF(name_width, 5, max(10, self.width() - name_width - tail), 12)
        painter.setPen(Qt.NoPen)
        back = QColor(palette.mid().color())
        back.setAlpha(90)
        painter.setBrush(back)
        painter.drawRoundedRect(track, 3, 3)
        share = max(0.0, self.value) / self.top
        painter.setBrush(self.colour)
        painter.drawRoundedRect(QRectF(track.left(), track.top(), track.width() * share, 12), 3, 3)
        x = track.left() + track.width() * max(0.0, self.average) / self.top
        painter.setPen(QPen(palette.text().color(), 2))
        painter.drawLine(QPointF(x, track.top() - 3), QPointF(x, track.bottom() + 3))
        painter.setPen(palette.text().color())
        painter.drawText(
            QRectF(track.right() + 8, 0, tail - 8, self.height()),
            Qt.AlignVCenter,
            f"{self.value:g}",
        )


class StatComparison(QWidget):
    """A record's numbers (``form``'s field ``key``, an enemy's stats) beside the same field of
    every other record of its kind, as bars; drawn again a moment after each edit."""

    COLUMNS = 2

    def __init__(self, form, key, siblings):
        super().__init__()
        self.form, self.key, self.siblings = form, key, siblings
        self.setObjectName("StatComparison")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(24)
        self.grid.setVerticalSpacing(2)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.redraw)
        form.changed.connect(self._timer.start)
        self.redraw()

    def _charted(self, stat):
        """A stat set to Grow with Level (Game Systems ▸ Stats); every stat that is not a
        Stat Formula's when the project defines none."""
        database = self._database()
        if database is None:
            return True
        if stat in database.derived_stats:  # worked out from others, not grown
            return False
        definitions = database.stat_definitions
        if not definitions:
            return True
        definition = definitions.get(stat)
        return definition is not None and "classes" in definition.set_on

    def _numbers(self, record):
        """The bars of a record, as its form groups them (HP and MP among the stats)."""
        return self.form.compared_numbers(record, self.key)

    def redraw(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        own = self._numbers(self.form._data)
        vocabulary = getattr(self.form, "vocabulary", None)
        names, rank = {}, {"vitality": 0, "technique": 1}
        if vocabulary is not None:
            for kind in ("resources", "stats"):
                for choice in vocabulary.choices(kind):
                    names.setdefault(choice.value, choice.label)
                    rank.setdefault(choice.value, len(rank))

        keys = sorted(own, key=lambda k: (rank.get(k, 1e9), k))
        for index, stat in enumerate(keys):
            others = [
                self._numbers(record)[stat]
                for record in self.siblings.values()
                if isinstance(record.get(self.key), dict)
                and isinstance(self._numbers(record).get(stat), (int, float))
            ]
            bar = StatBar(
                names.get(stat) or label_for(stat),
                own[stat],
                others,
                colour(index),
            )
            row, column = divmod(index, self.COLUMNS)
            self.grid.addWidget(bar, row, column)
        for column in range(self.COLUMNS):
            self.grid.setColumnStretch(column, 1)


class PositionsPreview(QWidget):
    """Where a list's entries stand (a formation's slots, by their ``x`` and ``y``), as dots
    with their names; drawn again a moment after each edit. ``entries`` gives
    ``[(name, entry)]``."""

    def __init__(self, form, entries):
        super().__init__()
        self.entries = entries
        self.setObjectName("PositionsPreview")
        self.setMinimumHeight(150)
        self.setToolTip("Where each entry stands, by its X and Y (only a picture)")
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(250)
        timer.timeout.connect(self.update)
        form.changed.connect(timer.start)

    def sizeHint(self):  # noqa: N802 - Qt API
        return QSize(400, 170)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())
        painter.setPen(QPen(palette.mid().color(), 1))
        painter.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        points = [(name, float(e["x"]), float(e["y"])) for name, e in self.entries()]
        if not points:
            return
        xs, ys = [p[1] for p in points], [p[2] for p in points]
        left, top = min(xs), min(ys)
        wide, tall = max(xs) - left, max(ys) - top
        area = QRectF(self.rect()).adjusted(60, 22, -60, -36)  # room for the names below
        scales = [area.width() / wide if wide else None, area.height() / tall if tall else None]
        scale = min([s for s in scales if s] or [1.0])
        # one scale for both (a square stays square), the drawing centred in the box
        dx = area.left() + (area.width() - wide * scale) / 2
        dy = area.top() + (area.height() - tall * scale) / 2
        for index, (name, x, y) in enumerate(points):
            at = QPointF(dx + (x - left) * scale, dy + (y - top) * scale)
            painter.setPen(Qt.NoPen)
            painter.setBrush(colour(index))
            painter.drawEllipse(at, 9, 9)
            painter.setPen(palette.base().color())
            painter.drawText(
                QRectF(at.x() - 9, at.y() - 9, 18, 18), Qt.AlignCenter, str(index + 1)
            )
            painter.setPen(palette.text().color())
            painter.drawText(
                QRectF(at.x() - 60, at.y() + 11, 120, 16), Qt.AlignHCenter, translate(name)
            )
