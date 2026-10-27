"""A formula field (D94): typed, or built with the buttons beside it.

A formula reads the fighters' stats as variables - ``source.dex``, ``target.evade``,
``self.luk`` - and resources through ``source.current("hp")``. A project that defines its stats
(Game Systems ▸ Stats) may only read those: any other name is an error, shown under the field
and not applied (the record keeps its last good formula), and listed in the Problems panel. A
project without stat definitions offers every stat its data uses and checks only that the
formula parses.

The buttons insert at the cursor: one per fighter the formula can see, with a menu of the
declared stats (and the resources), the plain numbers it is given (``value``, ``attempts``),
the functions and the operators. An empty formula leaves the record's other fields in charge.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.gameplay.expressions import (
    SUBJECTS,
    ExpressionError,
    check_expression,
    undeclared,
    variables,
)

from .i18n import translate

# what a function button inserts, and where the cursor lands (the count from the end)
FUNCTIONS = (
    ("min", "min(, )", 3),
    ("max", "max(, )", 3),
    ("clamp", "clamp(, 0, 1)", 7),
    ("floor", "floor()", 1),
    ("ceil", "ceil()", 1),
    ("round", "round()", 1),
    ("abs", "abs()", 1),
    ("sqrt", "sqrt()", 1),
    ("random", "random()", 0),
    ("randint", "randint(1, 6)", 0),
)
OPERATORS = (("+", " + "), ("−", " - "), ("×", " * "), ("÷", " / "), ("(", "("), (")", ")"))
OK_COLOR, ERROR_COLOR = "#7fcf95", "#ff7b7b"


def t(template, *values):
    return translate(template).format(*values)


def declared(vocabulary):
    """``(stats, resources, strict)``: the stats a formula may read (``Choice``s, Game Systems ▸
    Stats when the project defines any - then ``strict`` - else every stat its data uses) and
    the resources."""
    project = getattr(vocabulary, "project", None)
    if project is None:
        return [], [], False
    defined = getattr(project.rpg_database, "stat_definitions", {})
    stats = list(vocabulary.choices("stats"))
    if defined:
        stats = [c for c in stats if c.value in defined]
    return stats, list(vocabulary.choices("resources")), bool(defined)


def formula_problem(text, names, stats=(), resources=(), strict=False):
    """Why ``text`` cannot be used (words), or ``""``: it must parse, use only ``names`` and the
    functions, and - ``strict`` - read only the declared ``stats`` and ``resources``."""
    text = str(text or "").strip()
    if not text:
        return ""
    try:
        check_expression(text, names)
        variables(text)
    except ExpressionError as exc:
        return t("Not a formula: {0}", str(exc))
    if strict:
        missing = undeclared(text, stats, resources)
        if missing:
            return t("Not declared in Game Systems ▸ Stats: {0}", ", ".join(missing))
    return ""


class FormulaField(QWidget):
    """A formula's text, the insert buttons and a line saying what it reads or what is wrong.
    ``edited`` fires on every change; ``valid()`` says whether the text may be applied."""

    edited = Signal()

    def __init__(self, names, vocabulary=None, parent=None):
        super().__init__(parent)
        self.names = tuple(names)
        stats, resources, strict = declared(vocabulary)
        self.stats, self.resources, self.strict = stats, resources, strict
        self.edit = QLineEdit()
        self.edit.setObjectName("FormulaText")
        self.edit.setPlaceholderText(translate("Empty: the other fields are used"))
        mono = QFont("Menlo")
        mono.setStyleHint(QFont.Monospace)
        self.edit.setFont(mono)
        self.edit.textChanged.connect(self._changed)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(4)
        for name in self.names:
            buttons.addWidget(self._name_button(name))
        buttons.addWidget(self._function_button())
        for label, snippet in OPERATORS:
            button = QToolButton()
            button.setText(label)
            button.setObjectName("FormulaOperator")
            button.clicked.connect(lambda _=False, s=snippet: self.insert(s))
            buttons.addWidget(button)
        buttons.addStretch(1)
        self.status = QLabel()
        self.status.setObjectName("FormulaStatus")
        self.status.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.edit)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        self._show_status()

    # -- the buttons ---------------------------------------------------------------------------
    def _name_button(self, name):
        button = QToolButton()
        button.setObjectName("FormulaName")
        if name not in SUBJECTS:  # a number the formula is given (value, attempts)
            button.setText(name)
            button.clicked.connect(lambda _=False, n=name: self.insert(n))
            return button
        button.setText(f"{name} ▾")
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        for choice in self.stats:
            label = f"{choice.label}  ·  {name}.{choice.value}"
            action = menu.addAction(label)
            action.triggered.connect(lambda _=False, s=f"{name}.{choice.value}": self.insert(s))
        if self.resources:
            pools = menu.addMenu(translate("Resources"))
            for choice in self.resources:
                for method in ("current", "maximum", "ratio"):
                    snippet = f'{name}.{method}("{choice.value}")'
                    action = pools.addAction(f"{choice.label}  ·  {snippet}")
                    action.triggered.connect(lambda _=False, s=snippet: self.insert(s))
        button.setMenu(menu)
        return button

    def _function_button(self):
        button = QToolButton()
        button.setObjectName("FormulaFunctions")
        button.setText(translate("Functions") + " ▾")
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        for name, snippet, back in FUNCTIONS:
            action = menu.addAction(f"{name}  ·  {snippet}")
            action.triggered.connect(lambda _=False, s=snippet, b=back: self.insert(s, back=b))
        button.setMenu(menu)
        return button

    def insert(self, snippet, *, back=0):
        """Put ``snippet`` at the cursor, the cursor ``back`` characters before its end."""
        self.edit.insert(snippet)
        if back:
            self.edit.setCursorPosition(self.edit.cursorPosition() - back)
        self.edit.setFocus()

    # -- the text ------------------------------------------------------------------------------
    def text(self):
        return self.edit.text().strip()

    def setText(self, text):  # noqa: N802 - Qt-style
        self.edit.blockSignals(True)
        self.edit.setText(str(text or ""))
        self.edit.blockSignals(False)
        self._show_status()

    def problem(self):
        return formula_problem(
            self.text(),
            self.names,
            [c.value for c in self.stats],
            [c.value for c in self.resources],
            self.strict,
        )

    def valid(self):
        return not self.problem()

    def _changed(self, *_):
        self._show_status()
        self.edited.emit()

    def _show_status(self):
        problem = self.problem()
        if problem:
            self.status.setText(f"✗ {problem}  ·  {translate('Not applied')}")
            self.status.setStyleSheet(f"color: {ERROR_COLOR};")
            return
        if not self.text():
            self.status.setText(translate("Empty: the other fields are used"))
            self.status.setStyleSheet("")
            return
        stats, resources = variables(self.text())
        labels = {c.value: c.label for c in (*self.stats, *self.resources)}
        read = [labels.get(n, n) for n in (*stats, *resources)]
        words = ", ".join(dict.fromkeys(read)) if read else translate("no stats")
        self.status.setText("✓ " + t("Reads: {0}", words))
        self.status.setStyleSheet(f"color: {OK_COLOR};")


__all__ = ["FormulaField", "declared", "formula_problem"]
