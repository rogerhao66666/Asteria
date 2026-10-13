from copy import deepcopy
from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.rpg import ActorProgressionState, RpgRuntimeState
from asteria.runtime.game_save import GameRuntimeSave

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg"
PROJECT = REF / "project.asteria.json"


def load_project():
    d = EditorDocument()
    return Project.load_json(PROJECT, d.component_registry)


def save_path(name):
    return REF / "saves" / f"{name}.asteria-save.json"


@pytest.mark.parametrize("name", ["early", "mid", "endgame_complex", "boss_stress"])
def test_reference_save_loads_and_validates(name):
    p = load_project()
    save = GameRuntimeSave.load_json(save_path(name), p)
    assert save.validate(p)
    assert save.rpg_state.to_data()["version"] == 8
    assert save.event_context.get_variable("reference_profile") == name


def test_reference_saves_scale_in_complexity():
    p = load_project()
    saves = {
        n: GameRuntimeSave.load_json(save_path(n), p)
        for n in ("early", "mid", "endgame_complex", "boss_stress")
    }
    assert [len(saves[n].rpg_state.party_actor_ids) for n in saves] == [6, 8, 12, 12]
    assert (
        saves["early"].rpg_state.currencies["gold"]
        < saves["mid"].rpg_state.currencies["gold"]
        < saves["endgame_complex"].rpg_state.currencies["gold"]
        < saves["boss_stress"].rpg_state.currencies["gold"]
    )
    assert len(saves["boss_stress"].rpg_state.actor_progression) == 12
    assert min(x.level for x in saves["boss_stress"].rpg_state.actor_progression.values()) >= 80


def test_endgame_save_persists_character_build_state():
    p = load_project()
    save = GameRuntimeSave.load_json(save_path("endgame_complex"), p)
    state = save.rpg_state
    actor_id = state.party_actor_ids[0]
    progress = state.actor_progression[actor_id]
    snapshot = state.actor_snapshots[actor_id]
    loadout = state.loadouts[actor_id]
    allocation = state.progression_allocations[actor_id]

    assert progress.level >= 58
    assert progress.experience >= 74200
    assert len(progress.unlocked_class_ids) >= 6
    assert len(progress.active_class_ids) == 2
    assert len(snapshot.ability_state["active_passives"]) == 4
    assert len(loadout.equipped("weapon")) == 1
    assert len(loadout.equipped("accessory")) == 2
    weapon = loadout.equipped("weapon")[0]
    assert weapon.attachments["rune"].attachment_id.startswith("rune_")
    assert weapon.growth is not None
    assert weapon.growth.rank("temper_2") == 1
    assert any(
        allocation.rank(graph_id, node.node_id) > 0
        for graph_id, graph in allocation.definitions.items()
        for node in graph.nodes
    )


def test_boss_stress_save_is_near_encounter_and_tracks_world_state():
    p = load_project()
    save = GameRuntimeSave.load_json(save_path("boss_stress"), p)
    assert save.player_facing == "right"
    assert save.player_position == (38.0, 0.0)
    assert save.event_context.get_switch("boss_gate_unlocked")
    assert save.event_context.get_local("astral_tyrant", "challenged") is True


def test_actor_progression_state_rejects_locked_active_class():
    with pytest.raises(ValueError, match="active classes must be unlocked"):
        ActorProgressionState(
            10, 100, unlocked_class_ids=("vanguard",), active_class_ids=("arcanist",)
        )


def test_rpg_runtime_v3_backward_read_defaults_actor_progression_empty():
    p = load_project()
    current = GameRuntimeSave.load_json(save_path("early"), p).rpg_state.to_data()
    legacy = deepcopy(current)
    legacy["version"] = 3
    legacy.pop("actor_progression")
    legacy.pop("party_active_actor_ids")
    legacy.pop("party_placements")
    legacy.pop("shop_stock")
    legacy.pop("quests")
    legacy.pop("world")
    legacy.pop("equipment_bag")
    restored = RpgRuntimeState.from_data(legacy, p.rpg_database)
    assert restored.actor_progression == {}
    assert restored.party_actor_ids


@pytest.mark.parametrize("name", ["early", "mid", "endgame_complex", "boss_stress"])
def test_reference_save_roundtrip_is_exact(name, tmp_path):
    p = load_project()
    original = GameRuntimeSave.load_json(save_path(name), p)
    path = tmp_path / f"{name}.json"
    original.save_json(path)
    restored = GameRuntimeSave.load_json(path, p)
    assert restored.to_data() == original.to_data()


def test_reference_save_builder_is_deterministic(tmp_path):
    from reference_projects.complex_reference_rpg.build_saves import write_saves

    p1 = write_saves(PROJECT, tmp_path / "a")
    p2 = write_saves(PROJECT, tmp_path / "b")
    for name in p1:
        assert p1[name].read_text() == p2[name].read_text()
