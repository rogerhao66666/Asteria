import json
import random

from asteria.gameplay import (
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTargetMode,
    Effect,
    EffectOperation,
    EffectOperationKind,
    GameplaySubject,
    ResourcePool,
    StatBlock,
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    AICondition,
    AIDecisionRule,
    BattleRuntime,
    BossPhaseDefinition,
    EnemyAIDefinition,
    EnemyAIRuntime,
    Party,
    PartyMember,
    RpgDatabase,
)


def subject(hp=100, speed=10):
    r = ResourcePool()
    r.define("hp", hp)
    return GameplaySubject(StatBlock({"speed": speed}), r, TagSet())


def abilities():
    reg = AbilityRegistry()
    for aid, delta in [("claw", -10), ("meteor", -30)]:
        reg.register(
            AbilityDefinition(
                aid,
                targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
                effects=[
                    AbilityEffect(
                        AbilityTargetMode.SELECTED,
                        Effect(aid, [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", delta)]),
                    )
                ],
            )
        )
    return AbilityRuntime(reg)


def battle(ai_defs=(), handlers=None):
    hero = PartyMember("hero", "heroes", subject(), ability_ids=("claw", "meteor"))
    boss = PartyMember("boss", "enemies", subject(100, 8), ability_ids=("claw", "meteor"))
    return BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [boss])],
        abilities(),
        enemy_ai_definitions=ai_defs,
        ai_action_handlers=handlers,
    )


def ai_def():
    rules = (
        AIDecisionRule("normal", "ability", payload={"ability_id": "claw"}, priority=1, weight=1),
        AIDecisionRule(
            "rage",
            "ability",
            payload={"ability_id": "meteor"},
            priority=5,
            weight=1,
            conditions=(AICondition("phase", params={"value": "rage"}),),
        ),
    )
    phases = (
        BossPhaseDefinition("normal", conditions=(AICondition("always"),), priority=0, decision_rule_ids=("normal",)),
        BossPhaseDefinition(
            "rage",
            conditions=(AICondition("resource_ratio", params={"resource_id": "hp", "op": "<=", "value": 0.5}),),
            priority=10,
            decision_rule_ids=("rage",),
            actions_per_ready=2,
        ),
    )
    return EnemyAIDefinition("boss_ai", rules=rules, phases=phases, initial_phase_id="normal")


def test_definition_roundtrip():
    d = ai_def()
    assert EnemyAIDefinition.from_data(d.to_data()) == d


def test_seeded_decision_is_deterministic():
    d = EnemyAIDefinition(
        "x",
        rules=[
            AIDecisionRule("a", "hook", payload={"hook": "a"}, weight=1),
            AIDecisionRule("b", "hook", payload={"hook": "b"}, weight=3),
        ],
    )
    b = battle([d])
    r1 = random.Random(7)
    r2 = random.Random(7)
    assert b.enemy_ai.decide(b, "x", "boss", rng=r1).rule_id == b.enemy_ai.decide(b, "x", "boss", rng=r2).rule_id


def test_boss_phase_transition_changes_rule_and_multi_action_count():
    d = ai_def()
    b = battle([d])
    rng = random.Random(1)
    assert b.enemy_ai.decide(b, "boss_ai", "boss", rng=rng).rule_id == "normal"
    b.member("boss").subject.resources.change("hp", -60)
    dec = b.enemy_ai.decide(b, "boss_ai", "boss", rng=random.Random(1))
    assert dec.phase_id == "rage" and dec.rule_id == "rage"
    assert b.enemy_ai.actions_per_ready("boss_ai", "boss") == 2


def test_execute_ai_turn_uses_normal_ability_pipeline():
    d = EnemyAIDefinition("x", rules=[AIDecisionRule("a", "ability", payload={"ability_id": "claw"})])
    b = battle([d])
    b.execute_ai_turn("x", "boss", rng=random.Random(1))
    assert b.member("hero").subject.resources.current("hp") == 90


def test_custom_action_kind_can_hook_alchemy_summon_transform_or_project_systems():
    called = []

    def alchemy_handler(battle, decision, rng):
        called.append((decision.actor_id, decision.payload["recipe"]))
        return "crafted"

    d = EnemyAIDefinition("x", rules=[AIDecisionRule("mix", "alchemy", payload={"recipe": "bomb"})])
    b = battle([d], handlers={"alchemy": alchemy_handler})
    out = b.execute_ai_turn("x", "boss", rng=random.Random(1))
    assert called == [("boss", "bomb")]
    assert out[0][1] == "crafted"


def test_ai_memory_roundtrip_for_later_battle_snapshot():
    r = EnemyAIRuntime([ai_def()])
    r.set_memory("boss", "counter", 3)
    r.phases["boss"] = "rage"
    restored = EnemyAIRuntime([ai_def()]).restore_data(r.to_data())
    assert restored.get_memory("boss", "counter") == 3 and restored.phases["boss"] == "rage"


def test_database_v19_owns_enemy_ai_and_v18_is_backward_readable():
    db = RpgDatabase()
    db.add_enemy_ai(ai_def())
    raw = db.to_data()
    assert raw["version"] == 30 and "boss_ai" in RpgDatabase.from_data(raw).enemy_ai
    old = json.loads(json.dumps(raw))
    old["version"] = 18
    old.pop("enemy_ai")
    assert RpgDatabase.from_data(old).enemy_ai == {}


def test_many_ai_rules_have_no_engine_content_cap():
    d = EnemyAIDefinition("x", rules=[AIDecisionRule(f"r{i}", "hook", payload={"hook": f"h{i}"}) for i in range(512)])
    assert len(d.rules) == 512
