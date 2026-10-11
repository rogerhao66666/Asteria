"""Icons and colour roles for the editor's controls, applied app-wide.

Buttons, tabs and pickers are made in many editor modules; instead of touching each one, ``install(app)``
watches widgets as they appear and gives them an icon and a colour role from their text:

* buttons - "Delete" / "Remove" are ``danger`` (red), "Apply" / "Save" / "Run" / "Create" are ``primary``,
  "Add" / "New" get a green plus; every known verb gets its icon
* tab titles, and entries of combo boxes marked ``decorate=True`` (database categories), get the matching icon

It only sets icons and the ``role`` property the theme styles; it never changes text or behaviour.
"""

from __future__ import annotations

import re

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractButton, QComboBox, QPushButton, QTabWidget, QToolButton

from .icons import icon

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
)

# (pattern on a tab / combo / tree label, icon); first match wins
LABEL_RULES = (
    (r"^scene\b", "scene"),
    (r"^rpg\b|database", "rpg"),
    (r"^battle (presentation|events)", "presentation"),
    (r"^battle\b|battle rules", "battle"),
    (r"^(ui|runtime rpg ui)\b", "ui"),
    (r"^events?\b|event program|common", "events"),
    (r"^code\b|script", "code"),
    (r"combatant|visual|portrait", "presentation"),
    (r"motion|sequence|camera|cue", "timeline"),
    (r"actor|hero|party", "actor"),
    (r"class|job", "class"),
    (r"skill|abilit|spell", "skill"),
    (r"weapon", "weapon"),
    (r"armou?r|equipment", "armor"),
    (r"item|inventory|shop|loot", "item"),
    (r"troop|encounter|formation", "troop"),
    (r"enemy ai|behavior|behaviour", "behavior_tree"),
    (r"enemy|enemies|monster", "enemy"),
    (r"animation states|state machine", "state_machine"),
    (r"animation editor|animation", "animation"),
    (r"state|status|buff|effect", "state"),
    (r"composition|appearance|character", "composition"),
    (r"timeline|action", "timeline"),
    (r"vfx|particle|weather", "vfx"),
    (r"input", "input"),
    (r"flow|field", "flow"),
    (r"game systems|system|rule|resource|progression|growth", "settings"),
    (r"presentation|theme|style|window", "presentation"),
    (r"element|weakness", "skill"),
    (r"capture|companion", "troop"),
    (r"interaction|dialogue|message", "dialogue"),
    (r"audio|sound|music|bgm|sfx", "audio"),
    (r"image|sprite|tileset|texture", "image"),
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
    plain = text.replace("&", "").strip()
    for pattern, name in _LABELS:
        if pattern.search(plain):
            return name
    return None


def decorate_button(button):
    if button.property("decorated") == button.text():
        return
    button.setProperty("decorated", button.text())
    name, role = button_style(button.text())
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


def decorate(widget):
    """Decorate ``widget`` and everything inside it (safe to call again)."""
    for w in (widget, *widget.findChildren(QObject)):
        if isinstance(w, QPushButton) or (isinstance(w, QToolButton) and w.text() and not w.defaultAction()):
            decorate_button(w)
        elif isinstance(w, QTabWidget):
            decorate_tabs(w)
        elif isinstance(w, QComboBox) and w.property("decorate") is True:
            decorate_combo(w)


class _Decorator(QObject):
    def eventFilter(self, obj, event):
        kind = event.type()
        if kind == QEvent.Show:
            if isinstance(obj, QTabWidget):
                decorate_tabs(obj)
            elif isinstance(obj, QComboBox) and obj.property("decorate") is True:
                decorate_combo(obj)
            elif isinstance(obj, QAbstractButton) and not (isinstance(obj, QToolButton) and obj.defaultAction()):
                if isinstance(obj, QPushButton) or obj.text():
                    decorate_button(obj)
        return False


def install(app):
    """Decorate every button, tab widget and combo box as it is shown, app-wide."""
    if getattr(app, "_asteria_decorator", None) is None:
        app._asteria_decorator = _Decorator(app)
        app.installEventFilter(app._asteria_decorator)
    return app._asteria_decorator
