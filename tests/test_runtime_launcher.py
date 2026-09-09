from pathlib import Path
from asteria.core import Scene
from asteria.project import Project
from asteria.editor.model import EditorDocument
from asteria.editor.playmode import create_play_session
from asteria.editor.runtime_launcher import launch_play_session

class FakeProcess:
    def __init__(self,args):
        self.args=args;self.terminated=False;self._poll=None
    def poll(self):return self._poll
    def terminate(self):self.terminated=True;self._poll=0
    def wait(self,timeout=None):return 0
    def kill(self):self._poll=-9

def test_launcher_uses_external_module_and_cleans_snapshot():
    p=Project("P");s=p.add_scene(Scene("S"))
    session=create_play_session(EditorDocument(p))
    captured={}
    def factory(args):
        proc=FakeProcess(args);captured["proc"]=proc;return proc
    runtime=launch_play_session(session,popen_factory=factory,python_executable="python-test")
    assert runtime.snapshot_path.exists()
    assert captured["proc"].args[:3]==["python-test","-m","asteria.runtime.preview"]
    assert "--scene" in captured["proc"].args
    runtime.stop()
    assert captured["proc"].terminated
    assert not runtime.snapshot_path.exists()
