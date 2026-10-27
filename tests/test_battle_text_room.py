"""Full Verification boss fight, headless: the boss's state names wait with its name while the
camera zooms in (they fell on the boss), and no skill row's name runs into its cost when it is
drawn - measured with the battle font itself, at the selected row's (larger) size."""

import sys
from collections import Counter
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture
def battle(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.syspath_prepend(str(DEMO))
    import run_trial_smoke as smoke

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    rt.open()
    smoke.prepare(rt.game, Counter(), "brave")
    rt._ui_mode = "field"
    rt._frame([], 1 / 60)
    rt.game.start_encounter("boss_room")
    rt._battle_presentation.begin()
    rt._advance_to_hero_turn()
    yield pygame, rt
    rt.close()
    sys.modules.pop("run_trial_smoke", None)


def test_state_names_wait_with_the_names_while_the_camera_zooms_in(battle):
    _pygame, rt = battle
    adapter = rt._battle_presentation
    zoomed, idle = [], None
    for _ in range(400):
        rt._frame([], 1 / 60)
        if adapter.screen.overhead_hidden:
            zoomed += [b.caption for b in rt.battle_extras_blocks]
        elif zoomed:
            idle = list(rt.battle_extras_blocks)
            break
    assert zoomed and all(caption is None for caption in zoomed)
    boss = next(b for b in idle if b.member_id.startswith("crimson_warlord"))
    # back over its name once the camera is still
    assert boss.caption is not None
    assert boss.member_id in adapter.screen.composer.overhead_labels


def test_no_skill_name_runs_into_its_cost(battle):
    pygame, rt = battle
    adapter = rt._battle_presentation
    for _ in range(240):  # the intro zoom and the hero's turn
        rt._frame([], 1 / 60)
    for key in (pygame.K_DOWN, pygame.K_RETURN):  # Fight -> Skills
        rt._frame([pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="")], 1 / 60)
        for _ in range(10):
            rt._frame([], 1 / 60)
    menu = adapter.screen.action_menu
    pages = menu.view.page_count
    assert pages > 1  # the skill list is open (Roger has many)
    backend, theme = adapter._ui_backend, adapter.renderer.theme
    scale = backend.scale

    def width(value, size):
        return backend._text_image(value, (255, 255, 255, 255), size)[0].get_width() / scale

    checked = 0
    for page in range(pages):  # every skill, page by page
        menu.set_page(page)
        texts = adapter.draw().frame.texts
        rows = ("action_selected", "action_entry", "action_disabled")
        names = [t for t in texts if t.role in rows]
        for cost in (t for t in texts if t.role in ("action_cost", "action_cost_disabled")):
            name = next(t for t in names if abs(t.y - cost.y) < 0.5)
            # any row may be the selected one: its name is drawn a size larger
            right = name.x + width(name.text, theme.font_size + 1)
            left = cost.x - width(cost.text, theme.font_size)
            assert right + 1.0 <= left, (page, name.text, cost.text, right, left)
            checked += 1
    assert checked > 20
