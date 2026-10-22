"""The opaque tile canvas keeps the screen opaque: on a screen format with an alpha byte (a macOS
window) the blits used to leave it at 0, so a saved screenshot showed the map see-through."""

from pathlib import Path

import pytest

ARGB = (0xFF0000, 0xFF00, 0xFF, 0xFF000000)


@pytest.fixture
def view(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "diablo_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=320, height=180
    )
    runtime.open()
    runtime._ui_mode = "field"
    for _ in range(2):
        runtime._frame([], 1 / 60)
    yield pygame, runtime.tile_view
    runtime.close()


def test_the_opaque_layer_leaves_an_alpha_screen_opaque_and_its_colours_unchanged(view):
    pygame, tiles = view

    class ArgbCanvases(dict):  # the canvas a macOS window's pixel format gives
        def get(self, key, default=None):
            w, h, opaque = key
            if opaque and key not in self:
                self[key] = pygame.Surface((w, h), 0, 32, ARGB)
            return super().get(key, default)

    backdrop = (12, 14, 20)
    plain = pygame.Surface((320, 180), 0, 32)
    plain.fill(backdrop)
    tiles._layer(plain, "below", backdrop)
    tiles._canvas, tiles._scaled_canvas = ArgbCanvases(), {}
    screen = pygame.Surface((320, 180), 0, 32, ARGB)
    screen.fill(backdrop)
    tiles._layer(screen, "below", backdrop)
    points = [(x, y) for x in range(4, 320, 29) for y in range(4, 180, 23)]
    assert {screen.get_at(p).a for p in points} == {255}
    assert [screen.get_at(p)[:3] for p in points] == [plain.get_at(p)[:3] for p in points]
