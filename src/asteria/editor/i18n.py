"""Editor languages: English (the text the code is written in) and Traditional Chinese.

View ▸ Language switches live and the choice is kept (QSettings ``Asteria/Editor``
``editor/language``). Text is translated where it is shown, not where it is written: the
widget methods that put interface text on screen (labels, buttons, titles, tabs, menus, tool
tips, place-holders, headers, message boxes) look the English up in the language's table,
``translations/<language>.json``, and widgets made with their text already in them are
translated when Qt polishes them. The English stays with each widget, so switching back (or to
another language) needs no restart.

What the author typed is never translated: text boxes, lists, trees, tables and typed-in lists
show project data. A list of fixed choices is translated only for items that carry their value
as item data (the shown text is then only a label); a typed-in list whose value is its items'
data says so with the ``i18n_choices`` property. Text no table has stays English.

``{"exact": {english: translation}, "patterns": [[regex, template], ...]}``: a pattern
covers text built at run time (``Actors · 5 records``); its template names the regex groups,
``{name!t}`` translates a group as well (``{noun!t}``) and ``{name!T}`` must translate it (the
pattern does not apply when no table has that part: ``Kind: id`` but not data text).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGroupBox,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPlainTextEdit,
    QTabBar,
    QTableWidget,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QTreeWidget,
    QWidget,
)

LANGUAGES = {"en": "English", "zh_TW": "繁體中文"}
DEFAULT = "en"
FOLDER = Path(__file__).resolve().parent / "translations"
CURRENT = {"language": DEFAULT}

_SOURCE = "_i18n_source"  # the English of a widget's text (a dynamic property)
_TIP = "_i18n_tip"
_PLACEHOLDER = "_i18n_placeholder"
_TITLE = "_i18n_title"
_HEADERS = "_i18n_headers"
_ITEM_SOURCE = Qt.UserRole + 731  # the English of a fixed-choice list item
_tables = {}
_collected = None  # a set while collecting the English shown (see collect())


def language_name(settings):
    """The saved editor language (English when none is saved or it is unknown)."""
    value = settings.value("editor/language", DEFAULT) if settings is not None else DEFAULT
    return value if value in LANGUAGES else DEFAULT


def _table(language):
    table = _tables.get(language)
    if table is None:
        path = FOLDER / f"{language}.json"
        data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        patterns = [(re.compile(p), t) for p, t in data.get("patterns", ())]
        table = _tables[language] = (dict(data.get("exact", {})), patterns)
    return table


def translate(text, language=None):
    """``text`` in ``language`` (the current one by default); unknown text comes back as is."""
    if not isinstance(text, str) or not text:
        return text
    if _collected is not None:
        _collected.add(text)
    language = language or CURRENT["language"]
    if language == DEFAULT:
        return text
    exact, patterns = _table(language)
    found = exact.get(text)
    if found is None and text[:1].islower():  # "stat changes" inside "No stat changes yet."
        found = exact.get(text[:1].upper() + text[1:])
    if found is not None:
        return found
    stripped = text.strip()
    if stripped != text and stripped in exact:  # " Save " keeps its spaces
        return text.replace(stripped, exact[stripped])
    for pattern, template in patterns:
        match = pattern.fullmatch(text)
        if match is not None:
            shown = _fill(template, match, language)
            if shown is not None:
                return shown
    return text


_FIELD = re.compile(r"\{(\w+)(![tT])?\}")


class _Untranslated(Exception):
    """A ``{name!T}`` part no table has: the pattern does not apply."""


def _fill(template, match, language):
    groups = match.groupdict()

    def one(field):
        value = groups.get(field.group(1)) or ""
        if not field.group(2):
            return value
        shown = translate(value, language)
        if field.group(2) == "!T" and shown == value:
            raise _Untranslated
        return shown

    try:
        return _FIELD.sub(one, template)
    except _Untranslated:
        return None


def collect():
    """Start recording every interface text shown (English, before translation); returns
    the set it fills. Used to find text the tables do not have yet."""
    global _collected
    _collected = set()
    return _collected


# -- the widget methods that show text --------------------------------------------------------
def _remember(obj, key, text):
    if isinstance(text, str):
        obj.setProperty(key, text)


def _wrap(cls, name, key, index=0):
    """``cls.name(text, ...)`` translates its ``index``-th argument and remembers the English
    in the ``key`` property (for a later switch of language)."""
    original = getattr(cls, name)

    def method(self, *args, **kwargs):
        if len(args) > index and isinstance(args[index], str):
            _remember(self, key, args[index])
            args = (*args[:index], translate(args[index]), *args[index + 1 :])
        return original(self, *args, **kwargs)

    method.__wrapped__ = original
    setattr(cls, name, method)


def _wrap_tab(cls, name, text_index):
    """``addTab`` / ``insertTab`` / ``setTabText``: the English of a tab is kept on its page
    (a QTabWidget) or in the tab's data slot of a list kept on the bar."""
    original = getattr(cls, name)

    def method(self, *args, **kwargs):
        args = list(args)
        if len(args) > text_index and isinstance(args[text_index], str):
            source = args[text_index]
            args[text_index] = translate(source)
            result = original(self, *args, **kwargs)
            index = result if name != "setTabText" else args[0]
            _remember_tab(self, index, source)
            return result
        return original(self, *args, **kwargs)

    method.__wrapped__ = original
    setattr(cls, name, method)


def _remember_tab(owner, index, source):
    if isinstance(owner, QTabWidget):
        page = owner.widget(index)
        if page is not None:
            page.setProperty("_i18n_tab", source)
        return
    sources = dict(owner.property("_i18n_tabs") or {})
    sources[str(index)] = source
    owner.setProperty("_i18n_tabs", sources)


def _wrap_headers(cls, name):
    original = getattr(cls, name)

    def method(self, labels):
        labels = list(labels)
        self.setProperty(_HEADERS, labels)
        return original(self, [translate(x) for x in labels])

    method.__wrapped__ = original
    setattr(cls, name, method)


def _wrap_combo_add(cls, name):
    """``addItem(text, data)`` / ``insertItem(index, text, data)``: the shown text of a fixed
    choice (its value is the data) is translated; typed-in lists and items without data are
    left alone (their text is the value)."""
    original = getattr(cls, name)
    offset = 1 if name == "insertItem" else 0

    def method(self, *args, **kwargs):
        args = list(args)
        text_at = offset + (1 if args[offset : offset + 1] and _is_icon(args[offset]) else 0)
        has_data = len(args) > text_at + 1 or "userData" in kwargs
        fixed = not self.isEditable() or bool(self.property("i18n_choices"))
        if has_data and fixed and isinstance(args[text_at], str):
            source = args[text_at]
            args[text_at] = translate(source)
            result = original(self, *args, **kwargs)
            row = args[0] if name == "insertItem" else self.count() - 1
            row = max(0, min(int(row), self.count() - 1)) if name == "insertItem" else row
            self.setItemData(row, source, _ITEM_SOURCE)
            return result
        return original(self, *args, **kwargs)

    method.__wrapped__ = original
    setattr(cls, name, method)


def _is_icon(value):
    from PySide6.QtGui import QIcon

    return isinstance(value, QIcon)


def _wrap_static(cls, name, positions):
    """Static dialogs (``QMessageBox.question(parent, title, text, ...)``)."""
    original = getattr(cls, name)

    def method(*args, **kwargs):
        args = list(args)
        for i in positions:
            if len(args) > i and isinstance(args[i], str):
                args[i] = translate(args[i])
        return original(*args, **kwargs)

    method.__wrapped__ = original
    setattr(cls, name, staticmethod(method))


_INSTALLED = {"done": False}


def _install_wrappers():
    if _INSTALLED["done"]:
        return
    _INSTALLED["done"] = True
    for cls in (QLabel, QAbstractButton):
        _wrap(cls, "setText", _SOURCE)
    _wrap(QGroupBox, "setTitle", _TITLE)
    _wrap(QMenu, "setTitle", _TITLE)
    _wrap(QWidget, "setToolTip", _TIP)
    _wrap(QWidget, "setWindowTitle", _TITLE)  # docks and dialogs too
    for cls in (QLineEdit, QPlainTextEdit, QTextEdit):
        _wrap(cls, "setPlaceholderText", _PLACEHOLDER)
    _wrap(QAction, "setText", _SOURCE)
    _wrap(QAction, "setToolTip", _TIP)
    _wrap(QAction, "setStatusTip", "_i18n_status")
    _wrap_tab(QTabWidget, "addTab", 1)
    _wrap_tab(QTabWidget, "insertTab", 2)
    _wrap_tab(QTabWidget, "setTabText", 1)
    _wrap_tab(QTabBar, "addTab", 0)
    _wrap_tab(QTabBar, "setTabText", 1)
    _wrap_headers(QTreeWidget, "setHeaderLabels")
    _wrap_headers(QTableWidget, "setHorizontalHeaderLabels")
    _wrap_combo_add(QComboBox, "addItem")
    _wrap_combo_add(QComboBox, "insertItem")
    for name in ("question", "information", "warning", "critical"):
        _wrap_static(QMessageBox, name, (1, 2))
    _wrap_static(QFileDialog, "getOpenFileName", (1,))
    _wrap_static(QFileDialog, "getSaveFileName", (1,))
    _wrap_static(QFileDialog, "getExistingDirectory", (1,))
    _wrap_static(QInputDialog, "getText", (1, 2))
    _wrap_static(QInputDialog, "getItem", (1, 2))
    _wrap_menu_adds()


def _wrap_menu_adds():
    """``QMenu.addMenu("Title")`` / ``QMenu.addAction("Text")`` / ``QMenuBar.addMenu``: text
    handed straight to Qt."""
    for cls in (QMenu, QMenuBar):
        original = cls.addMenu

        def add_menu(self, *args, _original=original):
            if args and isinstance(args[-1], str) and len(args) <= 2:
                source = args[-1]
                menu = _original(self, *args[:-1], translate(source))
                menu.setProperty(_TITLE, source)
                return menu
            return _original(self, *args)

        add_menu.__wrapped__ = original
        cls.addMenu = add_menu
    original_add = QMenu.addAction

    def add_action(self, *args, **kwargs):
        args = list(args)
        text_at = 1 if args and _is_icon(args[0]) else 0
        if len(args) > text_at and isinstance(args[text_at], str):
            source = args[text_at]
            args[text_at] = translate(source)
            action = original_add(self, *args, **kwargs)
            action.setProperty(_SOURCE, source)
            return action
        return original_add(self, *args, **kwargs)

    add_action.__wrapped__ = original_add
    QMenu.addAction = add_action


# -- widgets made with their text: translated when polished ------------------------------------
def _english(obj, key, current):
    """The English of a text: remembered, else what is shown now (shown while English)."""
    value = obj.property(key)
    return value if isinstance(value, str) else current


def retranslate(obj, language=None):
    """Show ``obj``'s interface text in ``language`` (the current one by default)."""
    language = language or CURRENT["language"]

    def put(key, current, setter):
        source = _english(obj, key, current)
        if not source:
            return
        if obj.property(key) is None:
            obj.setProperty(key, source)
        shown = translate(source, language)
        if shown != current:
            setter(shown)

    if isinstance(obj, QAction):
        menu = obj.menu()
        if menu is not None:  # a menu's own action shows its title: the title is the source
            source = _english(menu, _TITLE, menu.title())
            menu.setProperty(_TITLE, source)
            shown = translate(source, language)
            if shown != menu.title():
                QMenu.setTitle.__wrapped__(menu, shown)
            return
        put(_SOURCE, obj.text(), lambda t: obj.setText.__wrapped__(obj, t))
        put(_TIP, obj.toolTip(), lambda t: obj.setToolTip.__wrapped__(obj, t))
        return
    if not isinstance(obj, QWidget) or obj.property("i18n") is False:
        return
    if isinstance(obj, (QLabel, QAbstractButton)) and not obj.property("i18n_data"):
        base = QLabel if isinstance(obj, QLabel) else QAbstractButton
        if obj.text():
            put(_SOURCE, obj.text(), lambda t: base.setText.__wrapped__(obj, t))
    if isinstance(obj, QGroupBox):
        put(_TITLE, obj.title(), lambda t: QGroupBox.setTitle.__wrapped__(obj, t))
    if isinstance(obj, QMenu):
        put(_TITLE, obj.title(), lambda t: QMenu.setTitle.__wrapped__(obj, t))
    if obj.toolTip():
        put(_TIP, obj.toolTip(), lambda t: QWidget.setToolTip.__wrapped__(obj, t))
    if obj.isWindow() and obj.windowTitle():
        put(_TITLE, obj.windowTitle(), lambda t: QWidget.setWindowTitle.__wrapped__(obj, t))
    if isinstance(obj, QDockWidget):
        put(_TITLE, obj.windowTitle(), lambda t: QWidget.setWindowTitle.__wrapped__(obj, t))
    if isinstance(obj, (QLineEdit, QPlainTextEdit, QTextEdit)) and obj.placeholderText():
        setter = type(obj).setPlaceholderText.__wrapped__
        put(_PLACEHOLDER, obj.placeholderText(), lambda t: setter(obj, t))
    if isinstance(obj, QTabWidget):
        for i in range(obj.count()):
            page = obj.widget(i)
            source = page.property("_i18n_tab") if page is not None else None
            if source is None and page is not None:
                source = obj.tabText(i)
                page.setProperty("_i18n_tab", source)
            if source is not None:
                QTabWidget.setTabText.__wrapped__(obj, i, translate(source, language))
    elif isinstance(obj, QTabBar) and not isinstance(obj.parent(), QTabWidget):
        sources = dict(obj.property("_i18n_tabs") or {})
        for i in range(obj.count()):
            source = sources.setdefault(str(i), obj.tabText(i))
            QTabBar.setTabText.__wrapped__(obj, i, translate(source, language))
        obj.setProperty("_i18n_tabs", sources)
    if isinstance(obj, QComboBox) and (not obj.isEditable() or obj.property("i18n_choices")):
        _retranslate_combo(obj, language)
    if isinstance(obj, (QTreeWidget, QTableWidget)):
        _retranslate_headers(obj, language)
    if isinstance(obj, (QMenu, QMenuBar, QToolBar)):
        for action in QWidget.actions(obj):
            retranslate(action, language)


def _retranslate_combo(combo, language):
    for row in range(combo.count()):
        source = combo.itemData(row, _ITEM_SOURCE)
        if source is None:
            data = combo.itemData(row)
            if data is None:
                continue  # no value of its own: the text is the value
            source = combo.itemText(row)
            combo.setItemData(row, source, _ITEM_SOURCE)
        shown = translate(source, language)
        if shown != combo.itemText(row):
            combo.setItemText(row, shown)


def _retranslate_headers(view, language):
    labels = view.property(_HEADERS)
    if labels is None:
        header = view.headerItem() if isinstance(view, QTreeWidget) else None
        if header is not None:
            labels = [header.text(i) for i in range(header.columnCount())]
        elif isinstance(view, QTableWidget):
            labels = [
                view.horizontalHeaderItem(i).text() if view.horizontalHeaderItem(i) else ""
                for i in range(view.columnCount())
            ]
        else:
            return
        view.setProperty(_HEADERS, labels)
    shown = [translate(x, language) for x in labels]
    if isinstance(view, QTreeWidget):
        QTreeWidget.setHeaderLabels.__wrapped__(view, shown)
    else:
        QTableWidget.setHorizontalHeaderLabels.__wrapped__(view, shown)


class _Translator(QObject):
    """Translates every widget once, when Qt polishes it (text given at construction)."""

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        if event.type() == QEvent.Polish and CURRENT["language"] != DEFAULT:
            try:
                retranslate(obj)
            except RuntimeError:  # deleted while polishing
                pass
        return False


def install(app, language=DEFAULT):
    """Use ``language`` for the editor (wrappers and the polish filter go in once)."""
    _install_wrappers()
    if getattr(app, "_asteria_translator", None) is None:
        app._asteria_translator = _Translator(app)
        app.installEventFilter(app._asteria_translator)
    set_language(language)


def set_language(language):
    """Switch the editor language live: every widget and action shows its text again."""
    language = language if language in LANGUAGES else DEFAULT
    if language == CURRENT["language"] and language == DEFAULT:
        return
    CURRENT["language"] = language
    app = QApplication.instance()
    if app is None:
        return
    for widget in app.allWidgets():
        try:
            retranslate(widget, language)
            for action in QWidget.actions(widget):  # (a widget may name a field "actions")
                retranslate(action, language)
        except RuntimeError:  # a widget going away
            continue


_reverse = {}


def english(text):
    """The English of shown text (the text itself in English or when no table has it): for
    code that picks icons, styles or panels by their title."""
    language = CURRENT["language"]
    if language == DEFAULT or not isinstance(text, str):
        return text
    reverse = _reverse.get(language)
    if reverse is None:
        reverse = _reverse[language] = {}
        for source, shown in _table(language)[0].items():
            reverse.setdefault(shown, source)
    return reverse.get(text, text)


def source_text(widget):
    """The English a widget's text was written in (for code that reads text back)."""
    value = widget.property(_SOURCE)
    return value if isinstance(value, str) else widget.text()


__all__ = [
    "CURRENT",
    "LANGUAGES",
    "collect",
    "english",
    "install",
    "language_name",
    "retranslate",
    "set_language",
    "source_text",
    "translate",
]
