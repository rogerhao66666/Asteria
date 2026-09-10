from asteria.gameplay import (
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTarget,
    ActionCue,
    ActionTimeline,
    ActionTimelinePlayer,
    Effect,
    EffectOperation,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
)


def subject(resources=None):
    pool = ResourcePool()
    for k, (cur, maxv) in (resources or {}).items():
        pool.define(k, maxv, current=cur)
    return GameplaySubject(StatBlock(), pool, TagSet(), None)


def setup():
    src = AbilityTarget("hero", subject())
    tgt = AbilityTarget("enemy", subject({"hp": (100, 100)}))
    ability = AbilityDefinition(
        "slash",
        effects=[
            AbilityEffect(
                "selected",
                Effect("hit", [EffectOperation("resource_delta", "hp", -25)]),
            )
        ],
    )
    return src, tgt, AbilityRuntime(AbilityRegistry([ability]))


def test_gameplay_happens_at_authored_hit_time():
    src, tgt, rt = setup()
    timeline = ActionTimeline(
        "slash_action",
        [
            ActionCue("windup", 0.0, "animation", {"clip": "slash"}),
            ActionCue("arc", 0.20, "vfx", {"effect": "slash_arc"}),
            ActionCue("hit", 0.28, "gameplay_ability", {"ability_id": "slash"}),
            ActionCue("shake", 0.29, "camera", {"preset": "impact"}),
        ],
    )
    player = ActionTimelinePlayer(timeline, rt, src, [tgt])
    first = player.advance(0.27)
    assert tgt.subject.resources.current("hp") == 100
    assert [x.cue.cue_id for x in first.presentation_cues] == ["windup", "arc"]
    second = player.advance(0.02)
    assert tgt.subject.resources.current("hp") == 75
    assert len(second.gameplay_results) == 1
    assert [x.cue.cue_id for x in second.presentation_cues] == ["shake"]


def test_large_dt_dispatches_all_crossed_cues_in_deterministic_order():
    src, tgt, rt = setup()
    timeline = ActionTimeline(
        "x",
        [
            ActionCue("b", 0.1, "audio", {}),
            ActionCue("a", 0.1, "vfx", {}),
            ActionCue("hit", 0.2, "gameplay_ability", {"ability_id": "slash"}),
            ActionCue("c", 0.3, "light", {}),
        ],
    )
    player = ActionTimelinePlayer(timeline, rt, src, [tgt])
    result = player.advance(1.0)
    assert [x.cue.cue_id for x in result.presentation_cues] == ["a", "b", "c"]
    assert tgt.subject.resources.current("hp") == 75
    assert result.completed


def test_presentation_cues_do_not_require_renderer_backend():
    src, tgt, rt = setup()
    timeline = ActionTimeline(
        "visual",
        [
            ActionCue("anim", 0, "animation", {"clip": "hero.slash"}),
            ActionCue("fx", 0.1, "vfx", {"asset": "slash.blue"}),
            ActionCue("sound", 0.1, "audio", {"asset": "sword.heavy"}),
            ActionCue("light", 0.1, "light", {"intensity": 1.8}),
            ActionCue("screen", 0.1, "screen_fx", {"hit_stop": 0.05}),
        ],
    )
    result = ActionTimelinePlayer(timeline, rt, src, [tgt]).advance(0.2)
    assert len(result.presentation_cues) == 5


def test_snapshot_restore_does_not_replay_old_hit():
    src, tgt, rt = setup()
    timeline = ActionTimeline(
        "slash",
        [
            ActionCue("hit", 0.2, "gameplay_ability", {"ability_id": "slash"}),
            ActionCue("end", 0.5, "animation", {"clip": "recover"}),
        ],
    )
    p = ActionTimelinePlayer(timeline, rt, src, [tgt])
    p.advance(0.25)
    assert tgt.subject.resources.current("hp") == 75
    snap = p.snapshot()
    p2 = ActionTimelinePlayer(timeline, rt, src, [tgt])
    p2.restore(snap)
    p2.advance(0.3)
    assert tgt.subject.resources.current("hp") == 75


def test_timeline_roundtrip():
    original = ActionTimeline(
        "thunder_slash",
        [
            ActionCue("charge", 0.12, "vfx", {"asset": "charge"}),
            ActionCue("hit", 0.28, "gameplay_ability", {"ability_id": "slash"}),
            ActionCue("shake", 0.29, "camera", {"strength": 0.7}),
        ],
    )
    assert ActionTimeline.from_data(original.to_data()) == original


def test_same_ability_can_use_different_presentation_timelines():
    src, tgt, rt = setup()
    quick = ActionTimeline(
        "quick", [ActionCue("hit", 0.1, "gameplay_ability", {"ability_id": "slash"})]
    )
    fancy = ActionTimeline(
        "fancy",
        [
            ActionCue("charge", 0.1, "vfx", {}),
            ActionCue("flash", 0.3, "light", {}),
            ActionCue("hit", 0.5, "gameplay_ability", {"ability_id": "slash"}),
        ],
    )
    ActionTimelinePlayer(quick, rt, src, [tgt]).advance(0.1)
    assert tgt.subject.resources.current("hp") == 75
    fancy_player = ActionTimelinePlayer(fancy, rt, src, [tgt])
    fancy_player.advance(0.49)
    assert tgt.subject.resources.current("hp") == 75
    fancy_player.advance(0.01)
    assert tgt.subject.resources.current("hp") == 50
