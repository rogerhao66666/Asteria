from pathlib import Path

from asteria.reference_world import build_reference_world
from asteria.runtime.reference_runtime import ReferenceRuntime, run_reference_runtime


class FakeTextureBackend:
    def __init__(self, actions=None):
        self.actions = list(actions or [{}])
        self.i = 0
        self.draws = []
        self.opened = False
        self.closed = False

    def should_close(self):
        return False

    def tick(self, fps):
        return 1 / 60

    def poll_actions(self):
        a = self.actions[min(self.i, len(self.actions) - 1)]
        self.i += 1
        return a

    def begin_frame(self):
        pass

    def end_frame(self):
        pass

    def load_texture(self, asset_id, path):
        from asteria.assets import TextureResource

        return TextureResource(asset_id, 128, 128, object())

    def draw_texture(self, resource, draw):
        self.draws.append(draw)


def make_runtime():
    b = build_reference_world()
    return ReferenceRuntime.load(
        b.project, b.scene, Path(__file__).resolve().parents[1]
    )


def test_reference_runtime_builds_map_and_hero_draws():
    runtime = make_runtime()
    draws = runtime.draw_commands(960, 540)
    assert len(draws) > 10
    assert any(d.layer == 100 for d in draws)


def test_reference_runtime_player_moves_and_camera_follows():
    runtime = make_runtime()
    start = runtime.hero.get(
        __import__("asteria.core", fromlist=["Transform"]).Transform
    ).x
    runtime.step({"move_right": 1.0}, 0.1)
    end = runtime.hero.get(
        __import__("asteria.core", fromlist=["Transform"]).Transform
    ).x
    assert end > start
    assert runtime.camera.x != 0


def test_reference_runtime_resolves_player_and_camera_by_stable_id():
    bundle = build_reference_world()
    bundle.hero.name = "Renamed Hero"
    bundle.camera.name = "Renamed Camera"
    runtime = ReferenceRuntime.load(
        bundle.project, bundle.scene, Path(__file__).resolve().parents[1]
    )
    assert runtime.hero is bundle.hero
    assert runtime.game_camera_entity is bundle.camera


def test_runtime_loop_renders_real_texture_commands(monkeypatch):
    runtime = make_runtime()
    # No filesystem decode occurs in fake loader; source paths are still resolved.
    backend = FakeTextureBackend([{"move_right": 1.0}, {}])
    frames = run_reference_runtime(runtime, backend, 960, 540, max_frames=2)
    assert frames == 2
    assert len(backend.draws) > 20
