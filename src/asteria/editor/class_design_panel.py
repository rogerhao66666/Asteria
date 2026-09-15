"""Class/Job design surface: gear, level table and point allocation.

The engine already expresses all of this, just not in one place: a class grants
capability tags, equipment requires them, a progression track carries the
per-level stat growth and learned abilities, and a progression graph is what
makes points spendable by hand. Authors think of those four things as one
screen ("what can this job wear, what does it learn, how does it grow"), so
this panel edits them together over canonical records only.

Two naming conventions tie a class to its own records — `<class_id>_growth`
for the level table and `<class_id>_tree` for the optional skill tree — so no
new engine field is needed to associate them.
"""
from __future__ import annotations

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QAbstractItemView, QCheckBox, QGroupBox, QHBoxLayout, QHeaderView,
        QInputDialog, QLabel, QPushButton, QTableWidget,
        QTableWidgetItem, QVBoxLayout, QWidget,
    )
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover - headless import guard
    QT_AVAILABLE = False

    class QWidget:
        pass

    class Signal:
        def __init__(self, *args, **kwargs):
            pass


_LEVEL_HINT = (
    "One row per level. Values are what that level itself adds; "
    "typing in the last row adds another level."
)

GROWTH_SUFFIX = "_growth"
TREE_SUFFIX = "_tree"
DEFAULT_LEVELS = 5
_FIXED_COLUMNS = ("Level", "Exp Total", "Learns")


def growth_track_id(class_id):
    return f"{class_id}{GROWTH_SUFFIX}"


def skill_tree_id(class_id):
    return f"{class_id}{TREE_SUFFIX}"


def _capability_universe(equipment_records):
    universe = set()
    for data in equipment_records.values():
        universe.update(data.get("required_capabilities") or ())
        universe.update(data.get("any_capabilities") or ())
    return universe


def can_equip(class_tags, equipment_data):
    """Mirror of EquipmentDefinition's own gate, over a class's granted tags."""
    available = set(class_tags)
    required = set(equipment_data.get("required_capabilities") or ())
    any_of = set(equipment_data.get("any_capabilities") or ())
    forbidden = set(equipment_data.get("forbidden_capabilities") or ())
    if required - available:
        return False
    if any_of and not (any_of & available):
        return False
    return not (forbidden & available)


class ClassDesignPanel(QWidget):
    """Gear / level / allocation editor for one class, over canonical records."""

    if QT_AVAILABLE:
        changed = Signal()

    def __init__(self, adapters, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.adapters = adapters
        self.class_id = None
        self._loading = False
        self._stats = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._build_equipment_group())
        layout.addWidget(self._build_levels_group())

    # ---------- construction ----------

    def _build_equipment_group(self):
        group = QGroupBox("Equippable")
        group.setObjectName("RecordFieldGroup")
        box = QVBoxLayout(group)
        self.equipment_table = QTableWidget()
        self.equipment_table.setObjectName("RecordTable")
        self.equipment_table.setColumnCount(4)
        self.equipment_table.setHorizontalHeaderLabels(
            ["Allowed", "Equipment", "Slot", "Requires"]
        )
        self.equipment_table.setAlternatingRowColors(True)
        self.equipment_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.equipment_table.verticalHeader().setDefaultSectionSize(22)
        self.equipment_table.itemChanged.connect(self._equipment_toggled)
        box.addWidget(self.equipment_table)
        self.equipment_hint = QLabel(
            "Tick what this job may wear — the capability tags it needs are granted automatically."
        )
        self.equipment_hint.setObjectName("MutedLabel")
        self.equipment_hint.setWordWrap(True)
        box.addWidget(self.equipment_hint)
        return group

    def _build_levels_group(self):
        group = QGroupBox("Levels, Growth and Skills")
        group.setObjectName("RecordFieldGroup")
        box = QVBoxLayout(group)
        self.level_table = QTableWidget()
        self.level_table.setObjectName("RecordTable")
        self.level_table.setAlternatingRowColors(True)
        self.level_table.verticalHeader().setDefaultSectionSize(22)
        self.level_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.AnyKeyPressed
        )
        self.level_table.itemChanged.connect(self._level_edited)
        box.addWidget(self.level_table)

        controls = QHBoxLayout()
        self.add_stat_button = QPushButton("Add Stat Column…")
        self.add_stat_button.clicked.connect(self._add_stat_column)
        self.allocation_checkbox = QCheckBox("Allow manual point allocation")
        self.allocation_checkbox.setToolTip(
            "Off: levels give the growth below automatically.\n"
            "On: this job also gets a skill tree whose nodes are bought with points."
        )
        self.allocation_checkbox.toggled.connect(self._allocation_toggled)
        controls.addWidget(self.add_stat_button)
        controls.addStretch(1)
        controls.addWidget(self.allocation_checkbox)
        box.addLayout(controls)

        self.level_hint = QLabel(_LEVEL_HINT)
        self.level_hint.setObjectName("MutedLabel")
        self.level_hint.setWordWrap(True)
        box.addWidget(self.level_hint)
        return group

    # ---------- canonical record access ----------

    def _records(self, category):
        adapter = self.adapters.get(category)
        if adapter is None:
            return {}
        return {key: adapter.encode(adapter.get(key)) for key in adapter.ids()}

    def _class_record(self):
        adapter = self.adapters.get("classes")
        if adapter is None or self.class_id is None:
            return None
        if self.class_id not in adapter.ids():
            return None
        return adapter.encode(adapter.get(self.class_id))

    def _track_record(self):
        adapter = self.adapters.get("tracks")
        track_id = growth_track_id(self.class_id)
        if adapter is None or track_id not in adapter.ids():
            return None
        return adapter.encode(adapter.get(track_id))

    def _write(self, category, key, data):
        adapter = self.adapters[category]
        adapter.edit(key, adapter.decode(data))
        self.changed.emit()

    # ---------- refresh ----------

    def set_class(self, class_id):
        self.class_id = None if class_id is None else str(class_id)
        self.reload()

    def reload(self):
        self._loading = True
        try:
            self._reload_equipment()
            self._reload_levels()
        finally:
            self._loading = False

    def _reload_equipment(self):
        record = self._class_record()
        tags = set(record.get("granted_tags") or ()) if record else set()
        equipment = self._records("equipment")
        table = self.equipment_table
        table.setRowCount(len(equipment))
        for row, (key, data) in enumerate(sorted(equipment.items())):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            check.setCheckState(
                Qt.Checked if record and can_equip(tags, data) else Qt.Unchecked
            )
            check.setData(Qt.UserRole, key)
            table.setItem(row, 0, check)
            for column, value in enumerate(
                (
                    data.get("display_name") or key,
                    data.get("slot") or "",
                    ", ".join(
                        list(data.get("required_capabilities") or ())
                        + list(data.get("any_capabilities") or ())
                    ),
                ),
                start=1,
            ):
                cell = QTableWidgetItem(str(value))
                cell.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                table.setItem(row, column, cell)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for column in range(1, 4):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        table.setMinimumHeight(max(3, min(6, len(equipment))) * 22 + 40)
        table.setEnabled(bool(equipment))
        if not equipment:
            self.equipment_hint.setText(
                "No Equipment defined yet — add some under the Equipment category first."
            )

    def _level_stats(self, milestones):
        stats = []
        for milestone in milestones:
            for stat in milestone.get("stat_bonuses") or {}:
                if stat not in stats:
                    stats.append(stat)
        return stats

    def _reload_levels(self):
        track = self._track_record()
        milestones = list(track.get("milestones") or ()) if track else []
        self._stats = self._level_stats(milestones)
        columns = ["Level", "Exp Total", *self._stats, "Learns"]
        table = self.level_table
        table.setColumnCount(len(columns))
        table.setHorizontalHeaderLabels(columns)
        rows = max(DEFAULT_LEVELS, len(milestones) + 1)
        table.setRowCount(rows)
        for row in range(rows):
            milestone = milestones[row] if row < len(milestones) else None
            values = [
                str(milestone["rank"]) if milestone else "",
                f"{float(milestone.get('required_total', 0.0)):g}" if milestone else "",
            ]
            for stat in self._stats:
                bonus = (milestone.get("stat_bonuses") or {}).get(stat) if milestone else None
                values.append("" if bonus is None else f"{float(bonus):g}")
            values.append(
                ", ".join(milestone.get("granted_abilities") or ()) if milestone else ""
            )
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))
        header = table.horizontalHeader()
        for column in range(len(columns)):
            header.setSectionResizeMode(column, QHeaderView.Stretch)
        table.setMinimumHeight(rows * 22 + 40)

        graphs = self.adapters.get("graphs")
        has_tree = graphs is not None and skill_tree_id(self.class_id or "") in graphs.ids()
        self.allocation_checkbox.blockSignals(True)
        self.allocation_checkbox.setChecked(has_tree)
        self.allocation_checkbox.blockSignals(False)

    # ---------- edits ----------

    def _equipment_toggled(self, item):
        if self._loading or item.column() != 0 or self.class_id is None:
            return
        record = self._class_record()
        if record is None:
            return
        equipment = self._records("equipment")
        universe = _capability_universe(equipment)
        allowed = set()
        for row in range(self.equipment_table.rowCount()):
            cell = self.equipment_table.item(row, 0)
            if cell is not None and cell.checkState() == Qt.Checked:
                allowed.add(cell.data(Qt.UserRole))
        needed = set()
        for key in allowed:
            data = equipment.get(key) or {}
            needed.update(data.get("required_capabilities") or ())
            any_of = list(data.get("any_capabilities") or ())
            if any_of:
                needed.add(any_of[0])
        # Tags the author wrote by hand are not equipment capabilities; keep them.
        kept = [tag for tag in (record.get("granted_tags") or ()) if tag not in universe]
        record["granted_tags"] = sorted(set(kept) | needed)
        self._write("classes", self.class_id, record)
        self.reload()

    def _ensure_track(self):
        adapter = self.adapters["tracks"]
        track_id = growth_track_id(self.class_id)
        if track_id not in adapter.ids():
            adapter.create(track_id)
        return adapter.encode(adapter.get(track_id))

    def _level_edited(self, item):
        if self._loading or self.class_id is None:
            return
        track = self._ensure_track()
        milestones = []
        for row in range(self.level_table.rowCount()):
            texts = [
                (self.level_table.item(row, column).text().strip()
                 if self.level_table.item(row, column) is not None else "")
                for column in range(self.level_table.columnCount())
            ]
            if not any(texts):
                continue
            try:
                rank = int(float(texts[0] or row + 1))
            except ValueError:
                rank = row + 1
            milestone = {
                "rank": rank,
                "required_total": _as_float(texts[1]),
                "stat_bonuses": {
                    stat: _as_float(texts[2 + index])
                    for index, stat in enumerate(self._stats)
                    if texts[2 + index]
                },
                "granted_abilities": [
                    x.strip() for x in texts[-1].split(",") if x.strip()
                ],
                "granted_tags": [],
            }
            milestones.append(milestone)
        track["milestones"] = milestones
        try:
            self._write("tracks", growth_track_id(self.class_id), track)
        except Exception as exc:
            # Inline table editing must never raise a modal — the row is simply
            # not valid yet (a half-typed level), so say so and let typing go on.
            self.level_hint.setText(str(exc))
            return
        self.level_hint.setText(_LEVEL_HINT)
        self.reload()

    def _add_stat_column(self):
        if self.class_id is None:
            return False
        name, ok = QInputDialog.getText(self, "Add Stat", "Stat name:")
        name = str(name).strip()
        if not ok or not name or name in self._stats:
            return False
        track = self._ensure_track()
        milestones = list(track.get("milestones") or ())
        if not milestones:
            milestones = [
                {"rank": level, "required_total": 0.0, "stat_bonuses": {},
                 "granted_abilities": [], "granted_tags": []}
                for level in range(1, DEFAULT_LEVELS + 1)
            ]
        for milestone in milestones:
            milestone.setdefault("stat_bonuses", {}).setdefault(name, 0.0)
        track["milestones"] = milestones
        self._write("tracks", growth_track_id(self.class_id), track)
        self.reload()
        return True

    def _allocation_toggled(self, enabled):
        """Manual allocation is exactly 'this job has a skill tree to spend on'."""
        if self._loading or self.class_id is None:
            return False
        adapter = self.adapters.get("graphs")
        if adapter is None:
            return False
        tree_id = skill_tree_id(self.class_id)
        exists = tree_id in adapter.ids()
        if enabled and not exists:
            adapter.create(tree_id)
        elif not enabled and exists:
            adapter.delete(tree_id)
        self.changed.emit()
        self.reload()
        return True


def _as_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0
