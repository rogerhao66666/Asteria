from copy import deepcopy

from asteria.presentation import BattleResultPresentationRuntime, BattleResultProfile
from asteria.rpg import (
    BattleOutcome,
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RewardApplicationResult,
)


def progression_result():
    runtime = ProgressionRuntime(
        [
            ProgressionTrackDefinition(
                "hero_level",
                milestones=[
                    ProgressionMilestone(1, 0),
                    ProgressionMilestone(
                        2, 100, granted_abilities=("slash_plus",), granted_tags=("veteran",)
                    ),
                ],
            )
        ],
        totals={"hero_level": 80},
    )
    return runtime.add("hero_level", 30)


def test_result_projection_mirrors_outcome_and_applied_rewards():
    outcome = BattleOutcome(True, ("heroes",), ("enemies",), (), ("boss_defeated",))
    reward = RewardApplicationResult({"gold": 50}, (progression_result(),), {"potion": 2})
    before = deepcopy(reward)
    profile = BattleResultProfile(
        currency_labels={"gold": "Gold"},
        progression_labels={"hero_level": "Level"},
        item_labels={"potion": "Potion"},
    )
    view = BattleResultPresentationRuntime(profile).present(
        outcome, reward, perspective_side_ids=("heroes",)
    )
    assert view.headline == "Victory"
    assert view.winning_sides == ("heroes",)
    assert view.currencies[0].label == "Gold" and view.currencies[0].amount == 50
    assert view.items[0].label == "Potion" and view.items[0].amount == 2
    prog = view.progression[0]
    assert (prog.old_rank, prog.new_rank, prog.crossed_ranks) == (1, 2, (2,))
    assert prog.granted_abilities == ("slash_plus",)
    assert prog.granted_tags == ("veteran",)
    assert reward == before


def test_unfinished_outcome_has_no_headline_and_no_invented_rewards():
    view = BattleResultPresentationRuntime().present(BattleOutcome(False))
    assert view.headline == ""
    assert view.currencies == () and view.progression == () and view.items == ()


def test_escape_and_defeat_headlines_are_project_owned():
    profile = BattleResultProfile(defeat_label="Wiped", escape_label="Retreated")
    runtime = BattleResultPresentationRuntime(profile)
    assert (
        runtime.present(
            BattleOutcome(True, (), ("heroes",), (), ()), perspective_side_ids=("heroes",)
        ).headline
        == "Wiped"
    )
    assert (
        runtime.present(
            BattleOutcome(True, (), (), ("heroes",), ()), perspective_side_ids=("heroes",)
        ).headline
        == "Retreated"
    )


def test_snapshot_restore_roundtrip():
    outcome = BattleOutcome(True, ("heroes",), ("enemies",), (), ())
    reward = RewardApplicationResult({"gold": 5}, (), {"potion": 1})
    runtime = BattleResultPresentationRuntime(
        BattleResultProfile(currency_labels={"gold": "Gold"})
    )
    runtime.present(outcome, reward, perspective_side_ids=("heroes",))
    snapshot = runtime.snapshot()
    restored = BattleResultPresentationRuntime()
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot


def test_requires_applied_reward_result_not_reward_definition_or_roll():
    import pytest

    from asteria.rpg import RewardDefinition

    with pytest.raises(TypeError):
        BattleResultPresentationRuntime().present(BattleOutcome(True, ("h",)), RewardDefinition())
