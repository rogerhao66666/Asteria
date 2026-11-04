"""The Choice command's editor: the prompt, the options and their values, the variable that
gets the answer, the option the pointer starts on, what the cancel key answers, how many
options stand side by side, where a game's own choice box stands and the world commands run
when the pointer comes to an option."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .i18n import translate
from .ui_fit import ValueCombo

DEFAULT_OPTIONS = ({"text": "Option 1", "value": 1}, {"text": "Option 2", "value": 2})


def _value(text):
    """A written value: a whole number, a number, true / false, else the text."""
    text = str(text).strip()
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return text


class ChoiceCommandDialog(QDialog):
    def __init__(self, args=None, parent=None, *, document=None):
        from .event_name_dialog import name_picker

        super().__init__(parent)
        self.setWindowTitle(translate("Choice"))
        self.document = document
        self._old = dict(args or {})
        self.choices = [dict(c) for c in self._old.get("choices") or DEFAULT_OPTIONS]
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.prompt = QPlainTextEdit(str(self._old.get("prompt", "")))
        self.prompt.setFixedHeight(60)
        self.options = QTableWidget(0, 2)
        self.options.setHorizontalHeaderLabels(
            [translate("Option Text"), translate("Answer Value")]
        )
        self.options.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.options.verticalHeader().setVisible(False)
        self.options.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.options.setSelectionMode(QAbstractItemView.SingleSelection)
        self.options.setFixedHeight(140)
        self.options.itemChanged.connect(self._option_edited)
        self.options.currentCellChanged.connect(lambda *_a: self._show_hover())
        self.add_option_button = QPushButton(translate("+ Add Option"))
        self.remove_option_button = QPushButton(translate("Remove Option"))
        self.add_option_button.clicked.connect(self.add_option)
        self.remove_option_button.clicked.connect(self.remove_option)
        option_buttons = QHBoxLayout()
        option_buttons.addWidget(self.add_option_button)
        option_buttons.addWidget(self.remove_option_button)
        option_buttons.addStretch(1)
        self.variable = name_picker(
            document, "variable", str(self._old.get("variable_name", "choice"))
        )
        self.cursor = QSpinBox()
        self.cursor.setRange(1, 99)
        self.cursor.setValue(int(self._old.get("cursor", 0) or 0) + 1)
        self.cancel = ValueCombo()
        self.cancel.setEditable(True)  # any value: the game reads it, not only an option's
        self.cancel.setProperty("i18n_choices", True)
        self.columns = QSpinBox()
        self.columns.setRange(1, 8)
        self.columns.setValue(int(self._old.get("columns", 1) or 1))
        self.columns.setToolTip("Options side by side: up / down move a whole row")
        self.hover_heading = QLabel()
        self.hover = QListWidget()
        self.hover.setFixedHeight(76)
        self.hover.itemDoubleClicked.connect(lambda _i: self.edit_hover())
        add_hover = QPushButton(translate("+ Add Command"))
        edit_hover = QPushButton(translate("Edit"))
        remove_hover = QPushButton(translate("Remove"))
        add_hover.clicked.connect(lambda: self.add_hover())
        edit_hover.clicked.connect(lambda: self.edit_hover())
        remove_hover.clicked.connect(self.remove_hover)
        hover_buttons = QHBoxLayout()
        for button in (add_hover, edit_hover, remove_hover):
            hover_buttons.addWidget(button)
        hover_buttons.addStretch(1)
        box = self._old.get("box_at")
        self.box_tick = QCheckBox(translate("Its own place"))
        self.box_x, self.box_y = QSpinBox(), QSpinBox()
        for spin, value in zip((self.box_x, self.box_y), box or (0, 0), strict=False):
            spin.setRange(-100_000, 100_000)
            spin.setValue(int(value))
            spin.setEnabled(bool(box))
            self.box_tick.toggled.connect(spin.setEnabled)
        self.box_tick.setChecked(bool(box))
        place = QHBoxLayout()
        place.addWidget(self.box_tick)
        place.addWidget(QLabel("X"))
        place.addWidget(self.box_x)
        place.addWidget(QLabel("Y"))
        place.addWidget(self.box_y)
        place.addStretch(1)
        form.addRow(translate("Prompt"), self.prompt)
        form.addRow(translate("Options"), self.options)
        form.addRow("", _row(option_buttons))
        form.addRow(translate("Answer Variable"), self.variable)
        form.addRow(translate("Start On Option"), self.cursor)
        form.addRow(translate("Cancel Key Answers"), self.cancel)
        form.addRow(translate("Columns"), self.columns)
        form.addRow(self.hover_heading)
        form.addRow(self.hover)
        form.addRow(_row(hover_buttons))
        form.addRow(translate("Choice Box Position"), _row(place))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self._show_options()
        self._fill_cancel("" if "cancel" not in self._old else str(self._old["cancel"]))
        self.options.selectRow(0)
        self._show_hover()

    # -- options ----------------------------------------------------------------------------------
    def _show_options(self):
        self.options.blockSignals(True)
        self.options.setRowCount(len(self.choices))
        for row, choice in enumerate(self.choices):
            self.options.setItem(row, 0, QTableWidgetItem(str(choice.get("text", ""))))
            self.options.setItem(row, 1, QTableWidgetItem(str(choice.get("value", ""))))
        self.options.blockSignals(False)
        self.remove_option_button.setEnabled(len(self.choices) > 1)

    def _option_edited(self, item):
        choice = self.choices[item.row()]
        if item.column() == 0:
            if item.text() != choice.get("text"):
                choice.pop("text_key", None)  # its translation was of the old words
            choice["text"] = item.text()
        else:
            choice["value"] = _value(item.text())
            self._fill_cancel(self.cancel.currentText())
        self._show_hover()

    def add_option(self):
        number = len(self.choices) + 1
        self.choices.append({"text": f"Option {number}", "value": number})
        self._show_options()
        self.options.selectRow(number - 1)
        self._fill_cancel(self.cancel.currentText())

    def remove_option(self):
        row = self.options.currentRow()
        if 0 <= row < len(self.choices) and len(self.choices) > 1:
            del self.choices[row]
            self._show_options()
            self.options.selectRow(min(row, len(self.choices) - 1))
            self._fill_cancel(self.cancel.currentText())

    def _fill_cancel(self, held):
        pairs = [
            (str(c.get("value", "")), f"{c.get('text', '')} ({c.get('value', '')})")
            for c in self.choices
        ]
        self.cancel.set_choices(pairs, none=translate("Does nothing"))
        self.cancel.setCurrentText(held)

    # -- what runs when the pointer comes to the option -------------------------------------------
    def _choice(self):
        row = self.options.currentRow()
        return self.choices[row] if 0 <= row < len(self.choices) else None

    def _show_hover(self):
        from asteria.events import EventInstruction

        from .event_editing import describe_instruction
        from .world_command_form import record_names

        names = record_names(self.document) if self.document is not None else None
        choice = self._choice()
        self.hover.clear()
        text = str(choice.get("text", "")) if choice else ""
        self.hover_heading.setText(f"{translate('When The Pointer Comes To')}: {text}")
        for hover in (choice or {}).get("hover") or ():
            said = describe_instruction(EventInstruction("WORLD", hover), names)
            self.hover.addItem(said.split("  ", 1)[-1])

    def _world_dialog(self, command="SHOW_POPUP", args=None):
        """The command picked, or None (tests replace this)."""
        from .world_command_form import WorldCommandDialog

        dialog = WorldCommandDialog(self.document, self, command=command, args=args)
        if dialog.exec() != QDialog.Accepted:
            return None
        return {"command": dialog.command_name(), "args": dialog.result_args()}

    def add_hover(self):
        choice = self._choice()
        command = self._world_dialog() if choice is not None else None
        if command is not None:
            choice.setdefault("hover", []).append(command)
            self._show_hover()

    def edit_hover(self):
        choice, row = self._choice(), self.hover.currentRow()
        if choice is None or row < 0:
            return
        old = choice["hover"][row]
        command = self._world_dialog(old.get("command", "SHOW_POPUP"), old.get("args"))
        if command is not None:
            choice["hover"][row] = command
            self._show_hover()
            self.hover.setCurrentRow(row)

    def remove_hover(self):
        choice, row = self._choice(), self.hover.currentRow()
        if choice is None or row < 0:
            return
        del choice["hover"][row]
        if not choice["hover"]:
            del choice["hover"]
        self._show_hover()

    def result_args(self):
        args = {
            k: v
            for k, v in self._old.items()
            if k
            not in ("prompt", "choices", "variable_name", "cursor", "cancel", "box_at", "columns")
        }
        args["prompt"] = self.prompt.toPlainText()
        args["choices"] = [dict(c) for c in self.choices]
        args["variable_name"] = self.variable.currentText().strip()
        if self.cursor.value() > 1:
            args["cursor"] = self.cursor.value() - 1
        if self.columns.value() > 1:
            args["columns"] = self.columns.value()
        cancel = self.cancel.currentText().strip()
        if cancel:
            args["cancel"] = _value(cancel)
        if self.box_tick.isChecked():
            args["box_at"] = [self.box_x.value(), self.box_y.value()]
        return args


def _row(layout):
    holder = QWidget()
    holder.setAttribute(Qt.WA_TranslucentBackground)
    layout.setContentsMargins(0, 0, 0, 0)
    holder.setLayout(layout)
    return holder


__all__ = ["ChoiceCommandDialog"]
