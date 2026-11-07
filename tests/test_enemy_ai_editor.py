"""CB10 / EDT-07: enemy AI / boss phase editor (API) and the preview that uses the runtime's
selection logic."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.editor.combat.enemy_ai_authoring import AIScenario, EnemyAIEditor, EnemyAIEditorError
from asteria.project import Project

REF = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
BOSS = "astral_tyrant_ai"


@pytest.fixture
def editor():
    document = EditorDocument()
    document.set_project(Project.load_json(REF, document.component_registry), file_path=REF)
    return EnemyAIEditor(document)


def test_reference_boss_ai_is_clean_and_its_phases_follow_vitality(editor):
    assert editor.problems(BOSS) == []
    assert editor.bound_enemies(BOSS) == ("astral_tyrant",) and "rage" in editor.resources(BOSS)
    curve = dict(editor.phase_by_ratio(BOSS, steps=10))
    assert (
        curve[1.0] == "phase_1"
        and curve[0.6] == "phase_2"
        and curve[0.3] == "phase_3"
        and curve[0.0] == "phase_3"
    )


def test_preview_shows_eligible_rules_and_pick_chances(editor):
    calm = editor.preview(BOSS, AIScenario(resource_ratios={"vitality": 1.0}))
    assert calm.phase_id == "phase_1" and calm.chances == (
        ("cleave", 1.0),
    )  # priority 5 beats roar (4)
    low = editor.preview(
        BOSS, AIScenario(resource_ratios={"vitality": 0.2}, resource_values={"rage": 0})
    )
    assert low.phase_id == "phase_3" and "nova" not in low.eligible_rule_ids  # not enough rage
    enraged = editor.preview(
        BOSS, AIScenario(resource_ratios={"vitality": 0.2}, resource_values={"rage": 40})
    )
    assert enraged.chances == (("nova", 1.0),)


def test_rule_phase_and_condition_edits_are_each_one_undo_step(editor):
    document = editor.document
    editor.add_rule(
        BOSS,
        "taunt",
        ability_id="boss_roar",
        target_selector="random_opponent",
        priority=6,
        weight=2,
    )
    editor.add_condition(BOSS, ("rule", "taunt"), "round_index", op=">=", value=3)
    assert editor.preview(BOSS, AIScenario(round_index=3)).chances == (
        ("cleave", 1.0),
    )  # phase 1 doesn't list it
    editor.edit_phase(BOSS, "phase_1", rule_ids=("cleave", "roar", "taunt"), actions_per_ready=2)
    assert editor.phase(BOSS, "phase_1").actions_per_ready == 2
    assert editor.preview(BOSS, AIScenario(round_index=1)).chances == (("cleave", 1.0),)
    assert editor.preview(BOSS, AIScenario(round_index=3)).chances == (("taunt", 1.0),)
    editor.edit_rule(BOSS, "taunt", weight=0.5, priority=5)
    chances = dict(editor.preview(BOSS, AIScenario(round_index=4)).chances)
    assert chances == pytest.approx({"cleave": 2 / 3, "taunt": 1 / 3})
    editor.remove_rule(BOSS, "taunt")
    assert (
        "taunt" not in editor.phase(BOSS, "phase_1").decision_rule_ids
    )  # phase rule lists follow
    for _ in range(5):
        document.undo()
    assert [r.rule_id for r in editor.get(BOSS).rules] == ["cleave", "roar", "nova", "meteor"]
    assert editor.phase(BOSS, "phase_1").actions_per_ready is None


def test_new_ai_bind_and_boss_phase_authoring(editor):
    editor.create("wisp_ai", ability_id="boss_roar")
    editor.add_phase("wisp_ai", "calm")
    editor.add_phase(
        "wisp_ai",
        "panic",
        priority=5,
        conditions=[
            {
                "kind": "resource_ratio",
                "params": {"resource_id": "vitality", "op": "<", "value": 0.5},
            }
        ],
    )
    assert editor.get("wisp_ai").initial_phase_id == "calm"
    assert (
        editor.preview("wisp_ai", AIScenario(resource_ratios={"vitality": 0.4})).phase_id
        == "panic"
    )
    assert "not used by any enemy" in editor.problems("wisp_ai")
    editor.unbind("mender_wisp") if editor.database.enemy_behavior_bindings.get(
        "mender_wisp"
    ) else None
    editor.bind("mender_wisp", "wisp_ai")
    assert editor.bound_enemies("wisp_ai") == ("mender_wisp",)
    editor.remove_phase("wisp_ai", "calm")
    assert editor.get("wisp_ai").initial_phase_id == "panic"
    editor.set_actions_per_ready("wisp_ai", 2)
    assert editor.get("wisp_ai").actions_per_ready == 2


def test_invalid_edits_are_refused_without_changing_the_record(editor):
    before = editor.get(BOSS)
    with pytest.raises(EnemyAIEditorError, match="unknown target selector"):
        editor.add_rule(BOSS, "x", ability_id="boss_roar", target_selector="everyone")
    with pytest.raises(EnemyAIEditorError, match="ability"):
        editor.add_rule(BOSS, "x", action_kind="ability")
    with pytest.raises(Exception, match="unknown AI abilities"):
        editor.add_rule(BOSS, "x", ability_id="no_such_ability")
    with pytest.raises(EnemyAIEditorError, match="between 0 and 1"):
        editor.add_condition(
            BOSS, ("rule", "cleave"), "resource_ratio", resource_id="vitality", op="<", value=50
        )
    with pytest.raises(EnemyAIEditorError, match="comparison"):
        editor.add_condition(BOSS, ("rule", "cleave"), "stat", stat_id="power", op="~", value=1)
    with pytest.raises(EnemyAIEditorError, match="unknown rules"):
        editor.edit_phase(BOSS, "phase_1", rule_ids=("ghost",))
    single = editor.create("one_rule_ai", ability_id="boss_roar")
    with pytest.raises(EnemyAIEditorError, match="at least one rule"):
        editor.remove_rule(single.ai_id, "basic_attack")
    assert editor.get(BOSS) == before


def test_boss_final_phase_runs_in_a_real_battle(runtime):
    """Regression: phase 3's nova rule used an unregistered condition kind and crashed the boss
    turn."""
    game = runtime.game
    game.start_encounter("boss_room")
    boss = next(m for m in game.battle.members if m.startswith("astral"))
    resources = game.battle.member(boss).subject.resources
    resources.set_current("vitality", resources.get("vitality").maximum * 0.2)
    game.enemy_turn(boss, BOSS)
    assert game.battle.enemy_ai.phases[boss] == "phase_3"
    game.battle.battle_resources.change(
        boss, "rage", 50
    )  # rage is a combat-layer resource (max 100)
    decision = game.battle.enemy_ai.decide(game.battle, BOSS, boss, rng=game.battle.rng)
    assert decision.rule_id == "nova"


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(None)
    value.document.set_project(
        Project.load_json(REF, value.document.component_registry), file_path=REF
    )
    value.refresh_all()
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_gui_shows_rules_phases_and_previews_the_boss(window):
    """The tab edits with Game Data's own form (names, words, picks) and previews in words."""
    from asteria.editor.records.form_shapes import ai_context

    widget = window.enemy_ai_editor
    assert window.rpg_workspace.tabText(window.rpg_workspace.indexOf(widget)) == "Enemy AI"
    assert widget.select_ai(BOSS)
    data = widget.family.editor._data
    assert len(data["rules"]) == 4 and len(data["phases"]) == 3
    assert widget.used_by.text() == "Astral Tyrant"  # by name, not id
    assert widget.problem_list.item(0).text() == "No problems"
    names = widget._names()
    assert ai_context(data, data["phases"][1], names) == "starts when HP % is at most 65 %"
    assert widget.run_preview().phase_id == "phase_1"
    assert widget.decision.item(0).text() == "1. Boss Cleave  100%"
    assert widget.curve.text() == "Phase 1 ≤100%  →  Phase 2 ≤65%  →  Phase 3 ≤30%"
    widget.set_preview_resource("vitality", 9000 * 0.2)
    widget.set_preview_resource("rage", 40)
    assert widget.decision.item(0).text() == "3. Boss Nova  100%"
    assert widget.phase_label.text() == "Phase: Phase 3"


def test_gui_edits_rules_phases_and_binding_with_undo(window):
    widget = window.enemy_ai_editor
    document = window.document
    widget.select_ai(BOSS)
    family = widget.family
    data = family.editor._data
    data["rules"][1]["priority"] = 9  # Boss Roar first
    assert family.auto_apply() and widget.api.rule(BOSS, "roar").priority == 9
    widget._load()
    assert widget.decision.item(0).text() == "2. Boss Roar  100%"  # the preview follows
    data = family.editor._data
    data["phases"][0]["decision_rule_ids"].append("nova")
    assert family.auto_apply() and "nova" in widget.api.phase(BOSS, "phase_1").decision_rule_ids
    assert widget.create_ai("wisp_ai") and widget.ai_id == "wisp_ai"
    assert widget.bind_enemy("mender_wisp") and widget.used_by.text() == "Mender Wisp"
    while document.undo():
        pass
    assert widget.api.rule(BOSS, "roar").priority == 4
    assert "nova" not in widget.api.phase(BOSS, "phase_1").decision_rule_ids
    assert "wisp_ai" not in widget.api.ai_ids()
