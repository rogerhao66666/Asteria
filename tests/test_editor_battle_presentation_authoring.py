import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.battle_presentation_authoring import (
    BattlePresentationAuthoringController,
    BattlePresentationAuthoringError,
)
from asteria.editor.battle_presentation_workspace import (
    BattlePresentationWorkspaceModel,
)
from asteria.presentation import (
    BattleActionMenuPolicy,
    BattleActionWorkflowDefinition, BattleWorkflowStep,
    BattleAnimationTimingProfile,
    BattleCombatantVisualProfile,
    BattleFeedbackProfile,
    BattleHudProfile,
    BattleInteractionProfile,
    BattleMotionSequence,
    BattlePartyLayoutPolicy,
    BattlePortraitPartyTemplateProfile,
    BattlePortraitPartyZone,
    BattlePresentationDirectorProfile,
    BattlePresentationLayeringProfile,
    BattleResultProfile,
    BattleSideviewTemplateProfile,
    BattleSideviewZone,
    BattleUiLayoutProfile,
    BattleUiPolishProfile,
    BattleUiTheme,
    BattleVisualAssetSet,
    BattleVisualStateDefinition,
)
from asteria.project import Project


def make():
    p=Project("Game"); p.add_scene(Scene("Main"))
    doc=EditorDocument(p)
    return p,doc,BattlePresentationAuthoringController(doc)


def profiles():
    return {
        "combatant_visuals": BattleCombatantVisualProfile(
            "hero_visual", BattleVisualAssetSet("hero.sprite"),
            (BattleVisualStateDefinition("idle","idle"),)
        ),
        "feedback": BattleFeedbackProfile(),
        "hud": BattleHudProfile(),
        "ui_layout": BattleUiLayoutProfile(),
        "ui_polish": BattleUiPolishProfile(),
        "sideview_templates": BattleSideviewTemplateProfile(
            "side",
            BattleSideviewZone("enemy",-60,20,24,"right"),
            BattleSideviewZone("player",60,20,24,"left"),
        ),
        "portrait_templates": BattlePortraitPartyTemplateProfile(
            "portrait",BattlePortraitPartyZone("enemy",40,30,24)
        ),
        "animation_timing": BattleAnimationTimingProfile(),
        "director": BattlePresentationDirectorProfile(),
        "layering": BattlePresentationLayeringProfile(),
        "action_menu": BattleActionMenuPolicy(),
        "interaction": BattleInteractionProfile(),
        "results": BattleResultProfile(),
        "party_layout": BattlePartyLayoutPolicy(),
        "ui_theme": BattleUiTheme(),
        "motion_sequences": BattleMotionSequence("attack",1.0),
        "action_workflows": BattleActionWorkflowDefinition("cast",steps=(BattleWorkflowStep("spell","Spell"),)),
    }


def test_all_presentation_categories_are_project_owned_and_authorable():
    p,doc,c=make()
    for category,value in profiles().items():
        c.create(category,"default",value)
        assert c.library.require(category,"default") is value
    assert set(profiles()).issubset(set(c.library.categories()))
    assert set(c.library.categories())-set(profiles())=={
        "rpg_character_screen","rpg_equipment_screen","rpg_ability_screen",
        "rpg_progression_screen","rpg_inventory_screen","rpg_party_screen",
    }
    assert doc.commands.can_undo


def test_presentation_library_project_v7_roundtrip():
    p,doc,c=make()
    for category,value in profiles().items():
        c.create(category,"default",value)
    raw=p.to_data()
    assert raw["version"]==8
    clone=Project.from_data(raw,doc.component_registry)
    assert clone.to_data()==raw
    for category in profiles():
        assert clone.battle_presentation_library.ids(category)==("default",)


def test_old_project_v6_remains_backward_readable():
    p,doc,c=make()
    raw=p.to_data()
    raw["version"]=6
    raw.pop("game_start",None)
    raw.pop("battle_presentation_library")
    clone=Project.from_data(raw,doc.component_registry)
    assert clone.battle_presentation_library.categories()
    assert all(not clone.battle_presentation_library.ids(x) for x in clone.battle_presentation_library.categories())


def test_visual_profile_roundtrip_preserves_nested_state():
    p,doc,c=make()
    value=profiles()["combatant_visuals"]
    c.create("combatant_visuals","hero",value)
    clone=Project.from_data(p.to_data(),doc.component_registry)
    restored=clone.battle_presentation_library.require("combatant_visuals","hero")
    assert restored.assets.battlefield_asset_id=="hero.sprite"
    assert restored.states[0].state_id=="idle"


def test_template_and_motion_roundtrip_for_custom_codecs():
    p,doc,c=make()
    for category in ("sideview_templates","portrait_templates","motion_sequences","interaction","ui_layout"):
        c.create(category,"x",profiles()[category])
    clone=Project.from_data(p.to_data(),doc.component_registry)
    assert clone.battle_presentation_library.require("sideview_templates","x").template_id=="side"
    assert clone.battle_presentation_library.require("motion_sequences","x").sequence_id=="attack"
    assert clone.battle_presentation_library.require("ui_layout","x").virtual_width==320


def test_edit_delete_duplicate_are_undoable():
    p,doc,c=make()
    c.create("results","default",BattleResultProfile(victory_label="Win"))
    c.edit("results","default",BattleResultProfile(victory_label="Victory!"))
    assert c.library.require("results","default").victory_label=="Victory!"
    assert doc.undo()
    assert c.library.require("results","default").victory_label=="Win"
    c.duplicate("results","default","alt")
    assert c.library.ids("results")==("alt","default")
    c.delete("results","alt")
    assert c.library.ids("results")==("default",)


def test_wrong_profile_type_is_rejected():
    _,_,c=make()
    with pytest.raises(TypeError):
        c.create("hud","wrong",BattleResultProfile())


def test_unknown_category_is_rejected():
    _,_,c=make()
    with pytest.raises(KeyError):
        c.create("everything","x",BattleResultProfile())


def test_information_architecture_separates_presentation_domains():
    _,_,c=make()
    ia=c.information_architecture
    assert ia.primary_navigation=="presentation_section_sidebar"
    assert ia.secondary_navigation=="category_tabs"
    assert ia.inspector_pattern=="preview_plus_contextual_detail"
    assert ia.live_preview_expected
    assert ia.progressive_disclosure
    assert not ia.show_all_categories_simultaneously
    assert not ia.show_all_details_simultaneously
    assert "motion_sequences" in ia.section("motion").categories
    assert "hud" in ia.section("hud").categories


def test_workspace_only_exposes_current_category_and_context():
    _,_,c=make()
    c.create("combatant_visuals","hero",profiles()["combatant_visuals"])
    c.create("sideview_templates","side",profiles()["sideview_templates"])
    w=BattlePresentationWorkspaceModel(c)
    assert w.snapshot().visible_ids==("hero",)
    w.select("hero"); w.focus_child("state:idle")
    assert w.snapshot().focused_child_id=="state:idle"
    w.set_category("sideview_templates")
    assert w.snapshot().visible_ids==("side",)
    assert w.snapshot().focused_child_id is None


def test_workspace_sections_reset_category_and_support_preview_modes():
    _,_,c=make()
    w=BattlePresentationWorkspaceModel(c)
    w.set_section("motion")
    assert w.snapshot().category=="motion_sequences"
    w.set_preview_mode("timeline")
    assert w.snapshot().preview_mode=="timeline"
    with pytest.raises(ValueError):
        w.set_preview_mode("all-at-once")


def test_project_validation_includes_presentation_library():
    p,_,c=make()
    c.create("results","default",BattleResultProfile())
    assert c.validate()==()
    assert p.validate()
