try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
        QComboBox,
        QHeaderView,
        QLabel,
        QTableWidget,
        QTableWidgetItem,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    Qt = None
    QT_AVAILABLE = False

    class QWidget:
        pass


class _HierarchyTree(QTreeWidget if QT_AVAILABLE else object):
    """Drops are applied to the scene model (reparent / reorder / move scene), never as a visual-only move."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner

    def dropEvent(self, event):  # noqa: N802 - Qt API
        target = self.itemAt(event.position().toPoint())
        position = {
            QAbstractItemView.OnItem: "on",
            QAbstractItemView.AboveItem: "above",
            QAbstractItemView.BelowItem: "below",
        }.get(self.dropIndicatorPosition(), "on")
        payload = None if target is None else target.data(0, Qt.UserRole)
        self._owner.drop_selected(payload, position)
        event.ignore()  # the tree is rebuilt from the model


class ProjectTreeWidget(QWidget):
    def __init__(self, document, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for editor UI")
        super().__init__(parent)
        self.document = document
        self.tree = _HierarchyTree(self)
        self.tree.setHeaderLabels(["Project"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setDragEnabled(True)
        self.tree.setAcceptDrops(True)
        self.tree.setDropIndicatorShown(True)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tree)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.refresh()

    def drop_selected(self, target_payload, position="on"):
        """Drag-and-drop of the selected entities onto a scene or an entity (EDT-14); one undo step."""
        from .hierarchy import HierarchyEditError, drop_entities

        entities = [p[1] for p in (i.data(0, Qt.UserRole) for i in self.tree.selectedItems()) if p and p[0] == "entity"]
        if not entities or target_payload is None or target_payload[0] not in ("scene", "entity"):
            return False
        try:
            drop_entities(self.document, entities, target_payload[0], target_payload[1], position)
        except (HierarchyEditError, ValueError) as exc:
            self.last_error = str(exc)
            window = self.window()
            if hasattr(window, "statusBar"):
                window.statusBar().showMessage(f"Can't drop there: {exc}", 4000)
            return False
        self.last_error = None
        window = self.window()
        if hasattr(window, "refresh_all"):
            window.refresh_all()
        else:
            self.refresh()
        return True

    def _on_selection_changed(self):
        items = self.tree.selectedItems()
        if not items:
            self.document.selection.set_many("none", ())
            return
        payloads = [i.data(0, Qt.UserRole) for i in items]
        payloads = [p for p in payloads if p]
        if not payloads:
            return
        kinds = {p[0] for p in payloads}
        if len(kinds) == 1:
            kind = payloads[0][0]
            values = [p[1] for p in payloads]
            self.document.selection.set_many(kind, values)
        else:
            kind, value = payloads[0]
            self.document.selection.set_single(kind, value)
        window = self.window()
        if hasattr(window, "refresh_selection_context"):
            window.refresh_selection_context()
        else:
            if hasattr(window, "refresh_inspector"):
                window.refresh_inspector()
            if hasattr(window, "_refresh_actions"):
                window._refresh_actions()

    def refresh(self):
        selection = self.document.selection
        selected = {(selection.kind, id(value)) for value in selection.values}
        selected_items = []
        self.tree.blockSignals(True)
        try:
            self.tree.clear()
            project = self.document.project
            if project is None:
                return

            from .icons import icon

            folder_icons = {"Scenes": "scene", "Prefabs": "prefab", "Assets": "folder"}
            kind_icons = {"project": "project", "scene": "scene", "entity": "entity", "component": "settings"}

            def item(label, kind=None, value=None):
                tree_item = QTreeWidgetItem([label])
                name = kind_icons.get(kind) or (folder_icons.get(label) if kind is None else None)
                if kind == "asset":
                    name = asset_icon_name(getattr(value, "source_path", ""))
                elif kind is None and name is None:
                    name = "prefab"
                if name:
                    tree_item.setIcon(0, icon(name))
                if kind is not None:
                    tree_item.setData(0, Qt.UserRole, (kind, value))
                    if (kind, id(value)) in selected:
                        tree_item.setSelected(True)
                        selected_items.append(tree_item)
                return tree_item

            root = item(project.name, "project", project)
            self.tree.addTopLevelItem(root)
            scenes = item("Scenes")
            root.addChild(scenes)
            from asteria.core.transform import parent_entity

            def add_entity(parent_item, entity, placed):
                placed.add(entity.id)
                eitem = item(entity.name, "entity", entity)
                parent_item.addChild(eitem)
                for component in entity.components():
                    citem = item(type(component).__name__, "component", component)
                    eitem.addChild(citem)
                for child in children_by_parent.get(entity.id, ()):
                    if child.id not in placed:
                        add_entity(eitem, child, placed)

            for scene in project.scenes():
                sitem = item(scene.name, "scene", scene)
                scenes.addChild(sitem)
                children_by_parent = {}
                roots = []
                for entity in scene.entities():
                    parent = parent_entity(entity)
                    if parent is None:
                        roots.append(entity)
                    else:
                        children_by_parent.setdefault(parent.id, []).append(entity)
                placed = set()
                for entity in roots:
                    add_entity(sitem, entity, placed)
                # Entities caught in a parent cycle still appear at scene level.
                for entity in scene.entities():
                    if entity.id not in placed:
                        add_entity(sitem, entity, placed)
            prefabs = item("Prefabs")
            root.addChild(prefabs)
            for prefab_id in project.prefabs.ids():
                definition = project.prefabs.get(prefab_id)
                label = f"{definition.name} ({prefab_id})"
                if definition.base_prefab_id:
                    label += f"  ← {definition.base_prefab_id}"
                prefabs.addChild(item(label))
            assets = item("Assets")
            root.addChild(assets)
            for record in project.assets.records():
                assets.addChild(item(record.source_path, "asset", record))
            root.setExpanded(True)
            scenes.setExpanded(True)
            for selected_item in selected_items:
                parent = selected_item.parent()
                while parent is not None:
                    parent.setExpanded(True)
                    parent = parent.parent()
            if selected_items:
                self.tree.setCurrentItem(selected_items[0])
        finally:
            self.tree.blockSignals(False)


def asset_icon_name(path):
    suffix = str(path).rsplit(".", 1)[-1].lower() if "." in str(path) else ""
    if suffix in ("png", "jpg", "jpeg", "gif", "bmp", "webp"):
        return "image"
    if suffix in ("ogg", "wav", "mp3", "flac", "m4a"):
        return "audio"
    if suffix in ("py",):
        return "code"
    if suffix in ("json", "tsj", "tmj", "tsx", "tmx"):
        return "list"
    return "folder"


class InspectorWidget(QWidget):
    def __init__(self, document, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for editor UI")
        super().__init__(parent)
        self.document = document
        self._refreshing = False
        self._field_models = {}
        self.title = QLabel("Nothing selected")
        self.error = QLabel("")
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Property", "Value", "Type"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.itemChanged.connect(self._item_changed)
        self.title.setObjectName("SectionLabel")
        self.error.setObjectName("ErrorLabel")
        self.empty_state = self._empty_state()
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.error)
        layout.addWidget(self.table)
        layout.addWidget(self.empty_state, 1)
        self._set_empty(True)

    def _empty_state(self):
        from .icons import pixmap

        box = QWidget()
        column = QVBoxLayout(box)
        column.addStretch(1)
        picture = QLabel()
        from .theme import CURRENT

        picture.setPixmap(pixmap("inspector", 44, CURRENT["palette"].text_muted, 2.0))
        picture.setAlignment(Qt.AlignCenter)
        heading = QLabel("Nothing selected")
        heading.setObjectName("EmptyStateTitle")
        heading.setAlignment(Qt.AlignCenter)
        hint = QLabel("Pick an entity in the scene or the project tree to edit its properties here.")
        hint.setObjectName("EmptyStateHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        for widget in (picture, heading, hint):
            column.addWidget(widget)
        column.addStretch(2)
        return box

    def _set_empty(self, empty):
        self.empty_state.setVisible(empty)
        self.table.setVisible(not empty)
        self.title.setVisible(not empty)

    def show_message(self, message):
        self._refreshing = True
        try:
            self.title.setText(message)
            self.error.setText("")
            self.table.setRowCount(0)
            self._field_models = {}
            self._set_empty(message == "Nothing selected")
        finally:
            self._refreshing = False

    def show_properties(self, title, rows):
        self._set_empty(False)
        self._refreshing = True
        try:
            self.title.setText(title)
            self.error.setText("")
            self._field_models = {}
            self.table.setRowCount(len(rows))
            for i, (name, value, type_name) in enumerate(rows):
                n = QTableWidgetItem(str(name))
                n.setFlags(n.flags() & ~Qt.ItemIsEditable)
                v = QTableWidgetItem(str(value))
                v.setFlags(v.flags() & ~Qt.ItemIsEditable)
                t = QTableWidgetItem(str(type_name))
                t.setFlags(t.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, 0, n)
                self.table.setItem(i, 1, v)
                self.table.setItem(i, 2, t)
        finally:
            self._refreshing = False

    def show_component(self, title, fields):
        self._refreshing = True
        try:
            self.title.setText(title)
            self.error.setText("")
            self.table.setRowCount(len(fields))
            self._field_models = {}
            for row, f in enumerate(fields):
                self._field_models[row] = f
                n = QTableWidgetItem(f.label)
                n.setFlags(n.flags() & ~Qt.ItemIsEditable)
                v = QTableWidgetItem(str(f.value))
                if not f.editable:
                    v.setFlags(v.flags() & ~Qt.ItemIsEditable)
                t = QTableWidgetItem(f.type_name)
                t.setFlags(t.flags() & ~Qt.ItemIsEditable)
                if f.tooltip:
                    n.setToolTip(f.tooltip)
                    v.setToolTip(f.tooltip)
                self.table.setItem(row, 0, n)
                # A cell widget from a previously shown component would otherwise
                # sit on top of this row's plain value item.
                self.table.removeCellWidget(row, 1)
                from .inspector import inspector_choices

                choices = inspector_choices(self.document, self.document.selection.value, f)
                if choices is not None:
                    combo = QComboBox()
                    for label, value in choices:
                        combo.addItem(label, value)
                    current = combo.findData(f.value if f.choices else str(f.value))
                    combo.setCurrentIndex(max(0, current))
                    combo.setEnabled(f.editable)
                    if f.tooltip:
                        combo.setToolTip(f.tooltip)
                    combo.currentIndexChanged.connect(lambda _index, r=row, c=combo: self._choice_changed(r, c))
                    self.table.setItem(row, 1, v)
                    self.table.setCellWidget(row, 1, combo)
                elif f.value_type is bool:
                    checkbox = QCheckBox()
                    checkbox.setChecked(bool(f.value))
                    checkbox.setEnabled(f.editable)
                    if f.tooltip:
                        checkbox.setToolTip(f.tooltip)
                    checkbox.toggled.connect(lambda checked, r=row: self._bool_changed(r, checked))
                    self.table.setItem(row, 1, v)
                    self.table.setCellWidget(row, 1, checkbox)
                else:
                    self.table.setItem(row, 1, v)
                self.table.setItem(row, 2, t)
        finally:
            self._refreshing = False

    def _bool_changed(self, row, checked):
        if self._refreshing:
            return
        field = self._field_models.get(row)
        if field is None or not field.editable:
            return
        window = self.window()
        if not hasattr(window, "edit_selected_component_field"):
            return
        ok, error = window.edit_selected_component_field(field.name, bool(checked))
        self.error.setText("" if ok else error or "Invalid value")

    def _choice_changed(self, row, combo):
        if self._refreshing:
            return
        field = self._field_models.get(row)
        if field is None or not field.editable:
            return
        window = self.window()
        if not hasattr(window, "edit_selected_component_field"):
            return
        ok, error = window.edit_selected_component_field(field.name, combo.currentData())
        self.error.setText("" if ok else error or "Invalid value")

    def _item_changed(self, item):
        if self._refreshing or item.column() != 1:
            return
        field = self._field_models.get(item.row())
        if field is None or not field.editable:
            return
        window = self.window()
        if not hasattr(window, "edit_selected_component_field"):
            return
        ok, error = window.edit_selected_component_field(field.name, item.text())
        if ok:
            self.error.setText("")
            self._refreshing = True
            try:
                item.setText(str(getattr(self.document.selection.value, field.name)))
            finally:
                self._refreshing = False
        else:
            self.error.setText(error or "Invalid value")
            self._refreshing = True
            try:
                item.setText(str(getattr(self.document.selection.value, field.name)))
            finally:
                self._refreshing = False


class SceneViewportPlaceholder(QWidget):
    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for editor UI")
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Scene View")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
