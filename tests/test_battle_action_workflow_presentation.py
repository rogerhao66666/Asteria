from asteria.presentation import (
    BattleActionWorkflowDefinition,
    BattleActionWorkflowRuntime,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
    BattleWorkflowOption,
    BattleWorkflowStep,
)
from asteria.runtime import Camera2D


def _definition():
    return BattleActionWorkflowDefinition(
        "concoct",
        "Concoct",
        (
            BattleWorkflowStep("base", "Choose Base"),
            BattleWorkflowStep("reagent", "Choose Reagent"),
            BattleWorkflowStep("catalyst", "Optional Catalyst", optional=True),
        ),
        confirmation_label="Mix",
    )


def test_generic_workflow_supports_alchemy_like_flow_without_alchemy_semantics():
    runtime = BattleActionWorkflowRuntime()
    view = runtime.begin(
        _definition(),
        (
            BattleWorkflowOption("herb", "Herb"),
            BattleWorkflowOption("powder", "Powder"),
        ),
    )
    assert view.workflow_id == "concoct"
    assert view.step.step_id == "base"
    runtime.select("herb")
    assert runtime.view.can_advance
    runtime.advance(
        (
            BattleWorkflowOption("fire", "Fire Dust"),
            BattleWorkflowOption("ice", "Ice Dust"),
        )
    )
    runtime.select("fire")
    runtime.advance((BattleWorkflowOption("ether", "Ether"),))
    runtime.advance()
    assert runtime.view.complete
    assert runtime.selection_payload() == {
        "workflow_id": "concoct",
        "selections": {"base": ["herb"], "reagent": ["fire"], "catalyst": []},
    }


def test_multiple_selection_step_can_model_runes_cards_or_ingredients():
    definition = BattleActionWorkflowDefinition(
        "combine",
        "Combine",
        (
            BattleWorkflowStep(
                "parts", "Choose Parts", selection_mode="multiple", minimum_selections=2, maximum_selections=3
            ),
        ),
    )
    runtime = BattleActionWorkflowRuntime()
    runtime.begin(definition, tuple(BattleWorkflowOption(x, x.upper()) for x in ("a", "b", "c", "d")))
    runtime.select("a")
    assert not runtime.view.can_advance
    runtime.select("b")
    assert runtime.view.can_advance
    runtime.select("c")
    runtime.select("d")
    selected = runtime.selection_payload()["selections"]["parts"]
    assert selected == ["a", "b", "c"]


def test_disabled_options_are_supplied_not_recomputed():
    runtime = BattleActionWorkflowRuntime()
    runtime.begin(
        _definition(),
        (
            BattleWorkflowOption("rare", "Rare Herb", enabled=False, disabled_reason="Out of stock"),
            BattleWorkflowOption("common", "Common Herb"),
        ),
    )
    runtime.select("rare")
    assert runtime.selection_payload()["selections"]["base"] == []
    runtime.select("common")
    assert runtime.selection_payload()["selections"]["base"] == ["common"]


def test_backtracking_changes_only_workflow_selection_state():
    runtime = BattleActionWorkflowRuntime()
    runtime.begin(_definition(), (BattleWorkflowOption("herb", "Herb"),))
    runtime.select("herb")
    runtime.advance((BattleWorkflowOption("fire", "Fire"),))
    runtime.select("fire")
    runtime.back((BattleWorkflowOption("herb", "Herb"), BattleWorkflowOption("water", "Water")))
    assert runtime.view.step.step_id == "base"
    assert runtime.selection_payload()["selections"]["base"] == ["herb"]


def test_ui_composer_prefers_active_workflow_over_action_menu_surface():
    runtime = BattleActionWorkflowRuntime()
    runtime.begin(
        _definition(),
        (
            BattleWorkflowOption("herb", "Herb"),
            BattleWorkflowOption("powder", "Powder"),
        ),
    )
    scene = BattlePresentationScene("workflow", "bg", ())
    frame = BattleUiComposer(scene).compose(
        Camera2D(),
        BattlePresentationFrame("workflow", "bg", ()),
        action_workflow=runtime.view,
    )
    assert any(x.panel_id == "action_workflow" for x in frame.panels)
    assert any(x.text == "Concoct" and x.role == "workflow_title" for x in frame.texts)
    assert any("Choose Base" in x.text for x in frame.texts)


def test_workflow_snapshot_roundtrip_is_deterministic():
    runtime = BattleActionWorkflowRuntime()
    runtime.begin(_definition(), (BattleWorkflowOption("herb", "Herb"),))
    runtime.select("herb")
    runtime.advance((BattleWorkflowOption("fire", "Fire"), BattleWorkflowOption("ice", "Ice")))
    snapshot = runtime.snapshot()
    restored = BattleActionWorkflowRuntime()
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
    assert restored.view.step.step_id == "reagent"
