try:
    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass


from .event_editing import describe_instruction

OLD_EMPTY_HINT = "Select an Entity to edit events"
EMPTY_HINT = (
    "Pick a person or object in the Scene, or from the list below, to see and edit what "
    "happens when the player talks to it, touches it or enters the map."
)


class EventEditorWidget(QWidget):
    if QT_AVAILABLE:
        bindingRequested = Signal()
        bindingChanged = Signal(str, str)
        addCommandRequested = Signal(str)
        addConditionRequested = Signal()
        removeCommandRequested = Signal(int)
        moveCommandRequested = Signal(int, int)
        editCommandRequested = Signal(int)

    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for Event Editor UI")
        super().__init__(parent)
        self._refreshing = False
        self._binding_ids = []
        self._program_ids = []

        self.title = QLabel("Select an Entity to edit events")
        self.title.setObjectName("AuthoringSidebarTitle")
        self.title.setProperty("presentationHeading", True)
        self.title.setWordWrap(True)

        self.binding_combo = QComboBox()
        self.binding_combo.currentIndexChanged.connect(self._binding_selected)
        self.new_binding_button = QPushButton("+ Event")
        self.new_binding_button.clicked.connect(lambda: self.bindingRequested.emit())

        header = QHBoxLayout()
        header.addWidget(self.binding_combo, 1)
        header.addWidget(self.new_binding_button)

        self.trigger_combo = QComboBox()
        self.trigger_combo.addItems(["Action", "Autorun", "Parallel"])
        self.trigger_combo.currentTextChanged.connect(
            lambda value: self._emit_binding_change("trigger", value.lower())
        )

        self.program_combo = QComboBox()
        self.program_combo.currentIndexChanged.connect(self._program_changed)

        form = QFormLayout()
        form.addRow("Trigger", self.trigger_combo)
        form.addRow("Program", self.program_combo)

        condition_row = QHBoxLayout()
        self.conditions = QLabel("Conditions: Always")
        self.conditions.setObjectName("MutedLabel")
        self.conditions.setWordWrap(True)
        add_condition = QPushButton("+ Condition")
        add_condition.clicked.connect(lambda: self.addConditionRequested.emit())
        condition_row.addWidget(self.conditions, 1)
        condition_row.addWidget(add_condition)

        self.commands = QListWidget()
        self.commands.itemDoubleClicked.connect(
            lambda _item: self.editCommandRequested.emit(self.commands.currentRow())
        )

        buttons = QHBoxLayout()
        for text, kind in [
            ("Dialogue", "dialogue"),
            ("Choice", "choice"),
            ("Wait", "wait"),
            ("If", "if"),
            ("Switch", "switch"),
            ("Variable", "variable"),
            ("World", "world"),
            ("Sequence…", "sequence"),
        ]:
            b = QPushButton(text)
            b.clicked.connect(lambda checked=False, k=kind: self.addCommandRequested.emit(k))
            buttons.addWidget(b)

        ordering = QHBoxLayout()
        up = QPushButton("↑")
        down = QPushButton("↓")
        delete = QPushButton("Delete")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        delete.clicked.connect(self._remove)
        ordering.addWidget(up)
        ordering.addWidget(down)
        ordering.addStretch(1)
        ordering.addWidget(delete)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(self.title)
        # everything below the title: greyed out until a person or object is picked
        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        body.addLayout(header)
        body.addLayout(form)
        body.addLayout(condition_row)
        commands_heading = QLabel("Commands")
        commands_heading.setProperty("presentationHeading", True)
        body.addWidget(commands_heading)
        body.addWidget(self.commands, 1)
        body.addLayout(buttons)
        body.addLayout(ordering)
        layout.addWidget(self.body, 1)

        self.show_empty(EMPTY_HINT)

    def show_empty(self, message):
        self._refreshing = True
        self.body.setEnabled(False)
        try:
            self.title.setText(EMPTY_HINT if message == OLD_EMPTY_HINT else message)
            self.binding_combo.clear()
            self.program_combo.clear()
            self.commands.clear()
            self.conditions.setText("Conditions: —")
            self._binding_ids = []
            self._program_ids = []
        finally:
            self._refreshing = False

    def set_entity_context(self, entity, bindings, registry):
        self._refreshing = True
        try:
            self.body.setEnabled(True)
            self.title.setText(f"Events — {entity.name}")
            entity_bindings = list(bindings.for_entity(entity.id))
            self._binding_ids = [b.binding_id for b in entity_bindings]
            self.binding_combo.clear()
            for b in entity_bindings:
                self.binding_combo.addItem(f"{b.trigger.value.title()} · {b.program_id}")

            self._program_ids = list(registry.ids())
            self.program_combo.clear()
            for pid in self._program_ids:
                program = registry.require(pid)
                self.program_combo.addItem(program.name or pid)

            if entity_bindings:
                self._show_binding(entity_bindings[0], registry)
            else:
                self.commands.clear()
                self.conditions.setText("Conditions: Always")
        finally:
            self._refreshing = False

    def _show_binding(self, binding, registry):
        self.trigger_combo.setCurrentText(binding.trigger.value.title())
        if binding.program_id in self._program_ids:
            self.program_combo.setCurrentIndex(self._program_ids.index(binding.program_id))
        self.conditions.setText(
            f"Conditions: {len(binding.conditions)}"
            if binding.conditions
            else "Conditions: Always"
        )
        self.commands.clear()
        program = registry.get(binding.program_id)
        if program is not None:
            for instruction in program.instructions:
                self.commands.addItem(describe_instruction(instruction))

    def selected_binding_id(self):
        i = self.binding_combo.currentIndex()
        return self._binding_ids[i] if 0 <= i < len(self._binding_ids) else None

    def selected_command_index(self):
        return self.commands.currentRow()

    def _binding_selected(self, index):
        if not self._refreshing and 0 <= index < len(self._binding_ids):
            self._emit_binding_change("select", self._binding_ids[index])

    def _program_changed(self, index):
        if not self._refreshing and 0 <= index < len(self._program_ids):
            self._emit_binding_change("program_id", self._program_ids[index])

    def _emit_binding_change(self, field, value):
        if not self._refreshing:
            self.bindingChanged.emit(field, value)

    def _remove(self):
        row = self.selected_command_index()
        if row >= 0:
            self.removeCommandRequested.emit(row)

    def _move(self, delta):
        row = self.selected_command_index()
        if row < 0:
            return
        target = row + delta
        if 0 <= target < self.commands.count():
            self.moveCommandRequested.emit(row, target)
