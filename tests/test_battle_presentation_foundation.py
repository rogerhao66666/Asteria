from asteria.core.lifecycle import LifecycleHookBus
from asteria.gameplay import ActionCue, PresentationCue
from asteria.presentation import (
    BattleCombatantVisual,
    BattlePresentationCoordinator,
    BattlePresentationEventKind,
    BattlePresentationScene,
    BattleVisualAnchor,
)


def scene():
    return BattlePresentationScene(
        "forest_encounter",
        "battle.bg.forest",
        [
            BattleCombatantVisual("hero", "battle.hero.sheet", "battle.hero.clips", BattleVisualAnchor(90, 112),
                                  {"idle": "idle", "attack": "slash", "hit": "hurt", "ko": "down"}),
            BattleCombatantVisual("slime", "battle.slime.sheet", "battle.slime.clips", BattleVisualAnchor(236, 108, "left")),
        ],
    )


def test_scene_is_canonical_serializable_data():
    original = scene()
    restored = BattlePresentationScene.from_data(original.to_data())
    assert restored == original
    assert restored.visual_for("hero").clip_for("attack") == "slash"
    assert restored.visual_for("slime").anchor.facing == "left"


def test_coordinator_preserves_timeline_cues_without_executing_gameplay():
    coordinator = BattlePresentationCoordinator(scene())
    coordinator.start()
    cues = [
        PresentationCue("slash", ActionCue("windup", 0.0, "animation", {"clip": "slash"})),
        PresentationCue("slash", ActionCue("impact", 0.2, "camera", {"preset": "impact"})),
    ]
    coordinator.consume_timeline_cues(cues)
    events = coordinator.drain()
    assert [x.kind for x in events] == [
        BattlePresentationEventKind.SCENE_STARTED,
        BattlePresentationEventKind.TIMELINE_CUE,
        BattlePresentationEventKind.TIMELINE_CUE,
    ]
    assert events[1].payload["cue"]["kind"] == "animation"
    assert events[2].payload["cue"]["payload"]["preset"] == "impact"


def test_lifecycle_bridge_observes_frozen_battle_hooks_only():
    hooks = LifecycleHookBus()
    coordinator = BattlePresentationCoordinator(scene()).attach(hooks)
    hooks.emit("rpg.battle.turn_ready", source="hero", data={"round_index": 2})
    hooks.emit("unrelated.event", source="hero")
    hooks.emit("rpg.battle.combatant_incapacitated", source="slime", data={"reason": "hp_zero"})
    events = coordinator.drain()
    assert [(x.kind, x.source_id) for x in events] == [
        (BattlePresentationEventKind.TURN_READY, "hero"),
        (BattlePresentationEventKind.COMBATANT_STATE, "slime"),
    ]


def test_coordinator_never_requires_pygame_or_qt_backend():
    coordinator = BattlePresentationCoordinator(scene())
    coordinator.push_custom("damage_number", source_id="slime", payload={"value": 42})
    event = coordinator.drain()[0]
    assert event.kind == BattlePresentationEventKind.CUSTOM
    assert event.payload == {"event_id": "damage_number", "value": 42}


def test_attach_detach_does_not_duplicate_observers():
    hooks = LifecycleHookBus()
    coordinator = BattlePresentationCoordinator(scene()).attach(hooks).attach(hooks)
    hooks.emit("rpg.battle.turn_ended", source="hero")
    assert len(coordinator.drain()) == 1
    coordinator.detach()
    hooks.emit("rpg.battle.turn_ended", source="hero")
    assert coordinator.drain() == ()
