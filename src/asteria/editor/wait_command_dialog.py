"""The Wait command's editor: a number of seconds, or until a condition holds (a switch, a
variable, the party (``rpg``), a person (``npc``), the battle, or ``audio``: a fanfare ``me`` /
a sound ``se`` still playing); or until it holds but no longer than the seconds (a title that
moves on by itself unless a key is pressed)."""

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
)

SOURCES = ("switch", "variable", "rpg", "npc", "battle", "audio")
HINTS = {
    "switch": "a switch name (route.<person>.done: that person's route was walked)",
    "variable": "a variable name",
    "rpg": "pets · gold · item:<id> · level:<actor> · quest:<id> · pressed:confirm · saves",
    "npc": "<npc>.visible · <npc>.mood · <npc>.flag.<name>",
    "battle": "running · round · hp_ratio:<member or enemy>",
    "audio": "me (a fanfare plays) · se (a sound plays)",
}
COMPARISONS = ("==", "!=", "<", "<=", ">", ">=")


def _value(text):
    text = str(text).strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


class WaitCommandDialog(QDialog):
    def __init__(self, args=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wait")
        args = dict(args or {})
        until = args.get("until") if isinstance(args.get("until"), dict) else None
        form = QFormLayout()
        self.mode = QComboBox()
        self.mode.addItem("Seconds", "seconds")
        self.mode.addItem("Until a condition holds", "until")
        self.mode.addItem("Until a condition holds, at most the seconds", "until_or_seconds")
        self.mode.setCurrentIndex((2 if "seconds" in args else 1) if until else 0)
        self.seconds = QDoubleSpinBox()
        self.seconds.setRange(0.0, 3600.0)
        self.seconds.setDecimals(3)
        self.seconds.setValue(float(args.get("seconds", 1.0) or 0.0))
        self.source = QComboBox()
        self.source.addItems(SOURCES)
        self.name = QLineEdit()
        self.comparison = QComboBox()
        self.comparison.addItems(COMPARISONS)
        self.value = QLineEdit("true")
        if until:
            self.source.setCurrentText(str(until.get("source", "switch")))
            self.name.setText(str(until.get("name", "")))
            self.comparison.setCurrentText(str(until.get("operator", "==")))
            self.value.setText(str(until.get("value", True)).lower()
                               if isinstance(until.get("value"), bool)
                               else str(until.get("value", "")))  # fmt: skip
        self.source.currentTextChanged.connect(self._hint)
        self._hint(self.source.currentText())
        form.addRow("Wait For", self.mode)
        form.addRow("Seconds", self.seconds)
        form.addRow("Source", self.source)
        form.addRow("Name", self.name)
        form.addRow("Comparison", self.comparison)
        form.addRow("Value", self.value)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _hint(self, source):
        self.name.setPlaceholderText(HINTS.get(source, ""))

    def result_args(self):
        if self.mode.currentData() == "seconds":
            return {"seconds": round(self.seconds.value(), 4)}
        out = {
            "until": {
                "source": self.source.currentText(),
                "name": self.name.text().strip(),
                "operator": self.comparison.currentText(),
                "value": _value(self.value.text()),
                "scope_id": None,
            }
        }
        if self.mode.currentData() == "until_or_seconds":
            out["seconds"] = round(self.seconds.value(), 4)
        return out


__all__ = ["WaitCommandDialog", "SOURCES"]
