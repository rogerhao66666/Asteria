"""The Choice command's editor: the prompt, the options and their values, the variable that
gets the answer, the option the pointer starts on, what the cancel key answers, how many
options stand side by side, where a game's own choice box stands and the world commands run
when the pointer comes to an option."""

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)


def _value(text):
    """A typed value: a whole number, a number, true / false, else the text."""
    text = str(text).strip()
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    return text


def options_text(choices):
    """``text = value`` lines of a choice's options."""
    return "\n".join(f"{c.get('text', '')} = {c.get('value', '')}" for c in choices or ())


def parse_options(text, old=()):
    """The options of ``text = value`` lines (a line without ``=`` gets its number); an
    option whose text did not change keeps its translation key."""
    keys = {c.get("text"): c.get("text_key") for c in old or () if c.get("text_key")}
    choices = []
    for number, line in enumerate([x for x in str(text).splitlines() if x.strip()], 1):
        label, sep, value = line.partition("=")
        choice = {"text": label.strip(), "value": _value(value) if sep else number}
        if keys.get(choice["text"]):
            choice["text_key"] = keys[choice["text"]]
        choices.append(choice)
    return choices


def hover_text(choices):
    """``number: COMMAND key=value, ...`` lines of the options' hover commands."""
    from .event_editing import format_world_args

    lines = []
    for number, choice in enumerate(choices or (), 1):
        for hover in choice.get("hover") or ():
            args = format_world_args(hover.get("args"))
            lines.append(f"{number}: {hover['command']} {args}".rstrip())
    return "\n".join(lines)


def parse_hover(text, count):
    """``{option index: [{"command", "args"}]}`` of hover lines (option numbers from 1)."""
    from .event_editing import parse_world_args

    found = {}
    for line in [x for x in str(text).splitlines() if x.strip()]:
        number, _sep, rest = line.partition(":")
        index = int(number.strip()) - 1
        if not 0 <= index < count:
            raise ValueError(f"no option {number.strip()}")
        command, _space, args = rest.strip().partition(" ")
        found.setdefault(index, []).append(
            {"command": command.strip().upper(), "args": parse_world_args(args)}
        )
    return found


class ChoiceCommandDialog(QDialog):
    def __init__(self, args=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choice")
        self._old = dict(args or {})
        form = QFormLayout()
        self.prompt = QPlainTextEdit(str(self._old.get("prompt", "")))
        self.prompt.setFixedHeight(60)
        self.options = QPlainTextEdit(
            options_text(self._old.get("choices")) or "Option 1 = 1\nOption 2 = 2"
        )
        self.options.setToolTip("One option a line: the text = the value the variable gets")
        self.variable = QLineEdit(str(self._old.get("variable_name", "choice")))
        self.cursor = QSpinBox()
        self.cursor.setRange(1, 99)
        self.cursor.setValue(int(self._old.get("cursor", 0) or 0) + 1)
        self.cancel = QLineEdit("" if "cancel" not in self._old else str(self._old.get("cancel")))
        self.cancel.setPlaceholderText("Empty = the cancel key does nothing")
        self.columns = QSpinBox()
        self.columns.setRange(1, 8)
        self.columns.setValue(int(self._old.get("columns", 1) or 1))
        self.columns.setToolTip("Options side by side: up / down move a whole row")
        self.hover = QPlainTextEdit(hover_text(self._old.get("choices")))
        self.hover.setFixedHeight(60)
        self.hover.setToolTip(
            "One command a line, run when the pointer comes to that option: "
            "2: MOVE_PICTURE picture_id=girl, x=148, duration=0.25"
        )
        box = self._old.get("box_at")
        self.box_at = QLineEdit("" if not box else f"{box[0]}, {box[1]}")
        self.box_at.setPlaceholderText("Empty = the usual place (x, y in the game's pixels)")
        form.addRow("Prompt", self.prompt)
        form.addRow("Options", self.options)
        form.addRow("Answer Variable", self.variable)
        form.addRow("Start On Option", self.cursor)
        form.addRow("Cancel Key Answers", self.cancel)
        form.addRow("Columns", self.columns)
        form.addRow("When The Pointer Comes To An Option", self.hover)
        form.addRow("Choice Box Position", self.box_at)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def result_args(self):
        args = {
            k: v
            for k, v in self._old.items()
            if k
            not in ("prompt", "choices", "variable_name", "cursor", "cancel", "box_at", "columns")
        }
        args["prompt"] = self.prompt.toPlainText()
        args["choices"] = parse_options(self.options.toPlainText(), self._old.get("choices"))
        for index, commands in parse_hover(self.hover.toPlainText(), len(args["choices"])).items():
            args["choices"][index]["hover"] = commands
        args["variable_name"] = self.variable.text().strip()
        if self.cursor.value() > 1:
            args["cursor"] = self.cursor.value() - 1
        if self.columns.value() > 1:
            args["columns"] = self.columns.value()
        if self.cancel.text().strip():
            args["cancel"] = _value(self.cancel.text())
        parts = [p.strip() for p in self.box_at.text().split(",") if p.strip()]
        if len(parts) == 2:
            args["box_at"] = [int(float(parts[0])), int(float(parts[1]))]
        return args


__all__ = ["ChoiceCommandDialog", "hover_text", "options_text", "parse_hover", "parse_options"]
