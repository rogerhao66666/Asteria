from asteria.core import Application, Scene, System
from asteria.platform import HeadlessBackend


class Count(System):
    def __init__(self):
        self.n = 0

    def update(self, scene, dt):
        self.n += 1


def test_application_scene_system_flow():
    b = HeadlessBackend(close_after=2)
    app = Application(b)
    s = Scene()
    sys = Count()
    s.scheduler.add(sys)
    app.set_scene(s)
    app.run(max_frames=2)
    assert sys.n == 2 and not app.running and not s.entered
