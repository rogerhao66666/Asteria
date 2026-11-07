"""The small controls every record page is built from: help tips, number boxes, pickers and
pick dialogs, elided and wrapped labels, colour buttons."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyleOptionComboBox,
    QVBoxLayout,
)

from asteria.editor.records.form_shapes import choice_text, repeated_choices
from asteria.editor.ui.decor import hide_help_tip, show_help_tip


def wheel_guard(widget):
    """Scrolling the form must not change a number or a choice it passes over."""
    widget.setFocusPolicy(Qt.StrongFocus)
    original = widget.wheelEvent

    def wheel(event):
        if widget.hasFocus():
            original(event)
        else:
            event.ignore()

    widget.wheelEvent = wheel
    return widget


LABEL_GAP = 4  # a label above its field: its letters (a "y", a "g") clear of the box


def hint_label(text, color="#8b8e98"):
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {color}; font-size: 11px;")
    return label


class _HelpTip(QObject):
    """A label's tooltip shown right beside its ⓘ (``decor.show_help_tip``), wherever the
    mouse entered it, instead of under the pointer."""

    def eventFilter(self, obj, event):  # noqa: N802 - Qt
        if event.type() in (QEvent.Leave, QEvent.Hide, QEvent.MouseButtonPress):
            hide_help_tip(obj)
            return False
        if event.type() != QEvent.ToolTip or not obj.toolTip():
            return False
        return show_help_tip(obj)


_HELP_TIPS = []  # the one filter, made once a QApplication exists


def help_tip(label):
    """``label``'s tooltip opens on its left."""
    if not _HELP_TIPS:
        _HELP_TIPS.append(_HelpTip())
    label.installEventFilter(_HELP_TIPS[0])
    return label


class NumberBox(QDoubleSpinBox):
    """A number; ``percent`` shows a 0..1 share as 0..100 %."""

    def __init__(self, value, *, integer=False, percent=False):
        super().__init__()
        wheel_guard(self)
        self.percent = percent
        self.integer = integer
        if percent:
            self.setRange(0.0, 1000.0)
            self.setDecimals(1)
            self.setSuffix(" %")
            self.setSingleStep(5.0)
        else:
            self.setRange(-1e9, 1e9)
            self.setDecimals(0 if integer else 3)
            self.setSingleStep(1.0)
        self.setButtonSymbols(QDoubleSpinBox.NoButtons)  # every number looks alike
        self.setMinimumWidth(90)
        self.setMaximumWidth(140)
        self.set_value(value)

    def set_value(self, value):
        value = float(value or 0)
        self.setValue(value * 100.0 if self.percent else value)

    def number(self):
        value = self.value() / 100.0 if self.percent else self.value()
        return int(round(value)) if self.integer else round(value, 6)

    def textFromValue(self, value):  # noqa: N802 - trailing zeros hidden: 2, 0.5, 12.25
        if self.decimals() == 0:
            return str(int(round(value)))
        return f"{value:.{self.decimals()}f}".rstrip("0").rstrip(".")


class Picker(QComboBox):
    """A drop-down of choices (with icons), searchable by typing; ``allow_other`` keeps a
    typed value that is not in the list."""

    picked = Signal()
    _widest = None  # Qt asks for a size hint while the box is still being built

    def __init__(self, choices, value, *, icons=None, allow_none=True, allow_other=True):
        super().__init__()
        wheel_guard(self)
        # the value is each item's data: its shown text may be translated (editor language)
        self.setProperty("i18n_choices", True)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(16)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(16)
        self.allow_other = allow_other
        self._values = []
        self._widest = None  # the longest choice's width, measured once (see sizeHint)
        model = self.model()  # any change of the choices measures again
        for signal in (model.rowsInserted, model.rowsRemoved, model.dataChanged):
            signal.connect(self._forget_width)
        if allow_none:
            self.addItem("(none)", "")
            self._values.append("")
        choices = tuple(choices)
        repeated = repeated_choices(choices)
        for choice in choices:
            text = choice_text(choice, repeated)
            icon = icons(choice.icon) if icons and choice.icon else None
            if icon is not None:
                self.addItem(icon, text, choice.value)
            else:
                self.addItem(text, choice.value)
            if text != choice.value:
                self.setItemData(self.count() - 1, f"ID: {choice.value}", Qt.ToolTipRole)
            self._values.append(choice.value)
        completer = QCompleter([self.itemText(i) for i in range(self.count())], self)
        completer.setFilterMode(Qt.MatchContains)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.setCompleter(completer)
        self.set_value(value)
        self.activated.connect(lambda _i: self.picked.emit())
        self.lineEdit().editingFinished.connect(self._typed)
        self.currentIndexChanged.connect(self._show_start)
        self._show_start()

    def _show_start(self, *_args):
        """Narrower than its words, a box shows how they begin (a line edit would show their
        end, where the cursor is). Not from resizeEvent: a cursor moved while a form is laid
        out crashed Qt."""
        if not self.lineEdit().hasFocus():
            self.lineEdit().setCursorPosition(0)

    def sizeHint(self):  # noqa: N802 - Qt API
        """As wide as the longest choice (up to 280 px) where the form has the room, so a
        chosen name shows whole; the minimum is unchanged, so a narrow window still fits."""
        hint = super().sizeHint()
        return QSize(max(hint.width(), self.choice_width(280)), hint.height())

    def choice_width(self, cap):
        """The width that shows the longest choice whole (up to ``cap``)."""
        if self._widest is None:
            self._widest = self._choice_width()
        return min(cap, self._widest)

    def _forget_width(self, *_args):
        self._widest = None

    def _choice_width(self):
        self.ensurePolished()  # the themed font and padding, not the system ones
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        field = self.style().subControlRect(
            QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, self
        )
        metrics = self.fontMetrics()
        widest = max(
            (metrics.horizontalAdvance(self.itemText(i)) for i in range(self.count())),
            default=0,
        )
        if any(not self.itemIcon(i).isNull() for i in range(self.count())):
            widest += self.iconSize().width() + 6
        return widest + self.width() - field.width() + 2

    def set_value(self, value):
        value = "" if value is None else str(value)
        if value not in self._values:  # a reference to something that is not there
            self.addItem(f"⚠ {value}  (missing - pick one from the list)", value)
            self._values.append(value)
        self.setCurrentIndex(self._values.index(value))

    def _typed(self):
        text = self.currentText().strip()
        for i in range(self.count()):
            if self.itemText(i) == text:
                self.setCurrentIndex(i)
                self.picked.emit()
                return
        lowered = text.lower()
        for i in range(self.count()):  # an id or a name typed on its own
            if str(self.itemData(i)).lower() == lowered or self.itemText(i).lower() == lowered:
                self.setCurrentIndex(i)
                self.picked.emit()
                return
        if self.allow_other and text:
            self.set_value(text)
            self.picked.emit()

    def value(self):
        data = self.currentData()
        return "" if data is None else str(data)


class PickDialog(QDialog):
    """Choose one or more entries from a long list (with a filter); ``allow_new`` lets a typed
    value that is not listed be added."""

    def __init__(self, title, choices, *, icons=None, allow_new=False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(420, 520)
        self.filter = QLineEdit()
        hint = "Type to filter…" + ("  (or a new one)" if allow_new else "")
        self.filter.setPlaceholderText(hint)
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setIconSize(QSize(24, 24))
        for choice in choices:
            item = QListWidgetItem(choice_text(choice))
            item.setData(Qt.UserRole, choice.value)
            if icons and choice.icon:
                icon = icons(choice.icon)
                if icon is not None:
                    item.setIcon(icon)
            self.list.addItem(item)
        self.allow_new = allow_new
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.list.itemDoubleClicked.connect(lambda _i: self.accept())
        self.filter.textChanged.connect(self._filter)
        layout = QVBoxLayout(self)
        layout.addWidget(self.filter)
        layout.addWidget(self.list, 1)
        layout.addWidget(buttons)

    def _filter(self, text):
        text = text.lower().strip()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(text) and text not in item.text().lower())

    def values(self):
        chosen = [i.data(Qt.UserRole) for i in self.list.selectedItems()]
        typed = self.filter.text().strip()
        if not chosen and self.allow_new and typed:
            chosen = [typed]
        return chosen


class ElidedLabel(QLabel):
    """One line of words ending in … where its room runs out; ``text()`` and its tooltip keep
    them whole. It asks for no width of its own: the fields beside it come first."""

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        return QSize(0, super().minimumSizeHint().height())

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        room = self.contentsRect()
        words = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, room.width())
        self.style().drawItemText(
            QPainter(self),
            room,
            int(self.alignment()),
            self.palette(),
            self.isEnabled(),
            words,
            self.foregroundRole(),
        )


class WrappedWords(QLabel):
    """Words that take as many lines as their width needs, and that height in any layout: a
    title never holds its card wider than the page."""

    LEAST = 120

    def __init__(self, text=""):
        super().__init__(text)
        self.setWordWrap(True)

    def minimumSizeHint(self):  # noqa: N802 - Qt API
        size = super().minimumSizeHint()
        size.setWidth(min(size.width(), self.LEAST))
        return size

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self.setMinimumHeight(self.heightForWidth(event.size().width()))


def combo_text_width(box, text):
    """How wide ``box`` must be to show ``text`` whole (and its icon): the words, plus the
    box's own frame, padding and arrow."""
    box.ensurePolished()
    option = QStyleOptionComboBox()
    box.initStyleOption(option)
    field = box.style().subControlRect(
        QStyle.CC_ComboBox, option, QStyle.SC_ComboBoxEditField, box
    )
    width = box.fontMetrics().horizontalAdvance(text) + box.width() - field.width() + 4
    if not box.itemIcon(box.currentIndex()).isNull():
        width += box.iconSize().width() + 6
    return width


def show_start(box):
    """An editable drop-down narrower than its words shows how they begin, not their end."""
    if box.isEditable() and not box.lineEdit().hasFocus():
        box.lineEdit().setCursorPosition(0)


class ColorButton(QPushButton):
    edited = Signal()

    def __init__(self, value):
        super().__init__()
        self.color = str(value or "")  # empty: none of its own (the theme's is used)
        self.clicked.connect(self._pick)
        self._show()

    def _show(self):
        if not self.color:
            self.setText("Theme colour")
            self.setStyleSheet("")
            return
        self.setText(self.color)
        self.setStyleSheet(
            f"QPushButton {{ background: {self.color}; color: "
            f"{'#000' if QColor(self.color).lightness() > 140 else '#fff'}; }}"
        )

    def _pick(self):
        chosen = QColorDialog.getColor(QColor(self.color or "#ffffff"), self, "Colour")
        if chosen.isValid():
            self.color = chosen.name()
            self._show()
            self.edited.emit()
