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


class ProjectTreeWidget(QWidget):
    def __init__(self, document, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for editor UI")
        super().__init__(parent)
        self.document = document
        self.tree = QTreeWidget()
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

            def item(label, kind=None, value=None):
                tree_item = QTreeWidgetItem([label])
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
            for scene in project.scenes():
                sitem = item(scene.name, "scene", scene)
                scenes.addChild(sitem)
                for entity in scene.entities():
                    eitem = item(entity.name, "entity", entity)
                    sitem.addChild(eitem)
                    for component in entity.components():
                        citem = item(type(component).__name__, "component", component)
                        eitem.addChild(citem)
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
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.table.itemChanged.connect(self._item_changed)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.error)
        layout.addWidget(self.table)

    def show_message(self, message):
        self._refreshing = True
        try:
            self.title.setText(message)
            self.error.setText("")
            self.table.setRowCount(0)
            self._field_models = {}
        finally:
            self._refreshing = False

    def show_properties(self, title, rows):
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
                    combo.currentIndexChanged.connect(
                        lambda _index, r=row, c=combo: self._choice_changed(r, c)
                    )
                    self.table.setItem(row, 1, v)
                    self.table.setCellWidget(row, 1, combo)
                elif f.value_type is bool:
                    checkbox = QCheckBox()
                    checkbox.setChecked(bool(f.value))
                    checkbox.setEnabled(f.editable)
                    if f.tooltip:
                        checkbox.setToolTip(f.tooltip)
                    checkbox.toggled.connect(
                        lambda checked, r=row: self._bool_changed(r, checked)
                    )
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
        ok, error = window.edit_selected_component_field(
            field.name, combo.currentData()
        )
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
        label = QLabel("Scene Viewport\n(runtime renderer integration comes next)")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
