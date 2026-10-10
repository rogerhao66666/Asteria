from __future__ import annotations

from copy import deepcopy

try:
    from PySide6.QtCore import Qt, Signal
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
        self.itemChanged.connect(lambda *_: self.changed.emit())

    def set_record(self, data):
        self.blockSignals(True)
        try:
            self.clear()
            self._data = deepcopy(data)
            self._append(None, self._data, "Record", ())
            self.expandToDepth(1)
        finally:
            self.blockSignals(False)

    def _append(self, parent, value, label, path):
        item = QTreeWidgetItem([str(label), ""])
        item.setData(0, Qt.UserRole, path)
        if parent is None:
            self.addTopLevelItem(item)
        else:
            parent.addChild(item)
        if isinstance(value, dict):
            for key, val in value.items():
                self._append(item, val, key, path + (key,))
        elif isinstance(value, list):
            for index, val in enumerate(value):
                self._append(item, val, f"[{index}]", path + (index,))
        else:
            item.setText(1, _scalar_text(value))
            item.setData(1, Qt.UserRole, deepcopy(value))
            item.setFlags(item.flags() | Qt.ItemIsEditable)
        return item

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
                if isinstance(original, (dict, list)):
                    if child.childCount():
                        walk(child)
                    continue
                value = _coerce_like(child.text(1), original)
                target = result
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value

        walk(root)
        return result


class AuthoringHubWidget(QWidget):
    """Reusable shell surface for one canonical authoring family.

    The hub owns navigation/presentation only. All mutations route through the
    supplied canonical controller; no parallel editor-side domain model exists.
    """

    if QT_AVAILABLE:
        changed = Signal()

    def __init__(self, title, controller, categories, *, encode, decode, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.title = str(title)
        self.controller = controller
        self.categories = tuple(categories)
        self.encode = encode
        self.decode = decode
        self._ids = []

        header = QHBoxLayout()
        heading = QLabel(self.title)
        heading.setObjectName("SectionLabel")
        self.category = QComboBox()
        for key, label in self.categories:
            self.category.addItem(label, key)
        self.category.currentIndexChanged.connect(self.refresh)
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(self.category)

        self.browser = QListWidget()
        self.browser.currentRowChanged.connect(self._selection_changed)
        self.editor = StructuredRecordEditor()
        split = QSplitter()
        split.addWidget(self.browser)
        split.addWidget(self.editor)
        split.setStretchFactor(1, 1)

        buttons = QHBoxLayout()
        self.apply_button = QPushButton("Apply Changes")
        self.delete_button = QPushButton("Delete")
        self.apply_button.clicked.connect(self.apply_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        buttons.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(split, 1)
        layout.addLayout(buttons)
        self.refresh()

    @property
    def category_id(self):
        return self.category.currentData()

    @property
    def selected_id(self):
        row = self.browser.currentRow()
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def refresh(self):
        category = self.category_id
        self.browser.clear()
        self.editor.clear()
        self._ids = []
        if category is None or self.controller.project is None:
            return
        self._ids = list(self._list_ids(category))
        self.browser.addItems(self._ids)
        if self._ids:
            self.browser.setCurrentRow(0)

    def _list_ids(self, category):
        # Controller families use either library ids or definitions().
        if hasattr(self.controller, "library") and category in getattr(self.controller, "CATEGORIES", ()):
            return self.controller.library.ids(category)
        if hasattr(self.controller, "library") and category in self.controller.library.categories():
            return self.controller.library.ids(category)
        kind = getattr(getattr(self.controller, "information_architecture", None), "kind", lambda x: None)(category)
        if kind is not None:
            return tuple(str(getattr(x, kind.key_attr)) for x in self.controller.definitions(category))
        # RPG authoring controllers expose canonical database mappings. Adapter encode
        # supplies mapping lookup and may expose an ids callback.
        ids = getattr(self.encode, "ids", None)
        return ids(category, self.controller) if ids else ()

    def _selection_changed(self, row):
        key = self.selected_id
        if key is None:
            self.editor.clear()
            return
        data = self.encode(self.category_id, key, self.controller)
        self.editor.set_record(data)

    def apply_selected(self):
        key = self.selected_id
        if key is None:
            return False
        data = self.editor.record()
        value = self.decode(self.category_id, data, self.controller)
        self.controller.edit(self.category_id, key, value)
        self.changed.emit()
        self.refresh()
        if key in self._ids:
            self.browser.setCurrentRow(self._ids.index(key))
        return True

    def delete_selected(self):
        key = self.selected_id
        if key is None:
            return False
        self.controller.delete(self.category_id, key)
        self.changed.emit()
        self.refresh()
        return True


class SkillTreeGraphView(QGraphicsView):
    """Functional no-icon graph view for canonical progression prerequisites."""

    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.scene_graph = QGraphicsScene(self)
        self.setScene(self.scene_graph)
        self.node_items = {}

    def set_graph_data(self, data):
        self.scene_graph.clear()
        self.node_items = {}
        if not data:
            return
        positions = data.get("node_positions", {})
        nodes = data.get("nodes", [])
        # Deterministic fallback layout by prerequisite depth.
        depths = {}

        def depth(node):
            nid = node["node_id"]
            if nid in depths:
                return depths[nid]
            req = node.get("prerequisites", []) + node.get("any_prerequisites", [])
            depths[nid] = (
                0
                if not req
                else 1 + max((depth(next(x for x in nodes if x["node_id"] == r["node_id"])) for r in req), default=0)
            )
            return depths[nid]

        rows = {}
        for node in nodes:
            d = depth(node)
            idx = rows.get(d, 0)
            rows[d] = idx + 1
            x, y = positions.get(node["node_id"], [d * 190, idx * 90])
            rect = QGraphicsRectItem(0, 0, 150, 52)
            rect.setFlag(QGraphicsRectItem.ItemIsMovable, True)
            rect.setFlag(QGraphicsRectItem.ItemIsSelectable, True)
            rect.setPos(float(x), float(y))
            self.scene_graph.addItem(rect)
            text = QGraphicsTextItem(node.get("display_name") or node["node_id"], rect)
            text.setPos(8, 6)
            self.node_items[node["node_id"]] = rect
        # Lines intentionally follow current saved positions; refresh after dragging/saving.
        for node in nodes:
            target = self.node_items[node["node_id"]]
            for req in node.get("prerequisites", []) + node.get("any_prerequisites", []):
                source = self.node_items.get(req["node_id"])
                if source is not None:
                    a = source.sceneBoundingRect().center()
                    b = target.sceneBoundingRect().center()
                    self.scene_graph.addLine(a.x(), a.y(), b.x(), b.y())
        self.scene_graph.setSceneRect(self.scene_graph.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def positions(self):
        return {key: [item.pos().x(), item.pos().y()] for key, item in self.node_items.items()}


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

        header = QHBoxLayout()
        heading = QLabel(self.title)
        heading.setObjectName("SectionLabel")
        self.category = QComboBox()
        for adapter in adapters:
            self.category.addItem(adapter.label, adapter.category_id)
        self.category.currentIndexChanged.connect(self.refresh)
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(self.category)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter records…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _text: self.refresh(keep=self.selected_ids))
        self.browser = QListWidget()
        self.browser.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.browser.currentRowChanged.connect(self._selection_changed)
        self.browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self.browser.customContextMenuRequested.connect(self._context_menu)
        browser_panel = QWidget()
        browser_layout = QVBoxLayout(browser_panel)
        browser_layout.setContentsMargins(0, 0, 0, 0)
        browser_layout.addWidget(self.search)
        browser_layout.addWidget(self.browser, 1)
        self.editor = StructuredRecordEditor()
        self.graph_view = SkillTreeGraphView()
        self.detail_stack = QStackedWidget()
        self.detail_stack.addWidget(self.editor)
        self.detail_stack.addWidget(self.graph_view)
        split = QSplitter()
        split.addWidget(browser_panel)
        split.addWidget(self.detail_stack)
        split.setStretchFactor(1, 1)

        actions = QHBoxLayout()
        self.view_button = QPushButton("Graph View")
        self.view_button.clicked.connect(self.toggle_skill_tree_view)
        self.save_layout_button = QPushButton("Save Graph Layout")
        self.save_layout_button.clicked.connect(self.save_graph_layout)
        self.duplicate_button = QPushButton("Duplicate…")
        self.apply_button = QPushButton("Apply Changes")
        self.delete_button = QPushButton("Delete")
        self.duplicate_button.clicked.connect(self.duplicate_selected)
        self.apply_button.clicked.connect(self.apply_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        actions.addWidget(self.view_button)
        actions.addWidget(self.save_layout_button)
        actions.addStretch(1)
        actions.addWidget(self.duplicate_button)
        actions.addWidget(self.apply_button)
        actions.addWidget(self.delete_button)

        layout = QVBoxLayout(self)
        layout.addLayout(header)
        layout.addWidget(split, 1)
        layout.addLayout(actions)
        self.refresh()

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
            self.browser.setCurrentRow(first, self.browser.selectionModel().SelectionFlag.NoUpdate)
            self._selection_changed(first)

    def refresh(self, *_args, keep=None):
        adapter = self.adapter
        self.browser.blockSignals(True)
        self.browser.clear()
        self.browser.blockSignals(False)
        self.editor.clear()
        self._ids = []
        if adapter is None:
            return
        needle = self.search.text().strip().lower()
        self._ids = [key for key in adapter.ids() if not needle or needle in key.lower()]
        self.browser.addItems(self._ids)
        self.duplicate_button.setEnabled(adapter.duplicate is not None and bool(self._ids))
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

    def _selection_changed(self, row):
        key = self.selected_id
        if key is None:
            self.editor.clear()
            return
        data = self.adapter.encode(self.adapter.get(key))
        self.editor.set_record(data)
        if self.category_id == "graphs":
            self.graph_view.set_graph_data(data)
            if data.get("editor_view") == "graph":
                self.detail_stack.setCurrentWidget(self.graph_view)

    def toggle_skill_tree_view(self):
        if self.category_id != "graphs":
            return False
        graph = self.detail_stack.currentWidget() is self.graph_view
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

    def apply_selected(self):
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
        from PySide6.QtWidgets import QInputDialog

        value, ok = QInputDialog.getText(self, "Duplicate", "New ID:")
        if not ok or not value.strip():
            return False
        return self.duplicate_selected_as(value.strip())

    # -- record clipboard, multi-delete, batch edit (EDT-03, EDT-13, EDT-14) ----------------
    def _run(self, title, operation):
        from .record_operations import RecordOperationError

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
        from .record_operations import copy_records

        ids = self.selected_ids
        return bool(ids) and self._run("Copy", lambda: copy_records(self.document.clipboard, self.adapter, ids))

    def cut_selected(self):
        from .record_operations import cut_records

        ids = self.selected_ids
        if not ids:
            return False
        done = self._run("Cut", lambda: cut_records(self.document, self.document.clipboard, self.adapter, ids))
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
        from .record_operations import paste_records

        created = self._run("Paste", lambda: paste_records(self.document, self.document.clipboard, self.adapter))
        if created:
            self.changed.emit()
            self.refresh(keep=created)
        return created or []

    def delete_selected(self):
        from .record_operations import delete_records

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
        from .record_operations import common_fields

        ids = self.selected_ids
        return common_fields(self.adapter, ids) if ids else {}

    def batch_edit_selected(self, path, value):
        from .record_operations import batch_set

        ids = self.selected_ids
        if not ids:
            return False
        done = self._run("Batch Edit", lambda: batch_set(self.document, self.adapter, ids, path, value))
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
            ("Duplicate…", self.duplicate_selected, has and not many and self.adapter.duplicate is not None),
            (None, None, False),
            (f"Batch Edit {len(self.selected_ids)} Records…", self.open_batch_edit, many and editable),
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
        from .record_operations import MIXED

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
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.rebuild()

    def rebuild(self):
        project = getattr(getattr(self.builder, "__self__", None), "project", None)
        pid = getattr(project, "id", None)
        if self.child is not None and pid == self.project_id:
            refresh = getattr(self.child, "refresh", None)
            if callable(refresh):
                refresh()
            return
        if self.child is not None:
            self.child.hide()
            self.layout.removeWidget(self.child)
            self.child.deleteLater()
            self.child = None
        self.project_id = pid
        if project is None:
            self.child = QLabel("Open a Project to use this authoring workspace.")
        else:
            document = getattr(getattr(self.builder, "__self__", None), "document", None)
            self.child = AdapterFamilyWidget(self.title, self.builder(), document=document)
            self.child.changed.connect(self.changed.emit)
        self.layout.addWidget(self.child)
