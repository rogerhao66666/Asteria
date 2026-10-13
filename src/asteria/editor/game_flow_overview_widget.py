from __future__ import annotations

try:
    from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QListWidget, QVBoxLayout, QWidget

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass


from asteria.runtime.components2d import Interaction2DComponent

from .event_editing import bindings_for_scene


class GameFlowOverviewWidget(QWidget):
    """Read/write context surface for canonical scene interaction flow.

    Detailed event command editing remains in EventEditorWidget; component fields
    remain in the canonical Inspector. This page makes the end-to-end chain visible
    and navigable rather than inventing another flow graph model.
    """

    def __init__(self, document, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.document = document
        self.scene_combo = QComboBox()
        self.entity_list = QListWidget()
        self.binding = QLabel("—")
        self.program = QLabel("—")
        self.interaction = QLabel("—")
        self.scene_combo.currentIndexChanged.connect(self._scene_changed)
        self.entity_list.currentRowChanged.connect(self._entity_changed)
        form = QFormLayout()
        form.addRow("Binding", self.binding)
        form.addRow("Program", self.program)
        form.addRow("Interaction", self.interaction)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Field / Interaction / Game Flow"))
        layout.addWidget(self.scene_combo)
        layout.addWidget(self.entity_list, 1)
        layout.addLayout(form)
        self._scenes = []
        self._entities = []
        self.refresh()

    def refresh(self):
        p = self.document.project
        self.scene_combo.blockSignals(True)
        self.scene_combo.clear()
        self._scenes = list(p.scenes()) if p else []
        for s in self._scenes:
            self.scene_combo.addItem(s.name, s.id)
        self.scene_combo.blockSignals(False)
        self._scene_changed(self.scene_combo.currentIndex())

    def _scene_changed(self, index):
        self.entity_list.clear()
        self._entities = []
        if not 0 <= index < len(self._scenes):
            return
        scene = self._scenes[index]
        self._entities = [
            e
            for e in scene.entities()
            if e.try_get(Interaction2DComponent) is not None
            or bindings_for_scene(self.document.project, scene).for_entity(e.id)
        ]
        for e in self._entities:
            self.entity_list.addItem(e.name)
        if self._entities:
            self.entity_list.setCurrentRow(0)
        else:
            self._show(None)

    def _entity_changed(self, row):
        self._show(self._entities[row] if 0 <= row < len(self._entities) else None)

    def _show(self, entity):
        if entity is None:
            self.binding.setText("—")
            self.program.setText("—")
            self.interaction.setText("—")
            return
        scene = entity.scene
        bs = bindings_for_scene(self.document.project, scene).for_entity(entity.id)
        b = bs[0] if bs else None
        c = entity.try_get(Interaction2DComponent)
        self.binding.setText(b.binding_id if b else "—")
        self.program.setText(b.program_id if b else (c.event_program_id if c else "—"))
        self.interaction.setText(
            f"range={c.range:g}, facing={'yes' if c.require_facing else 'no'}"
            if c
            else "No Interaction2D"
        )
