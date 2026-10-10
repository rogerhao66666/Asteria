import pytest

from asteria.core import Entity, Scene, Transform
from asteria.editor import EditorDocument
from asteria.editor.field_game_flow_authoring import FieldGameFlowAuthoringController, FieldGameFlowAuthoringError
from asteria.editor.field_game_flow_workspace import FieldGameFlowWorkspaceModel
from asteria.events import EventBinding, EventInstruction, EventProgram, EventTriggerKind
from asteria.project import Project
from asteria.runtime.components2d import Interaction2DComponent


def make():
    p = Project("Game")
    s = Scene("Field")
    p.add_scene(s)
    player = Entity("Player")
    player.add_component(Transform())
    s.add_entity(player)
    boss = Entity("Boss")
    boss.add_component(Transform())
    s.add_entity(boss)
    d = EditorDocument(p)
    return p, s, player, boss, d, FieldGameFlowAuthoringController(d)


def encounter_program():
    return EventProgram(
        (
            EventInstruction("DIALOGUE", {"speaker": "Boss", "text": "Face me."}),
            EventInstruction("WORLD", {"command": "START_ENCOUNTER", "encounter_id": "boss_room"}),
            EventInstruction("END"),
        ),
        name="Boss Encounter",
    )


def test_create_program_and_action_binding_are_canonical_and_undoable():
    p, s, _, boss, d, c = make()
    c.create_program("boss_event", encounter_program())
    b = c.create_binding(s.id, EventBinding("boss_interact", boss.id, "boss_event"))
    assert p.event_programs.require("boss_event").name == "Boss Encounter"
    assert p.scene_event_bindings[s.id].bindings["boss_interact"] == b
    assert d.undo()
    assert "boss_interact" not in p.scene_event_bindings[s.id].bindings


def test_binding_requires_existing_scene_entity_and_program():
    _, s, _, boss, _, c = make()
    with pytest.raises(FieldGameFlowAuthoringError):
        c.create_binding(s.id, EventBinding("x", boss.id, "missing"))
    c.create_program("boss_event", encounter_program())
    with pytest.raises(FieldGameFlowAuthoringError):
        c.create_binding(s.id, EventBinding("x", "missing-entity", "boss_event"))


def test_interaction_configuration_connects_entity_binding_and_program():
    _, s, _, boss, _, c = make()
    c.create_program("boss_event", encounter_program())
    c.create_binding(s.id, EventBinding("boss_interact", boss.id, "boss_event", local_scope_id="boss"))
    comp = c.configure_interaction(s.id, boss.id, binding_id="boss_interact", range=32, require_facing=True)
    assert isinstance(comp, Interaction2DComponent)
    assert comp.event_binding_id == "boss_interact"
    assert comp.event_program_id == "boss_event"
    assert comp.range == 32 and comp.require_facing
    assert comp.local_scope_id == "boss"


def test_interaction_rejects_autorun_binding():
    _, s, _, boss, _, c = make()
    c.create_program("boss_event", encounter_program())
    c.create_binding(s.id, EventBinding("boss_auto", boss.id, "boss_event", trigger=EventTriggerKind.AUTORUN))
    with pytest.raises(FieldGameFlowAuthoringError):
        c.configure_interaction(s.id, boss.id, binding_id="boss_auto")


def test_action_flow_resolves_full_chain():
    _, s, _, boss, _, c = make()
    c.create_program("boss_event", encounter_program())
    c.create_binding(s.id, EventBinding("boss_interact", boss.id, "boss_event"))
    c.configure_interaction(s.id, boss.id, binding_id="boss_interact")
    flow = c.action_flow(s.id, boss.id)
    assert flow["entity"] is boss
    assert flow["binding"].program_id == "boss_event"
    assert flow["program"].instructions[1].args["command"] == "START_ENCOUNTER"


def test_program_edit_is_undoable():
    p, s, _, boss, d, c = make()
    c.create_program("boss_event", encounter_program())
    edited = EventProgram(
        (
            EventInstruction("WORLD", {"command": "START_ENCOUNTER", "encounter_id": "hard_boss"}),
            EventInstruction("END"),
        ),
        name="Hard Boss",
    )
    c.edit_program("boss_event", edited)
    assert p.event_programs.require("boss_event").name == "Hard Boss"
    assert d.undo()
    assert p.event_programs.require("boss_event").name == "Boss Encounter"


def test_project_roundtrip_preserves_interaction_game_flow():
    p, s, _, boss, d, c = make()
    c.create_program("boss_event", encounter_program())
    c.create_binding(s.id, EventBinding("boss_interact", boss.id, "boss_event"))
    c.configure_interaction(s.id, boss.id, binding_id="boss_interact", range=40)
    raw = p.to_data()
    clone = Project.from_data(raw, d.component_registry)
    assert clone.to_data() == raw
    cs = clone.scene(s.id)
    cb = cs.get_entity(boss.id)
    assert cb.get(Interaction2DComponent).range == 40
    assert clone.scene_event_bindings[s.id].bindings["boss_interact"].program_id == "boss_event"


def test_validation_detects_broken_interaction_reference():
    _, s, _, boss, _, c = make()
    boss.add_component(Interaction2DComponent())
    comp = boss.get(Interaction2DComponent)
    comp.event_binding_id = "missing"
    comp.event_program_id = "missing"
    issues = c.validate()
    assert any("interaction binding missing" in x for x in issues)
    assert any("interaction program missing" in x for x in issues)


def test_information_architecture_keeps_flow_contextual():
    *_, c = make()
    ia = c.information_architecture
    assert ia.primary_navigation == "game_flow_section_sidebar"
    assert ia.inspector_pattern == "viewport_plus_contextual_detail"
    assert ia.progressive_disclosure
    assert not ia.show_all_flow_details_simultaneously
    assert ia.section("encounter").detail_groups == ("Trigger", "Encounter Command", "Battle Transition", "Return Flow")


def test_workspace_scene_entity_and_command_focus():
    _, s, _, boss, _, c = make()
    c.create_program("boss_event", encounter_program())
    c.create_binding(s.id, EventBinding("boss_interact", boss.id, "boss_event"))
    c.configure_interaction(s.id, boss.id, binding_id="boss_interact")
    w = FieldGameFlowWorkspaceModel(c)
    w.select_scene(s.id)
    w.select_entity(boss.id)
    assert w.snapshot().binding_id == "boss_interact"
    assert w.snapshot().program_id == "boss_event"
    w.set_section("encounter")
    w.focus_command(1)
    assert w.snapshot().focused_command_index == 1
