try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QCheckBox,
        QComboBox,
        QLabel,
        QLineEdit,
        QPushButton,
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
    """Drops are applied to the scene model (reparent / reorder / move scene), never as a
    visual-only move."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setObjectName("ProjectHierarchyTree")

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
        """Drag-and-drop of the selected entities onto a scene or an entity (EDT-14); one undo
        step."""
        from .hierarchy import HierarchyEditError, drop_entities

        entities = [
            p[1]
            for p in (i.data(0, Qt.UserRole) for i in self.tree.selectedItems())
            if p and p[0] == "entity"
        ]
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
            kind_icons = {
                "project": "project",
                "scene": "scene",
                "entity": "entity",
                "component": "settings",
            }

            from .i18n import translate

            def item(label, kind=None, value=None):
                # a folder (no kind) is the editor's own word; a record's name is the author's
                tree_item = QTreeWidgetItem([translate(label) if kind is None else label])
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
    """The selected object's properties as a form: an entity shows every component as its own
    section (numbers, drop-downs, switches, text; each field's hint on hover and under it).
    Edits apply at once through undoable commands; a problem shows in red."""

    def __init__(self, document, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for editor UI")
        super().__init__(parent)
        from PySide6.QtWidgets import QFrame, QScrollArea

        self.document = document
        self._refreshing = False
        self._field_models = {}
        self.title = QLabel("Nothing selected")
        self.title.setObjectName("SectionLabel")
        self.error = QLabel("")
        self.error.setObjectName("ErrorLabel")
        self.error.setWordWrap(True)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.empty_state = self._empty_state()
        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.error)
        layout.addWidget(self.scroll, 1)
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
        hint = QLabel(
            "Pick an entity in the scene or the project tree to edit its properties here."
        )
        hint.setObjectName("EmptyStateHint")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)
        for widget in (picture, heading, hint):
            column.addWidget(widget)
        column.addStretch(2)
        return box

    def _set_empty(self, empty):
        self.empty_state.setVisible(empty)
        self.scroll.setVisible(not empty)
        self.title.setVisible(not empty)

    def _page(self):
        page = QWidget()
        column = QVBoxLayout(page)
        column.setContentsMargins(2, 2, 2, 8)
        column.setSpacing(8)
        return page, column

    def _show(self, page, column):
        column.addStretch(1)
        from .ui_fit import swap_scroll_page

        swap_scroll_page(self.scroll, page)

    def show_message(self, message):
        self.title.setText(message)
        self.error.setText("")
        self._field_models = {}
        self._set_empty(message == "Nothing selected")
        page, column = self._page()
        if message != "Nothing selected":
            column.addWidget(QLabel(message))
        self._show(page, column)

    def show_properties(self, title, rows):
        """Read-only facts (a project, a scene, an asset...)."""
        from .record_form import Section

        self._set_empty(False)
        self.title.setText(title)
        self.error.setText("")
        page, column = self._page()
        section = Section(title, compact=True)
        for name, value, _type_name in rows:
            label = QLabel(str(value))
            label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            section.add_row(str(name), label)
        column.addWidget(section)
        self._show(page, column)

    def show_component(self, title, fields):
        """One component (picked in the project tree)."""
        self._set_empty(False)
        self.title.setText(_pretty_type(title))
        self.error.setText("")
        page, column = self._page()
        component = self.document.selection.value
        column.addWidget(self._component_section(component, fields, selected=True))
        self._show(page, column)

    def show_entity(self, entity):
        """An entity: its name and switch, then every component's fields."""
        from .inspector import build_inspector_fields
        from .record_form import Section

        self._set_empty(False)
        self.title.setText(entity.name or "Entity")
        self.error.setText("")
        page, column = self._page()
        head = Section("Entity", compact=True)
        name = QLineEdit(entity.name)
        name.editingFinished.connect(lambda e=entity, w=name: self._entity(e, name=w.text()))
        head.add_row("Name", name, help_text="What the scene list and events call it.")
        enabled = QCheckBox("Active in the game")
        enabled.setChecked(bool(entity.enabled))
        enabled.toggled.connect(lambda on, e=entity: self._entity(e, enabled=on))
        head.add_row("Enabled", enabled)
        column.addWidget(head)
        passable = self._passability_section(entity)
        if passable is not None:
            column.addWidget(passable)
        for component in entity.components():
            try:
                fields = build_inspector_fields(component)
            except Exception:  # noqa: BLE001 - a component without a schema shows its name
                fields = ()
            column.addWidget(
                self._component_section(component, fields, title=type(component).__name__)
            )
        self._show(page, column)

    def _passability_section(self, entity):
        """Passable, blocks at its feet, or blocks its whole picture (D88), with a picture of
        what blocks; None for an entity without a picture or a collider."""
        from asteria.runtime.collision import Collider2DComponent
        from asteria.runtime.components2d import SpriteRenderer2D

        from .image_tools import project_root
        from .passability import MODE_LABELS, MODES, passability, passability_preview
        from .record_form import Section, _wheel_guard

        if (
            entity.try_get(SpriteRenderer2D) is None
            and entity.try_get(Collider2DComponent) is None
        ):
            return None
        section = Section("Passability", compact=True)
        combo = QComboBox()
        _wheel_guard(combo)
        for mode in MODES:
            combo.addItem(MODE_LABELS[mode], mode)
        combo.setCurrentIndex(MODES.index(passability(entity)))
        combo.currentIndexChanged.connect(
            lambda _i, e=entity, c=combo: self._passability(e, c.currentData())
        )
        section.add_row(
            "Player",
            combo,
            help_text="Passable: the player walks through it. Blocks at its feet: a solid box "
            "at its foot (size it in Collider 2D below). Blocks its whole picture: nothing of "
            "it can be walked into (like an RPG Maker event set to Same as characters).",
            key="passability",
        )
        if passability(entity) == "picture":
            again = QPushButton("Measure the Picture Again")
            again.clicked.connect(lambda _c=False, e=entity: self._passability(e, "picture"))
            section.add_row(
                "",
                again,
                help_text="After changing its picture: the box covers the new one.",
            )
        image = passability_preview(self.document.project, project_root(self.document), entity)
        if image is not None:
            from .image_tools import _pixmap

            preview = QLabel()
            preview.setObjectName("PassabilityPreview")
            preview.setPixmap(_pixmap(image, 180))
            section.add_row(
                "Preview",
                preview,
                help_text="Red: what blocks the player. Blue cross: where it stands.",
            )
        self._passability_combo = combo
        return section

    def _passability(self, entity, mode):
        window = self.window()
        if self._refreshing or not hasattr(window, "edit_passability"):
            return
        ok, error = window.edit_passability(entity, mode)
        self.error.setText("" if ok else "⚠  " + (error or "Invalid value"))

    def _component_section(self, component, fields, *, title=None, selected=False):
        from .record_form import Section

        name = _pretty_type(title or type(component).__name__)
        section = Section(name, hint="" if fields else "No editable fields.", compact=True)
        for f in fields:
            self._field_models[(id(component), f.name)] = f
            widget = self._field_widget(component, f, selected)
            section.add_row(f.label, widget, help_text=f.tooltip or "", key=f.name)
        return section

    def _field_widget(self, component, f, selected):
        from .inspector import inspector_choices
        from .record_form import NumberBox, _wheel_guard

        def commit(value):
            if self._refreshing:
                return
            self._apply(component, f, value, selected)

        choices = inspector_choices(self.document, component, f)
        if choices is not None:
            combo = QComboBox()
            _wheel_guard(combo)
            for label, value in choices:
                combo.addItem(label, value)
            current = combo.findData(f.value if f.choices else str(f.value))
            combo.setCurrentIndex(max(0, current))
            combo.setEnabled(f.editable)
            combo.currentIndexChanged.connect(lambda _i, c=combo: commit(c.currentData()))
            return combo
        if f.value_type is bool:
            box = QCheckBox("Yes")
            box.setChecked(bool(f.value))
            box.setEnabled(f.editable)
            box.toggled.connect(lambda on: commit(bool(on)))
            return box
        if f.value_type in (int, float) and isinstance(f.value, (int, float)):
            box = NumberBox(f.value, integer=f.value_type is int)
            if f.minimum is not None or f.maximum is not None:
                box.setRange(
                    float(f.minimum) if f.minimum is not None else -1e9,
                    float(f.maximum) if f.maximum is not None else 1e9,
                )
                box.set_value(f.value)
            box.setEnabled(f.editable)
            box.editingFinished.connect(lambda b=box: commit(b.number()))
            return box
        edit = QLineEdit(str(f.value))
        edit.setEnabled(f.editable)
        edit.editingFinished.connect(lambda e=edit: commit(e.text()))
        return edit

    def _apply(self, component, f, value, selected):
        window = self.window()
        if selected and hasattr(window, "edit_selected_component_field"):
            ok, error = window.edit_selected_component_field(f.name, value)
        elif hasattr(window, "edit_component_field"):
            ok, error = window.edit_component_field(component, f.name, value)
        else:
            return
        self.error.setText("" if ok else "⚠  " + (error or "Invalid value"))

    def _entity(self, entity, **changes):
        window = self.window()
        if hasattr(window, "edit_entity"):
            window.edit_entity(entity, **changes)


def _pretty_type(name):
    """``SpriteRenderer2D`` -> "Sprite Renderer 2D", ``ActorLinkComponent`` -> "Actor Link"."""
    import re

    name = re.sub(r"Component$", "", str(name))
    words = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+[A-Z]?", name)
    return " ".join(words) or str(name)


class SceneViewportPlaceholder(QWidget):
    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for editor UI")
        super().__init__(parent)
        layout = QVBoxLayout(self)
        label = QLabel("Scene View")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
