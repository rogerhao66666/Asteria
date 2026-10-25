"""The game folder's own settings file (``playable_test_manifest.json``) edited in the editor.

Templates and older games keep part of their setup only in that file: the field's background
and player sheet, the sprites of the map's figures, the battle's heroes, enemy pictures and
layouts, skill labels, music, controls words... This dialog shows every section as the same
typed settings tree as Creature screens… (a picture picker, colour button, place, number box,
yes / no or table for each value; right click adds, duplicates or removes rows and settings),
so none of it has to be typed as JSON. OK writes the file back (two-space indented, the order
kept); Cancel leaves it as it was. The file is never created here: a game folder with one
plays through the play-test runtime, one without plays the plain preview.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .creature_screens_dialog import SettingsTree
from .i18n import translate

FILE = "playable_test_manifest.json"
GENERAL = ""  # the section of the file's own plain values (title, schema, sounds...)


def manifest_path(root):
    return Path(root) / FILE


def sections(manifest):
    """``[(section, title)]``: the plain values first, then each table in the file's order."""
    out = []
    if any(not isinstance(v, dict) for v in manifest.values()):
        out.append((GENERAL, "General"))
    out.extend((k, k) for k, v in manifest.items() if isinstance(v, dict))
    return out


def section_data(manifest, section):
    if section == GENERAL:
        return {k: v for k, v in manifest.items() if not isinstance(v, dict)}
    return manifest.get(section, {})


def with_section(manifest, section, data):
    """``manifest`` with ``section`` replaced by ``data`` (the keys' order kept)."""
    if section != GENERAL:
        return {**manifest, section: data}
    out = {}
    for key, value in manifest.items():
        if isinstance(value, dict):
            out[key] = value
        elif key in data:
            out[key] = data[key]
    out.update({k: v for k, v in data.items() if k not in out})  # added in the dialog
    return out


class GameFolderSettingsDialog(QDialog):
    """``changed`` after OK: whether the file was written."""

    def __init__(self, document, root, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Game Folder Settings")
        self.resize(1200, 820)
        self.path = manifest_path(root)
        self.original = json.loads(self.path.read_text(encoding="utf-8"))
        self.work = copy.deepcopy(self.original)
        self.changed = False
        self.section = None
        self.list = QListWidget()
        for section, title in sections(self.work):
            item = QListWidgetItem(translate(title))
            item.setData(Qt.UserRole, section)
            self.list.addItem(item)
        self.tree = SettingsTree(document)
        self.tree.setColumnWidth(0, 280)
        note = QLabel(
            f"{FILE} in the game folder: the settings templates and older games keep outside "
            "the project. Right click a row to add, duplicate or remove settings."
        )
        note.setWordWrap(True)
        right = QWidget()
        column = QVBoxLayout(right)
        column.setContentsMargins(0, 0, 0, 0)
        column.addWidget(note)
        column.addWidget(self.tree, 1)
        split = QSplitter()
        split.addWidget(self.list)
        split.addWidget(right)
        split.setSizes([220, 980])
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addWidget(buttons)
        self.list.currentRowChanged.connect(self._chosen)
        self.list.setCurrentRow(0)

    def _chosen(self, row):
        self._keep()
        item = self.list.item(row)
        self.section = item.data(Qt.UserRole) if item is not None else None
        if self.section is not None:
            self.tree.load(section_data(self.work, self.section))

    def _keep(self):
        if self.section is not None:
            self.work = with_section(self.work, self.section, self.tree.data)

    def settings(self):
        """The file's contents as they are now in the dialog."""
        self._keep()
        return self.work

    def _accept(self):
        data = self.settings()
        if data != self.original:
            text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
            self.path.write_text(text, encoding="utf-8")
            self.changed = True
        self.accept()


__all__ = ["GameFolderSettingsDialog", "manifest_path", "sections", "with_section"]
