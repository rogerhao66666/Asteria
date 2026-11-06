"""A drawn menu frame only reads the save: inside ``reading_builds()`` each actor's build, its
stat breakdown and a screen's rows are worked out once, not again by every panel showing them
(the status page resolved eight builds a frame). Outside the scope nothing is remembered, so
an equip or a point spent shows at once."""

import sys
from pathlib import Path

import pytest

from asteria.runtime.component_registry import default_component_registry

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture
def host(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import trial_ui_tour

    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    trial_ui_tour.prepare(runtime.game)
    yield runtime
    runtime.close()


def _count_resolves(game, monkeypatch):
    calls = []
    real = game._resolve_actor_build

    def counted(actor_id, apply_slots):
        calls.append(actor_id)
        return real(actor_id, apply_slots)

    monkeypatch.setattr(game, "_resolve_actor_build", counted)
    return calls


def test_inside_the_scope_a_build_is_resolved_once_outside_every_time(host, monkeypatch):
    game = host.game
    host._open_pause_page("status")
    actor = host.status_menu.actor_id
    calls = _count_resolves(game, monkeypatch)
    game.resolve_actor_build(actor)
    game.resolve_actor_build(actor)
    assert len(calls) == 2  # no scope: nothing is remembered
    with game.reading_builds():
        first = game.resolve_actor_build(actor)
        with game.reading_builds():  # a nested scope shares the outer one
            assert game.resolve_actor_build(actor) is first
        assert game.resolve_actor_build(actor, apply_slots=False) is not first
        assert game.stat_breakdown(actor) is game.stat_breakdown(actor)
    assert len(calls) == 2 + 2  # one build each way (the breakdown is kept as a whole)
    assert game._build_memo is None  # forgotten on leaving


def test_a_drawn_status_page_resolves_each_build_once(host, monkeypatch):
    host._open_pause_page("status")
    host.status_menu.view()  # opened: the page's own state is ready
    calls = _count_resolves(host.game, monkeypatch)
    with host.menu_fit():
        host._draw_status_menu()
    assert calls and len(calls) == len(set(calls))  # each actor's build at most once a frame


def test_rows_are_remembered_for_one_frame_and_follow_a_change_after_it(host):
    game = host.game
    made = []
    with game.reading_builds():
        assert game.remembered("rows", lambda: made.append(1) or [1]) == [1]
        assert game.remembered("rows", lambda: made.append(2) or [2]) == [1]
    assert game.remembered("rows", lambda: made.append(3) or [3]) == [3]
    assert made == [1, 3]
