import json

import pytest

from asteria.editor import (
    ProjectWorkspaceController,
    ProjectWorkspaceError,
    RecentProjectStore,
)


def controller(tmp_path):
    return ProjectWorkspaceController(recent_store=RecentProjectStore(tmp_path / "recent.json"))


def test_new_project_is_immediately_real_and_reloadable(tmp_path):
    c = controller(tmp_path)
    path = tmp_path / "game.asteria.json"
    p = c.new_project("Reference RPG", path)
    assert path.exists()
    assert p.name == "Reference RPG"
    assert len(p.scenes()) == 1
    assert p.startup_scene_id == p.scenes()[0].id
    assert not c.document.dirty

    other = controller(tmp_path)
    loaded = other.open_project(path)
    assert loaded.to_data() == p.to_data()


def test_recent_projects_persist_and_deduplicate(tmp_path):
    store = RecentProjectStore(tmp_path / "recent.json", capacity=2)
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    store.add(a)
    store.add(b)
    store.add(a)
    assert store.items == (str(a.resolve()), str(b.resolve()))
    loaded = RecentProjectStore(tmp_path / "recent.json", capacity=2)
    loaded.load()
    assert loaded.items == store.items


def test_save_as_updates_document_and_recent(tmp_path):
    c = controller(tmp_path)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    c.new_project("Game", first)
    c.save_as(second)
    assert c.document.file_path == second.resolve()
    assert c.state().recent_projects[0] == str(second.resolve())


def test_validation_is_exposed_without_crashing_editor(tmp_path):
    c = controller(tmp_path)
    c.new_project("Game", tmp_path / "game.json")
    c.document.project.startup_scene_id = "missing"
    errors = c.validate_project()
    assert errors
    assert "startup" in errors[0]


def test_run_uses_isolated_project_snapshot(tmp_path):
    c = controller(tmp_path)
    c.new_project("Game", tmp_path / "game.json")
    source = c.document.project
    session = c.run()
    assert session.runtime_project is not source
    assert session.runtime_project.to_data() == source.to_data()
    session.runtime_project.name = "Runtime Mutation"
    assert source.name == "Game"
    assert c.state().running


def test_run_stop_run_cycle(tmp_path):
    c = controller(tmp_path)
    c.new_project("Game", tmp_path / "game.json")
    first = c.run()
    with pytest.raises(ProjectWorkspaceError):
        c.run()
    c.stop()
    assert not first.active
    assert not c.state().running
    second = c.run()
    assert second.active


def test_open_is_blocked_while_playing(tmp_path):
    a = controller(tmp_path)
    pa = tmp_path / "a.json"
    pb = tmp_path / "b.json"
    a.new_project("A", pa)
    b = controller(tmp_path)
    b.new_project("B", pb)
    a.run()
    with pytest.raises(ProjectWorkspaceError):
        a.open_project(pb)


def test_state_reports_workspace_capabilities(tmp_path):
    c = controller(tmp_path)
    empty = c.state()
    assert empty.project_name is None
    assert not empty.can_run
    c.new_project("Game", tmp_path / "game.json")
    state = c.state()
    assert state.project_name == "Game"
    assert state.scene_count == 1
    assert state.startup_scene_id
    assert state.can_run
    assert not state.dirty


def test_recent_store_can_prune_missing_files(tmp_path):
    store = RecentProjectStore(tmp_path / "recent.json")
    live = tmp_path / "live.json"
    live.write_text("{}")
    store.add(tmp_path / "missing.json")
    store.add(live)
    assert store.remove_missing() == (str(live.resolve()),)


def test_recent_store_schema_is_validated(tmp_path):
    p = tmp_path / "recent.json"
    p.write_text(json.dumps({"schema": "wrong", "projects": []}))
    with pytest.raises(ProjectWorkspaceError):
        RecentProjectStore(p).load()
