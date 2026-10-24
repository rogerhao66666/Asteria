"""Map area rules: events, floor damage, footsteps, restrictions, sliding and stealth."""

import pytest

from asteria.rpg.map_rules import AreaRule, MapRuleSet, MapRulesRuntime


def _runtime(rules, areas, switches=None, **options):
    """``areas``: a function (x, y) -> keys."""
    return MapRulesRuntime(MapRuleSet("m", rules, **options), areas, switches)


def _strip(x, y):  # region 1 for x < 100, region 2 for 100..200, ice tag beyond
    if x < 100:
        return ("region:1",)
    if x < 200:
        return ("region:2", "tag:wet")
    return ("tag:ice",)


def test_enter_and_leave_fire_once_per_crossing():
    rt = _runtime((AreaRule("region:1", on_enter="a"), AreaRule("region:2", on_leave="b")), _strip)
    first = rt.advance("p", 10, 0, 0.1)
    assert [(e.kind, e.rule.key) for e in first] == [("enter", "region:1")]
    assert rt.advance("p", 20, 0, 0.1) == ()
    crossing = rt.advance("p", 110, 0, 0.1)
    assert [(e.kind, e.rule.key) for e in crossing] == [
        ("enter", "region:2"),
        ("leave", "region:1"),
    ]
    assert [(e.kind, e.rule.key) for e in rt.advance("p", 250, 0, 0.1)] == [("leave", "region:2")]


def test_each_entity_is_tracked_on_its_own():
    rt = _runtime((AreaRule("region:1"),), _strip)
    assert len(rt.advance("a", 10, 0, 0.1)) == 1
    assert len(rt.advance("b", 10, 0, 0.1)) == 1
    assert rt.advance("a", 11, 0, 0.1) == ()


def test_floor_damage_scales_with_time_spent():
    rule = AreaRule("tag:wet", damage_resource="hp", damage_per_second=4, can_kill=False)
    rt = _runtime((rule,), _strip)
    rt.advance("p", 150, 0, 0.0)
    events = rt.advance("p", 150, 0, 0.5)
    (damage,) = [e for e in events if e.kind == "damage"]
    assert damage.amount == pytest.approx(2.0) and damage.rule is rule
    assert [e for e in rt.advance("p", 10, 0, 0.5) if e.kind == "damage"] == []


def test_footsteps_come_every_step_distance():
    rule = AreaRule("region:1", footstep_cue="grass", step_distance=10)
    rt = _runtime((rule,), _strip)
    rt.advance("p", 0, 0, 0.1)
    counts = [
        sum(e.kind == "footstep" for e in rt.advance("p", x, 0, 0.1)) for x in (4, 8, 12, 25)
    ]
    assert counts == [0, 0, 1, 1]  # 4, 8 -> none yet; 12 -> first; 25 -> 10 more -> second
    assert sum(e.kind == "footstep" for e in rt.advance("p", 45, 0, 0.1)) == 2


def test_step_programs_fire_with_or_without_a_cue():
    rt = _runtime((AreaRule("region:1", on_step="ev", step_distance=5),), _strip)
    rt.advance("p", 0, 0, 0.1)
    assert [e.kind for e in rt.advance("p", 5, 0, 0.1)] == ["step"]
    both = _runtime(
        (AreaRule("region:1", on_step="ev", footstep_cue="x", step_distance=5),), _strip
    )
    both.advance("p", 0, 0, 0.1)
    assert [e.kind for e in both.advance("p", 5, 0, 0.1)] == ["footstep", "step"]


def test_blocks_by_group_or_all():
    rt = _runtime(
        (AreaRule("region:1", blocks=("enemy",)), AreaRule("region:2", blocks=("all",))), _strip
    )
    assert rt.blocked("enemy", 10, 0) and not rt.blocked("player", 10, 0)
    assert rt.blocked("player", 150, 0) and not rt.blocked("player", 250, 0)


def test_rules_follow_their_switch():
    on = {"gate": False}
    rt = _runtime((AreaRule("region:1", blocks=("all",), switch="gate"),), _strip, on.get)
    assert not rt.blocked("player", 10, 0)
    on["gate"] = True
    assert rt.blocked("player", 10, 0)


def test_slippery_floor_carries_the_last_direction_then_stops():
    rt = _runtime((AreaRule("tag:ice", slippery=True, slip_seconds=0.5),), _strip)
    assert rt.shape_movement("p", 1, 0, 10, 0) == (1, 0)  # dry floor: as asked
    assert rt.shape_movement("p", 1, 0, 250, 0) == (1, 0)  # steps onto ice
    assert rt.shape_movement("p", 0, 0, 255, 0) == (1, 0)  # lets go: keeps sliding
    rt.settle_slide("p", 0.3)
    assert rt.sliding("p")
    rt.settle_slide("p", 0.3)
    assert not rt.sliding("p") and rt.shape_movement("p", 0, 0, 260, 0) == (0.0, 0.0)


def test_sliding_stops_at_a_wall_and_on_dry_floor():
    rt = _runtime((AreaRule("tag:ice", slippery=True),), _strip)
    rt.shape_movement("p", 0, 1, 250, 0)
    rt.settle_slide("p", 0.01, blocked=True)
    assert not rt.sliding("p")
    rt.shape_movement("p", 0, 1, 250, 0)
    rt.shape_movement("p", 0, 0, 10, 0)  # stepped off the ice
    assert not rt.sliding("p")


def test_visibility_takes_the_darkest_area_and_the_stance():
    rules = (AreaRule("region:1", visibility=0.5), AreaRule("tag:wet", visibility=0.8))
    rt = _runtime(rules, _strip, crouch_visibility=0.5, still_visibility=0.9)
    assert rt.visibility(10, 0) == 0.5
    assert rt.visibility(10, 0, crouching=True) == pytest.approx(0.25)
    assert rt.visibility(150, 0, moving=False) == pytest.approx(0.8 * 0.9)
    assert rt.visibility(250, 0) == 1.0


def test_data_round_trip_keeps_only_what_differs_from_the_defaults():
    rule = AreaRule("region:3", damage_resource="hp", damage_per_second=2, blocks=("npc", "enemy"))
    assert rule.to_data() == {
        "key": "region:3",
        "damage_resource": "hp",
        "damage_per_second": 2.0,
        "blocks": ["enemy", "npc"],
    }
    ruleset = MapRuleSet("m", (rule, AreaRule("tag:ice", slippery=True)), crouch_visibility=0.4)
    assert MapRuleSet.from_data(ruleset.to_data()) == ruleset


@pytest.mark.parametrize("key", ["", "3", "region:", "tile:3"])
def test_bad_keys_are_rejected(key):
    with pytest.raises(ValueError):
        AreaRule(key)


def test_validation_of_numbers_and_duplicates():
    with pytest.raises(ValueError):
        AreaRule("region:1", damage_per_second=-1)
    with pytest.raises(ValueError):
        AreaRule("region:1", step_distance=0)
    with pytest.raises(ValueError):
        MapRuleSet("m", (AreaRule("region:1"), AreaRule("region:1")))
    with pytest.raises(TypeError):
        MapRuleSet("m", ("region:1",))
    with pytest.raises(ValueError):
        MapRuleSet.from_data({"schema": "x", "version": 1})


def test_an_encounter_table_picks_by_weight():
    import random

    rule = AreaRule("tag:grass", encounters={"common": 9, "rare": 1}, encounter_chance=1.0)
    rng = random.Random(4)
    picks = [rule.pick_encounter(rng) for _ in range(2000)]
    assert 0.85 < picks.count("common") / len(picks) < 0.95
    assert AreaRule("tag:grass").pick_encounter(rng) == ""


def test_a_step_rolls_the_area_chance_and_the_first_step_scale():
    import random

    grass = AreaRule(
        "tag:grass", encounters={"wild": 1}, encounter_chance=1.0, encounter_first_step=0.0
    )
    rt = _runtime([grass], lambda x, y: ("tag:grass",))
    rng = random.Random(0)
    assert rt.roll_encounter(0, 0, rng, before=()) == ""  # stepping in: scaled to nothing
    assert rt.roll_encounter(0, 0, rng, before=("tag:grass",)) == "wild"
    never = AreaRule("tag:grass", encounters={"wild": 1}, encounter_chance=0.0)
    assert _runtime([never], lambda x, y: ("tag:grass",)).roll_encounter(0, 0, rng) == ""
    odds = AreaRule("tag:grass", encounters={"wild": 1}, encounter_chance=0.25)
    rolls = [
        _runtime([odds], lambda x, y: ("tag:grass",)).roll_encounter(0, 0, rng, ("tag:grass",))
        for _ in range(4000)
    ]
    assert 0.22 < rolls.count("wild") / len(rolls) < 0.28


def test_music_title_and_encounters_round_trip():
    rule = AreaRule(
        "region:3",
        music="song",
        title="ROUTE 101",
        encounters={"a": 20, "b": 5},
        encounter_chance=0.11,
        encounter_first_step=0.6,
    )
    data = rule.to_data()
    assert data["encounters"] == {"a": 20.0, "b": 5.0} and data["title"] == "ROUTE 101"
    assert AreaRule.from_data(data) == rule
    assert "encounters" not in AreaRule("region:3").to_data()
    with pytest.raises(ValueError):
        AreaRule("region:3", encounter_chance=1.5)
    with pytest.raises(ValueError):
        AreaRule("region:3", encounter_first_step=2)


def test_an_unknown_encounter_in_an_area_is_a_reference_error():
    from asteria.rpg.actors import RpgDatabase

    db = RpgDatabase()
    db.add_map_rule_set(
        MapRuleSet("m", [AreaRule("region:1", encounters={"missing": 1}, encounter_chance=0.1)])
    )
    assert any("unknown encounter missing" in e for e in db.reference_errors())
