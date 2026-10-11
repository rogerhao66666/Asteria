import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_enemy_encounter_authoring import (
    RpgEnemyEncounterAuthoringController,
    RpgEnemyEncounterAuthoringError,
)
from asteria.editor.rpg_enemy_encounter_workspace import RpgEnemyEncounterWorkspaceModel
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import (
    AICondition,
    AIDecisionRule,
    BossPhaseDefinition,
    EncounterDefinition,
    EncounterMember,
    EnemyAIDefinition,
    EnemyDefinition,
    ItemDefinition,
    LootEntry,
    ProgressionMilestone,
    ProgressionTrackDefinition,
    RewardDefinition,
)


def make():
    p = Project("Game")
    p.add_scene(Scene("Main"))
    for aid in ("slash", "fire", "heal", "summon_add"):
        p.gameplay_library.add_ability(AbilityDefinition(aid))
    p.rpg_database.add_item(ItemDefinition("boss_core"))
    p.rpg_database.add_progression_track(
        ProgressionTrackDefinition("exp", "EXP", milestones=(ProgressionMilestone(1, 0),))
    )
    doc = EditorDocument(p)
    return p, doc, RpgEnemyEncounterAuthoringController(doc)


def boss():
    return EnemyDefinition(
        "boss",
        "Boss",
        stats={"power": 50, "defense": 30},
        resources={"vitality": 1000, "focus": 100},
        tags=("boss", "elite"),
        abilities=("slash", "fire"),
        reward=RewardDefinition(
            currencies={"gold": 500},
            experience={"exp": 300},
            loot=(LootEntry("boss_core", chance=1.0, minimum=1, maximum=1),),
        ),
    )


def ai():
    return EnemyAIDefinition(
        "boss_ai",
        rules=(
            AIDecisionRule(
                "basic", "ability", payload={"ability_id": "slash"}, target_selector="first_opponent", priority=1
            ),
            AIDecisionRule(
                "burn",
                "ability",
                payload={"ability_id": "fire"},
                target_selector="all_opponents",
                conditions=(
                    AICondition("resource_ratio", params={"resource_id": "vitality", "op": "<=", "value": 0.5}),
                ),
                priority=10,
            ),
        ),
        phases=(
            BossPhaseDefinition("phase1", decision_rule_ids=("basic",), priority=1),
            BossPhaseDefinition(
                "phase2",
                conditions=(
                    AICondition("resource_ratio", params={"resource_id": "vitality", "op": "<=", "value": 0.5}),
                ),
                decision_rule_ids=("burn", "basic"),
                priority=10,
                actions_per_ready=2,
            ),
        ),
        initial_phase_id="phase1",
        actions_per_ready=1,
    )


def test_enemy_complete_definition_and_reward_validation():
    p, doc, c = make()
    e = c.create_enemy(boss())
    assert e.resources["vitality"] == 1000
    assert e.reward.currencies["gold"] == 500
    assert e.reward.experience["exp"] == 300
    assert e.reward.loot[0].item_id == "boss_core"
    assert doc.undo()
    assert "boss" not in p.rpg_database.enemies


def test_unknown_enemy_ability_and_reward_refs_rejected():
    _, _, c = make()
    with pytest.raises(RpgEnemyEncounterAuthoringError):
        c.create_enemy(EnemyDefinition("bad", abilities=("missing",)))
    with pytest.raises(RpgEnemyEncounterAuthoringError):
        c.create_enemy(EnemyDefinition("bad2", reward=RewardDefinition(loot=(LootEntry("missing"),))))


def test_encounter_composition_count_weight_and_tags():
    p, doc, c = make()
    c.create_enemy(boss())
    c.create_enemy(EnemyDefinition("add"))
    enc = c.create_encounter(
        EncounterDefinition(
            "boss_room",
            members=(EncounterMember("boss", count=1, weight=1.0), EncounterMember("add", count=3, weight=0.5)),
            tags=("boss", "scripted"),
        )
    )
    assert enc.members[1].count == 3
    assert enc.members[1].weight == 0.5


def test_ai_rules_phases_conditions_and_targets_are_authorable():
    p, doc, c = make()
    value = c.create_ai(ai())
    assert value.initial_phase_id == "phase1"
    assert value.phases[1].actions_per_ready == 2
    assert value.rules[1].target_selector == "all_opponents"
    assert value.rules[1].conditions[0].kind == "resource_ratio"


def test_ai_ability_payload_reference_is_validated():
    _, _, c = make()
    bad = EnemyAIDefinition("bad", rules=(AIDecisionRule("r", "ability", payload={"ability_id": "missing"}),))
    with pytest.raises(RpgEnemyEncounterAuthoringError):
        c.create_ai(bad)


def test_enemy_ai_binding_is_canonical_and_undoable():
    p, doc, c = make()
    c.create_enemy(boss())
    c.create_ai(ai())
    binding = c.bind_enemy_ai("boss", "boss_ai", tags=("boss",))
    assert binding.ai_id == "boss_ai"
    assert p.rpg_database.enemy_behavior_bindings["boss"].ai_id == "boss_ai"
    assert doc.undo()
    assert "boss" not in p.rpg_database.enemy_behavior_bindings
    assert doc.redo()


def test_delete_enemy_and_ai_protect_live_references():
    _, _, c = make()
    c.create_enemy(boss())
    c.create_ai(ai())
    c.bind_enemy_ai("boss", "boss_ai")
    with pytest.raises(RpgEnemyEncounterAuthoringError):
        c.delete_enemy("boss")
    with pytest.raises(RpgEnemyEncounterAuthoringError):
        c.delete_ai("boss_ai")


def test_database_v23_roundtrip_preserves_behavior_binding():
    p, doc, c = make()
    c.create_enemy(boss())
    c.create_ai(ai())
    c.bind_enemy_ai("boss", "boss_ai")
    raw = p.to_data()
    assert raw["rpg_database"]["version"] == 26
    clone = Project.from_data(raw, doc.component_registry)
    assert clone.to_data() == raw
    assert clone.rpg_database.enemy_behavior_bindings["boss"].ai_id == "boss_ai"


def test_old_v22_database_remains_backward_readable():
    p, doc, c = make()
    raw = p.rpg_database.to_data()
    raw["version"] = 22
    raw.pop("enemy_behavior_bindings")
    from asteria.rpg import RpgDatabase

    restored = RpgDatabase.from_data(raw)
    assert restored.enemy_behavior_bindings == {}


def test_information_architecture_keeps_boss_complexity_contextual():
    _, _, c = make()
    ia = c.information_architecture
    assert ia.primary_navigation == "category_sidebar"
    assert ia.ai_pattern == "rule_phase_browser_plus_contextual_detail"
    assert ia.progressive_disclosure
    assert not ia.show_all_boss_logic_simultaneously
    assert not ia.show_all_details_simultaneously


def test_workspace_rule_phase_focus_is_mutually_contextual():
    _, _, c = make()
    c.create_ai(ai())
    w = RpgEnemyEncounterWorkspaceModel(c)
    w.set_section("ai")
    w.select("boss_ai")
    w.select_rule("burn")
    assert w.snapshot().selected_rule_id == "burn"
    assert w.snapshot().selected_phase_id is None
    w.select_phase("phase2")
    assert w.snapshot().selected_phase_id == "phase2"
    assert w.snapshot().selected_rule_id is None


def test_project_validation_after_enemy_encounter_authoring():
    p, _, c = make()
    c.create_enemy(boss())
    c.create_ai(ai())
    c.bind_enemy_ai("boss", "boss_ai")
    c.create_encounter(EncounterDefinition("boss_room", members=(EncounterMember("boss"),)))
    assert c.validate() == ()
    assert p.validate()
