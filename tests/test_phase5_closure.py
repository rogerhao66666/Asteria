from asteria.events import (
    EventBinding,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventRunner,
    EventScheduleMode,
    EventScheduler,
    EventTriggerKind,
    SceneEventBindings,
    SceneEventRuntime,
    ScheduledEventSpec,
    WorldCommandRouter,
)


def registry_with(program_id, instructions):
    registry = EventProgramRegistry()
    registry.register(program_id, EventProgram(instructions, name=program_id))
    return registry


def test_runner_snapshot_restores_blocked_dialogue_without_skipping():
    registry = registry_with(
        "p",
        [
            EventInstruction("DIALOGUE", {"speaker": "Lina", "text": "Hello"}),
            EventInstruction("SET_SWITCH", {"name": "after", "value": True}),
            EventInstruction("END"),
        ],
    )
    runner = EventRunner(registry)
    runner.start("p", source_entity_id="npc")
    runner.update()

    assert runner.dialogue.dialogue is not None
    assert not runner.context.get_switch("after")

    snapshot = runner.snapshot()

    restored = EventRunner(registry, context=runner.context)
    restored.restore(snapshot)

    assert restored.dialogue.dialogue is not None
    assert restored.dialogue.dialogue.line.text == "Hello"
    restored.update()
    assert not restored.context.get_switch("after")

    restored.acknowledge_dialogue()
    restored.update()
    assert restored.context.get_switch("after")


def test_runner_snapshot_restores_blocked_choice_and_result_target():
    registry = registry_with(
        "p",
        [
            EventInstruction(
                "CHOICE",
                {
                    "prompt": "Go?",
                    "choices": [
                        {"text": "Yes", "value": "yes"},
                        {"text": "No", "value": "no"},
                    ],
                    "variable_name": "answer",
                },
            ),
            EventInstruction("END"),
        ],
    )
    runner = EventRunner(registry)
    runner.start("p")
    runner.update()
    snapshot = runner.snapshot()

    restored = EventRunner(registry, context=runner.context)
    restored.restore(snapshot)
    assert restored.dialogue.choice is not None
    restored.choose(1)
    restored.update()

    assert restored.context.get_variable("answer") == "no"


def test_v2_active_event_snapshot_remains_backward_compatible():
    registry = registry_with("p", [EventInstruction("WAIT", {"seconds": 1.0})])
    runner = EventRunner(registry)
    runner.start("p")
    runner.update()
    data = runner.snapshot()
    data["version"] = 2
    data.pop("dialogue_state")
    data.pop("sequences")
    data.pop("background_tweens")

    restored = EventRunner(registry)
    restored.restore(data)
    assert restored.waiting


def test_scheduled_world_command_uses_shared_router():
    registry = registry_with(
        "p",
        [
            EventInstruction(
                "WORLD",
                {
                    "command": "PLAY_AUDIO",
                    "args": {"clip": "bell"},
                },
            ),
            EventInstruction("END"),
        ],
    )
    seen = []
    router = WorldCommandRouter()
    router.register("PLAY_AUDIO", lambda command: seen.append(command.args["clip"]))

    scheduler = EventScheduler(registry, world_commands=router)
    scheduler.add(
        ScheduledEventSpec(
            "evt",
            "p",
            EventScheduleMode.PARALLEL,
            source_entity_id="bell",
        )
    )
    scheduler.update()

    assert seen == ["bell"]


def test_scene_runtime_propagates_world_router_to_scheduled_binding():
    registry = registry_with(
        "p",
        [
            EventInstruction(
                "WORLD",
                {
                    "command": "TRANSFER",
                    "args": {"destination": "Forest"},
                },
            ),
            EventInstruction("END"),
        ],
    )
    seen = []
    router = WorldCommandRouter()
    router.register("TRANSFER", lambda command: seen.append(command.args["destination"]))

    bindings = SceneEventBindings()
    bindings.add(
        EventBinding(
            "b",
            "door",
            "p",
            trigger=EventTriggerKind.AUTORUN,
        )
    )
    runtime = SceneEventRuntime.build(
        bindings,
        registry,
        world_commands=router,
    )
    runtime.update()

    assert seen == ["Forest"]
