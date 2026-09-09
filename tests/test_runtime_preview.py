from asteria.core import Entity, Scene, Transform
from asteria.project import Project
from asteria.runtime.preview import run_preview


class FakeBackend:
    def __init__(self):
        self.frames = 0
        self.closed = False
        self.markers = []

    def open(self, title, width, height):
        self.title = title
        self.size = (width, height)

    def tick(self, fps):
        return 1 / fps

    def begin_frame(self):
        pass

    def draw_grid(self, *args):
        pass

    def draw_marker(self, *args):
        self.markers.append(args)

    def end_frame(self):
        self.frames += 1

    def should_close(self):
        return self.frames >= 1

    def close(self):
        self.closed = True


def test_preview_runs_snapshot_with_backend_adapter(tmp_path):
    p = Project("Preview")
    s = p.add_scene(Scene("Town"))
    e = s.add_entity(Entity("Hero"))
    e.add_component(Transform(10, 20))
    path = tmp_path / "preview.json"
    p.save_json(path)
    b = FakeBackend()
    assert run_preview(path, s.id, backend=b) == 0
    assert b.frames == 1 and b.closed
    assert len(b.markers) == 1
    x, y, *_ = b.markers[0]
    assert (x, y) == (490, 290)


def test_pygame_runtime_backend_module_imports():
    from asteria.platform.backend import RuntimeBackend, TextureBackend
    from asteria.platform.pygame_backend import (
        PygameRuntimeBackend,
        PygameTextureBackend,
    )

    assert issubclass(PygameRuntimeBackend, (RuntimeBackend, TextureBackend))
    assert issubclass(PygameTextureBackend, TextureBackend)
