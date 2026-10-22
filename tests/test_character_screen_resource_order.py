"""The status screen lists HP first (the game's knockout resource) unless the project sets its
own resource order; the order is saved only when set."""

from asteria.presentation.rpg_character_screen import CharacterScreenProfile


def test_resources_follow_the_profile_order_else_the_lead_resource_then_names():
    profile = CharacterScreenProfile()
    names = ("technique", "vitality", "focus")
    assert profile.ordered_resources(names, ("vitality",)) == ("vitality", "focus", "technique")
    assert profile.ordered_resources(names) == ("focus", "technique", "vitality")
    custom = CharacterScreenProfile(resource_order=("technique", "missing"))
    assert custom.ordered_resources(names, ("vitality",)) == ("technique", "focus", "vitality")


def test_the_resource_order_is_written_only_when_set():
    assert "resource_order" not in CharacterScreenProfile().to_data()
    data = CharacterScreenProfile(resource_order=("technique",)).to_data()
    assert data["resource_order"] == ["technique"]
    assert CharacterScreenProfile.from_data(data).resource_order == ("technique",)


def test_the_status_screen_shows_hp_above_mp(monkeypatch):
    """Full Verification: HP (the knockout resource) leads the status tab, as in the battle HUD
    (the resources were listed by id: technique, MP, came before vitality, HP)."""
    from pathlib import Path

    import pytest

    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from asteria.runtime.status_menu import StatusMenu

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), root)
    runtime.open()
    try:
        rows = [row[1] for row in StatusMenu(runtime.game).rows() if row[0] == "resource"]
    finally:
        runtime.close()
    assert rows[:2] == ["vitality", "technique"]
