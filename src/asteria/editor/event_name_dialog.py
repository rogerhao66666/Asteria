"""Pick a switch or a variable: from the ones the events already use, or a new one with a click.

``SwitchDialog`` is a name and on / off (Set Switch, If, a condition); ``VariableDialog`` is a name
and what it becomes - a number, words, yes / no or a copy of another variable.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QStackedWidget,
    QVBoxLayout,
)

from .event_flow_authoring import EventFlowAuthoring
from .i18n import translate
from .record_vocabulary import words
from .ui_fit import ValueCombo
from .world_command_form import PlainNumber


def name_picker(document, source, name=""):
    """A drop-down of the names ``source`` ("switch" / "variable") has, ending with one that
    makes a new name; ``name``, else the first, else a new one is picked. It can be typed over."""
    combo = ValueCombo()
    combo.setEditable(True)
    combo.setProperty("i18n_choices", True)
    combo.offer_new(f"New {source.title()}", f"new_{source}")
    used = EventFlowAuthoring(document).names_used(source) if document is not None else ()
    combo.set_choices([(used_name, words(used_name)) for used_name in used])
    if name:
        combo.setCurrentText(name)
    elif used:
        combo.setCurrentIndex(0)
    else:
        combo.setCurrentIndex(combo.findData(ValueCombo.NEW))
    return combo


class _NameDialog(QDialog):
    def __init__(self, title, parent):
        super().__init__(parent)
        self.setWindowTitle(translate(title))
        self.setMinimumWidth(340)
        self.form = QFormLayout()
        self.form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(buttons)

    def name(self):
        return self.picker.currentText().strip()

    def accept(self):
        if self.name():
            super().accept()


class SwitchDialog(_NameDialog):
    def __init__(self, document, title="Set Switch", parent=None, *, name="", value=True):
        super().__init__(title, parent)
        self.picker = name_picker(document, "switch", name)
        self.state = ValueCombo()
        self.state.set_choices((("on", "Turned on"), ("off", "Turned off")))
        self.state.setCurrentText("on" if value else "off")
        self.form.addRow(translate("Switch"), self.picker)
        word = "Set To" if title == "Set Switch" else "Is"
        self.form.addRow(translate(word), self.state)

    def value(self):
        return self.state.currentText() == "on"


class VariableDialog(_NameDialog):
    """What the variable becomes; a value of a kind the form doesn't have (a list) is kept."""

    def __init__(self, document, parent=None, *, args=None):
        super().__init__("Set Variable", parent)
        args = dict(args or {})
        self._rest = {k: v for k, v in args.items() if k not in ("name", "value", "from_variable")}
        self._kept = None
        self.picker = name_picker(document, "variable", str(args.get("name", "")))
        self.kind = ValueCombo()
        self.kind.set_choices(
            (
                ("number", "A number"),
                ("text", "Words"),
                ("flag", "Yes or no"),
                ("copy", "Another variable's value"),
            )
        )
        self.number = PlainNumber()
        self.number.setRange(-1_000_000_000.0, 1_000_000_000.0)
        self.number.setDecimals(3)
        self.text = QLineEdit()
        self.flag = ValueCombo()
        self.flag.set_choices((("yes", "Yes"), ("no", "No")))
        self.source = name_picker(document, "variable", str(args.get("from_variable", "")))
        self.values = QStackedWidget()
        for widget in (self.number, self.text, self.flag, self.source):
            self.values.addWidget(widget)
        self.kind.currentIndexChanged.connect(self.values.setCurrentIndex)
        self.form.addRow(translate("Variable"), self.picker)
        self.form.addRow(translate("Becomes"), self.kind)
        self.form.addRow(translate("Value"), self.values)
        self._load(args)

    def _load(self, args):
        value = args.get("value", 0)
        if "from_variable" in args:
            self.kind.setCurrentText("copy")
        elif isinstance(value, bool):
            self.kind.setCurrentText("flag")
            self.flag.setCurrentText("yes" if value else "no")
        elif isinstance(value, (int, float)) and round(value, 3) == value:
            self.number.setValue(float(value))
        elif isinstance(value, str):
            self.kind.setCurrentText("text")
            self.text.setText(value)
        else:
            self._kept = value

    def result_args(self):
        args = dict(self._rest, name=self.name())
        kind = self.kind.currentText()
        if kind == "copy":
            args["from_variable"] = self.source.currentText().strip()
        elif self._kept is not None:
            args["value"] = self._kept
        elif kind == "text":
            args["value"] = self.text.text()
        elif kind == "flag":
            args["value"] = self.flag.currentText() == "yes"
        else:
            number = self.number.value()
            args["value"] = int(number) if number.is_integer() else number
        return args


__all__ = ["SwitchDialog", "VariableDialog", "name_picker"]
