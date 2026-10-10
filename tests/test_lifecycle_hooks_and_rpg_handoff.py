from asteria.core.lifecycle import LifecycleHookBus
from asteria.events import (
    EventInstruction,
    EventProgram,
    EventProgramRegistry,
    EventRunner,
)
from asteria.events.lifecycle_bridge import LifecycleEventBinding, LifecycleEventBridge
from asteria.gameplay import (
    AbilityRegistry,
    AbilityRuntime,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
)
from asteria.rpg import (
    BattleRuntime,
    Inventory,
    Party,
    PartyMember,
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RewardRoll,
    RewardRuntime,
)


def subject(hp):
    resources = ResourcePool()
    resources.define("hp", hp, current=hp)
    return GameplaySubject(StatBlock(), resources, TagSet())


def test_generic_lifecycle_bus_supports_any_named_flow_and_wildcard():
    hooks = LifecycleHookBus()
    seen = []
    hooks.subscribe("*", lambda e: seen.append(e.name))
    hooks.emit("world.door.opened")
    hooks.emit("quest.custom_step.completed")
    hooks.emit("crafting.recipe.before_execute")
    assert seen == [
        "world.door.opened",
        "quest.custom_step.completed",
        "crafting.recipe.before_execute",
    ]


def test_lifecycle_event_can_bridge_to_phase5_event_vm():
    hooks = LifecycleHookBus()
    registry = EventProgramRegistry()
    registry.register("after_battle", EventProgram([EventInstruction("END")]))
    runner = EventRunner(registry)
    bridge = LifecycleEventBridge(hooks, runner, [LifecycleEventBinding("rpg.battle.finished", "after_battle")])
    hooks.emit("rpg.battle.finished", source="boss")
    assert runner.active.program_id == "after_battle"
    assert runner.active.source_entity_id == "boss"
    assert bridge.pending_count() == 0


def test_bridge_queues_when_event_runner_is_busy():
    hooks = LifecycleHookBus()
    registry = EventProgramRegistry()
    registry.register(
        "blocking",
        EventProgram([EventInstruction("WAIT", {"seconds": 1.0}), EventInstruction("END")]),
    )
    registry.register("follow", EventProgram([EventInstruction("END")]))
    runner = EventRunner(registry)
    runner.start("blocking")
    bridge = LifecycleEventBridge(hooks, runner, [LifecycleEventBinding("x.done", "follow")])
    hooks.emit("x.done")
    assert bridge.pending_count() == 1


def test_battle_outcome_has_no_hardcoded_hp_semantics():
    hooks = LifecycleHookBus()
    seen = []
    hooks.subscribe("rpg.battle.finished", lambda e: seen.append(e.data["outcome"]))
    a = PartyMember("a", "left", subject(5))
    b = PartyMember("b", "right", subject(0))
    battle = BattleRuntime(
        [Party("left", [a]), Party("right", [b])],
        AbilityRuntime(AbilityRegistry()),
        hooks=hooks,
        is_active=lambda m: m.subject.resources.current("hp") > 0,
    )
    outcome = battle.resolve_outcome()
    assert outcome.finished and outcome.winning_sides == ("left",)
    assert seen[-1] == outcome


def test_reward_handoff_applies_currency_progression_items_and_hooks():
    hooks = LifecycleHookBus()
    seen = []
    hooks.subscribe("*", lambda e: seen.append(e.name))
    track = ProgressionTrackDefinition("rank", milestones=[ProgressionMilestone(1, 0), ProgressionMilestone(2, 10)])
    progression = ProgressionRuntime([track], hooks=hooks)
    inventory = Inventory()
    wallet = {}
    runtime = RewardRuntime(inventory=inventory, progression=progression, currencies=wallet, hooks=hooks)
    result = runtime.apply(RewardRoll({"coin": 3}, {"rank": 10}, {"potion": 2}))
    assert wallet["coin"] == 3
    assert progression.rank("rank") == 2
    assert inventory.count("potion") == 2
    assert result.progression_results[0].new_rank == 2
    assert "rpg.reward.before_apply" in seen
    assert "rpg.progression.rank_changed" in seen
    assert "rpg.reward.after_apply" in seen
