from __future__ import annotations

import re
from copy import deepcopy
from math import atan2, cos, sin

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFormLayout,
        QGraphicsRectItem,
        QGraphicsScene,
        QGraphicsTextItem,
        QGraphicsView,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QMenu,
        QMessageBox,
        QPushButton,
        QSplitter,
        QStackedWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass

    class QTreeWidget:
        pass

    class QTreeWidgetItem:
        pass

    class QComboBox:
        pass

    class QHBoxLayout:
        pass

    class QLabel:
        pass

    class QListWidget:
        pass

    class QPushButton:
        pass

    class QSplitter:
        pass

    class QVBoxLayout:
        pass

    class QGraphicsView:
        pass

    class QGraphicsScene:
        pass

    class QGraphicsRectItem:
        pass

    class QGraphicsTextItem:
        pass

    class QStackedWidget:
        pass

    class Signal:
        def __init__(self, *args, **kwargs):
            pass


def with_optional_fields(data, value):
    """Show optional fields a definition leaves out of its data when they are empty
    (``OPTIONAL_DATA``), so an
    author can find and fill them; empty values are still left out when saved."""
    if not isinstance(data, dict):
        return data
    optional = getattr(type(value), "OPTIONAL_DATA", None) or {}
    data = {**data, **{k: deepcopy(v) for k, v in optional.items() if k not in data}}
    for key, kind in (getattr(type(value), "NESTED_OPTIONAL", None) or {}).items():
        entries = data.get(key)
        defaults = getattr(kind, "OPTIONAL_DATA", None) or {}
        if isinstance(entries, list) and defaults:
            data[key] = [
                {**x, **{k: deepcopy(v) for k, v in defaults.items() if k not in x}}
                if isinstance(x, dict)
                else x
                for x in entries
            ]
    return _with_formula_fields(data)


def _with_formula_fields(data):
    """Every record that can hold a formula shows its formula field, however deep it sits (a
    skill's damage formula inside its effect), empty when unset (D94)."""
    from asteria.gameplay.expressions import FORMULA_FIELDS

    if isinstance(data, list):
        return [_with_formula_fields(x) for x in data]
    if not isinstance(data, dict):
        return data
    out = {k: _with_formula_fields(v) for k, v in data.items()}
    schema = out.get("schema")
    for (owner, key), _names in FORMULA_FIELDS.items():
        if owner == schema and key not in out:
            out[key] = ""
    return out


def _count_heading(label, category_label, count):
    """The list heading names what is listed: "Actors" (no count: the list shows them)."""
    label.setText(category_label)


def _category_icons(browser, category_label):
    """Give every record in a database list its category's icon (actor, skill, item...)."""
    from asteria.editor.ui.decor import label_icon
    from asteria.editor.ui.icons import icon

    name = label_icon(category_label)
    if name:
        for row in range(browser.count()):
            browser.item(row).setIcon(icon(name))


class AuthoringHubError(RuntimeError):
    pass


def _scalar_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _coerce_like(text, original):
    if original is None:
        value = text.strip()
        return None if value == "" else value
    if isinstance(original, bool):
        low = text.strip().lower()
        if low in {"true", "1", "yes", "on"}:
            return True
        if low in {"false", "0", "no", "off"}:
            return False
        raise ValueError("boolean value must be true/false")
    if isinstance(original, int) and not isinstance(original, bool):
        return int(text)
    if isinstance(original, float):
        return float(text)
    return str(text)


_SCALARS = (str, int, float, bool)


def _coerce_list(text, original):
    """``"a, b"`` -> ``["a", "b"]``; each entry takes the type of the list's existing entries (text
    if empty)."""
    template = original[0] if original else ""
    return [_coerce_like(part.strip(), template) for part in str(text).split(",") if part.strip()]


_FORMAT_KEYS = ("schema", "version")
_ACRONYMS = {
    "tag": "Property",  # the word the editor uses for tags
    "tags": "Properties",
    "id": "ID",
    "ids": "IDs",
    "hp": "HP",
    "mp": "MP",
    "sp": "SP",
    "tp": "TP",
    "xp": "XP",
    "exp": "EXP",
    "ui": "UI",
    "hud": "HUD",
    "ai": "AI",
    "vfx": "VFX",
    "sfx": "SFX",
    "bgm": "BGM",
    "fx": "FX",
    "uri": "URI",
    "x": "X",
    "y": "Y",
    "z": "Z",
    "rpg": "RPG",
    "bp": "BP",
    "ap": "AP",
    "jp": "JP",
    "atb": "ATB",
    "ko": "KO",
    "npc": "NPC",
    "aoe": "AOE",
}


def free_id(base, taken, suffix="copy"):
    """A suggested id for a new or copied record: ``fire_bolt_copy``, ``fire_bolt_copy2``...;
    a tag family keeps its ``*`` at the end (``rune.*`` -> ``rune_copy.*``, D91)."""
    base, family = (base[:-2], ".*") if str(base).endswith(".*") else (base, "")
    base = f"{base}_{suffix}" if base else suffix
    taken, candidate, number = set(taken), base + family, 2
    while candidate in taken:
        candidate, number = f"{base}{number}{family}", number + 1
    return candidate


def _new_name(kind_label):
    """A new record's name from its kind: "Enemies / Bosses" -> "New Enemy", "Loot Rarities"
    -> "New Loot Rarity"."""
    from asteria.editor.records.form_shapes import singular

    head = re.split(r" / | \(", str(kind_label))[0].split() or ["Record"]
    last = head[-1] if head[-1].isupper() else singular(head[-1].lower())  # "AI" stays
    return " ".join(["New", *head[:-1], last[:1].upper() + last[1:]])


def field_label(key):
    """``display_name`` -> "Display Name", ``actor_id`` -> "Actor ID" (the data key itself is
    unchanged)."""
    words = str(key).replace("-", "_").split("_")
    return " ".join(_ACRONYMS.get(w.lower(), w[:1].upper() + w[1:]) for w in words if w) or str(
        key
    )


def _summary(value):
    """A short name for a list entry: its id / name if it has one, the value itself if it is
    short."""
    if isinstance(value, dict):
        for key in ("id", "name", "display_name", "label", "title"):
            if isinstance(value.get(key), (str, int)) and str(value[key]):
                return str(value[key])
        for key, val in value.items():
            if key.endswith("_id") and isinstance(val, (str, int)) and str(val):
                return str(val)
        return ""
    if isinstance(value, (str, int, float)) and len(str(value)) <= 32:
        return ""  # shown in the value column
    return ""


def _record_title(data):
    if isinstance(data, dict):
        for key, val in data.items():
            if key.endswith("_id") and isinstance(val, str) and val:
                return val
        for key in ("id", "name", "display_name"):
            if isinstance(data.get(key), str) and data[key]:
                return data[key]
    return "Record"


class StructuredRecordEditor(QTreeWidget):
    """Small recursive structured-data editor.

    It is deliberately not a raw JSON text box. Dict/list structure is navigated
    as a tree and only scalar leaves are directly editable. Reconstruction still
    goes through each canonical type's deserializer/constructor, so domain
    validation remains authoritative.
    """

    if QT_AVAILABLE:
        changed = Signal()

    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.setHeaderLabels(["Field", "Value"])
        self.setAlternatingRowColors(True)
        self._data = None
        # field name -> callable returning ((value, QIcon or None), ...): those leaves get an
        # editable
        # drop-down of suggestions (any typed value is still accepted)
        self.field_choices = {}
        self.icon_library = None  # an ``IconLibrary``: icon_id fields become icon pickers
        self.itemChanged.connect(lambda *_: self.changed.emit())
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._structure_menu)

    def set_record(self, data, title=None):
        self.blockSignals(True)
        try:
            self.clear()
            self._data = deepcopy(data)
            root = self._append(
                None, self._data, title or _record_title(self._data), (), root=True
            )
            if isinstance(self._data, dict) and (
                "schema" in self._data or "version" in self._data
            ):
                root.setToolTip(
                    0, f"Format {self._data.get('schema', '?')} v{self._data.get('version', '?')}"
                )
            self.expandToDepth(1)
            self.resizeColumnToContents(0)  # full field names (they were cut to "def…", "resour…")
            self.setColumnWidth(0, min(max(self.columnWidth(0), 140), 360))
        finally:
            self.blockSignals(False)

    def _append(self, parent, value, label, path, *, root=False):
        item = QTreeWidgetItem([str(label), ""])
        item.setData(0, Qt.UserRole, path)
        if parent is None:
            self.addTopLevelItem(item)
        else:
            parent.addChild(item)
        if isinstance(value, dict):
            for key, val in value.items():
                if root and key in _FORMAT_KEYS:
                    # file-format bookkeeping, not game data (kept as is; shown in the tooltip)
                    continue
                child = self._append(item, val, field_label(key), path + (key,))
                child.setToolTip(0, str(key))
            if not root:
                item.setText(1, f"{len(value)} field" + ("" if len(value) == 1 else "s"))
                item.setForeground(1, self.palette().placeholderText())
        elif isinstance(value, list) and all(isinstance(v, _SCALARS) for v in value):
            # a list of plain values (tags, ids, numbers) is edited as one comma-separated text
            item.setText(1, ", ".join(_scalar_text(v) for v in value))
            item.setData(1, Qt.UserRole, deepcopy(value))
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setToolTip(1, "Comma-separated list; leave empty for none")
        elif isinstance(value, list):
            for index, val in enumerate(value):
                summary = _summary(val)
                self._append(
                    item,
                    val,
                    f"#{index + 1}" + (f" · {summary}" if summary else ""),
                    path + (index,),
                )
            item.setText(1, f"{len(value)} item" + ("" if len(value) == 1 else "s"))
            item.setForeground(1, self.palette().placeholderText())
        else:
            item.setText(1, _scalar_text(value))
            item.setData(1, Qt.UserRole, deepcopy(value))
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            key = path[-1] if path else None
            from asteria.editor.assets.image_tools import picture_field

            if picture_field(key) and isinstance(value, str) and self.icon_library is not None:
                self._icon_widget(item, value)
            elif isinstance(key, str) and key in self.field_choices and isinstance(value, str):
                self._choice_widget(item, value, self.field_choices[key]())
        return item

    def _icon_widget(self, item, value):
        """An icon id field: the icon picker (project icons, built-in library, Browse…)."""
        from PySide6.QtGui import QBrush

        from asteria.editor.rpg.game_systems_widget import _IconPicker

        picker = _IconPicker(self.icon_library)
        picker.setText(value)
        picker.changed.connect(lambda it=item, p=picker: it.setText(1, p.text()))
        item.setForeground(1, QBrush(Qt.transparent))
        self.setItemWidget(item, 1, picker)
        return picker

    def _choice_widget(self, item, value, choices):
        from PySide6.QtGui import QBrush

        combo = QComboBox()
        combo.setEditable(True)
        combo.addItem("", "")
        for choice, icon in choices:
            if icon is not None:
                combo.addItem(icon, choice, choice)
            else:
                combo.addItem(choice, choice)
        combo.setCurrentText(value)
        combo.setToolTip("Pick one, or type any id or path; empty for none")
        combo.currentTextChanged.connect(lambda text, it=item: it.setText(1, text))
        item.setForeground(
            1, QBrush(Qt.transparent)
        )  # the combo shows the value; the text stays for record()
        self.setItemWidget(item, 1, combo)
        return combo

    # Entries a list field starts from when "Add Entry" is used on an empty list (any field may
    # have one).
    LIST_TEMPLATES = {
        "hits": {
            "tags": [],
            "power": 1.0,
            "checks": [""],  # outcome check ids rolled for this hit (crit, evade...)
            "kill": {"chance": 0.0, "resource": "", "immune_tags": [], "immune_fraction": 0.0},
        },
        "forms": {  # a way to cast the skill: chosen from a list when it is used
            "form_id": "new_form",
            "label": "New Form",
            "tags": [""],
            "power": 1.0,
            "resource_costs": {},
            "battle_costs": {},
            "apply_states": [],
        },
        "battle_resource_gains": {"to": "targets", "resource": "", "amount": 1.0},
        "commands": {"command": "", "args": {}},
        "apply_states": {"state": "", "to": "targets", "remove": False},
    }

    def _value_at(self, data, path):
        for part in path:
            data = data[part]
        return data

    def _structure_menu(self, position):
        """Add or remove list entries and dict fields (hits, commands, battle costs...) - the
        tree's structure."""
        item = self.itemAt(position)
        if item is None or self._data is None:
            return
        path = tuple(item.data(0, Qt.UserRole) or ())
        menu = QMenu(self)
        target = self._value_at(self.record(), path)
        if isinstance(target, list) and not (
            target and all(isinstance(v, _SCALARS) for v in target)
        ):
            menu.addAction("Add Entry", lambda: self.add_entry(path))
        if isinstance(target, dict) and path:
            menu.addAction("Add Field…", lambda: self.add_field(path))
        if path and isinstance(path[-1], int):
            menu.addAction("Remove Entry", lambda: self.remove_entry(path))
        if not menu.isEmpty():
            menu.exec(self.viewport().mapToGlobal(position))

    def _restructure(self, data):
        title = self.topLevelItem(0).text(0) if self.topLevelItem(0) is not None else None
        self.set_record(data, title)
        self.changed.emit()

    def add_entry(self, path):
        data = self.record()
        values = self._value_at(data, path)
        key = next((p for p in reversed(path) if isinstance(p, str)), "")
        if values:
            entry = deepcopy(values[-1])
        else:
            entry = deepcopy(self.LIST_TEMPLATES.get(key, {}))
        values.append(entry)
        self._restructure(data)
        return entry

    def remove_entry(self, path):
        data = self.record()
        del self._value_at(data, path[:-1])[path[-1]]
        self._restructure(data)

    def add_field(self, path, name=None, value=0.0):
        if name is None:
            from PySide6.QtWidgets import QInputDialog

            name, ok = QInputDialog.getText(
                self, "Add Field", "Name (e.g. a resource id):", text="new_field"
            )
            if not ok or not str(name).strip():
                return None
        data = self.record()
        self._value_at(data, path)[str(name).strip()] = value
        self._restructure(data)
        return name

    def record(self):
        if self._data is None:
            return None
        result = deepcopy(self._data)
        root = self.topLevelItem(0)

        def walk(item):
            for i in range(item.childCount()):
                child = item.child(i)
                path = child.data(0, Qt.UserRole)
                original = self._data
                for part in path:
                    original = original[part]
                if isinstance(original, list) and not child.childCount():
                    value = _coerce_list(child.text(1), original)
                elif isinstance(original, (dict, list)):
                    if child.childCount():
                        walk(child)
                    continue
                else:
                    value = _coerce_like(child.text(1), original)
                target = result
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value

        walk(root)
        return result


# node cards of the skill tree graph: what a node gives decides its colour
_NODE_KINDS = (
    ("skill", "#4f8fe8", "Grants a skill"),
    ("passive", "#a46be0", "Unlocks a passive"),
    ("choice", "#e0954f", "One of an exclusive group"),
    ("stats", "#4caf7d", "Stats / resources"),
    ("other", "#7b8496", "Properties / capabilities"),
)
_NODE_W, _NODE_H, _ICON = 176.0, 64.0, 40


def _node_kind(node):
    rewards = node.get("rewards", [])
    if node.get("exclusive_group"):
        return "choice"
    if any(r.get("granted_abilities") for r in rewards):
        return "skill"
    if any(r.get("unlocked_passives") for r in rewards):
        return "passive"
    if any(r.get("stat_bonuses") or r.get("resource_bonuses") for r in rewards):
        return "stats"
    return "other"


def _spread(positions, gap=16.0):
    """Saved node positions scaled up just enough that no two cards overlap (a layout saved
    for smaller cards, or packed by hand)."""
    points = [(float(x), float(y)) for x, y in positions.values()]
    scale = 1.0
    for i, (ax, ay) in enumerate(points):
        for bx, by in points[i + 1 :]:
            dx, dy = abs(ax - bx), abs(ay - by)
            need = min(
                (_NODE_W + gap) / dx if dx else float("inf"),
                (_NODE_H + gap) / dy if dy else float("inf"),
            )
            if need != float("inf"):
                scale = max(scale, need)
    return {k: [float(x) * scale, float(y) * scale] for k, (x, y) in positions.items()}


def _pretty(key):
    return str(key).replace("_", " ").title()


class SkillTreeGraphView(QGraphicsView):
    """A progression graph drawn as its players see the design: a card per node with its icon,
    name, ranks and what it gives (coloured by kind), arrows from each prerequisite (dashed for
    "any of"). Cards can be dragged (Save Graph Layout keeps them); Ctrl + wheel zooms."""

    # defaults until something sets them (code may read them first)
    _edge_items = ()

    def __init__(self, parent=None, *, document=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        from PySide6.QtGui import QPainter

        self.document = document
        self.scene_graph = QGraphicsScene(self)
        self.setScene(self.scene_graph)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.node_items = {}
        self._edges = []
        self._zoom = 1.0

    # -- names for what a node gives -------------------------------------------------------------
    def _name(self, kind, key):
        project = getattr(self.document, "project", None)
        record = None
        if project is not None:
            if kind == "ability":
                record = project.gameplay_library.abilities.get(key)
            elif kind == "passive":
                record = project.rpg_database.passives.get(key)
        return (getattr(record, "display_name", "") or _pretty(key)) if key else ""

    def _reward_icon(self, node):
        """A node without its own icon shows the icon of the skill or passive it gives."""
        project = getattr(self.document, "project", None)
        if project is None:
            return ""
        for reward in node.get("rewards", []):
            for ability_id in reward.get("granted_abilities", []):
                record = project.gameplay_library.abilities.get(ability_id)
                if getattr(record, "icon_id", ""):
                    return record.icon_id
            for passive_id in reward.get("unlocked_passives", []):
                record = project.rpg_database.passives.get(passive_id)
                if getattr(record, "icon_id", ""):
                    return record.icon_id
        return ""

    def _summary(self, node):
        rewards = node.get("rewards", [])
        skills = [a for r in rewards for a in r.get("granted_abilities", [])]
        passives = [p for r in rewards for p in r.get("unlocked_passives", [])]
        if skills:
            return self._name("ability", skills[0]) + (" +" if len(set(skills)) > 1 else "")
        if passives:
            return self._name("passive", passives[0])
        stats = {}
        for r in rewards:
            bonuses = {**r.get("stat_bonuses", {}), **r.get("resource_bonuses", {})}
            for key, value in bonuses.items():
                stats[key] = stats.get(key, 0.0) + float(value)
        return ", ".join(f"+{v:g} {_pretty(k)}" for k, v in list(stats.items())[:2])

    def _tooltip(self, node):
        lines = [f"<b>{node.get('display_name') or node['node_id']}</b> ({node['node_id']})"]
        lines.append(f"Ranks: {node.get('max_rank', 1)}")
        if node.get("exclusive_group"):
            lines.append(f"Exclusive group: {node['exclusive_group']}")
        costs = node.get("rank_costs", [])
        if costs:
            first = ", ".join(f"{v:g} {k}" for k, v in costs[0].items())
            lines.append(f"Cost per rank: {first}")
        need = [r["node_id"] for r in node.get("prerequisites", [])]
        either = [r["node_id"] for r in node.get("any_prerequisites", [])]
        if need:
            lines.append("Needs: " + ", ".join(need))
        if either:
            lines.append("Needs one of: " + ", ".join(either))
        rewards = node.get("rewards", [])
        skills = sorted({a for r in rewards for a in r.get("granted_abilities", [])})
        passives = sorted({p for r in rewards for p in r.get("unlocked_passives", [])})
        if skills:
            lines.append("Skills: " + ", ".join(self._name("ability", a) for a in skills))
        if passives:
            lines.append("Passives: " + ", ".join(self._name("passive", x) for x in passives))
        summary = self._summary(node)
        if summary and not skills and not passives:
            lines.append("Gives (all ranks): " + summary)
        return "<br>".join(lines)

    # -- drawing ---------------------------------------------------------------------------------
    def set_graph_data(self, data):
        from PySide6.QtGui import QBrush, QColor, QFont, QPen

        self.scene_graph.clear()  # the old arrows go with it
        self.node_items = {}
        self._edges = []
        self._edge_items = []
        if not data:
            return
        positions = _spread(data.get("node_positions", {}))
        nodes = data.get("nodes", [])
        by_id = {n["node_id"]: n for n in nodes}
        depths = {}

        def depth(node, seen=()):
            nid = node["node_id"]
            if nid in depths:
                return depths[nid]
            req = [
                by_id[r["node_id"]]
                for r in node.get("prerequisites", []) + node.get("any_prerequisites", [])
                if r["node_id"] in by_id and r["node_id"] not in seen
            ]
            depths[nid] = 0 if not req else 1 + max(depth(r, (*seen, nid)) for r in req)
            return depths[nid]

        rows = {}
        colours = {k: c for k, c, _ in _NODE_KINDS}
        name_font = QFont()
        name_font.setBold(True)
        small = QFont()
        small.setPointSizeF(max(7.0, small.pointSizeF() - 2))
        for node in nodes:
            d = depth(node)
            idx = rows.get(d, 0)
            rows[d] = idx + 1
            x, y = positions.get(node["node_id"], [d * (_NODE_W + 70), idx * (_NODE_H + 22)])
            colour = QColor(colours[_node_kind(node)])
            card = QGraphicsRectItem(0, 0, _NODE_W, _NODE_H)
            card.setFlag(QGraphicsRectItem.ItemIsMovable, True)
            card.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
            card.setPos(float(x), float(y))
            red, green, blue = colour.red(), colour.green(), colour.blue()
            fill = QColor(red // 4 + 20, green // 4 + 22, blue // 4 + 28)  # a dark card
            card.setBrush(QBrush(fill))
            card.setPen(QPen(colour, 2.0))
            card.setZValue(1)
            card.setToolTip(self._tooltip(node))
            self.scene_graph.addItem(card)
            pixmap = None
            icon_id = node.get("icon_id") or self._reward_icon(node)
            if self.document is not None and icon_id:
                from asteria.editor.assets.image_tools import icon_pixmap

                pixmap = icon_pixmap(self.document, icon_id, _ICON)
            text_x = 8.0
            if pixmap is not None:
                from PySide6.QtWidgets import QGraphicsPixmapItem

                icon = QGraphicsPixmapItem(pixmap)
                icon.setParentItem(card)
                icon.setPos(8, (_NODE_H - _ICON) / 2)
                text_x = 8.0 + _ICON + 8.0
            width = _NODE_W - text_x - 6
            title = QGraphicsTextItem()
            title.setParentItem(card)  # the card owns it (else it is collected)
            title.setDefaultTextColor(QColor("#f2f4f8"))
            title.setFont(name_font)
            title.setPlainText(
                self.fontMetrics().elidedText(
                    node.get("display_name") or node["node_id"], Qt.ElideRight, int(width) - 8
                )
            )
            title.setPos(text_x - 4, 4)
            rank = QGraphicsTextItem()
            rank.setParentItem(card)  # the card owns it (else it is collected)
            rank.setDefaultTextColor(colour.lighter(150))
            rank.setFont(small)
            rank.setPlainText(f"Rank {node.get('max_rank', 1)}")
            rank.setPos(text_x - 4, 24)
            gives = QGraphicsTextItem()
            gives.setParentItem(card)  # the card owns it (else it is collected)
            gives.setDefaultTextColor(QColor("#b9c0cc"))
            gives.setFont(small)
            gives.setPlainText(
                self.fontMetrics().elidedText(self._summary(node), Qt.ElideRight, int(width))
            )
            gives.setPos(text_x - 4, 40)
            self.node_items[node["node_id"]] = card
        for node in nodes:
            target = self.node_items[node["node_id"]]
            for kind in ("prerequisites", "any_prerequisites"):
                for req in node.get(kind, []):
                    source = self.node_items.get(req["node_id"])
                    if source is not None:
                        self._edges.append((source, target, kind == "any_prerequisites"))
        self._draw_edges()
        self.scene_graph.setSceneRect(
            self.scene_graph.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        )
        self.fit()

    def _draw_edges(self):
        """Arrows from each prerequisite's right edge to the node's left edge (behind cards)."""

        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF

        for item in self._edge_items:
            self.scene_graph.removeItem(item)
        self._edge_items = []
        for source, target, either in self._edges:
            a = source.sceneBoundingRect()
            b = target.sceneBoundingRect()
            start = QPointF(a.right(), a.center().y())
            end = QPointF(b.left(), b.center().y())
            if b.left() < a.right():  # a card placed left of its prerequisite
                start, end = QPointF(a.center().x(), a.bottom()), QPointF(b.center().x(), b.top())
            path = QPainterPath(start)
            mid = (start.x() + end.x()) / 2
            path.cubicTo(QPointF(mid, start.y()), QPointF(mid, end.y()), end)
            pen = QPen(QColor("#d6a64f" if either else "#8fa3c0"), 2.0)
            if either:
                pen.setStyle(Qt.DashLine)
            line = self.scene_graph.addPath(path, pen)
            line.setZValue(0)
            before = path.pointAtPercent(0.95)
            angle = atan2(end.y() - before.y(), end.x() - before.x())
            size, a1, a2 = 9.0, angle - 0.45, angle + 0.45
            head = QPolygonF(
                [
                    end,
                    QPointF(end.x() - size * cos(a1), end.y() - size * sin(a1)),
                    QPointF(end.x() - size * cos(a2), end.y() - size * sin(a2)),
                ]
            )
            arrow = self.scene_graph.addPolygon(head, QPen(pen.color()), QBrush(pen.color()))
            arrow.setZValue(0)
            self._edge_items += [line, arrow]

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.scene_graph.selectedItems():  # a card was dragged: the arrows follow it
            self._draw_edges()

    def fit(self):
        if self.node_items:
            self.resetTransform()
            self.fitInView(self.scene_graph.sceneRect(), Qt.KeepAspectRatio)
            scale = self.transform().m11()
            if scale > 1.0:  # a small tree is not blown up
                self.resetTransform()
                scale = 1.0
            elif scale < 0.35:  # a big web opens readable; scroll / zoom to see the rest
                self.resetTransform()
                self.scale(0.35, 0.35)
                scale = 0.35
            self._zoom = scale

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._zoom = max(0.15, min(3.0, self._zoom * factor))
            self.resetTransform()
            self.scale(self._zoom, self._zoom)
            return
        super().wheelEvent(event)

    def positions(self):
        return {key: [item.pos().x(), item.pos().y()] for key, item in self.node_items.items()}


_UNREAD = object()  # AdapterFamilyWidget._encoded: no record handed in / not encoded yet


class _EncodeFailed:
    """What encoding a record raised, kept so every reader sees it again."""

    __slots__ = ("error",)

    def __init__(self, error):
        self.error = error


class AdapterFamilyWidget(QWidget):
    """Qt authoring surface over a set of AuthoringCategoryAdapter objects."""

    if QT_AVAILABLE:
        changed = Signal()

    def __init__(self, title, adapters, parent=None, *, document=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title = str(title)
        self.document = document
        self.adapters = {x.category_id: x for x in adapters}
        self._ids = []
        self.last_error = None
        self._list_chosen = False
        # each record's encoded data (or the error encoding it raised), shared by the filter,
        # the name sort and the row titles; kept across filter / sort changes while nothing is
        # edited (_encodings_stamp)
        self._encodings = {}
        self._encodings_stamp = None
        self._form_stamp = None  # what the form was last built under
        self._applied = 0  # edits applied from the form (they change what is encoded)

        header = QHBoxLayout()
        heading = self.heading = QLabel(self.title)
        heading.setObjectName("SectionLabel")
        self.category = QComboBox()
        self.category.setProperty("decorate", True)  # category icons (decor.py)
        for adapter in adapters:
            self.category.addItem(adapter.label, adapter.category_id)
        from asteria.editor.ui.fit import fit_combo_to_items

        fit_combo_to_items(self.category)  # "Combatant Sprites" whole, with its icon
        self.category.currentIndexChanged.connect(self.refresh)
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(self.category)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter records…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(
            lambda _text: self.refresh(keep=self.selected_ids, same_data=True)
        )
        self.sort = QComboBox()
        for order in ("ID A→Z", "ID Z→A", "Name A→Z", "Name Z→A"):
            self.sort.addItem(order, order)  # the English words are the order's value
        self.sort.currentIndexChanged.connect(
            lambda _i: self.refresh(keep=self.selected_ids, same_data=True)
        )
        self.browser = QListWidget()
        self.browser.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.browser.currentRowChanged.connect(self._selection_changed)
        self.browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser.customContextMenuRequested.connect(self._context_menu)
        browser_panel = QWidget()
        browser_panel.setProperty("sidePanel", True)  # Focus Mode folds it away
        browser_layout = QVBoxLayout(browser_panel)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        filter_row = QHBoxLayout()
        filter_row.addWidget(self.search, 1)
        filter_row.addWidget(self.sort)
        browser_layout.addLayout(filter_row)
        browser_layout.addWidget(self.browser, 1)
        from asteria.editor.records.form import RecordForm

        self.editor = RecordForm(document=document)
        # an edit applies on its own a moment after typing stops (undoable, like any edit)
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(350)
        self._apply_timer.timeout.connect(self.auto_apply)
        self._unannounced = False  # applied edits the rest of the editor has not heard of yet
        self._editing = None
        self.editor.changed.connect(self._apply_timer.start)
        if document is not None:
            from asteria.editor.assets.image_tools import icon_choices

            self.editor.field_choices["icon_id"] = lambda: icon_choices(document)
            from asteria.rpg.battle.states import TARGET_OVERRIDES

            self.editor.field_choices["target_override"] = lambda: [
                (value, None) for value in TARGET_OVERRIDES if value
            ]
            from asteria.editor.assets.image_tools import IconLibrary

            self.editor.icon_library = IconLibrary(document)
        self.graph_view = SkillTreeGraphView(document=document)
        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(self.editor)
        self.detail_stack.addWidget(self.graph_view)
        from asteria.editor.records.note_box import AuthorNoteBox

        # the makers' own note: the last block of every record's form, scrolling with it
        self.note_box = AuthorNoteBox(document)
        self.editor.description_switch = self.note_box.switch
        self.editor.siblings = self._sibling_records  # its numbers beside theirs
        self.editor.trailer = self.note_box
        split = QSplitter()
        split.addWidget(browser_panel)
        split.addWidget(self.detail_stack)
        split.setStretchFactor(1, 1)

        self.view_button = QPushButton("Graph View")
        self.view_button.clicked.connect(self.toggle_skill_tree_view)
        self.save_layout_button = QPushButton("Save Graph Layout")
        self.save_layout_button.clicked.connect(self.save_graph_layout)
        self.new_button = QPushButton("New")
        self.new_button.setToolTip("A new, empty record of this kind")
        self.new_button.clicked.connect(self.new_record)
        self.duplicate_button = QPushButton("Duplicate")
        self.apply_button = QPushButton("Apply Changes")
        self.delete_button = QPushButton("Delete")
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.apply_button.clicked.connect(self.apply_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        from asteria.editor.records.actions import record_action_bar

        actions, self.undo_buttons = record_action_bar(
            self.new_button,
            self.duplicate_button,
            self.delete_button,
            extras=(self.view_button, self.save_layout_button),
        )
        self.apply_button.hide()  # kept for scripts; edits apply on their own

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(split, 1)
        layout.addLayout(actions)
        self.refresh()

    def _name_rows(self):
        """Each row shows the record's name (and its own icon when it has one); the id stays
        after the name when the two differ."""
        icon_for = getattr(self.editor, "icon", None)
        for row, key in enumerate(self._ids):
            item = self.browser.item(row)
            try:
                record = self.adapter.get(key)
            except Exception:  # noqa: BLE001 - a record that cannot be read keeps its id
                continue
            name = str(getattr(record, "display_name", "") or getattr(record, "name", "") or "")
            if not name:  # an evolution, a skill's targeting...: a title made from its parts
                from asteria.editor.records.vocabulary import record_title

                try:
                    data = self._encoded(key, record)
                except Exception:  # noqa: BLE001 - a record that cannot be encoded keeps its id
                    data = None
                name = record_title(self.category_id, data, self.editor.vocabulary, key)
            if name:  # the name only; the internal id is in the filter
                from asteria.editor.ui.i18n import translate

                item.setText(translate(name))  # a list item is drawn as given
            item.setData(Qt.UserRole, key)
            icon_id = getattr(record, "icon_id", "")
            icon = icon_for(icon_id) if icon_for and icon_id else None
            if icon is None:  # an actor's or enemy's own picture, when the project has one
                from PySide6.QtGui import QIcon

                picture = getattr(self.editor, "record_picture", lambda *_: None)(key, 22)
                icon = QIcon(picture) if picture is not None else None
            if icon is not None:
                item.setIcon(icon)

    @property
    def category_id(self):
        return self.category.currentData()

    @property
    def adapter(self):
        return self.adapters.get(self.category_id)

    @property
    def selected_id(self):
        row = self.browser.currentRow()
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def _encoded(self, key, record=_UNREAD):
        """``adapter.encode`` of record ``key``, once per refresh (raises what it raised)."""
        found = self._encodings.get(key, _UNREAD)
        if found is _UNREAD:
            try:
                found = self.adapter.encode(self.adapter.get(key) if record is _UNREAD else record)
            except Exception as exc:  # noqa: BLE001 - raised again to every caller
                found = _EncodeFailed(exc)
            self._encodings[key] = found
        if isinstance(found, _EncodeFailed):
            raise found.error
        return found

    def _name_has(self, key, needle):
        """Whether the filter finds ``needle`` in the record's name, as written or as shown."""
        from asteria.editor.ui.i18n import translate

        name = self._display_name(key)
        return needle in name.lower() or needle in translate(name).lower()

    def _display_name(self, key):
        try:
            data = self._encoded(key)
        except Exception:  # noqa: BLE001 - a record that can't be encoded sorts by id
            return key
        return str(data.get("display_name") or data.get("name") or key)

    def _sorted(self, ids):
        mode = (self.sort.currentData() if hasattr(self, "sort") else None) or "ID A→Z"
        if mode.startswith("Name"):
            ids = sorted(ids, key=lambda k: (self._display_name(k).lower(), k))
        else:
            ids = sorted(ids)
        return ids[::-1] if mode.endswith("Z→A") else ids

    @property
    def selected_ids(self):
        """Selected record ids in list order (multi-select, EDT-14)."""
        rows = sorted(self.browser.row(item) for item in self.browser.selectedItems())
        ids = [self._ids[r] for r in rows if 0 <= r < len(self._ids)]
        if not ids and self.selected_id is not None:
            ids = [self.selected_id]
        return ids

    def select_ids(self, ids):
        wanted = set(ids)
        self.browser.clearSelection()
        first = None
        for row, key in enumerate(self._ids):
            if key in wanted:
                self.browser.item(row).setSelected(True)
                first = row if first is None else first
        if first is not None:
            before = self.browser.currentRow()
            self.browser.setCurrentRow(first, self.browser.selectionModel().SelectionFlag.NoUpdate)
            if first == before:  # another row has told _selection_changed already
                self._selection_changed(first)

    def refresh(self, *_args, keep=None, same_data=False):
        """Rebuild the list; ``same_data``: only the filter or the sort changed, so records
        encoded for the last list are reused unless anything was edited since."""
        from asteria.editor.ui.i18n import CURRENT

        self.flush_edits()
        adapter = self.adapter
        stamp = (
            self.category_id,
            id(adapter),
            getattr(self.document, "revision", None),
            self._applied,
        )
        if not same_data or stamp != self._encodings_stamp:
            self._encodings = {}
        self._encodings_stamp = stamp
        self.browser.blockSignals(True)
        self.browser.clear()
        self.browser.blockSignals(False)
        # nothing changed since the form was built (a refresh with no edit, the second of an
        # edit's two): it stays, if the same record comes back; a big record takes a second
        form_stamp = (*stamp, CURRENT["language"])
        if form_stamp != self._form_stamp or adapter is None:
            self.editor.clear()
        self._form_stamp = form_stamp
        self._ids = []
        if adapter is None:
            return
        needle = self.search.text().strip().lower()
        self._ids = self._sorted(
            [
                key
                for key in adapter.ids()
                if not needle or needle in key.lower() or self._name_has(key, needle)
            ]
        )
        self.browser.addItems(self._ids)
        _category_icons(self.browser, self.category.currentText())
        self._name_rows()
        _count_heading(self.heading, self.category.currentText(), len(self._ids))
        self.duplicate_button.setEnabled(adapter.duplicate is not None and bool(self._ids))
        # a new record is shaped after one that exists: a kind with none yet has no shape
        can_new = adapter.create is not None and bool(adapter.ids())
        self.new_button.setEnabled(can_new)
        self.new_button.setToolTip(
            "A new, empty record of this kind"
            if can_new
            else "No record of this kind yet to take the shape from"
        )
        is_graph = self.category_id == "graphs"
        self.view_button.setVisible(is_graph)
        self.save_layout_button.setVisible(is_graph)
        if not is_graph:
            self.detail_stack.setCurrentWidget(self.editor)
        kept = [key for key in (keep or ()) if key in self._ids]
        if kept:
            self.select_ids(kept)
        elif self._ids:
            self.browser.setCurrentRow(0)
        else:
            self.editor.clear()

    def _selection_changed(self, row):
        self.flush_edits()
        key = self.selected_id
        self.note_box.set_record(
            self.category_id, key, self.adapter.get(key) if key is not None else None
        )
        if key is None:
            self._editing = None
            self.editor.clear()
            return
        value = self.adapter.get(key)
        encoded = self.adapter.encode(value)
        data = with_optional_fields(encoded, value)
        optional = set(data) - set(encoded) if isinstance(data, dict) else ()
        self._editing = key
        graph_first = self.category_id == "graphs" and not self._list_chosen
        if graph_first:  # the graph shows first: the form waits behind it, unbuilt
            self.detail_stack.setCurrentWidget(self.graph_view)
        self.editor.set_record(
            data, key, optional=optional, category=self.category_id, defer=graph_first
        )
        self.editor.set_error(None)
        if self.category_id == "graphs":
            self.graph_view.set_graph_data(data)
            if not self._list_chosen:  # a skill tree opens as its graph until List is asked for
                self.detail_stack.setCurrentWidget(self.graph_view)
                self.view_button.setText("List / Data View")

    def _sibling_records(self):
        """Every record of the kind shown, as the form edits them (for comparing)."""
        adapter = self.adapter
        if adapter is None:
            return {}
        return {key: adapter.encode(adapter.get(key)) for key in adapter.ids()}

    def toggle_skill_tree_view(self):
        if self.category_id != "graphs":
            return False
        graph = self.detail_stack.currentWidget() is self.graph_view
        self._list_chosen = graph  # the author asked for the fields
        self.detail_stack.setCurrentWidget(self.editor if graph else self.graph_view)
        self.view_button.setText("Graph View" if graph else "List / Data View")
        return True

    def save_graph_layout(self):
        if self.category_id != "graphs" or self.selected_id is None:
            return False
        data = self.editor.record()
        data["node_positions"] = self.graph_view.positions()
        data["editor_view"] = "graph"
        value = self.adapter.decode(data)
        self.adapter.edit(self.selected_id, value)
        self.changed.emit()
        self.refresh()
        return True

    def auto_apply(self):
        """Apply what the form holds to the record being edited; a problem shows on the form
        (and nothing is applied)."""
        key = self._editing
        if key is None or self.adapter is None or key not in self._ids:
            return False
        data = self.editor.record()
        if data is None:
            return False
        try:
            value = self.adapter.decode(data)
            self.adapter.edit(key, value)
        except Exception as exc:  # noqa: BLE001 - shown to the author beside the form
            self.editor.set_error(str(exc))
            return False
        self.editor.set_error(None)
        self._unannounced = True
        self._applied += 1
        return True

    def flush_edits(self):
        """Apply a pending edit now and tell the rest of the editor about applied ones."""
        self.note_box.flush()
        if self._apply_timer.isActive():
            self._apply_timer.stop()
            self.auto_apply()
        if self._unannounced:
            self._unannounced = False
            self.changed.emit()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self.flush_edits()
        super().hideEvent(event)

    def apply_selected(self):
        self._apply_timer.stop()
        key = self.selected_id
        if key is None:
            return False
        value = self.adapter.decode(self.editor.record())
        self.adapter.edit(key, value)
        self.changed.emit()
        current = key
        self.refresh()
        if current in self._ids:
            self.browser.setCurrentRow(self._ids.index(current))
        return True

    def new_record_as(self, new_id, name=None):
        """A new record of the shown kind, as empty as the kind allows, named ``name``."""
        from asteria.editor.records.blank import blank_record

        adapter = self.adapter
        if adapter is None or adapter.create is None:
            raise AuthoringHubError("this kind cannot take new records here")
        ids = adapter.ids()
        if not ids:
            raise AuthoringHubError("no record of this kind yet to take the shape from")
        new_id = str(new_id).strip()
        if new_id in ids:
            raise AuthoringHubError(f"{new_id} already exists")
        template = adapter.encode(adapter.get(ids[0]))
        value = blank_record(adapter, template, new_id, str(name or new_id))
        adapter.create(new_id, value)
        self.changed.emit()
        self.refresh(keep=[new_id])
        return new_id

    def new_record(self):
        """A new record made at once: "New Ability" with an id made from it; renamed in its
        form."""
        from asteria.editor.records.blank import suggest_id

        if self.adapter is None or self.adapter.create is None or not self.adapter.ids():
            return None
        name = _new_name(self.category.currentText())
        try:
            return self.new_record_as(suggest_id(name, self.adapter.ids()), name)
        except (AuthoringHubError, ValueError, KeyError, TypeError) as exc:
            self.last_error = str(exc)
            QMessageBox.warning(self, "New", str(exc))
            return None

    def duplicate_selected_as(self, new_id):
        key = self.selected_id
        if key is None:
            return False
        if self.adapter.duplicate is None:
            raise AuthoringHubError("current category does not support direct duplication")
        self.adapter.duplicate(key, str(new_id))
        self.changed.emit()
        self.refresh()
        if str(new_id) in self._ids:
            self.browser.setCurrentRow(self._ids.index(str(new_id)))
        return True

    def duplicate_selected(self):
        if self.selected_id is None or self.adapter.duplicate is None:
            return False
        return self.duplicate_selected_as(free_id(self.selected_id, self._ids))  # id made

    # -- record clipboard, multi-delete, batch edit (EDT-03, EDT-13, EDT-14) ----------------
    def _run(self, title, operation):
        from asteria.editor.records.operations import RecordOperationError

        if self.document is None:
            self.last_error = "no editor document"
            return None
        try:
            result = operation()
        except (RecordOperationError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            self.last_error = str(exc)
            if self.isVisible():
                QMessageBox.warning(self, title, str(exc))
            return None
        self.last_error = None
        return result

    def copy_selected(self):
        from asteria.editor.records.operations import copy_records

        ids = self.selected_ids
        return bool(ids) and self._run(
            "Copy", lambda: copy_records(self.document.clipboard, self.adapter, ids)
        )

    def cut_selected(self):
        from asteria.editor.records.operations import cut_records

        ids = self.selected_ids
        if not ids:
            return False
        done = self._run(
            "Cut", lambda: cut_records(self.document, self.document.clipboard, self.adapter, ids)
        )
        if done:
            self.changed.emit()
            self.refresh()
        return bool(done)

    def can_paste(self):
        return (
            self.document is not None
            and self.adapter is not None
            and self.adapter.create is not None
            and self.document.clipboard.has_records(self.category_id)
        )

    def paste(self):
        from asteria.editor.records.operations import paste_records

        created = self._run(
            "Paste", lambda: paste_records(self.document, self.document.clipboard, self.adapter)
        )
        if created:
            self.changed.emit()
            self.refresh(keep=created)
        return created or []

    def delete_selected(self):
        from asteria.editor.records.operations import delete_records

        ids = self.selected_ids
        if not ids:
            return False
        if self.document is None:
            for key in ids:
                self.adapter.delete(key)
            done = True
        else:
            done = self._run("Delete", lambda: delete_records(self.document, self.adapter, ids))
        if done:
            self.changed.emit()
            self.refresh()
        return bool(done)

    def batch_fields(self):
        from asteria.editor.records.operations import common_fields

        ids = self.selected_ids
        return common_fields(self.adapter, ids) if ids else {}

    def batch_edit_selected(self, path, value):
        from asteria.editor.records.operations import batch_set

        ids = self.selected_ids
        if not ids:
            return False
        done = self._run(
            "Batch Edit", lambda: batch_set(self.document, self.adapter, ids, path, value)
        )
        if done:
            self.changed.emit()
            self.refresh(keep=ids)
        return bool(done)

    def open_batch_edit(self):
        fields = self.batch_fields()
        if not fields:
            return False
        dialog = BatchEditDialog(fields, len(self.selected_ids), self)
        if dialog.exec() != QDialog.Accepted:
            return False
        return self.batch_edit_selected(dialog.path, dialog.value)

    def context_actions(self):
        """(label, callable, enabled) entries of the record list's right-click menu."""
        has = bool(self.selected_ids)
        many = len(self.selected_ids) > 1
        editable = self.document is not None
        return [
            ("Copy", self.copy_selected, has and editable),
            ("Cut", self.cut_selected, has and editable),
            ("Paste", self.paste, self.can_paste()),
            (
                "Duplicate",
                self.duplicate_selected,
                has and not many and self.adapter.duplicate is not None,
            ),
            (None, None, False),
            (
                f"Batch Edit {len(self.selected_ids)} Records…",
                self.open_batch_edit,
                many and editable,
            ),
            ("Delete", self.delete_selected, has),
        ]

    def _context_menu(self, pos):
        if self.adapter is None:
            return
        menu = QMenu(self)
        for label, handler, enabled in self.context_actions():
            if label is None:
                menu.addSeparator()
                continue
            action = menu.addAction(label)
            action.setEnabled(enabled)
            action.triggered.connect(handler)
        menu.exec(self.browser.viewport().mapToGlobal(pos))


class BatchEditDialog(QDialog if QT_AVAILABLE else object):
    """Pick one field shared by the selected records and the value to give all of them."""

    def __init__(self, fields, count, parent=None):
        super().__init__(parent)
        from asteria.editor.records.operations import MIXED

        self.setWindowTitle(f"Batch Edit — {count} records")
        self.fields = fields
        self.mixed = MIXED
        self.field = QComboBox()
        self.field.addItems(list(fields))
        self.input = QLineEdit()
        self.current = QLabel()
        self.field.currentTextChanged.connect(self._field_changed)
        form = QFormLayout(self)
        form.addRow("Field", self.field)
        form.addRow("Current", self.current)
        form.addRow("New value", self.input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self._field_changed(self.field.currentText())

    def _field_changed(self, path):
        value = self.fields.get(path)
        if value is self.mixed:
            self.current.setText("(differs between records)")
            self.input.clear()
        else:
            text = ", ".join(map(str, value)) if isinstance(value, list) else str(value)
            self.current.setText(text)
            self.input.setText(text)

    @property
    def path(self):
        return self.field.currentText()

    @property
    def value(self):
        return self.input.text()


class FamilyHostWidget(QWidget):
    """Rebuildable host so opening another Project never leaves stale adapters."""

    if QT_AVAILABLE:
        changed = Signal()

    def __init__(self, title, builder, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title = str(title)
        self.builder = builder
        self.child = None
        self.project_id = None
        self._project = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.rebuild()

    def rebuild(self, keep=None):
        """Show the project's records; ``keep``: the ids to select in a list that stays, by
        default the ones selected now (a refresh never moves the author to the first record)."""
        project = getattr(getattr(self.builder, "__self__", None), "project", None)
        # the project object itself: two files can share an id (a project copied from another)
        pid = (id(project), getattr(project, "id", None))
        if self.child is not None and pid == self.project_id and project is self._project:
            refresh = getattr(self.child, "refresh", None)
            if callable(refresh):
                if keep is None:
                    keep = getattr(self.child, "selected_ids", None)
                refresh(keep=keep) if keep else refresh()
            return
        if self.child is not None:
            self.child.hide()
            self.layout.removeWidget(self.child)
            self.child.deleteLater()
            self.child = None
        self.project_id = pid
        self._project = project
        if project is None:
            from asteria.editor.project.empty_state import ProjectEmptyState

            self.child = ProjectEmptyState(f"Open a project to edit {self.title.lower()}.")
        else:
            document = getattr(getattr(self.builder, "__self__", None), "document", None)
            self.child = AdapterFamilyWidget(self.title, self.builder(), document=document)
            self.child.changed.connect(self.changed.emit)
        self.layout.addWidget(self.child)
