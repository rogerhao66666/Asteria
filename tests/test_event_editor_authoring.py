import json

from asteria.core import ComponentRegistry, Entity, Scene, Transform
from asteria.editor.event_editing import (
    AddEventBindingCommand,
    AddEventProgramCommand,
    ReplaceEventBindingCommand,
    ReplaceEventProgramCommand,
    bindings_for_scene,
    program_with_insert,
    program_with_move,
    program_with_remove,
    replace_binding_fields,
)
from asteria.events import (
    EventBinding,
    EventInstruction,
    EventProgram,
    EventTriggerKind,
)
from asteria.project import Project


def make_project():
    project = Project("Event Authoring")
    scene = project.add_scene(Scene("Town"))
    entity = scene.add_entity(Entity("NPC"))
    entity.add_component(Transform(4, 8))
    return project, scene, entity


def test_project_v4_persists_event_programs_scene_bindings_and_rpg_database():
    project, scene, entity = make_project()
    project.event_programs.register(
        "program-1",
        EventProgram(
            [EventInstruction("DIALOGUE", {"speaker": "Lina", "text": "Hello"})],
            name="Greeting",
        ),
    )
    bindings = bindings_for_scene(project, scene)
    bindings.add(
        EventBinding(
            "binding-1",
            entity.id,
            "program-1",
            trigger=EventTriggerKind.ACTION,
        )
    )

    data = json.loads(json.dumps(project.to_data()))
    assert data["version"] == 6
    registry = ComponentRegistry()
    registry.register(Transform)
    restored = Project.from_data(data, registry)

    assert restored.event_programs.require("program-1").name == "Greeting"
    restored_bindings = restored.scene_event_bindings[scene.id]
    assert restored_bindings.bindings["binding-1"].program_id == "program-1"


def test_project_v2_remains_loadable_with_empty_event_data():
    project, _, _ = make_project()
    data = project.to_data()
    data["version"] = 2
    data.pop("event_programs")
    data.pop("scene_event_bindings")
    data.pop("rpg_database")
    data.pop("lifecycle_event_bindings")
    data.pop("gameplay_library")

    registry = ComponentRegistry()
    registry.register(Transform)
    restored = Project.from_data(data, registry)
    assert len(restored.event_programs) == 0
    assert restored.scene_event_bindings == {}


def test_program_edit_helpers_insert_move_remove_without_mutating_original():
    original = EventProgram(
        [
            EventInstruction("DIALOGUE", {"text": "A"}),
            EventInstruction("END"),
        ],
        name="Test",
    )

    inserted = program_with_insert(
        original, 1, EventInstruction("SET_SWITCH", {"name": "x", "value": True})
    )
    moved = program_with_move(inserted, 1, 0)
    removed = program_with_remove(moved, 0)

    assert [x.opcode for x in original.instructions] == ["DIALOGUE", "END"]
    assert [x.opcode for x in inserted.instructions] == [
        "DIALOGUE",
        "SET_SWITCH",
        "END",
    ]
    assert [x.opcode for x in moved.instructions] == ["SET_SWITCH", "DIALOGUE", "END"]
    assert [x.opcode for x in removed.instructions] == ["DIALOGUE", "END"]


def test_event_authoring_commands_are_reversible():
    project, scene, entity = make_project()
    bindings = bindings_for_scene(project, scene)
    program = EventProgram([], name="Greeting")
    add_program = AddEventProgramCommand(project.event_programs, "p1", program)
    add_binding = AddEventBindingCommand(
        bindings,
        EventBinding("b1", entity.id, "p1", trigger=EventTriggerKind.ACTION),
    )

    add_program.redo()
    add_binding.redo()
    assert project.event_programs.get("p1") is program
    assert bindings.bindings["b1"].program_id == "p1"

    replacement_program = EventProgram([EventInstruction("END")], name="Greeting")
    ReplaceEventProgramCommand(
        project.event_programs, "p1", replacement_program, program
    ).redo()
    assert len(project.event_programs.require("p1").instructions) == 1

    old_binding = bindings.bindings["b1"]
    new_binding = replace_binding_fields(old_binding, trigger=EventTriggerKind.AUTORUN)
    command = ReplaceEventBindingCommand(bindings, new_binding, old_binding)
    command.redo()
    assert bindings.bindings["b1"].trigger == EventTriggerKind.AUTORUN
    command.undo()
    assert bindings.bindings["b1"].trigger == EventTriggerKind.ACTION

    add_binding.undo()
    add_program.undo()
    assert "b1" not in bindings.bindings
    assert project.event_programs.get("p1") is None
