import json

from asteria.events import (
    EventBinding,
    EventCondition,
    EventContext,
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventTriggerCondition,
    EventTriggerKind,
    SceneEventBindings,
    SceneEventRuntime,
)


def registry():
    r = EventProgramRegistry()
    r.register("action-program", EventProgram([EventInstruction("END")]))
    r.register(
        "auto-program",
        EventProgram(
            [
                EventInstruction("SET_SWITCH", {"name": "auto_started", "value": True}),
                EventInstruction("WAIT", {"seconds": 1}),
                EventInstruction("END"),
            ]
        ),
    )
    r.register(
        "parallel-program",
        EventProgram(
            [
                EventInstruction("SET_VARIABLE", {"name": "parallel", "value": 1}),
                EventInstruction("END"),
            ]
        ),
    )
    return r


def test_binding_roundtrip_preserves_trigger_and_conditions():
    condition = EventTriggerCondition(EventCondition("switch", "quest_started", "==", True))
    binding = EventBinding(
        "binding-1",
        "npc-1",
        "action-program",
        trigger=EventTriggerKind.ACTION,
        conditions=[condition],
        local_scope_id="npc-self",
    )
    restored = EventBinding.from_data(json.loads(json.dumps(binding.to_data())))
    assert restored.binding_id == "binding-1"
    assert restored.entity_id == "npc-1"
    assert restored.program_id == "action-program"
    assert restored.trigger == EventTriggerKind.ACTION
    assert restored.local_scope_id == "npc-self"
    assert len(restored.conditions) == 1


def test_scene_bindings_roundtrip_and_entity_lookup():
    bindings = SceneEventBindings()
    bindings.add(EventBinding("b1", "npc-1", "action-program"))
    bindings.add(EventBinding("b2", "npc-2", "action-program"))

    restored = SceneEventBindings.from_data(json.loads(json.dumps(bindings.to_data())))
    assert [x.binding_id for x in restored.for_entity("npc-1")] == ["b1"]


def test_trigger_conditions_control_action_binding_visibility():
    ctx = EventContext()
    bindings = SceneEventBindings()
    bindings.add(
        EventBinding(
            "b1",
            "npc-1",
            "action-program",
            conditions=[EventTriggerCondition(EventCondition("switch", "can_talk", "==", True))],
        )
    )
    runtime = SceneEventRuntime.build(bindings, registry(), context=ctx)

    assert runtime.action_binding_for_entity("npc-1") is None
    ctx.set_switch("can_talk", True)
    assert runtime.action_binding_for_entity("npc-1").binding_id == "b1"


def test_autorun_and_parallel_bindings_feed_scheduler():
    ctx = EventContext()
    bindings = SceneEventBindings()
    bindings.add(
        EventBinding(
            "auto-1",
            "scene-controller",
            "auto-program",
            trigger=EventTriggerKind.AUTORUN,
        )
    )
    bindings.add(
        EventBinding(
            "parallel-1",
            "weather",
            "parallel-program",
            trigger=EventTriggerKind.PARALLEL,
        )
    )

    runtime = SceneEventRuntime.build(bindings, registry(), context=ctx)
    ids = {x.event_id for x in runtime.scheduler.specs()}
    assert ids == {"auto-1", "parallel-1"}

    runtime.update(0)
    assert ctx.get_switch("auto_started") is True
    assert ctx.get_variable("parallel") == 1


def test_scheduled_binding_condition_refresh_adds_and_removes_runtime_specs():
    ctx = EventContext()
    condition = EventTriggerCondition(EventCondition("switch", "night", "==", True))
    bindings = SceneEventBindings()
    bindings.add(
        EventBinding(
            "parallel-night",
            "lamp",
            "parallel-program",
            trigger=EventTriggerKind.PARALLEL,
            conditions=[condition],
        )
    )
    runtime = SceneEventRuntime.build(bindings, registry(), context=ctx)
    assert runtime.scheduler.specs() == ()

    ctx.set_switch("night", True)
    runtime.refresh_scheduled_bindings()
    assert [x.event_id for x in runtime.scheduler.specs()] == ["parallel-night"]

    ctx.set_switch("night", False)
    runtime.refresh_scheduled_bindings()
    assert runtime.scheduler.specs() == ()


def test_action_binding_is_not_converted_to_scheduler_spec():
    binding = EventBinding(
        "action-1",
        "npc",
        "action-program",
        trigger=EventTriggerKind.ACTION,
    )
    try:
        binding.to_scheduler_spec()
    except ValueError:
        pass
    else:
        raise AssertionError("action binding must remain foreground interaction")
