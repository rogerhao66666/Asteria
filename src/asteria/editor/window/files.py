"""Opening, saving, exporting and importing projects, and asking before unsaved changes go."""

from __future__ import annotations

import sys
from pathlib import Path

from asteria.editor.project.storage import EditorStorageError, load_document, save_document
from asteria.editor.project.workspace import WorkspaceMode

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None
from asteria.editor.assets.resource_resolver import EditorResourceError


class ProjectFilesMixin:
    """Opening, saving, exporting and importing projects."""

    def set_project(self, project, file_path=None):
        self.document.set_project(project, file_path=file_path)
        if file_path is not None:
            self._resolve_project_resources()
        else:
            self.document.asset_views.clear()
            self.set_tilemap_render_source(None)
        self._show_new_project()

    def _show_new_project(self):
        """After the document took another project (set, opened, made from a template or
        imported): the old project's play-test stops (it was left running), the code page
        reads the new project's script and every workspace is rebuilt now - none may keep the
        old one's records, even before it is opened."""
        if self.play_session is not None and self.play_session.active:
            self.stop_play()
        self.play_session = None
        self.runtime_process = None
        self.code_workspace.load_default_script()
        self.refresh_all()
        for mode in WorkspaceMode:
            self._ensure_workspace_fresh(mode, every_tab=True)
        QTimer.singleShot(0, self.viewport, self.viewport.frame_initial)

    def _confirm_discard(self, question):
        """True when there is nothing unsaved, or the author answers Yes to ``question``."""
        if not self.document.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Unsaved Changes",
            f"This project has unsaved changes. {question}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def save_project(self):
        if self.document.project is None:
            return False
        if self.document.file_path is None:
            return self.save_project_as()
        try:
            save_document(self.document)
        except EditorStorageError as exc:
            QMessageBox.critical(self, "Save Project", str(exc))
            return False
        self.statusBar().showMessage(f"Saved {self.document.file_path}", 3000)
        self.refresh_all()
        return True

    def save_project_as(self):
        if self.document.project is None:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Asteria Project",
            "",
            "Asteria Project (*.asteria.json);;JSON (*.json)",
        )
        if not path:
            return False
        try:
            save_document(self.document, path)
        except EditorStorageError as exc:
            QMessageBox.critical(self, "Save Project", str(exc))
            return False
        self.statusBar().showMessage(f"Saved {self.document.file_path}", 3000)
        self.refresh_all()
        return True

    def export_game(self, output, *, name=None, pyz=True, app=False):
        """Save, then package the project (AST-06): game folder, single-file .pyz, optional macOS
        .app."""
        from asteria.project_tools import package_game

        if self.document.project is None or not self.document.file_path:
            raise ValueError("save the project to a file before exporting")
        if self.document.dirty and not self.save_project():
            raise ValueError("the project could not be saved")
        result = package_game(self.document.file_path, output, name=name, pyz=pyz, app=app)
        self.statusBar().showMessage(f"Exported {result['pyz'] or result['folder']}", 5000)
        return result

    def export_game_dialog(self):
        from PySide6.QtWidgets import (
            QCheckBox,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLabel,
            QLineEdit,
        )

        from asteria.frozen import player_runtime

        if self.document.project is None:
            return None
        standalone = player_runtime() is not None  # the standalone app carries a player
        dialog = QDialog(self)
        dialog.setWindowTitle("Export Game")
        name = QLineEdit(self.document.project.name or "Asteria Game")
        pyz = QCheckBox("Single-file game (.pyz, needs Python)")
        pyz.setChecked(not standalone)
        if sys.platform == "darwin":
            app = QCheckBox("macOS app (.app)")
        else:
            app = QCheckBox("Game folder that runs without Python")
        app.setChecked(sys.platform == "darwin" or standalone)
        app.setEnabled(sys.platform == "darwin" or standalone)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form = QFormLayout(dialog)
        form.addRow("Game name", name)
        form.addRow("", pyz)
        form.addRow("", app)
        if standalone:
            note = "The app runs without Python; the .pyz and the game folder need Python 3.12+."
        else:
            note = (
                "The game folder always carries the engine; players need Python 3.12+ with "
                "pygame-ce."
            )
        form.addRow(QLabel(note))
        form.addRow(buttons)
        if dialog.exec() != QDialog.Accepted:
            return None
        output = QFileDialog.getExistingDirectory(self, "Export To Folder")
        if not output:
            return None
        try:
            result = self.export_game(
                output, name=name.text().strip() or None, pyz=pyz.isChecked(), app=app.isChecked()
            )
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Export Game", str(exc))
            return None
        lines = [f"Game folder: {result['folder']}"]
        if result["pyz"]:
            lines.append(f"Single file: {result['pyz']}")
        if result["app"]:
            kind = "no Python needed" if result.get("standalone") else "needs Python"
            lines.append(f"Game app: {result['app']} ({kind})")
        missing = result["report"].missing
        if missing:
            lines.append("Missing: " + ", ".join(missing))
        lines.extend(result["report"].warnings)
        QMessageBox.information(self, "Export Game", "\n".join(lines))
        return result

    def open_project(self):
        if not self._confirm_discard("Open another project anyway?"):
            return False
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Asteria Project", "", "Asteria Project (*.asteria.json *.json)"
        )
        if not path:
            return False
        try:
            load_document(self.document, path)
            self._resolve_project_resources()
        except (EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "Open Project", str(exc))
            return False
        self._show_new_project()
        return True

    def new_from_template(self, template_id, name, folder):
        """Copy a project template into ``folder`` and open it."""
        from asteria.editor.project.templates import create_from_template

        path = create_from_template(template_id, name, folder)
        load_document(self.document, path)
        self._resolve_project_resources()
        self._show_new_project()
        guide = Path(path).parent / "START_HERE.md"
        if guide.is_file():  # where every rule lives in this project
            self.console.setText(f"New project from a template.\n\n{guide.read_text()}")
        return path

    def new_from_template_dialog(self):
        from PySide6.QtWidgets import QInputDialog

        from asteria.editor.project.templates import available_templates
        from asteria.editor.ui.i18n import translate

        templates = available_templates()
        if not templates:
            QMessageBox.information(
                self, "New from Template", "No project templates are installed."
            )
            return None
        if not self._confirm_discard("Start a new project anyway?"):
            return None
        titles = [f"{translate(t.title)} - {translate(t.description)}" for t in templates]
        choice, ok = QInputDialog.getItem(self, "New from Template", "Template:", titles, 0, False)
        if not ok:
            return None
        template = templates[titles.index(choice)]
        name, ok = QInputDialog.getText(  # the name keeps its English: it becomes the folder
            self, "New from Template", "Project name:", text=template.title.split(" (")[0]
        )
        if not ok or not name.strip():
            return None
        parent = QFileDialog.getExistingDirectory(self, "Folder to create the project in")
        if not parent:
            return None
        folder = Path(parent) / name.strip().replace(" ", "_").lower()
        try:
            return self.new_from_template(template.template_id, name, folder)
        except (OSError, ValueError, EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "New from Template", str(exc))
            return None

    def import_mv_project(self, source, output):
        """Import an RPG Maker MV project into a new Asteria project folder and open it (W-18)."""
        from asteria.assets.rpg_maker_mv.project import import_mv_project

        project_path, result = import_mv_project(source, output)
        load_document(self.document, project_path)
        self._resolve_project_resources()
        self._show_new_project()
        lines = [f"{issue.code}: {issue.message}" for issue in result.issues]
        self.console.setText(
            f"Imported {len(result.project.scenes())} maps from {source}\n"
            + "\n".join(lines[:200])
        )
        return project_path, result

    def import_mv_project_dialog(self):
        if not self._confirm_discard("Import into a new project anyway?"):
            return None
        source = QFileDialog.getExistingDirectory(
            self, "RPG Maker MV Project Folder (contains data/)"
        )
        if not source:
            return None
        output = QFileDialog.getExistingDirectory(self, "New Asteria Project Folder")
        if not output:
            return None
        try:
            project_path, result = self.import_mv_project(source, output)
        except (OSError, ValueError, EditorStorageError, EditorResourceError) as exc:
            QMessageBox.critical(self, "Import RPG Maker MV Project", str(exc))
            return None
        QMessageBox.information(
            self,
            "Import RPG Maker MV Project",
            f"Imported {len(result.project.scenes())} maps into {project_path}.\n"
            f"{len(result.issues)} notes (content kept out or simplified) are listed in the "
            f"Console.",
        )
        return project_path

    def closeEvent(self, event):
        if self.play_session is not None and self.play_session.active:
            self.stop_play()
        if self.document.dirty:
            answer = QMessageBox.question(
                self,
                "Unsaved Changes",
                "Save changes before closing Asteria?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save,
            )
            if answer == QMessageBox.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.Save and not self.save_project():
                event.ignore()
                return
        if self.layout_settings is not None:
            self.save_layout()
        self.multiplayer_workspace.shutdown()
        event.accept()
