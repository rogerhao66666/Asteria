"""Play-testing from the editor: starting, restarting and stopping the game process and reading
its log."""

from __future__ import annotations

import os

from asteria.core import Transform
from asteria.editor.project.playmode import PlayModeError, create_play_session
from asteria.editor.project.runtime_launcher import RuntimeLaunchError, launch_play_session

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QMessageBox
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None


class PlayTestMixin:
    """Play-testing from the editor."""

    def _start_play(self, *, from_start, spawn=None, title="Run Project"):
        """Launch the play-test with the debug channel and log capture (EDT-10, EDT-11)."""
        try:
            self.play_session = create_play_session(self.document, from_start=from_start)
            self.runtime_process = launch_play_session(
                self.play_session, debug=True, capture_log=True, spawn=spawn
            )
        except (PlayModeError, RuntimeLaunchError) as exc:
            if self.play_session is not None:
                self.play_session.stop()
            self.play_session = None
            self.runtime_process = None
            QMessageBox.warning(self, title, str(exc))
            return False
        self._last_play = {"from_start": from_start, "spawn": spawn, "title": title}
        self._shown_log = ""
        if self.runtime_process.debug_port is not None:
            self.debugger_widget.attach(
                self.runtime_process.debug_port, self.runtime_process.debug_token
            )
        where = "" if spawn is None else f" from ({spawn[0]:g}, {spawn[1]:g})"
        self.console.setText(f"Playing: {self.play_session.runtime_scene.name}{where}")
        console_dock = self.findChild(QDockWidget, "ConsoleDock")
        # the play log, even in a workspace that keeps its bottom panels closed
        console_dock.show()
        console_dock.raise_()
        self.statusBar().showMessage(f"Playing — {self.play_session.runtime_scene.name}{where}")
        self._refresh_actions()
        return True

    def play_project(self):
        return self._start_play(from_start=True)

    def play_menu_screen(self, screen_id):
        """Run the project from its start, opened on one menu screen (Menu Screens ▸ Layout ▸
        Open in game)."""
        os.environ["ASTERIA_OPEN_MENU"] = str(screen_id)
        try:
            return self._start_play(from_start=True, title="Open in Game")
        finally:
            os.environ.pop("ASTERIA_OPEN_MENU", None)

    def play_current_scene(self):
        return self._start_play(from_start=False, title="Play")

    def play_from_selection(self):
        """Play the current scene with the player starting at the selected entity's position."""

        entity = self._selected_entity()
        if entity is None or not entity.has(Transform):
            QMessageBox.information(
                self, "Play from Selection", "Select an entity in the scene first."
            )
            return False
        t = entity.get(Transform)
        return self._start_play(from_start=False, spawn=(t.x, t.y), title="Play from Selection")

    def restart_play(self):
        """Fast restart: stop the running play-test and launch it again the same way."""
        last = getattr(self, "_last_play", None)
        if last is None:
            return self.play_project()
        if self.play_session is not None and self.play_session.active:
            self.stop_play()
        return self._start_play(**last)

    def stop_play(self):
        if self.play_session is None or not self.play_session.active:
            return False
        self._flush_runtime_log()
        self.debugger_widget.detach()
        if self.runtime_process is not None:
            self.runtime_process.stop()
            self.runtime_process = None
        self.play_session.stop()
        self.console.setText("Play session stopped")
        self.statusBar().showMessage("Play session stopped", 2000)
        self._refresh_actions()
        return True

    def _flush_runtime_log(self):
        """Show what the game printed so far in the Console (play-test log panel)."""
        if self.runtime_process is None:
            return
        text = self.runtime_process.read_log()
        if text and text != getattr(self, "_shown_log", ""):
            self._shown_log = text
            self.console.setText(text)

    def _poll_runtime_process(self):
        if self.runtime_process is None:
            return
        flush = getattr(self, "_flush_runtime_log", None)
        if flush is not None:
            flush()
        if self.runtime_process.running:
            return
        debugger = getattr(self, "debugger_widget", None)
        if debugger is not None:
            debugger.detach()
        self.runtime_process.stop()
        self.runtime_process = None
        if self.play_session is not None and self.play_session.active:
            self.play_session.stop()
        if getattr(self, "_shown_log", ""):
            self.console.append("Game closed")  # keep the play-test log visible
        else:
            self.console.setText("Game closed")
        self.statusBar().showMessage("Game closed", 2000)
        self._refresh_actions()
