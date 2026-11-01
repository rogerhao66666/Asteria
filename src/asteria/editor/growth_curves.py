"""Growth curves (as RPG Maker's Parameter Curves): a small area chart per stat and resource,
level 1 to the level shown, worked out by the game's own rules (``RpgActorRuntime``: base
stats, the job's bonuses, its growth per level). A job's page shows them for an actor taking
that job; an actor's page for the actor with its own jobs. The charts follow every edit."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from .i18n import translate

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


def growth_curves(actor_data, class_datas, max_level):
    """``[(kind, key, [value at level 1 … max_level])]`` for every stat and resource maximum of
    the actor (``actor_data``, as saved) with ``class_datas`` as its jobs."""
    from asteria.rpg.actors import (
        ActorDefinition,
        ClassAssignment,
        ClassDefinition,
        RpgActorRuntime,
    )

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
    for resource_id in sorted(runtime.resources.names()):
        top = runtime.resources.maximum(resource_id)
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
    """The charts of a job (``category`` "classes") or an actor ("actors") being edited in
    ``form`` (a RecordForm); they are drawn again a moment after each edit."""

    COLUMNS = 4

    def __init__(self, form, category):
        super().__init__()
        self.form, self.category = form, category
        self.setObjectName("GrowthCurves")
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        controls = QHBoxLayout()
        self.actor = QComboBox()
        self.actor.setToolTip("The actor whose base stats the job's growth is added to")
        self.actor.currentIndexChanged.connect(lambda _i: self.redraw())
        self.max_level = QSpinBox()
        self.max_level.setRange(2, 999)
        self.max_level.setValue(99)
        self.max_level.setToolTip("How far the charts reach (only what is shown here)")
        self.max_level.valueChanged.connect(lambda _v: self.redraw())
        if category == "classes":
            controls.addWidget(QLabel("Preview with"))
            controls.addWidget(self.actor)
        else:
            self.actor.hide()
        controls.addWidget(QLabel("Up to level"))
        controls.addWidget(self.max_level)
        controls.addStretch(1)
        column.addLayout(controls)
        self.grid = QGridLayout()
        self.grid.setSpacing(8)
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
        self._fill_actors()
        self.redraw()

    def _database(self):
        project = getattr(self.form.document, "project", None)
        return getattr(project, "rpg_database", None)

    def _fill_actors(self):
        database = self._database()
        if database is None or self.category != "classes":
            return
        own = str(self.form._data.get("class_id", ""))
        actors = sorted(
            database.actors.values(),
            key=lambda a: (
                own not in [c.class_id for c in a.class_assignments],
                a.display_name.lower(),
            ),
        )
        self.actor.blockSignals(True)
        for actor in actors:
            self.actor.addItem(actor.display_name or actor.actor_id, actor.actor_id)
        self.actor.blockSignals(False)

    def _inputs(self):
        """``(actor data, [class data])`` from the record being edited."""
        database = self._database()
        data = self.form._data
        if self.category == "classes":
            actor_id = self.actor.currentData()
            if database is None or actor_id not in database.actors:
                from asteria.rpg.actors import ActorDefinition

                return ActorDefinition("preview").to_data(), [data]
            return database.actors[actor_id].to_data(), [data]
        classes = []
        for assignment in data.get("class_assignments") or ():
            if not isinstance(assignment, dict) or not assignment.get("enabled", True):
                continue
            definition = (database.classes if database else {}).get(assignment.get("class_id"))
            if definition is not None:
                classes.append(definition.to_data())
        return data, classes

    def redraw(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().hide()
                item.widget().setParent(None)  # gone now (not found among the children)
                item.widget().deleteLater()
        try:
            actor, classes = self._inputs()
            curves = growth_curves(actor, classes, self.max_level.value())
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            self.note.setText(f"Cannot draw the curves yet: {exc}")
            self.note.show()
            return
        self.note.hide()
        vocabulary = getattr(self.form, "vocabulary", None)
        names = {}
        if vocabulary is not None:
            for kind in ("stats", "resources"):
                names.update({c.value: c.label for c in vocabulary.choices(kind)})
        from .record_vocabulary import label_for

        rank = {"vitality": 0, "technique": 1}  # HP, MP first, as RPG Maker lists them
        if vocabulary is not None:  # stats in the game's own order (STR, DEX, INT…)
            for kind in ("resources", "stats"):
                for choice in vocabulary.choices(kind):
                    rank.setdefault(choice.value, len(rank))
        curves.sort(key=lambda c: (c[0] != "resource", rank.get(c[1], 1e9), c[1]))
        for index, (_kind, key, values) in enumerate(curves):
            title = names.get(key) or label_for(key)
            chart = CurveChart(title, values, COLOURS[index % len(COLOURS)])
            chart.setToolTip("")
            row, column = divmod(index, self.COLUMNS)
            self.grid.addWidget(chart, row, column)
        for column in range(self.COLUMNS):
            self.grid.setColumnStretch(column, 1)


class StatBar(QWidget):
    """One stat beside the others of its kind: a bar to the strongest record's value, a tick
    at the average, the value and its place (``#2 of 14``)."""

    def __init__(self, title, value, others, colour, parent=None):
        super().__init__(parent)
        self.setObjectName("StatCompareBar")
        self.title, self.value, self.colour = title, float(value), QColor(colour)
        values = [self.value, *(float(v) for v in others)]  # this record and the rest
        self.top = max([*values, 0.0]) or 1.0
        self.average = sum(values) / len(values)
        self.rank = 1 + sum(1 for v in values[1:] if v > self.value)
        self.count = len(values)
        self.setMinimumHeight(22)
        self.setToolTip(translate(f"Average {self.average:g} · strongest {self.top:g}"))

    def sizeHint(self):  # noqa: N802 - Qt API
        return QSize(260, 22)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        name_width, tail = 70, 118
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
        words = translate(f"{self.value:g}  #{self.rank} of {self.count}")
        painter.drawText(
            QRectF(track.right() + 8, 0, tail - 8, self.height()), Qt.AlignVCenter, words
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

    def redraw(self):
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        own = self.form._data.get(self.key) or {}
        vocabulary = getattr(self.form, "vocabulary", None)
        names, rank = {}, {"vitality": 0, "technique": 1}
        if vocabulary is not None:
            for kind in ("resources", "stats"):
                for choice in vocabulary.choices(kind):
                    names.setdefault(choice.value, choice.label)
                    rank.setdefault(choice.value, len(rank))
        from .record_vocabulary import label_for

        keys = sorted(own, key=lambda k: (rank.get(k, 1e9), k))
        for index, stat in enumerate(keys):
            others = [
                record[self.key][stat]
                for record in self.siblings.values()
                if isinstance(record.get(self.key), dict)
                and isinstance(record[self.key].get(stat), (int, float))
            ]
            bar = StatBar(
                names.get(stat) or label_for(stat),
                own[stat],
                others,
                COLOURS[index % len(COLOURS)],
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
            painter.setBrush(QColor(COLOURS[index % len(COLOURS)]))
            painter.drawEllipse(at, 9, 9)
            painter.setPen(palette.base().color())
            painter.drawText(
                QRectF(at.x() - 9, at.y() - 9, 18, 18), Qt.AlignCenter, str(index + 1)
            )
            painter.setPen(palette.text().color())
            painter.drawText(
                QRectF(at.x() - 60, at.y() + 11, 120, 16), Qt.AlignHCenter, translate(name)
            )
