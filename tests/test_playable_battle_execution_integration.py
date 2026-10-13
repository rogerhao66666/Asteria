from asteria.rpg import BattleAction
from asteria.validation import PlayableBattleValidationHarness, build_reference_battle_scenario


def test_batch119_resolved_actor_enters_real_battle_with_multisource_abilities():
    s = build_reference_battle_scenario()
    member = s.battle.member(s.player_member_id)
    assert {"power_strike", "double_strike", "flame_slash", "venom_edge", "tempered_arc"}.issubset(
        set(member.ability_ids)
    )
    assert member.subject.resources.current("vitality") == 250


def test_player_action_executes_through_canonical_battle_runtime():
    h = PlayableBattleValidationHarness()
    before = h.scenario.battle.member("reference_enemy").subject.resources.current("vitality")
    h.player_action("power_strike")
    after = h.scenario.battle.member("reference_enemy").subject.resources.current("vitality")
    assert (before, after) == (320, 292)
    assert h.scenario.trace[-1].source == "player_input"


def test_enemy_ai_chooses_but_canonical_battle_runtime_executes():
    h = PlayableBattleValidationHarness()
    before = h.scenario.battle.member("validation_hero").subject.resources.current("vitality")
    h.enemy_action()
    after = h.scenario.battle.member("validation_hero").subject.resources.current("vitality")
    assert after < before
    assert h.scenario.trace[-1].source == "enemy_ai"
    assert h.scenario.trace[-1].ability_id in {"enemy_claw", "enemy_crush"}


def test_enemy_ability_can_be_executed_by_same_battle_action_pipeline_without_ai():
    s = build_reference_battle_scenario()
    before = s.battle.member("validation_hero").subject.resources.current("vitality")
    s.battle.execute(BattleAction("reference_enemy", "enemy_claw", ("validation_hero",)))
    assert s.battle.member("validation_hero").subject.resources.current("vitality") == before - 17


def test_player_equipment_and_progression_abilities_share_execution_mechanism():
    h = PlayableBattleValidationHarness()
    h.player_action("double_strike")
    first = h.scenario.trace[-1]
    h.player_action("venom_edge")
    second = h.scenario.trace[-1]
    assert first.target_vitality_before[0] - first.target_vitality_after[0] == 18
    assert second.target_vitality_before[0] - second.target_vitality_after[0] == 16


def test_opaque_side_ids_prove_enemy_player_names_are_not_side_semantics():
    s = build_reference_battle_scenario()
    assert set(s.battle.parties) == {"side.alpha", "side.omega"}
    decision = s.battle.enemy_ai.decide(
        s.battle, s.enemy_ai_id, s.enemy_member_id, rng=s.battle.rng
    )
    assert decision.target_ids == ("validation_hero",)


def test_complete_exchange_produces_auditable_shared_trace():
    h = PlayableBattleValidationHarness()
    trace = h.run_exchange("flame_slash")
    assert len(trace) == 2
    assert [x.source for x in trace] == ["player_input", "enemy_ai"]
    assert trace[0].actor_id == "validation_hero"
    assert trace[1].actor_id == "reference_enemy"
