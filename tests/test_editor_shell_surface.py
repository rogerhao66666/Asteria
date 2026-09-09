def test_shell_class_has_core_file_and_play_actions_as_methods():
    from asteria.editor.shell import AsteriaEditorWindow

    for name in (
        "add_scene",
        "delete_scene",
        "add_entity",
        "add_component",
        "delete_selected",
        "save_project",
        "save_project_as",
        "open_project",
        "play_current_scene",
        "stop_play",
    ):
        assert callable(getattr(AsteriaEditorWindow, name, None)), name
    assert callable(getattr(AsteriaEditorWindow, "_poll_runtime_process", None))


def test_project_tree_has_selection_callback_used_during_construction():
    from asteria.editor.widgets import ProjectTreeWidget

    assert callable(getattr(ProjectTreeWidget, "_on_selection_changed", None))


def test_runtime_monitor_cleans_up_an_exited_preview():
    from asteria.editor.shell import AsteriaEditorWindow

    class Process:
        running = False
        stopped = False

        def stop(self):
            self.stopped = True

    class Session:
        active = True

        def stop(self):
            self.active = False

    class Label:
        def setText(self, text):
            self.text = text

    class Status:
        def showMessage(self, text, timeout):
            self.message = (text, timeout)

    class Window:
        runtime_process = Process()
        play_session = Session()
        console = Label()
        refreshed = False

        def statusBar(self):
            return Status()

        def _refresh_actions(self):
            self.refreshed = True

    window = Window()
    AsteriaEditorWindow._poll_runtime_process(window)
    assert window.runtime_process is None
    assert not window.play_session.active
    assert window.console.text == "Runtime preview closed"
    assert window.refreshed
