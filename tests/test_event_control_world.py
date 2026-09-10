import pytest

from asteria.events import (
    EventCondition,
    EventContext,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventRunner,
    EventRunnerError,
    EventVM,
    EventVMError,
    WorldCommandRouter,
)


def test_labels_and_jump_create_deterministic_branch():
    program = EventProgram(
        [
            EventInstruction("SET_VARIABLE", {"name": "n", "value": 1}),
            EventInstruction("JUMP", {"label": "target"}),
            EventInstruction("SET_VARIABLE", {"name": "n", "value": 99}),
            EventInstruction("LABEL", {"name": "target"}),
            EventInstruction("SET_SWITCH", {"name": "done", "value": True}),
        ]
    )
    ctx = EventContext()
    EventVM(program, context=ctx).run_until_blocked()
    assert ctx.get_variable("n") == 1
    assert ctx.get_switch("done") is True


def test_jump_if_uses_event_condition():
    cond = EventCondition("variable", "route", "==", "forest").to_data()
    program = EventProgram(
        [
            EventInstruction("JUMP_IF", {"condition": cond, "label": "forest"}),
            EventInstruction("SET_SWITCH", {"name": "town", "value": True}),
            EventInstruction("END"),
            EventInstruction("LABEL", {"name": "forest"}),
            EventInstruction("SET_SWITCH", {"name": "forest", "value": True}),
        ]
    )
    ctx = EventContext()
    ctx.set_variable("route", "forest")
    EventVM(program, context=ctx).run_until_blocked()
    assert ctx.get_switch("town") is False
    assert ctx.get_switch("forest") is True


def test_duplicate_or_missing_labels_are_rejected():
    with pytest.raises(ValueError):
        EventProgram(
            [
                EventInstruction("LABEL", {"name": "a"}),
                EventInstruction("LABEL", {"name": "a"}),
            ]
        )
    vm = EventVM(EventProgram([EventInstruction("JUMP", {"label": "missing"})]))
    with pytest.raises(EventVMError):
        vm.step()


def test_choice_result_can_drive_later_jump():
    registry = EventProgramRegistry()
    condition = EventCondition("variable", "route", "==", "forest").to_data()
    registry.register(
        "route-event",
        EventProgram(
            [
                EventInstruction(
                    "CHOICE",
                    {
                        "prompt": "Route?",
                        "choices": [
                            {"text": "Town", "value": "town"},
                            {"text": "Forest", "value": "forest"},
                        ],
                        "variable_name": "route",
                    },
                ),
                EventInstruction(
                    "JUMP_IF", {"condition": condition, "label": "forest"}
                ),
                EventInstruction("SET_SWITCH", {"name": "town_path", "value": True}),
                EventInstruction("END"),
                EventInstruction("LABEL", {"name": "forest"}),
                EventInstruction("SET_SWITCH", {"name": "forest_path", "value": True}),
            ]
        ),
    )
    runner = EventRunner(registry)
    runner.start("route-event")
    runner.update()
    runner.choose(1)
    runner.update()
    assert runner.context.get_switch("forest_path") is True
    assert runner.context.get_switch("town_path") is False


def test_world_command_routes_to_registered_service():
    calls = []
    router = WorldCommandRouter()
    router.register("TRANSFER", lambda command: calls.append(command))
    registry = EventProgramRegistry()
    registry.register(
        "door",
        EventProgram(
            [
                EventInstruction(
                    "WORLD",
                    {
                        "command": "TRANSFER",
                        "args": {"scene_id": "scene-2", "x": 8, "y": 12},
                    },
                ),
                EventInstruction("END"),
            ]
        ),
    )
    runner = EventRunner(registry, world_commands=router)
    runner.start("door", source_entity_id="door-entity")
    runner.update()

    assert len(calls) == 1
    assert calls[0].name == "TRANSFER"
    assert calls[0].args["scene_id"] == "scene-2"
    assert calls[0].source_entity_id == "door-entity"


def test_world_boundary_is_generic_for_future_services():
    seen = []
    router = WorldCommandRouter()
    for name in [
        "PLAY_ANIMATION",
        "PLAY_AUDIO",
        "SCREEN_EFFECT",
        "GIVE_ITEM",
        "REMOVE_ITEM",
    ]:
        router.register(name, lambda command, seen=seen: seen.append(command.name))

    registry = EventProgramRegistry()
    registry.register(
        "effects",
        EventProgram(
            [
                EventInstruction("WORLD", {"command": name, "args": {}})
                for name in [
                    "PLAY_ANIMATION",
                    "PLAY_AUDIO",
                    "SCREEN_EFFECT",
                    "GIVE_ITEM",
                    "REMOVE_ITEM",
                ]
            ]
        ),
    )
    runner = EventRunner(registry, world_commands=router)
    runner.start("effects")
    runner.update()
    assert seen == [
        "PLAY_ANIMATION",
        "PLAY_AUDIO",
        "SCREEN_EFFECT",
        "GIVE_ITEM",
        "REMOVE_ITEM",
    ]


def test_world_command_without_router_or_handler_fails_clearly():
    registry = EventProgramRegistry()
    registry.register(
        "event",
        EventProgram([EventInstruction("WORLD", {"command": "TRANSFER", "args": {}})]),
    )
    runner = EventRunner(registry)
    runner.start("event")
    with pytest.raises(EventRunnerError):
        runner.update()

    runner = EventRunner(registry, world_commands=WorldCommandRouter())
    runner.start("event")
    with pytest.raises(EventRunnerError):
        runner.update()
