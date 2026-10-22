"""Icons and colour roles for the editor's controls, applied app-wide.

Buttons, tabs and pickers are made in many editor modules; instead of touching each one,
``install(app)``
watches widgets as they appear and gives them an icon and a colour role from their text:

* buttons - "Delete" / "Remove" are ``danger`` (red), "Apply" / "Save" / "Run" / "Create" are
  ``primary``,
  "Add" / "New" get a green plus; every known verb gets its icon
* tab titles, and entries of combo boxes marked ``decorate=True`` (database categories), get the
  matching icon

Wheel input over numeric fields scrolls the surrounding content instead of editing values.

``compact`` keeps panels narrow so more columns fit on screen (``compact_widget``): combo boxes
stop
growing to their longest entry (the drop-down still shows it), long one-line labels wrap, and a
long
group title keeps its name while its explanation moves into a wrapped hint inside the group.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QApplication,
    QBoxLayout,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QToolButton,
    QWidget,
)

from .icons import icon
from .ui_fit import layout_children, layout_widgets

# (pattern on the button text, icon, role); first match wins
BUTTON_RULES = (
    (r"^(delete|remove)\b|^[-−–] ", "delete", "danger"),
    (r"^apply\b", "apply", "primary"),
    (r"^save\b", "save", "primary"),
    (r"^run\b", "play", "success"),
    (r"^(create|place)\b", "add", "primary"),
    (r"^(new|add)\b|^\+ ?", "add", ""),
    (r"^duplicate\b|^copy\b", "duplicate", ""),
    (r"^(reload|refresh|rescan)\b", "reload", ""),
    (r"^(export|package|build)\b", "export", ""),
    (r"^(import|open)\b", "folder", ""),
    (r"^(stop)\b", "stop", ""),
    (r"^(preview|play)\b", "play", ""),
    (r"^dialogue\b", "dialogue", ""),
    (r"^choice\b", "list", ""),
    (r"^sequence\b", "timeline", ""),
    (r"^(settings|options)\b", "settings", ""),
    (r"^(search|find)\b", "search", ""),
    (r"^revert\b", "reload", ""),
)

# (pattern on a tab / combo / tree label, icon); first match wins
LABEL_RULES = (
    # game systems kinds
    (r"^quests?$", "quest"),
    (r"faction|reputation", "banner"),
    (r"achievement", "trophy"),
    (r"drop tables?", "chest"),
    (r"translation|locale", "globe"),
    (r"map areas?|region", "pin"),
    (r"durab|disassembl", "hammer"),
    (r"new game", "cycle"),
    (r"message settings", "dialogue"),
    (r"^credits", "list"),
    (r"^battle options", "inspector"),
    (r"^battle extras", "battle"),
    (r"doodad", "doodad"),
    (r"capture", "net"),
    (r"stat formula|derived stat", "gauge"),
    (r"world interactions?", "interact"),
    # workspace sub-tabs
    (r"^scene\b", "scene"),
    (r"^game start$|^start\b", "flag"),
    (r"^pets?\b|pet species", "paw"),
    (r"gauge", "gauge"),
    (r"^game data$|database", "rpg"),
    (r"^game systems$", "settings"),
    (r"^enemy ai$|behavior|behaviour", "behavior_tree"),
    (r"^battle screen$", "presentation"),
    (r"^menu screens?$|^runtime rpg ui$", "ui"),
    (r"^animation states$|state machine", "state_machine"),
    (r"animation", "animation"),
    (r"composition", "composition"),
    (r"timeline", "timeline"),
    (r"^battle effects$|vfx|particle|weather", "vfx"),
    (r"^controls$|input", "input"),
    (r"^entity events$|^common .* events$|^events?\b", "events"),
    (r"overview|flow", "flow"),
    (r"^code\b|script", "code"),
    # database categories
    (r"real-time combat|^attacks|projectile", "battle"),
    (r"damage numbers", "ui"),
    (r"target", "target"),
    (r"combatant|sprite|portrait", "presentation"),
    (r"motion|sequence|camera|choreograph", "timeline"),
    (r"actor|hero|party", "actor"),
    (r"class|job", "class"),
    (r"skill|abilit|spell|passive|evolution", "skill"),
    (r"weapon", "weapon"),
    (r"armou?r|equipment|attachment", "armor"),
    (r"item|inventory|shop|loot|craft|alchemy", "item"),
    (r"troop|encounter|formation", "troop"),
    (r"enemy|enemies|monster|boss", "enemy"),
    (r"status|state|buff", "state"),
    (r"turn order|timing|recovery", "timeline"),
    (r"damage|interaction|chance|counter|follow-up|gauge|break", "battle"),
    (r"victory|defeat|escape|objective", "flow"),
    (r"resource|cost|rule|progression|growth|track|tree", "settings"),
    (r"menu|command|hud|ui|screen|layout|spacing|theme|result|damage numbers", "ui"),
    (r"channel|sound|audio|music|bgm|sfx", "audio"),
    (r"image|tileset|texture", "image"),
    (r"prefab", "prefab"),
    (r"asset", "assets"),
    (r"layer", "layers"),
)

_BUTTONS = [(re.compile(p, re.I), name, role) for p, name, role in BUTTON_RULES]
_LABELS = [(re.compile(p, re.I), name) for p, name in LABEL_RULES]


def button_style(text):
    """``(icon name, role)`` for a button text, or ``(None, "")``."""
    plain = text.replace("&", "").strip()
    for pattern, name, role in _BUTTONS:
        if pattern.search(plain):
            return name, role
    return None, ""


def label_icon(text):
    from .i18n import english

    plain = english(text.replace("&", "").strip())  # icons are picked by the English title
    for pattern, name in _LABELS:
        if pattern.search(plain):
            return name
    return None


def decorate_button(button):
    if button.property("decorated") == button.text():
        return
    button.setProperty("decorated", button.text())
    from .i18n import english

    name, role = button_style(english(button.text().strip()))  # by the English (Delete: red)
    if re.match(r"^[+\-−–↑↓▲▼]", button.text().strip()):
        name = None  # the text already carries its symbol
    if name and button.icon().isNull():
        button.setIcon(icon(name, "#ffffff") if role in ("primary", "success") else icon(name))
    if role and not button.objectName() and button.property("role") is None:
        button.setProperty("role", role)
        button.style().unpolish(button)
        button.style().polish(button)


def decorate_tabs(tabs):
    for index in range(tabs.count()):
        if tabs.tabIcon(index).isNull():
            name = label_icon(tabs.tabText(index))
            if name:
                tabs.setTabIcon(index, icon(name))


def decorate_combo(combo):
    for index in range(combo.count()):
        if combo.itemIcon(index).isNull():
            name = label_icon(combo.itemText(index))
            if name:
                combo.setItemIcon(index, icon(name))


COMBO_CHARS = (
    8  # a combo box shows about this many characters; its drop-down is as wide as it needs
)
WRAP_AT = 48  # one-line labels longer than this wrap
COMBO_MIN_WIDTH = 96
SPIN_MIN_WIDTH = 64


def compact_widget(widget):
    if isinstance(widget, QGroupBox) and not widget.title() and not widget.isCheckable():
        # Inset headings use layout padding; do not also reserve a native title row.
        widget.setContentsMargins(0, 0, 0, 0)
    if isinstance(widget, QComboBox):
        # Use a bounded scrolling list across every workspace, including dynamic pickers.
        widget.setMaxVisibleItems(10)
        widget.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        if (
            widget.sizeAdjustPolicy() != QComboBox.AdjustToMinimumContentsLengthWithIcon
            and not widget.isEditable()
        ):
            widget.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
            widget.setMinimumContentsLength(COMBO_CHARS)
        if widget.minimumWidth() == 0:
            widget.setMinimumWidth(
                COMBO_MIN_WIDTH
            )  # explicit: the styled size hint ignores the policy
        if (
            widget.property("full_text_tip") is None
        ):  # a narrow combo box still tells its whole value
            widget.setProperty("full_text_tip", True)
            widget.currentTextChanged.connect(widget.setToolTip)
            widget.setToolTip(widget.currentText())
    elif isinstance(widget, QAbstractSpinBox):
        if widget.minimumWidth() == 0:
            widget.setMinimumWidth(SPIN_MIN_WIDTH)
    elif isinstance(widget, QLabel):
        text = widget.text()
        if (
            not widget.wordWrap()
            and len(text) > WRAP_AT
            and "\n" not in text
            and widget.pixmap().isNull()
        ):
            widget.setWordWrap(True)
    elif isinstance(widget, QGroupBox) and widget.property("compacted") is None:
        widget.setProperty("compacted", True)
        for form in widget.findChildren(QFormLayout):
            _wrap_form(form)
        title = widget.title()
        if len(title) > 28 and " (" in title and title.endswith(")"):
            head, detail = title.split(" (", 1)
            widget.setTitle(head)
            widget.setToolTip(title)
            hint = QLabel(detail[:-1][0].upper() + detail[:-1][1:])
            hint.setObjectName("MutedLabel")
            hint.setWordWrap(True)
            layout = widget.layout()
            if isinstance(layout, QBoxLayout):
                layout.insertWidget(0, hint)
            elif isinstance(layout, QFormLayout):
                layout.insertRow(0, hint)
            else:
                hint.deleteLater()


def _widen_popup(container):
    """A compact combo box's drop-down still shows its longest entry (sized when it opens, so the
    combo box itself stays narrow)."""
    combo = container.parentWidget()
    if not isinstance(combo, QComboBox):
        return
    metrics = combo.fontMetrics()
    widest = max(
        (metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())), default=0
    )
    icon = (
        combo.iconSize().width() + 8
        if any(not combo.itemIcon(i).isNull() for i in range(combo.count()))
        else 0
    )
    container.setMinimumWidth(min(520, max(combo.width(), widest + icon + 44)))


def _wrap_form(form):
    if form.property("stackFields"):
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        return
    # a label goes above its field only when the pane is too narrow for both side by side
    form.setRowWrapPolicy(QFormLayout.WrapLongRows)
    form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)


def flow_button_rows(layout):
    """Rows of two or more buttons wrap onto a second line in narrow panels."""
    from .flow_layout import FlowLayout

    # Rows are found without itemAt (see ui_fit.layout_widgets): this runs on every page shown,
    # and an item wrapper it left behind crashed the editor once Qt deleted that item.
    for child in layout_children(layout):
        if (
            isinstance(child, QHBoxLayout)
            and isinstance(layout, QBoxLayout)
            and not isinstance(child, FlowLayout)
            and _button_row(child)
        ):
            widgets = layout_widgets(child)
            used = {child.indexOf(w) for w in widgets}
            used.update(child.indexOf(sub) for sub in layout_children(child))
            leading_stretch = child.count() > 0 and 0 not in used  # a spacer comes first
            flow = FlowLayout(spacing=max(4, child.spacing()))
            if leading_stretch:
                flow.setAlignment(Qt.AlignRight)
            index = layout.indexOf(child)
            layout.takeAt(index)
            child.deleteLater()
            # the row goes in empty: inserting a filled one would wrap its items as well
            layout.insertLayout(index, flow)
            for widget in widgets:
                child.removeWidget(widget)
                flow.addWidget(widget)
        else:
            flow_button_rows(child)


def _button_row(row):
    widgets = layout_widgets(row)
    return len(widgets) >= 2 and all(isinstance(w, QAbstractButton) for w in widgets)


def compact(widget):
    for w in (widget, *widget.findChildren(QObject)):
        if isinstance(w, (QComboBox, QLabel, QGroupBox, QAbstractSpinBox)):
            compact_widget(w)
        if isinstance(w, QWidget) and isinstance(QWidget.layout(w), QBoxLayout):
            flow_button_rows(QWidget.layout(w))


def decorate(widget):
    """Decorate ``widget`` and everything inside it (safe to call again)."""
    for w in (widget, *widget.findChildren(QObject)):
        if isinstance(w, QPushButton) or (
            isinstance(w, QToolButton) and w.text() and not w.defaultAction()
        ):
            decorate_button(w)
        elif isinstance(w, QTabWidget):
            decorate_tabs(w)
        elif isinstance(w, QComboBox) and w.property("decorate") is True:
            decorate_combo(w)


class _Decorator(QObject):
    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Wheel and isinstance(obj, QAbstractSpinBox):
            # Scrolling never edits a number: hand the wheel to the containing scroll area
            # (a filter that swallows the event stops Qt passing it on to the parent itself).
            area = obj.parentWidget()
            while area is not None and not isinstance(area, QAbstractScrollArea):
                area = area.parentWidget()
            if area is not None:
                QApplication.sendEvent(area.viewport(), event)
            else:
                event.ignore()
            return True
        if kind == QEvent.Polish and isinstance(obj, QCheckBox):
            # the themed box and its spacing draw wider than the macOS style tells layouts:
            # without this a box's text ran into the field beside it
            obj.setAttribute(Qt.WA_LayoutUsesWidgetRect, True)
        if kind == QEvent.Show:
            if isinstance(obj, (QComboBox, QLabel, QGroupBox, QAbstractSpinBox)):
                compact_widget(obj)
            elif obj.metaObject().className() == "QComboBoxPrivateContainer":
                _widen_popup(obj)
            layout = (
                QWidget.layout(obj) if isinstance(obj, QWidget) else None
            )  # some editors override layout()
            if isinstance(layout, QFormLayout):
                _wrap_form(layout)
            elif isinstance(layout, QBoxLayout) and obj.property("flowed") is None:
                obj.setProperty("flowed", True)
                flow_button_rows(layout)
            if isinstance(obj, QTabWidget):
                decorate_tabs(obj)
            elif isinstance(obj, QComboBox) and obj.property("decorate") is True:
                decorate_combo(obj)
            elif isinstance(obj, QAbstractButton) and not (
                isinstance(obj, QToolButton) and obj.defaultAction()
            ):
                if isinstance(obj, QPushButton) or obj.text():
                    decorate_button(obj)
        return False


def install(app):
    """Decorate every button, tab widget and combo box as it is shown, app-wide."""
    if getattr(app, "_asteria_decorator", None) is None:
        app._asteria_decorator = _Decorator(app)
        app.installEventFilter(app._asteria_decorator)
    return app._asteria_decorator
