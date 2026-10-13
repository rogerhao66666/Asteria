from asteria.rpg import (
    AICondition,
    AIDecisionRule,
    BossPhaseDefinition,
    EnemyAIDefinition,
    EnemyAIRuntime,
)

ai = EnemyAIDefinition(
    "demo_boss",
    rules=[
        AIDecisionRule("slash", "hook", payload={"hook": "demo.slash"}, priority=1),
        AIDecisionRule(
            "rage",
            "hook",
            payload={"hook": "demo.rage"},
            priority=5,
            conditions=[AICondition("phase", params={"value": "rage"})],
        ),
    ],
    phases=[
        BossPhaseDefinition(
            "normal", conditions=[AICondition("always")], decision_rule_ids=["slash"]
        ),
        BossPhaseDefinition(
            "rage",
            conditions=[AICondition("always")],
            priority=10,
            decision_rule_ids=["rage"],
            actions_per_ready=2,
        ),
    ],
    initial_phase_id="normal",
)
raw = ai.to_data()
restored = EnemyAIDefinition.from_data(raw)
assert restored.ai_id == "demo_boss"
r = EnemyAIRuntime([restored])
r.set_memory("boss", "turns", 3)
snap = r.to_data()
r2 = EnemyAIRuntime([restored]).restore_data(snap)
assert r2.get_memory("boss", "turns") == 3
print("Batch 91 enemy AI demo: PASS")
