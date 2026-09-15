import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from asteria.editor.authoring_hub_widget import ProgressionCurveChart

_app = QApplication.instance() or QApplication([])


def test_set_milestones_computes_cumulative_stat_totals_per_rank():
    chart = ProgressionCurveChart()
    chart.set_milestones(
        [
            {"rank": 1, "required_total": 0, "stat_bonuses": {"hp": 10, "atk": 2}},
            {"rank": 2, "required_total": 100, "stat_bonuses": {"hp": 15, "atk": 3}},
            {"rank": 3, "required_total": 300, "stat_bonuses": {"hp": 20, "atk": 4}},
        ]
    )
    assert chart._ranks == (1, 2, 3)
    assert chart._series["hp"] == [10.0, 25.0, 45.0]
    assert chart._series["atk"] == [2.0, 5.0, 9.0]


def test_a_stat_missing_from_a_later_milestone_holds_its_running_total():
    chart = ProgressionCurveChart()
    chart.set_milestones(
        [
            {"rank": 1, "required_total": 0, "stat_bonuses": {"hp": 10}},
            {"rank": 2, "required_total": 100, "stat_bonuses": {}},
        ]
    )
    assert chart._series["hp"] == [10.0, 10.0]


def test_empty_milestones_clear_the_chart_without_raising():
    chart = ProgressionCurveChart()
    chart.set_milestones([{"rank": 1, "required_total": 0, "stat_bonuses": {"hp": 5}}])
    chart.set_milestones(())
    assert chart._ranks == ()
    assert chart._series == {}


def test_paint_event_does_not_raise_with_or_without_data():
    chart = ProgressionCurveChart()
    chart.resize(300, 150)
    chart.grab()  # empty state
    chart.set_milestones(
        [{"rank": 1, "required_total": 0, "stat_bonuses": {"hp": 10, "atk": 2}}]
    )
    pixmap = chart.grab()
    assert not pixmap.isNull()
