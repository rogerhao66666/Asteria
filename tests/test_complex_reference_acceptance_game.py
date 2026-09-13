from pathlib import Path

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime

ROOT=Path(__file__).resolve().parents[1]/"reference_projects"/"complex_reference_rpg"


def load_project():
    return Project.load_json(ROOT/"project.asteria.json",EditorDocument().component_registry)


def test_new_game_is_full_acceptance_start_not_midgame_save():
    project=load_project(); save=project.game_start.instantiate(project)
    assert len(save.rpg_state.party_actor_ids)==6
    assert len(save.rpg_state.party_active_actor_ids)==6
    first=save.rpg_state.party_actor_ids[0]
    state=save.rpg_state.actor_progression[first]
    assert len(state.active_class_ids)==2
    assert len(state.unlocked_class_ids)>=4
    assert state.points["ability_points"]>=4
    assert save.rpg_state.progression_allocations[first].balance("ap")>0


def test_build_customization_all_mutates_runtime_state():
    project=load_project(); save=project.game_start.instantiate(project); game=GameSessionRuntime(project,save)
    actor=save.rpg_state.party_actor_ids[0]
    state=save.rpg_state.actor_progression[actor]
    alternate=next(x for x in state.unlocked_class_ids if x not in state.active_class_ids)
    game.set_secondary_class(actor,alternate)
    assert save.rpg_state.actor_progression[actor].active_class_ids[-1]==alternate

    graph_id=f"{alternate}_tree"; graph=project.rpg_database.progression_graphs[graph_id]
    allocation=save.rpg_state.progression_allocations[actor]
    node=next(x for x in graph.nodes if allocation.preview_allocate(graph_id,x.node_id).allowed)
    before=allocation.balance("ap")
    game.allocate_progression(actor,graph_id,node.node_id)
    assert allocation.rank(graph_id,node.node_id)==1
    assert allocation.balance("ap")<before

    game.set_passives(actor,("passive_01","passive_02"),capacity=4)
    assert game._ability_state(actor).active_passives==("passive_01","passive_02")

    weapon=game.equip_definition(actor,"weapon_12")
    assert weapon.equipment.equipment_id=="weapon_12"
    next_node=next(node.node_id for node in weapon.growth.definition.nodes if weapon.growth.preview_unlock(node.node_id).allowed)
    before_rank=weapon.growth.rank(next_node)
    game.upgrade_equipment(actor,weapon.instance_id,next_node)
    assert weapon.growth.rank(next_node)==before_rank+1

    accessory=game.equip_definition(actor,"accessory_08",slot_id="accessory")
    assert accessory.equipment.equipment_id=="accessory_08"

    rotated=save.rpg_state.party_actor_ids[1:]+save.rpg_state.party_actor_ids[:1]
    game.set_active_party(rotated[:6],{x:f"slot_{i+1}" for i,x in enumerate(rotated[:6])})
    assert save.rpg_state.party_active_actor_ids==rotated[:6]


def test_repeated_equipment_changes_keep_instance_ids_unique():
    project=load_project(); save=project.game_start.instantiate(project); game=GameSessionRuntime(project,save)
    actor=save.rpg_state.party_actor_ids[0]
    for equipment_id in ("weapon_12","weapon_01","weapon_12","weapon_01"):
        game.equip_definition(actor,equipment_id,slot_id="weapon")
    ids=[item.instance_id for item in save.rpg_state.loadouts[actor].equipped()]
    assert len(ids)==len(set(ids))
    loadout=save.rpg_state.loadouts[actor]
    while loadout.equipped("accessory"):loadout.unequip("accessory",0)
    game.equip_definition(actor,"accessory_01",slot_id="accessory",replace=False)
    game.equip_definition(actor,"accessory_01",slot_id="accessory",replace=False)
    loadout.unequip("accessory",0)
    game.equip_definition(actor,"accessory_01",slot_id="accessory",replace=False)
    ids=[item.instance_id for item in loadout.equipped()]
    assert len(ids)==len(set(ids))


def test_battle_has_generic_boost_and_weakness_break_path():
    project=load_project(); save=project.game_start.instantiate(project); game=GameSessionRuntime(project,save)
    battle=game.start_encounter("boss_room")
    hero=game.active_hero_ids()[0]
    boss=next(x for x in game.active_enemy_ids() if x.startswith("astral_tyrant"))
    assert battle.battle_resources.current(hero,"momentum")>=1
    before=battle.battle_resources.current(boss,"stagger")
    result=game.execute(hero,"fire_arc",(boss,))
    outcome=battle.resolve_interaction(result.action,boss,1.0)
    assert "outcome.weak" in outcome.outcome_tags
    battle.apply_gauge_impact("stagger_system",hero,boss,trigger="battle.hit",outcome=outcome)
    assert battle.battle_resources.current(boss,"stagger")==before-1
    m=battle.battle_resources.current(hero,"momentum")
    battle.battle_resources.spend(hero,"momentum",1,trigger="test.boost")
    assert battle.battle_resources.current(hero,"momentum")==m-1


def test_level_ap_ability_points_and_player_save_round_trip(tmp_path):
    project=load_project(); save=project.game_start.instantiate(project); game=GameSessionRuntime(project,save)
    actor=save.rpg_state.party_actor_ids[0]; old=save.rpg_state.actor_progression[actor]
    info=game.grant_actor_experience(actor,1600,level_threshold=1000,ap_per_level=2,ability_points_per_level=1)
    assert info["new_level"]>old.level
    assert info["points"]["ability_points"]>old.points["ability_points"]
    graph=save.rpg_state.progression_allocations[actor]
    assert graph.balance("ap")>0

    out=tmp_path/"player.asteria-save.json"
    game.sync_world_state(); save.save_json(out)
    loaded=GameRuntimeSave.load_json(out,project)
    assert loaded.to_data()==save.to_data()
