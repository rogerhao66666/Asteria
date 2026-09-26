from asteria.core import Scene
from asteria.editor.model import EditorDocument
from asteria.editor.playmode import create_play_session
from asteria.editor.runtime_launcher import launch_play_session
from asteria.project import Project


class FakeProcess:
    def __init__(self, args):
        self.args = args
        self.terminated = False
        self._poll = None

    def poll(self):
        return self._poll

    def terminate(self):
        self.terminated = True
        self._poll = 0

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self._poll = -9


def test_launcher_uses_external_module_resource_root_and_cleans_snapshot(tmp_path):
    p = Project("P")
    p.add_scene(Scene("S"))
    project_path = tmp_path / "game.asteria.json"
    session = create_play_session(EditorDocument(p, file_path=project_path))
    captured = {}

    def factory(args):
        proc = FakeProcess(args)
        captured["proc"] = proc
        return proc

    runtime = launch_play_session(
        session, popen_factory=factory, python_executable="python-test"
    )
    assert runtime.snapshot_path.exists()
    assert captured["proc"].args[:3] == ["python-test", "-m", "asteria.runtime.preview"]
    assert "--scene" in captured["proc"].args
    root_index = captured["proc"].args.index("--resource-root") + 1
    assert captured["proc"].args[root_index] == str(tmp_path.resolve())
    runtime.stop()
    assert captured["proc"].terminated
    assert not runtime.snapshot_path.exists()
