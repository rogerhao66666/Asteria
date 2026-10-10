from copy import deepcopy
from pathlib import Path

from asteria.editor import EditorDocument
from asteria.presentation import CharacterScreenRuntime
from asteria.project import Project
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime

REF=Path(__file__).parents[1]/"reference_projects/complex_reference_rpg"
PROJECT=REF/"project.asteria.json"
SAVE=REF/"saves"/"boss_stress.asteria-save.json"


def load():
    d=EditorDocument()
    p=Project.load_json(PROJECT,d.component_registry)
    s=GameRuntimeSave.load_json(SAVE,p)
    return p,s,GameSessionRuntime(p,s)


def test_runtime_build_edits_are_visible_before_battle():
    p,s,g=load()
    actor=s.rpg_state.party_active_actor_ids[0]
    g.set_active_classes(actor,("arcanist","oracle"))
    g.learn_ability(actor,"meteor")
    g.equip_passive(actor,"passive_01",capacity=8)

    build=g.resolve_actor_build(actor)
    assert "fire_arc" in build.abilities
    assert "heal" in build.abilities
    assert "meteor" in build.abilities
    assert "passive_01" in build.active_passives

    profile=p.battle_presentation_library.require("rpg_character_screen","default")
    view=CharacterScreenRuntime(profile).project(
        build,
        display_name=p.rpg_database.actors[actor].display_name,
        loadout=s.rpg_state.loadouts[actor],
        progression=s.rpg_state.progression,
        actor_definition=p.rpg_database.actors[actor],
    )
    assert view.actor_id==actor
    assert any(x.ability_id=="meteor" for x in view.abilities)


def test_party_active_and_formation_state_are_real_save_state():
    _,s,g=load()
    roster=s.rpg_state.party_actor_ids
    chosen=(roster[0],roster[1],roster[2],roster[3],roster[4],roster[6])
    placements={actor:f"slot_{i+1}" for i,actor in enumerate(chosen)}
    g.set_active_party(chosen,placements)
    assert s.rpg_state.party_active_actor_ids==chosen
    assert s.rpg_state.party_placements==placements


def test_full_project_save_field_interaction_battle_reward_reload(tmp_path):
    p,s,g=load()
    project_before=deepcopy(p.to_data())
    actor=s.rpg_state.party_active_actor_ids[0]

    # Runtime player customization before returning to the field.
    g.set_active_classes(actor,("arcanist","oracle"))
    g.learn_ability(actor,"meteor")
    g.equip_passive(actor,"passive_01",capacity=8)
    build_before=g.resolve_actor_build(actor)
    assert {"fire_arc","heal","meteor"}<=set(build_before.abilities)

    # Real field interaction: loaded player is in front of the authored Boss.
    assert g.mode=="field"
    trigger=g.field_step({"interact":1})
    assert trigger is not None
    # The authored event speaks first; the encounter starts after the line is acknowledged.
    assert g.mode=="field"
    assert g.pending_dialogue.line.speaker=="Astral Tyrant"
    g.acknowledge_dialogue()
    assert g.pending_dialogue is None
    assert g.mode=="battle"
    assert g.encounter_id=="boss_room"
    assert len(g.active_hero_ids())==6
    assert set(g.active_enemy_ids())=={
        "astral_tyrant:1","mender_wisp:2","mender_wisp:3"
    }

    # The current modified build, not the immutable authored default, entered battle.
    hero_member=g.battle.member(actor)
    assert "meteor" in hero_member.ability_ids
    boss="astral_tyrant:1"

    # At least one genuine Boss AI turn happens through EnemyAIRuntime.
    hero_vitality_before=hero_member.subject.resources.current("vitality")
    result=g.enemy_turn(boss,"astral_tyrant_ai")
    assert result is not None
    assert hero_member.subject.resources.current("vitality") < hero_vitality_before

    # Finish the real encounter through AbilityRuntime/BattleRuntime actions.
    action_count=0
    for enemy_id in tuple(g.active_enemy_ids()):
        while enemy_id in g.active_enemy_ids():
            for hero_id in tuple(g.active_hero_ids()):
                if enemy_id not in g.active_enemy_ids():
                    break
                g.execute(hero_id,"strike",(enemy_id,))
                action_count+=1
                assert action_count<300
    assert not g.active_enemy_ids()

    gold_before=s.rpg_state.currencies["gold"]
    emblem_before=s.rpg_state.inventory.count("boss_emblem")
    rewards=g.finish_victory()
    assert len(rewards)==3
    assert s.rpg_state.currencies["gold"]>gold_before
    assert s.rpg_state.inventory.count("boss_emblem")>emblem_before
    assert s.event_context.get_switch("encounter.boss_room.defeated")
    assert g.mode=="field"

    # Battle resource changes are written back to canonical actor snapshots.
    restored_actor_snapshot=s.rpg_state.actor_snapshots[actor]
    assert restored_actor_snapshot.resources==hero_member.subject.resources.to_data()

    # Runtime session may mutate save state, never project definitions.
    assert p.to_data()==project_before

    # Save -> close -> reload is exact.
    path=tmp_path/"post_boss.asteria-save.json"
    g.sync_world_state().save_json(path)
    reloaded=GameRuntimeSave.load_json(path,p)
    assert reloaded.to_data()==s.to_data()
    assert reloaded.event_context.get_switch("encounter.boss_room.defeated")
    assert reloaded.rpg_state.actor_progression[actor].active_class_ids==("arcanist","oracle")


def test_runtime_state_v4_backward_read_defaults_active_party_to_roster():
    p,save,_=load()
    raw=save.rpg_state.to_data()
    raw["version"]=4
    raw.pop("party_active_actor_ids")
    raw.pop("party_placements")
    raw.pop("shop_stock")
    raw.pop("quests")
    from asteria.rpg import RpgRuntimeState
    restored=RpgRuntimeState.from_data(raw,p.rpg_database)
    assert restored.party_active_actor_ids==restored.party_actor_ids
    assert restored.party_placements=={}
