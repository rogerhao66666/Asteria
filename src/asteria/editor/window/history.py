"""Back and forward through the editor's jumps (D108): a usage card's record, a problem, a
search result - every jump goes through ``navigate_to_problem`` - and the place it left is kept
so View ▸ Back (Ctrl+[) returns to it and View ▸ Forward (Ctrl+]) goes again.

A place is a ``navigate_to_problem`` target (``("game_system", "stat_definitions", "str")``)
worked out from what is shown, or ``("mode", workspace, page)`` where no record is chosen.
"""

from __future__ import annotations

from types import SimpleNamespace

from asteria.editor.project.workspace import WorkspaceMode

KEPT = 50  # places kept each way


class NavigationHistoryMixin:
    """The window's back and forward lists, and the place it shows now."""

    # defaults until the first jump sets them (code may read them first)
    _back = ()
    _forward = ()
    _history_project = None
    back_action = None
    forward_action = None

    def current_place(self):
        """Where the editor is: the record shown (a target ``navigate_to_problem`` opens), else
        the workspace and its page; ``None`` without a project."""
        if self.document.project is None:
            return None
        mode = self.workspace.mode
        page = None
        if mode == WorkspaceMode.RPG:
            page = self.rpg_workspace.currentWidget()
            if page is self.game_systems_editor:
                editor = self.game_systems_editor
                if editor.selected_id is not None:
                    return ("game_system", editor.kind_id, str(editor.selected_id))
            elif page is self.rpg_authoring:
                return self._record_place("rpg", self.rpg_authoring) or self._page(mode, page)
            elif page is self.combat_editor and self.combat_editor.record_id:
                editor = self.combat_editor
                return ("combat", editor.kind_id, editor.record_id)
            return self._page(mode, page)
        if mode == WorkspaceMode.BATTLE:
            return self._record_place("battle", self.battle_authoring) or ("mode", mode.value)
        if mode == WorkspaceMode.UI:
            page = self.ui_workspace.currentWidget()
            if page is self.presentation_authoring:
                place = self._record_place("presentation", page)
                if place:
                    return place
            return self._page(mode, page)
        return ("mode", mode.value)

    def _record_place(self, family, host):
        child = getattr(host, "child", None)
        ids = list(getattr(child, "selected_ids", None) or ())
        if child is None or len(ids) != 1:
            return None
        return ("record", family, child.category.currentData(), ids[0])

    def _page(self, mode, page):
        tabs = self.rpg_workspace if mode == WorkspaceMode.RPG else self.ui_workspace
        return ("mode", mode.value, tabs.indexOf(page))

    def _history(self):
        """The two lists, emptied when another project is open."""
        if self._history_project is not self.document.project:
            self._history_project = self.document.project
            self._back, self._forward = [], []
        return self._back, self._forward

    def remember_place(self, going_to):
        """Keeps where the editor is before a jump to ``going_to`` (the same place: nothing)."""
        here = self.current_place()
        back, forward = self._history()
        if here is None or here == tuple(going_to):
            return
        if not back or back[-1] != here:
            back.append(here)
            del back[:-KEPT]
        forward.clear()
        self._refresh_history_actions()

    def go_back(self):
        self._step(*self._history())

    def go_forward(self):
        back, forward = self._history()
        self._step(forward, back)

    def _step(self, source, other):
        """Opens the newest place of ``source``; where the editor was goes on ``other``."""
        here = self.current_place()
        while source:
            place = source.pop()
            if place == here:
                continue
            if self.open_place(place):
                if here is not None:
                    other.append(here)
                    del other[:-KEPT]
                break
        self._refresh_history_actions()

    def open_place(self, place):
        """Shows ``place`` without keeping a history step of its own."""
        if place[0] != "mode":
            return bool(self.open_target(SimpleNamespace(target=place)))
        mode = WorkspaceMode(place[1])
        self.workspace.set_mode(mode)
        if len(place) > 2 and place[2] >= 0:
            tabs = self.rpg_workspace if mode == WorkspaceMode.RPG else self.ui_workspace
            tabs.setCurrentIndex(place[2])
        return True

    def _refresh_history_actions(self):
        back, forward = self._history()
        if self.back_action is not None:
            self.back_action.setEnabled(bool(back))
            self.forward_action.setEnabled(bool(forward))


__all__ = ["KEPT", "NavigationHistoryMixin"]
