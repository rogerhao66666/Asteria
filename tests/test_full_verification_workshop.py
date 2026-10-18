"""The workshop screen of the playtest host: refine, sockets and attribute points by keys."""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


@pytest.fixture
def host(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    yield runtime
    runtime.close()


def _press(host, key):
    host._frame([host.pg.event.Event(host.pg.KEYDOWN, key=key)], 0.016)


def test_the_workshop_refines_sockets_and_spends_attribute_points(host):
    pg = host.pg
    host._ui_mode = "build"
    _press(host, pg.K_8)
    assert host._ui_mode == "workshop"
    actor = host._menu_actor()
    weapon = host._current_weapon(actor)
    level = weapon.refine_level
    for _ in range(8):
        _press(host, pg.K_r)
    assert weapon.refine_level > level or "Refine" in host._workshop_message
    allocation = host.save.rpg_state.progression_allocations[actor]
    allocation.grant("stat_points", 2)
    before = sum(allocation.allocations.get("attributes", {}).values())
    _press(host, pg.K_a)
    assert sum(allocation.allocations.get("attributes", {}).values()) == before + 1
    bag = host.save.rpg_state.inventory
    bag.add("ruby_item", 1)
    free = [s for s in weapon.equipment.sockets if s.socket_id not in weapon.attachments]
    _press(host, pg.K_s)
    if any(not s.locked for s in free):
        assert "Socketed" in host._workshop_message or weapon.attachments
    _press(host, pg.K_c)
    assert host._ui_mode == "build"
    host.capture()  # the screen draws
