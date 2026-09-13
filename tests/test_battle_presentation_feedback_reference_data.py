import json
from pathlib import Path

from asteria.presentation import BattleFeedbackProfile


def test_batch96_reference_feedback_profile_is_valid_and_round_trips():
    path = Path(__file__).parents[1] / "reference_data" / "batch96_battle_feedback_profile.json"
    data = json.loads(path.read_text())
    profile = BattleFeedbackProfile.from_data(data)
    assert profile.to_data() == data
    assert profile.labels_for(outcome_tags=("outcome.weak",)) == ("WEAK",)
    assert profile.threshold_label("guard_break") == "BREAK"
