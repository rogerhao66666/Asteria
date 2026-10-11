from asteria.gameplay import GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import (
    BattleScheduler,
    BattleSchedulerDefinition,
    BattleSchedulerMode,
    PartyMember,
)


def subject():
    return GameplaySubject(StatBlock(), ResourcePool(), TagSet())


def member(mid, speed):
    return PartyMember(mid, "side", subject(), initiative=speed)


def test_round_mode_is_project_order_not_speed():
    s = BattleScheduler([member("b", 99), member("a", 1)], BattleSchedulerDefinition("round", mode="round"))
    assert [x.member_id for x in s.pending()] == ["a", "b"]


def test_speed_ordered_one_action_each_per_round():
    s = BattleScheduler(
        [member("slow", 2), member("fast", 10)], BattleSchedulerDefinition("speed", mode="speed_ordered")
    )
    assert [s.pop().member_id, s.pop().member_id] == ["fast", "slow"]
    assert s.exhausted()
    s.start_next_round()
    assert [x.member_id for x in s.pending()] == ["fast", "slow"]


def test_continuous_fast_actor_can_act_multiple_times_before_slow_actor():
    s = BattleScheduler(
        [member("fast", 100), member("slow", 25)],
        BattleSchedulerDefinition("ct", mode="continuous", timeline_scale=100),
    )
    order = [s.pop().member_id for _ in range(5)]
    assert order == ["fast", "fast", "fast", "fast", "slow"]


def test_continuous_ties_are_deterministic_by_member_id():
    s = BattleScheduler([member("b", 10), member("a", 10)], BattleSchedulerDefinition("ct", mode="continuous"))
    assert [s.pop().member_id, s.pop().member_id] == ["a", "b"]


def test_continuous_round_advances_after_every_current_member_has_acted():
    s = BattleScheduler([member("fast", 100), member("slow", 25)], BattleSchedulerDefinition("ct", mode="continuous"))
    assert s.round_index == 1
    for _ in range(5):
        s.pop()
    assert s.round_index == 2


def test_snapshot_restore_preserves_timeline_and_pending_order():
    members = [member("fast", 100), member("slow", 25)]
    s = BattleScheduler(members, BattleSchedulerDefinition("ct", mode="continuous"))
    s.pop()
    s.pop()
    restored = BattleScheduler.from_data(s.to_data(), members)
    assert restored.current_time == s.current_time
    assert restored.round_index == s.round_index
    assert [(x.member_id, x.ready_time) for x in restored.pending()] == [
        (x.member_id, x.ready_time) for x in s.pending()
    ]


def test_continuous_summon_schedules_from_current_time():
    s = BattleScheduler([member("fast", 100)], BattleSchedulerDefinition("ct", mode="continuous"))
    s.pop()
    now = s.current_time
    s.register_member(member("summon", 50))
    summon = next(x for x in s.pending() if x.member_id == "summon")
    assert summon.ready_time == now + 2.0


def test_definition_roundtrip():
    d = BattleSchedulerDefinition("custom", mode=BattleSchedulerMode.CONTINUOUS, timeline_scale=250, minimum_speed=0.5)
    assert BattleSchedulerDefinition.from_data(d.to_data()) == d


def test_database_latest_owns_scheduler_definitions():
    from asteria.rpg import RpgDatabase

    db = RpgDatabase()
    db.add_battle_scheduler(BattleSchedulerDefinition("ct", mode="continuous"))
    data = db.to_data()
    assert data["version"] == 29
    restored = RpgDatabase.from_data(data)
    assert restored.battle_schedulers["ct"].mode == BattleSchedulerMode.CONTINUOUS


def test_database_v13_backward_read_has_no_invented_scheduler():
    from asteria.rpg import RpgDatabase

    db = RpgDatabase()
    data = db.to_data()
    data["version"] = 13
    data.pop("battle_schedulers")
    restored = RpgDatabase.from_data(data)
    assert restored.battle_schedulers == {}
