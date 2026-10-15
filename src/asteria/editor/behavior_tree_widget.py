"""Behavior tree editor (RPG-09): tree list, node hierarchy, node kind and parameters, add / remove
/ move."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .authoring_sidebar import authoring_sidebar
from .behavior_tree_authoring import (
    KIND_GROUPS,
    PARAMS,
    BehaviorTreeAuthoring,
    BehaviorTreeAuthoringError,
)


def describe(node):
    params = ", ".join(f"{k}={v}" for k, v in node.params.items())
    return f"{node.kind}" + (f"  ({params})" if params else "")


class BehaviorTreeEditorWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = BehaviorTreeAuthoring(document)
        self.last_error = None
        self.tree_list = QListWidget()
        self.tree_list.currentTextChanged.connect(lambda _t: self._load())
        new_button, delete_button = QPushButton("New…"), QPushButton("Delete")
        new_button.clicked.connect(self._new_clicked)
        delete_button.clicked.connect(self.delete_tree)
        row = QHBoxLayout()
        row.addWidget(new_button)
        row.addWidget(delete_button)
        left_box = authoring_sidebar("Behavior Trees", self.tree_list, footer=row)

        self.nodes = QTreeWidget()
        self.nodes.setObjectName("BehaviorTreeNodes")
        self.nodes.setHeaderLabels(["Node"])
        self.nodes.setHeaderHidden(True)
        self.nodes.setFrameShape(QFrame.NoFrame)
        self.nodes.itemSelectionChanged.connect(self._node_selected)
        center_box = QGroupBox()
        center_box.setObjectName("EnemyAISectionCard")
        center_box.setContentsMargins(0, 0, 0, 0)
        center = QVBoxLayout(center_box)
        center.setContentsMargins(10, 10, 10, 10)
        center.setSpacing(10)
        nodes_heading = QLabel("Node")
        nodes_heading.setObjectName("EnemyAISectionTitle")
        center.addWidget(nodes_heading)
        nodes_hint = QLabel(
            "Ticks top to bottom: sequence = all in order, selector = first that works"
        )
        nodes_hint.setObjectName("MutedLabel")
        nodes_hint.setWordWrap(True)
        center.addWidget(nodes_hint)
        center.addWidget(self.nodes, 1)

        self.kind = QComboBox()
        self.add_kind = QComboBox()
        for label, kinds in KIND_GROUPS:
            for kind in kinds:
                self.kind.addItem(f"{label}: {kind}", kind)
                self.add_kind.addItem(f"{label}: {kind}", kind)
        self.form = QFormLayout()
        self.fields = {}
        apply_kind, apply_params = QPushButton("Change Kind"), QPushButton("Apply Parameters")
        apply_kind.clicked.connect(self.apply_kind)
        apply_params.clicked.connect(self.apply_params)
        add_child, remove, up, down = (
            QPushButton("Add Child"),
            QPushButton("Remove"),
            QPushButton("↑"),
            QPushButton("↓"),
        )
        add_child.clicked.connect(lambda: self.add_child(self.add_kind.currentData()))
        remove.clicked.connect(self.remove_node)
        up.clicked.connect(lambda: self.move_node(-1))
        down.clicked.connect(lambda: self.move_node(1))
        node_box = QGroupBox()
        node_box.setObjectName("EnemyAISectionCard")
        node_box.setMinimumHeight(320)
        card_layout = QVBoxLayout(node_box)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(10)
        heading = QLabel("Selected Node")
        heading.setObjectName("EnemyAISectionTitle")
        card_layout.addWidget(heading)
        node_content = QWidget()
        nv = QVBoxLayout(node_content)
        nv.setContentsMargins(8, 8, 8, 8)
        nv.setSpacing(12)
        kind_row = QHBoxLayout()
        kind_row.addWidget(self.kind, 1)
        kind_row.addWidget(apply_kind)
        nv.addLayout(kind_row)
        nv.addLayout(self.form)
        nv.addWidget(apply_params)
        order = QHBoxLayout()
        for b in (up, down, remove):
            order.addWidget(b)
        nv.addLayout(order)
        add_row = QHBoxLayout()
        add_row.addWidget(self.add_kind, 1)
        add_row.addWidget(add_child)
        nv.addLayout(add_row)
        nv.addStretch(1)
        node_scroll = QScrollArea()
        node_scroll.setWidgetResizable(True)
        node_scroll.setFrameShape(QFrame.NoFrame)
        node_scroll.setViewportMargins(0, 0, 8, 0)
        node_scroll.setWidget(node_content)
        card_layout.addWidget(node_scroll, 1)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.addWidget(node_box, 1)
        right.addWidget(self.status)
        right_box = QWidget()
        right_box.setLayout(right)
        split = QSplitter()
        for w in (left_box, center_box, right_box):
            split.addWidget(w)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split)
        self.refresh()

    # -- state -----------------------------------------------------------------------------------
    @property
    def tree_id(self):
        item = self.tree_list.currentItem()
        return None if item is None else item.text()

    @property
    def path(self):
        item = self.nodes.currentItem()
        return None if item is None else tuple(item.data(0, Qt.UserRole))

    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        current = select or self.tree_id
        ids = self.api.ids()
        self.tree_list.blockSignals(True)
        self.tree_list.clear()
        self.tree_list.addItems(list(ids))
        self.tree_list.blockSignals(False)
        if ids:
            self.tree_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load()

    def _load(self, path=None):
        self.nodes.clear()
        if self.tree_id is None:
            return
        tree = self.api.get(self.tree_id)
        items = {}
        for node_path, node in tree.root.walk():
            item = QTreeWidgetItem([describe(node)])
            item.setData(0, Qt.UserRole, list(node_path))
            if node_path:
                items[node_path[:-1]].addChild(item)
            else:
                self.nodes.addTopLevelItem(item)
            items[node_path] = item
        self.nodes.expandAll()
        target = items.get(tuple(path) if path is not None else ()) or items[()]
        self.nodes.setCurrentItem(target)
        self._node_selected()

    def select_node(self, path):
        self._load(path)
        return self.path == tuple(path)

    def _node_selected(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.fields = {}
        if self.tree_id is None or self.path is None:
            return
        node = self.api.get(self.tree_id).node(self.path)
        self.kind.setCurrentIndex(self.kind.findData(node.kind))
        for name, default in PARAMS.get(node.kind, ()):
            edit = QLineEdit(str(node.params.get(name, default)))
            self.fields[name] = edit
            self.form.addRow(name, edit)

    # -- edits -----------------------------------------------------------------------------------
    def _try(self, action, message, path=None):
        try:
            result = action()
        except (BehaviorTreeAuthoringError, ValueError, TypeError, KeyError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self._load(path if path is not None else self.path)
        self.changed.emit()
        return result if result is not None else True

    def apply_params(self):
        values = {}
        for name, edit in self.fields.items():
            default = dict(PARAMS[self.api.get(self.tree_id).node(self.path).kind])[name]
            text = edit.text().strip()
            values[name] = (
                text.lower() in ("1", "true", "yes", "on") if isinstance(default, bool) else text
            )
        path = self.path
        return self._try(
            lambda: self.api.set_params(self.tree_id, path, **values), "Parameters saved", path
        )

    def apply_kind(self):
        path, kind = self.path, self.kind.currentData()
        return self._try(lambda: self.api.set_kind(self.tree_id, path, kind), f"Now {kind}", path)

    def add_child(self, kind):
        path = self.path
        return self._try(
            lambda: self.api.add_child(self.tree_id, path, kind), f"Added {kind}", path
        )

    def remove_node(self):
        path = self.path
        if not path:
            self.status.setText("The root node cannot be removed")
            return None
        return self._try(lambda: self.api.remove(self.tree_id, path), "Removed", path[:-1])

    def move_node(self, delta):
        path = self.path
        if not path:
            return None
        target = (*path[:-1], path[-1] + delta)
        return self._try(lambda: self.api.move(self.tree_id, path, delta), "Moved", target)

    def create_tree(self, tree_id, root_kind="selector"):
        result = self._try(lambda: self.api.create(tree_id, root_kind), f"Created {tree_id}")
        if result:
            self.refresh(select=tree_id)
        return result

    def delete_tree(self):
        tree_id = self.tree_id
        result = tree_id and self._try(lambda: self.api.delete(tree_id), f"Deleted {tree_id}")
        if result:
            self.refresh()
        return result

    def _new_clicked(self):
        value, ok = QInputDialog.getText(self, "New Behavior Tree", "Tree id:")
        if ok and value.strip():
            self.create_tree(value.strip())
