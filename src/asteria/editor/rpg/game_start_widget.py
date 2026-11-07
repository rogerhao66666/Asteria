"""Qt form for the project's Game Start (the New Game state). Edits apply on their own a moment
after typing stops (undoable); a problem is shown and nothing is applied."""

from __future__ import annotations

import dataclasses

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.editor.events.map_point_picker import MapPointPicker
from asteria.editor.project.empty_state import ProjectEmptyState
from asteria.editor.records.form_tables import AmountTable
from asteria.editor.rpg.game_start_authoring import GAME_START_CARDS, GameStartAuthoringError
from asteria.editor.rpg.game_systems_widget import RecordForm
from asteria.editor.ui.i18n import CURRENT, DEFAULT, translate
from asteria.editor.ui.icons import icon
from asteria.editor.ui.responsive_form import ResponsiveSplit
from asteria.editor.ui.undo_buttons import UndoRedoButtons

SIDE_BY_SIDE_AT = 800
FOLD_FROM = 25  # a card holding a list this long starts folded: the page stays a page
_NAMES_WHEN_FOLDED = 6
_NO_LIMIT = 16777215


class _Card(QFrame):
    """A titled card with its picture; the title folds it."""

    def __init__(self, title, icon_name, body, help_text=""):
        super().__init__()
        self.setObjectName("FormSection")
        self.body = body
        self.title = QToolButton()
        self.title.setObjectName("FormSectionTitle")
        self.title.setText(title)
        self.title.setIcon(icon(icon_name))
        self.title.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.title.setCheckable(True)
        self.title.setChecked(True)
        self.title.toggled.connect(self._fold)
        self.arrow = QToolButton()
        self.arrow.setObjectName("FormSectionTitle")
        self.arrow.setArrowType(Qt.DownArrow)
        self.arrow.setFixedSize(16, 16)
        self.arrow.clicked.connect(self.title.toggle)
        head = QHBoxLayout()
        head.setSpacing(6)
        head.addWidget(self.title)
        head.addWidget(self.arrow)
        if help_text:
            from asteria.editor.records.form_controls import help_tip

            mark = QLabel("ⓘ")
            mark.setObjectName("FormSectionHelp")
            mark.setToolTip(help_text)
            mark.setStyleSheet("color: #8b8e98;")
            head.addWidget(help_tip(mark))
        # folded, the card still says what it holds
        self.summary = QLabel("")
        self.summary.setStyleSheet("color: #8b8e98;")
        self.summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.summary.hide()
        head.addWidget(self.summary, 100)
        head.addStretch(1)  # open, the title stays at the card's left
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 12)
        layout.setSpacing(6)
        layout.addLayout(head)
        layout.addWidget(body)
        layout.addStretch(1)

    def _fold(self, open_):
        self.body.setVisible(open_)
        self.arrow.setArrowType(Qt.DownArrow if open_ else Qt.RightArrow)
        self.summary.setVisible(not open_ and bool(self.summary.text()))

    def is_open(self):
        return self.title.isChecked()

    def set_open(self, open_):
        self.title.setChecked(open_)


class GameStartForm(QWidget):
    """The page's fields, a card for each part of the start (``GAME_START_CARDS``): where it
    starts beside the party, then what the party owns."""

    changed = Signal()

    def __init__(self, fields, references, document, parent=None):
        super().__init__(parent)
        by_key = {f.key: f for f in fields}
        self.forms = []
        self.widgets = {}
        self.cards = {}
        for title, icon_name, keys in GAME_START_CARDS:
            own = [by_key[key] for key in keys]
            # a field named as its card: the title is its caption, the ⓘ moves up beside it
            shown = [dataclasses.replace(f, label="") if f.label == title else f for f in own]
            form = RecordForm(tuple(shown), references, document=document, column_width=200)
            form.changed.connect(self.changed)
            form.changed.connect(self._line_up)
            self.forms.append(form)
            self.widgets.update(form.widgets)
            hint = next((f.help for f in own if f.label == title), "")
            body = form
            if "position" in keys:
                body = self._with_map(form, document)
            self.cards[title] = _Card(title, icon_name, body, hint)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        cards = list(self.cards.values())
        layout.addWidget(
            ResponsiveSplit(
                cards[0],
                cards[1],
                side_by_side_at=SIDE_BY_SIDE_AT,
                first_share=3,
                second_share=2,
                stacked_height=_NO_LIMIT,
            )
        )
        for card in cards[2:]:
            layout.addWidget(card)
        layout.addStretch(1)

    def _with_map(self, form, document):
        """The place's fields with the map they are about: a click on it sets the position, and
        it follows the scene, the facing and the position as they change."""
        self.map = MapPointPicker(document)
        self.map.picked.connect(self._picked)
        form.changed.connect(self._show_place)
        body = QWidget()
        column = QVBoxLayout(body)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(8)
        column.addWidget(form)
        column.addWidget(self.map)
        return body

    def _picked(self, x, y):
        self.widgets["position"].set_value([x, y])
        self._show_place()

    def _show_place(self):
        written = self.forms[0].data()
        self.map.show_place(written["scene_id"], written["position"], written["player_facing"])
        if written["position"] is None:  # turned on, the switch starts from where the player is
            self.widgets["position"].show_unset(self.map.canvas.player_place())

    def fold_long_lists(self):
        """Fold each card whose list is long, and let it say what is in it."""
        for title, _icon, keys in GAME_START_CARDS:
            for key in keys:
                table = self.widgets[key]
                if isinstance(table, AmountTable) and len(table.values) >= FOLD_FROM:
                    self.cards[title].set_open(False)

    def _say_what_is_folded(self):
        for title, _icon, keys in GAME_START_CARDS:
            tables = [self.widgets[k] for k in keys if isinstance(self.widgets[k], AmountTable)]
            if not tables:
                continue
            table = tables[0]
            held = list(table.values)[:_NAMES_WHEN_FOLDED]
            names = [translate(table._name(key)) for key in held]
            more = "…" if len(table.values) > _NAMES_WHEN_FOLDED else ""
            card = self.cards[title]
            between = ", " if CURRENT["language"] == DEFAULT else "、"
            card.summary.setText(between.join(names) + more)
            card.summary.setVisible(not card.is_open() and bool(names))

    def _line_up(self):
        """The lists of amounts share one name width, so their columns line up across cards."""
        tables = [w for w in self.widgets.values() if isinstance(w, AmountTable)]
        widest = max(t.wanted_name_width() for t in tables)
        for table in tables:
            if table.least_name_width != widest:
                table.least_name_width = widest
                table._build()
        self._say_what_is_folded()

    def set_data(self, data):
        for form in self.forms:
            form.set_data(data)
        self._line_up()
        self._show_place()

    def data(self):
        out = {}
        for form in self.forms:
            written = form.data()
            out.update({f.key: written[f.key] for f in form.fields})
        return out


class GameStartEditorWidget(QWidget):
    changed = Signal()

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.form = None
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.NoFrame)
        self.scroll.setViewportMargins(0, 0, 10, 0)  # fields never touch the scroll bar
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self.auto_apply)
        self._unannounced = False
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(UndoRedoButtons())  # edits apply on their own: a step back or on
        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll, 1)
        layout.addWidget(self.status)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self):
        self.flush_edits()
        if self.controller.document.project is None:
            self.form = None
            self.scroll.setWidget(ProjectEmptyState("Open a project to edit its Game Start."))
            return
        folded = {} if self.form is None else {
            title: card.is_open() for title, card in self.form.cards.items()
        }  # fmt: skip
        self.form = GameStartForm(
            self.controller.form, self.controller.references, self.controller.document
        )
        self.form.set_data(self.controller.form_data())
        if folded:  # the author's folds stay; a page opened anew folds its long lists
            for title, open_ in folded.items():
                self.form.cards[title].set_open(open_)
        else:
            self.form.fold_long_lists()
        self.form.changed.connect(self._timer.start)
        self.scroll.setWidget(self.form)

    def auto_apply(self):
        if self.form is None:
            return False
        try:
            self.controller.apply(self.form.data())
        except (GameStartAuthoringError, ValueError, TypeError) as exc:
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText("⚠  Not applied: " + str(exc))
            return False
        self.status.setText("")
        self._unannounced = True
        return True

    def flush_edits(self):
        if self._timer.isActive():
            self._timer.stop()
            self.auto_apply()
        if self._unannounced:
            self._unannounced = False
            self.changed.emit()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        self.flush_edits()
        super().hideEvent(event)

    def apply(self):
        """Apply now and rebuild the page (scripts and tests)."""
        self._timer.stop()
        if not self.auto_apply():
            return False
        self._unannounced = False
        self.status.setText("Game Start applied")
        self.changed.emit()
        self.refresh()
        return True
