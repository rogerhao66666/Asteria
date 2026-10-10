from pathlib import Path
import json

from asteria.core import ComponentRegistry, Transform
from asteria.gameplay import GameplayAttributesComponent
from asteria.project import Project
from asteria.runtime.components2d import (
    Animator2DComponent,
    Camera2DComponent,
    Interaction2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)
from asteria.editor.playtest_profiles import PlaytestProfileLibrary
from asteria.editor.model import EditorDocument
from asteria.editor.playmode import create_play_session


REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg"


def registry():
    r = ComponentRegistry()
    for t in (
        Transform,
        SpriteRenderer2D,
        Camera2DComponent,
        Interaction2DComponent,
        Animator2DComponent,
        TileMap2DComponent,
        GameplayAttributesComponent,
    ):
        r.register(t)
    return r


def load_project():
    return Project.load_json(REF / "project.asteria.json", registry())


def test_reference_project_has_five_developer_profiles():
    lib = PlaytestProfileLibrary(REF)
    values = lib.profiles()
    assert {x.profile_id for x in values} == {"default", "early", "mid", "endgame", "boss_stress"}
    assert lib.default().profile_id == "default"


def test_profile_is_not_player_save_schema():
    data = json.loads((REF / "playtest_profiles/boss_stress.asteria-playtest.json").read_text())
    assert data["schema"] == "asteria.playtest_profile"
    assert data["runtime_state"]["schema"] == "asteria.game_runtime_save"


def test_profile_instantiates_fresh_runtime_each_time():
    p = load_project()
    lib = PlaytestProfileLibrary(REF)
    a = lib.instantiate("boss_stress", p)
    b = lib.instantiate("boss_stress", p)
    assert a is not b
    assert a.to_data() == b.to_data()
    a.rpg_state.currencies["gold"] += 123
    assert a.to_data() != b.to_data()


def test_boss_profile_has_six_active_and_near_boss():
    p = load_project()
    s = PlaytestProfileLibrary(REF).instantiate("boss_stress", p)
    assert len(s.rpg_state.party_active_actor_ids) == 6
    assert s.player_position is not None


def test_play_session_carries_profile_id_without_player_save():
    p = load_project()
    d = EditorDocument(p, component_registry=registry())
    d.file_path = REF / "project.asteria.json"
    session = create_play_session(d, playtest_profile_id="boss_stress")
    assert session.playtest_profile_id == "boss_stress"
    assert session.runtime_save is None


def test_preview_accepts_playtest_profile_argument():
    text = (Path(__file__).parents[1] / "src/asteria/runtime/preview.py").read_text()
    assert "--playtest-profile" in text
    assert "PlaytestProfileLibrary" in text


def test_shell_normal_run_uses_project_game_start_not_profile_or_player_save():
    text = (Path(__file__).parents[1] / "src/asteria/editor/shell.py").read_text()
    body = text.split("def play_project", 1)[1].split("def play_current_scene", 1)[0]
    assert "from_start=True" in body
    assert "selected_playtest_profile_id" not in body
    assert "loaded_save" not in body


def test_profile_files_are_valid_project_runtime_templates():
    p = load_project()
    lib = PlaytestProfileLibrary(REF)
    for profile in lib.profiles():
        state = profile.instantiate(p)
        assert state.project_id == p.id
        state.validate(p)
