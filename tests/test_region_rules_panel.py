"""The Tiles panel edits the AreaRule attached to its selected region id."""

import pytest

from asteria.editor.tile_palette_widget import TilePaletteWidget
from asteria.rpg.map_rules import AreaRule, MapRuleSet


@pytest.fixture(scope="module")
def app():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


def test_region_selection_loads_and_applies_the_matching_area_rule(app):
    palette = TilePaletteWidget()
    ruleset = MapRuleSet(
        "field",
        (AreaRule("region:9", damage_resource="hp", damage_per_second=3.5),),
        region_layer="hazards",
    )
    changed, removed = [], []
    palette.areaRuleChanged.connect(changed.append)
    palette.areaRuleRemoved.connect(removed.append)
    try:
        palette.set_area_rule_set(ruleset)
        palette.region_spin.setValue(9)
        assert palette.damage_resource.text() == "hp"
        assert palette.damage_per_second.value() == 3.5
        assert palette.region_layer_label.text() == "Region layer: hazards"
        assert palette.create_map_ruleset.isHidden()

        palette.damage_per_second.setValue(6.0)
        palette.slippery.setChecked(True)
        palette.blocks.setText("enemy, npc")
        palette.apply_region_rule.click()
        palette.remove_region_rule.click()

        assert changed[0] == AreaRule(
            "region:9",
            damage_resource="hp",
            damage_per_second=6,
            slippery=True,
            blocks=("enemy", "npc"),
        )
        assert removed == [9]
    finally:
        palette.close()


def test_panel_requests_a_ruleset_when_the_project_has_none(app):
    palette = TilePaletteWidget()
    requested = []
    palette.createMapRuleSetRequested.connect(lambda: requested.append(True))
    try:
        palette.set_area_rule_set(None)
        assert not palette.create_map_ruleset.isHidden()
        palette.create_map_ruleset.click()
        assert requested == [True]
    finally:
        palette.close()


def test_area_rule_form_wraps_rows_in_a_narrow_tile_panel(app):
    from PySide6.QtWidgets import QFormLayout, QScrollArea

    palette = TilePaletteWidget()
    try:
        palette.resize(264, 600)
        palette.show()
        app.processEvents()
        assert palette.region_rule_form.layout().rowWrapPolicy() in (
            QFormLayout.WrapLongRows,
            QFormLayout.WrapAllRows,
        )
        assert palette.region_rules.geometry().right() <= palette.rect().right()
        fields = palette.region_rules.findChild(QScrollArea, "AreaRuleFieldsScroll")
        assert fields is not None
        assert fields.verticalScrollBar().maximum() > 0
        assert palette.region_rules.maximumHeight() <= 360
    finally:
        palette.close()


def test_area_rule_frame_stays_above_scene_dock_tabs(app):
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QScrollArea, QTabBar

    from asteria.editor.shell import AsteriaEditorWindow

    for size in ((1440, 900), (1000, 640)):
        window = AsteriaEditorWindow()
        try:
            window.resize(*size)
            window.show()
            app.processEvents()
            tabs = next(
                bar
                for bar in window.findChildren(QTabBar)
                if bar.parent() is window
                and bar.isVisible()
                and {"Project", "Tiles", "Layers"}.issubset(
                    {bar.tabText(index) for index in range(bar.count())}
                )
            )
            tabs.setCurrentIndex([tabs.tabText(i) for i in range(tabs.count())].index("Tiles"))
            app.processEvents()
            scroll = window.findChild(QScrollArea, "TilePaletteWidgetScroll")
            rule = window.tile_palette.region_rules
            top_in_content = rule.mapTo(scroll.widget(), QPoint(0, 0)).y()
            scroll.verticalScrollBar().setValue(max(0, top_in_content - 12))
            app.processEvents()
            rule_bottom = rule.mapTo(window, QPoint(0, rule.height())).y()
            viewport_bottom = (
                scroll.viewport().mapTo(window, QPoint(0, scroll.viewport().height())).y()
            )
            assert viewport_bottom - rule_bottom >= 24
        finally:
            window.close()
            window.runtime_monitor.stop()
            window.deleteLater()
            app.processEvents()


def test_editor_window_wires_region_form_to_project_commands(app):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QMessageBox

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    project = Project("Map rules")
    project.rpg_database.add_map_rule_set(MapRuleSet("field", region_layer="hazards"))
    window = AsteriaEditorWindow(project)
    try:
        assert window.viewport.tile_tools.region_layer_name == "hazards"
        assert window.tile_palette.region_layer_label.text() == "Region layer: hazards"
        window.tile_palette.region_spin.setValue(12)
        window.tile_palette.damage_resource.setText("hp")
        window.tile_palette.damage_per_second.setValue(5.0)
        window.tile_palette.apply_region_rule.click()

        ruleset = project.rpg_database.map_rule_sets["field"]
        assert ruleset.rule("region:12").damage_per_second == 5.0
        assert window.document.undo()
        assert project.rpg_database.map_rule_sets["field"].rule("region:12") is None
        assert window.document.redo()
        assert (
            project.rpg_database.map_rule_sets["field"].rule("region:12").damage_resource == "hp"
        )
    finally:

        def discard_unsaved_changes():
            for widget in app.topLevelWidgets():
                if isinstance(widget, QMessageBox):
                    widget.done(QMessageBox.Discard)

        QTimer.singleShot(0, discard_unsaved_changes)
        window.close()
        app.processEvents()
