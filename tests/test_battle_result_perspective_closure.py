from asteria.presentation import BattleResultPresentationRuntime, BattleResultProfile
from asteria.rpg import BattleOutcome


def test_result_without_viewer_perspective_is_neutral():
    outcome = BattleOutcome(True, ("red",), ("blue",), (), ())
    view = BattleResultPresentationRuntime().present(outcome)
    assert view.headline == "Battle Complete"


def test_result_headline_is_relative_to_supplied_perspective():
    outcome = BattleOutcome(True, ("red",), ("blue",), (), ())
    runtime = BattleResultPresentationRuntime()
    assert runtime.present(outcome, perspective_side_ids=("red",)).headline == "Victory"
    assert runtime.present(outcome, perspective_side_ids=("blue",)).headline == "Defeat"
    assert runtime.present(outcome, perspective_side_ids=("spectator",)).headline == "Battle Complete"


def test_controller_can_supply_explicit_presentation_disposition():
    outcome = BattleOutcome(True, ("red",), ("blue",), (), ())
    profile = BattleResultProfile(
        victory_label="Won",
        defeat_label="Lost",
        escape_label="Withdrew",
        complete_label="Resolved",
    )
    runtime = BattleResultPresentationRuntime(profile)
    assert runtime.present(outcome, disposition="victory").headline == "Won"
    assert runtime.present(outcome, disposition="defeat").headline == "Lost"
    assert runtime.present(outcome, disposition="complete").headline == "Resolved"


def test_result_perspective_does_not_change_canonical_outcome_data():
    outcome = BattleOutcome(True, ("red",), ("blue",), (), ("objective",))
    view = BattleResultPresentationRuntime().present(
        outcome, perspective_side_ids=("blue",)
    )
    assert view.winning_sides == ("red",)
    assert view.defeated_sides == ("blue",)
    assert view.objective_ids == ("objective",)
