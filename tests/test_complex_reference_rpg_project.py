from pathlib import Path

from asteria.editor import EditorDocument
from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
from asteria.project import Project
from asteria.runtime.components2d import Interaction2DComponent

REF=Path(__file__).parents[1]/"reference_projects/complex_reference_rpg/project.asteria.json"


def load():
    d=EditorDocument()
    p=Project.load_json(REF,d.component_registry)
    d.set_project(p,file_path=REF)
    return p,d,IntegratedAuthoringControllers(d)


def test_reference_project_loads_and_validates():
    p,_,_=load()
    assert p.validate()
    assert p.name=="Asteria Complex Reference RPG"


def test_reference_project_has_required_system_density():
    p,_,_=load(); db=p.rpg_database
    assert len(db.actors)>=12
    assert len(db.classes)>=8
    assert len(p.gameplay_library.abilities.ids())>=24
    assert len(db.passives)>=16
    assert len(db.progression_graphs)>=8
    assert len(db.equipment)>=20
    assert len(db.attachments)>=6
    assert len(db.items)>=16
    assert len(db.composition_recipes)>=4
    assert len(db.party_setups)==1
    party=db.party_setups["main_party"]
    assert len(party.roster_actor_ids)==12
    assert party.active_capacity==6
    assert len(party.active_actor_ids)==4


def test_reference_boss_uses_multi_phase_ai_and_adds():
    p,_,_=load(); db=p.rpg_database
    encounter=db.encounters["boss_room"]
    assert len(encounter.members)==2
    assert encounter.members[0].enemy_id=="astral_tyrant"
    assert encounter.members[1].count==2
    ai=db.enemy_ai["astral_tyrant_ai"]
    assert len(ai.phases)==3
    assert max(x.actions_per_ready or 1 for x in ai.phases)>=3
    assert db.enemy_behavior_bindings["astral_tyrant"].ai_id=="astral_tyrant_ai"


def test_reference_project_exercises_generic_battle_rules():
    p,_,_=load(); db=p.rpg_database
    assert {"stagger","rage"}<=set(db.battle_resources)
    assert {"weak_fire","weak_ice","weak_lightning"}<=set(db.interaction_rules)
    assert "broken" in db.battle_state_policies
    assert "stagger_system" in db.gauge_compositions
    assert "counter_reaction" in db.reactions
    assert "speed_timeline" in db.battle_schedulers
    assert "standard_victory" in db.battle_objectives
    assert len(db.battle_targeting)>=24
    assert len(db.action_timings)>=24
    assert len(db.action_transactions)>=24


def test_reference_project_has_project_owned_presentation_and_runtime_ui():
    p,_,_=load(); lib=p.battle_presentation_library
    for category in (
        "feedback","hud","ui_layout","ui_polish","action_menu","results",
        "party_layout","ui_theme","rpg_character_screen","rpg_equipment_screen",
        "rpg_ability_screen","rpg_progression_screen","rpg_inventory_screen",
        "rpg_party_screen",
    ):
        assert lib.ids(category),category


def test_reference_field_has_real_boss_interaction_chain():
    p,_,_=load()
    scene=p.scene(p.startup_scene_id)
    boss=next(x for x in scene.entities() if x.name=="Astral Tyrant")
    interaction=boss.get(Interaction2DComponent)
    binding=p.scene_event_bindings[scene.id].bindings[interaction.event_binding_id]
    program=p.event_programs.require(interaction.event_program_id)
    assert binding.entity_id==boss.id
    assert any(x.opcode=="WORLD" and x.args.get("command")=="START_ENCOUNTER" and x.args.get("args",{}).get("encounter_id")=="boss_room" for x in program.instructions)


def test_reference_project_is_visible_through_real_editor_authoring_adapters():
    _,_,c=load()
    rpg={x.category_id:x for x in c.rpg_categories()}
    assert len(rpg["actors"].ids())==12
    assert len(rpg["classes"].ids())==8
    assert len(rpg["equipment"].ids())==20
    assert len(rpg["enemies"].ids())==4

    battle={x.category_id:x for x in c.battle_categories()}
    assert "resources" in battle and len(battle["resources"].ids())==3

    presentation={x.category_id:x for x in c.presentation_categories()}
    runtime={x.category_id:x for x in c.runtime_ui_categories()}
    assert presentation["hud"].ids()==("adaptive",)
    assert runtime["rpg_character_screen"].ids()==("default",)


def test_reference_generator_is_reproducible(tmp_path):
    from reference_projects.complex_reference_rpg.build_project import write_project
    generated=write_project(tmp_path)
    d=EditorDocument()
    p=Project.load_json(generated,d.component_registry)
    assert p.validate()
    assert len(p.rpg_database.actors)==12
    assert (tmp_path/"reference_ids.json").exists()
