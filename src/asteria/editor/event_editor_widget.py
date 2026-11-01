"""Entity Events: the people and objects of the scene on the left (how many events each has);
on the right the picked one's events - when each starts (in words), the commands it runs, the
switches it waits for - and its commands as a coloured list, as RPG Maker shows an event."""

try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import (
        QComboBox,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QSplitter,
        QVBoxLayout,
        QWidget,
    )

    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False

    class QWidget:
        pass


from html import escape

from .event_editing import describe_instruction
from .i18n import translate

OLD_EMPTY_HINT = "Select an Entity to edit events"
EMPTY_HINT = "Pick a person or object on the left (or in the Scene) to see and edit its events."

# when an event starts, in words; the value is the binding's trigger
TRIGGERS = (
    ("When the player talks to it", "action"),
    ("By itself when the map opens", "autorun"),
    ("Always, in the background", "parallel"),
)
TRIGGER_HELP = {
    "action": "The player faces it and presses the Action key (RPG Maker: Action Button)",
    "autorun": "Starts on its own and holds the player until it ends (RPG Maker: Autorun)",
    "parallel": "Keeps running beside play, the player still moves (RPG Maker: Parallel)",
}
TRIGGER_SHORT = {"action": "When talked to", "autorun": "Autorun", "parallel": "Background"}

# a command's colour by what it does, as RPG Maker colours its event list
COMMAND_COLOURS = {
    "DIALOGUE": "#e6e8ee",
    "CHOICE": "#e6e8ee",
    "SET_SWITCH": "#e8798a",
    "SET_VARIABLE": "#e8798a",
    "JUMP_IF": "#e5b45a",
    "IF_FALSE_SKIP": "#e5b45a",
    "WAIT": "#e5b45a",
    "CALL": "#e5b45a",
    "WORLD": "#5ec4b6",
    "SEQUENCE": "#8aa8ff",
    "MOVE": "#8aa8ff",
    "FACE": "#8aa8ff",
    "ANIMATE": "#8aa8ff",
    "END": "#777a84",
}

ADD_COMMANDS = (
    ("Dialogue", "dialogue", "A line of dialogue, with its speaker and portrait"),
    ("Choice", "choice", "A question with answers the player picks"),
    ("Wait", "wait", "Wait some seconds, or until a switch or variable is set"),
    ("If", "if", "Run the next commands only when a switch or variable says so"),
    ("Switch", "switch", "Turn a switch on or off (remembered in the save)"),
    ("Variable", "variable", "Set a number the game remembers"),
    ("World", "world", "Change the world: give items, start a battle, open a shop…"),
    ("Sequence…", "sequence", "Moves, camera and effects running side by side (a cutscene)"),
)


def command_line(instruction):
    """``(text, colour)`` of a command as the list shows it: ◆ and its words."""
    if instruction.opcode == "END":
        return "◆", COMMAND_COLOURS["END"]
    text = describe_instruction(instruction)
    return f"◆ {text}", COMMAND_COLOURS.get(instruction.opcode, "#e6e8ee")


def condition_words(binding):
    if not binding.conditions:
        return translate("Always")
    parts = []
    for item in binding.conditions:
        condition = getattr(item, "condition", item)
        name = getattr(condition, "name", str(condition))
        value = getattr(condition, "value", True)
        operator = getattr(condition, "operator", "==")
        if value is True and operator == "==":
            parts.append(f"{name} is ON")
        elif value is False and operator == "==":
            parts.append(f"{name} is OFF")
        else:
            parts.append(f"{name} {operator} {value}")
    return translate(" and ".join(parts))


def command_preview(instruction):
    """Rich text for the panel beside the list: a line of dialogue as its message window, any
    other command as its settings."""
    if instruction is None:
        return f"<p style='color:#8b8e98'>{translate('Click a command to see it here.')}</p>"
    a = instruction.args
    if instruction.opcode == "DIALOGUE":
        speaker = escape(str(a.get("speaker", "")).strip())
        text = escape(str(a.get("text", ""))).replace("\n", "<br>")
        portrait = str(a.get("portrait_asset_id", "") or "").rsplit("/", 1)[-1]
        rows = f"<b style='color:#f0c674'>{speaker}</b><br>" if speaker else ""
        rows += f"<span style='font-size:14px'>{text}</span>"
        if portrait:
            word = translate("Portrait")
            rows += f"<br><span style='color:#8b8e98'>{word}: {escape(portrait)}</span>"
        return (
            "<table width='100%' cellpadding='10' style='background:#1b2133;"
            f"border:1px solid #4a5578'><tr><td>{rows}</td></tr></table>"
        )
    title = escape(describe_instruction(instruction).split("  ")[0])
    values = dict(a)
    if instruction.opcode == "WORLD":
        title = "World · " + escape(str(a.get("command", "")).replace("_", " ").title())
        values = {k: v for k, v in a.items() if k != "command"}
        values.update(values.pop("args", None) or {})
    rows = "".join(
        f"<tr><td style='color:#8b8e98;padding-right:12px'>{escape(str(k))}</td>"
        f"<td>{escape(str(v))}</td></tr>"
        for k, v in values.items()
        if not isinstance(v, (list, dict))
    )
    nested = [k for k, v in values.items() if isinstance(v, (list, dict))]
    also = translate("Also")
    more = f"<p style='color:#8b8e98'>{also}: {escape(', '.join(nested))}</p>" if nested else ""
    return f"<p><b>{title}</b></p><table>{rows}</table>{more}"


class EventEditorWidget(QWidget):
    if QT_AVAILABLE:
        bindingRequested = Signal()
        bindingChanged = Signal(str, str)
        addCommandRequested = Signal(str)
        addConditionRequested = Signal()
        removeCommandRequested = Signal(int)
        moveCommandRequested = Signal(int, int)
        editCommandRequested = Signal(int)
        entityPicked = Signal(object)

    def __init__(self, parent=None):
        if not QT_AVAILABLE:
            raise RuntimeError("PySide6 is required for Event Editor UI")
        super().__init__(parent)
        self._refreshing = False
        self._binding_ids = []
        self._program_ids = []
        self._entity_id = None

        # left: the people and objects of the scene
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 0, 0, 0)
        heading = QLabel("People & Objects")
        heading.setObjectName("AuthoringSidebarTitle")
        lv.addWidget(heading)
        self.picker = QListWidget()
        self.picker.setObjectName("EventEntityPicker")
        self.picker.setToolTip("Click to see and edit its events")
        self.picker.itemClicked.connect(self._picked)
        self.picker.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.picker.setTextElideMode(Qt.ElideRight)
        lv.addWidget(self.picker, 1)

        # right: the picked one's events
        self.title = QLabel(EMPTY_HINT)
        self.title.setObjectName("AuthoringSidebarTitle")
        self.title.setProperty("presentationHeading", True)
        self.title.setWordWrap(True)

        self.binding_combo = QComboBox()
        self.binding_combo.setToolTip("Each event of this person or object (RPG Maker: a page)")
        self.binding_combo.currentIndexChanged.connect(self._binding_selected)
        self.new_binding_button = QPushButton("+ New Event")
        self.new_binding_button.setToolTip("Another event: started another way, or on a switch")
        self.new_binding_button.clicked.connect(lambda: self.bindingRequested.emit())
        header = QHBoxLayout()
        event_label = QLabel("Event")
        header.addWidget(event_label)
        header.addWidget(self.binding_combo, 1)
        header.addWidget(self.new_binding_button)

        self.trigger_combo = QComboBox()
        for words, value in TRIGGERS:
            self.trigger_combo.addItem(words, value)
            self.trigger_combo.setItemData(
                self.trigger_combo.count() - 1, TRIGGER_HELP[value], Qt.ToolTipRole
            )
        self.trigger_combo.currentIndexChanged.connect(
            lambda _i: self._emit_binding_change("trigger", self.trigger_combo.currentData())
        )
        self.program_combo = QComboBox()
        self.program_combo.setToolTip(
            "The command list this event runs; several events may share one"
        )
        self.program_combo.currentIndexChanged.connect(self._program_changed)
        self.conditions = QLabel("Always")
        self.conditions.setWordWrap(True)
        add_condition = QPushButton("+ Condition")
        add_condition.setToolTip("Run only while a switch is on (RPG Maker: page conditions)")
        add_condition.clicked.connect(lambda: self.addConditionRequested.emit())

        card = QFrame()
        card.setObjectName("EventSettingsCard")
        grid = QGridLayout(card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        for column, (caption, widget) in enumerate(
            (("Starts", self.trigger_combo), ("Runs", self.program_combo))
        ):
            label = QLabel(caption)
            label.setObjectName("MutedLabel")
            grid.addWidget(label, 0, column)
            grid.addWidget(widget, 1, column)
        only = QLabel("Only when")
        only.setObjectName("MutedLabel")
        grid.addWidget(only, 0, 2)
        condition_row = QHBoxLayout()
        condition_row.addWidget(self.conditions, 1)
        condition_row.addWidget(add_condition)
        grid.addLayout(condition_row, 1, 2)
        for column in range(3):
            grid.setColumnStretch(column, 1)

        self.commands = QListWidget()
        self.commands.setObjectName("EventCommandList")
        self.commands.setToolTip("Double-click a command to change it")
        self.commands.itemDoubleClicked.connect(
            lambda _item: self.editCommandRequested.emit(self.commands.currentRow())
        )
        self.commands.currentItemChanged.connect(self._preview)
        self.preview = QLabel()
        self.preview.setObjectName("EventCommandPreview")
        self.preview.setWordWrap(True)
        self.preview.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.preview.setTextFormat(Qt.RichText)
        preview_box = QFrame()
        preview_box.setObjectName("EventSettingsCard")
        pv = QVBoxLayout(preview_box)
        pv.setContentsMargins(12, 10, 12, 10)
        preview_title = QLabel("Selected command")
        preview_title.setObjectName("MutedLabel")
        pv.addWidget(preview_title)
        pv.addWidget(self.preview, 1)
        self.command_split = QSplitter()
        self.command_split.addWidget(self.commands)
        self.command_split.addWidget(preview_box)
        self.command_split.setStretchFactor(0, 3)
        self.command_split.setStretchFactor(1, 2)

        buttons = QHBoxLayout()
        add_label = QLabel("Add")
        add_label.setObjectName("MutedLabel")
        buttons.addWidget(add_label)
        for text, kind, tip in ADD_COMMANDS:
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(lambda checked=False, k=kind: self.addCommandRequested.emit(k))
            buttons.addWidget(b)
        buttons.addStretch(1)
        up = QPushButton("↑")
        up.setToolTip("Move the command up")
        down = QPushButton("↓")
        down.setToolTip("Move the command down")
        delete = QPushButton("Delete")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        delete.clicked.connect(self._remove)
        for b in (up, down, delete):
            buttons.addWidget(b)

        self.body = QWidget()
        body = QVBoxLayout(self.body)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(10)
        body.addLayout(header)
        body.addWidget(card)
        commands_heading = QLabel("Commands")
        commands_heading.setProperty("presentationHeading", True)
        body.addWidget(commands_heading)
        body.addWidget(self.command_split, 1)
        body.addLayout(buttons)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(0, 0, 0, 0)
        rv.setSpacing(10)
        rv.addWidget(self.title)
        rv.addWidget(self.body, 1)

        split = QSplitter()
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(1, 1)
        split.setSizes([260, 900])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(split)

        self.show_empty(EMPTY_HINT)

    def _fill_picker(self, candidates):
        """``candidates``: ``(entity, event count)``, those with events first."""
        self.picker.blockSignals(True)
        self.picker.clear()
        ordered = sorted(candidates, key=lambda pair: (-pair[1], pair[0].name.lower()))
        for entity, count in ordered:
            events = f"{count} event{'s' if count != 1 else ''}" if count else "no events yet"
            item = QListWidgetItem(translate(f"{entity.name}   ·   {events}"))
            item.setData(Qt.UserRole, entity)
            if not count:
                item.setForeground(QColor("#8b8e98"))
            self.picker.addItem(item)
            if entity.id == self._entity_id:
                self.picker.setCurrentItem(item)
        self.picker.blockSignals(False)

    def show_empty(self, message, candidates=()):
        """Nothing picked: the list on the left; the editing part greyed until a pick."""
        self._refreshing = True
        self._entity_id = None
        try:
            self._fill_picker(candidates)
            self.body.setEnabled(False)
            self.title.setText(EMPTY_HINT if message == OLD_EMPTY_HINT else message)
            self.binding_combo.clear()
            self.program_combo.clear()
            self.commands.clear()
            self._preview()
            self.conditions.setText("—")
            self._binding_ids = []
            self._program_ids = []
        finally:
            self._refreshing = False

    def set_entity_context(self, entity, bindings, registry, candidates=()):
        self._refreshing = True
        try:
            self._entity_id = entity.id
            if candidates:
                self._fill_picker(candidates)
            self.body.setEnabled(True)
            self.title.setText(f"Events — {entity.name}")
            entity_bindings = list(bindings.for_entity(entity.id))
            self._binding_ids = [b.binding_id for b in entity_bindings]
            self.binding_combo.clear()
            for index, b in enumerate(entity_bindings, 1):
                program = registry.get(b.program_id)
                name = (program.name if program is not None else "") or b.program_id
                when = TRIGGER_SHORT.get(b.trigger.value, b.trigger.value)
                self.binding_combo.addItem(f"{index} · {translate(when)} · {name}")

            self._program_ids = list(registry.ids())
            self.program_combo.clear()
            for pid in self._program_ids:
                program = registry.require(pid)
                self.program_combo.addItem(program.name or pid)
                self.program_combo.setItemData(self.program_combo.count() - 1, pid, Qt.ToolTipRole)

            if entity_bindings:
                self._show_binding(entity_bindings[0], registry)
            else:
                self.commands.clear()
                self.commands.addItem("No event yet: + New Event makes one")
                self.conditions.setText("Always")
        finally:
            self._refreshing = False

    def _picked(self, item):
        self.entityPicked.emit(item.data(Qt.UserRole))

    def _show_binding(self, binding, registry):
        index = self.trigger_combo.findData(binding.trigger.value)
        if index >= 0:
            self.trigger_combo.setCurrentIndex(index)
        if binding.program_id in self._program_ids:
            self.program_combo.setCurrentIndex(self._program_ids.index(binding.program_id))
        self.conditions.setText(condition_words(binding))
        self.commands.clear()
        program = registry.get(binding.program_id)
        if program is not None:
            for instruction in program.instructions:
                text, colour = command_line(instruction)
                item = QListWidgetItem(text)
                item.setForeground(QColor(colour))
                item.setData(Qt.UserRole, instruction)
                self.commands.addItem(item)
        self._preview()

    def _preview(self, *_args):
        item = self.commands.currentItem()
        instruction = item.data(Qt.UserRole) if item is not None else None
        self.preview.setText(command_preview(instruction))

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
        if row >= 0:
            self.moveCommandRequested.emit(row, delta)
