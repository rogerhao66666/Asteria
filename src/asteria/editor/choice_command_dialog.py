"""The Choice command's editor: the prompt, the options and their values, the variable that
gets the answer, the option the pointer starts on, what the cancel key answers, how many
options stand side by side and where a game's own choice box stands."""

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
        box = self._old.get("box_at")
        self.box_at = QLineEdit("" if not box else f"{box[0]}, {box[1]}")
        self.box_at.setPlaceholderText("Empty = the usual place (x, y in the game's pixels)")
        form.addRow("Prompt", self.prompt)
        form.addRow("Options", self.options)
        form.addRow("Answer Variable", self.variable)
        form.addRow("Start On Option", self.cursor)
        form.addRow("Cancel Key Answers", self.cancel)
        form.addRow("Columns", self.columns)
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


__all__ = ["ChoiceCommandDialog", "options_text", "parse_options"]
