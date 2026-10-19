"""D19 UI polish: drawn icons, button roles, labelled tabs and dock title bars."""

import pytest

pytest.importorskip("PySide6")


def test_every_icon_draws_something():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.icons import DRAWINGS, icon, pixmap

    QApplication.instance() or QApplication([])
    for name in DRAWINGS:
        image = pixmap(name, 24, ratio=1.0).toImage()
        painted = sum(
            1
            for x in range(0, 24, 2)
            for y in range(0, 24, 2)
            if image.pixelColor(x, y).alpha() > 0
        )
        assert painted >= 4, name
        assert not icon(name).isNull()
    assert icon("no-such-icon").isNull()


def test_button_and_label_rules():
    from asteria.editor.decor import button_style, label_icon

    assert button_style("Delete") == ("delete", "danger")
    assert button_style("Apply Changes") == ("apply", "primary")
    assert button_style("Run") == ("play", "success")
    assert button_style("+ Condition")[0] == "add"
    assert button_style("Frobnicate") == (None, "")
    assert label_icon("Animation States") == "state_machine"
    assert label_icon("Enemy AI") == "behavior_tree"
    assert label_icon("Enemies") == "enemy"
    assert label_icon("Skills") == "skill"


def test_editor_has_icons_roles_and_titled_docks():
    from PySide6.QtWidgets import QApplication, QDockWidget, QPushButton

    from asteria.editor.decor import decorate
    from asteria.editor.dock_title import DockTitleBar
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.theme import apply_asteria_theme

    app = QApplication.instance() or QApplication([])
    apply_asteria_theme(app)
    window = AsteriaEditorWindow()
    try:
        decorate(window)
        for dock in window.findChildren(QDockWidget):
            bar = dock.titleBarWidget()
            assert isinstance(bar, DockTitleBar), dock.objectName()
            assert bar.title.text() == dock.windowTitle() and not dock.windowIcon().isNull()
        window.problems_dock.setWindowTitle("Problems (3)")
        assert window.problems_dock.titleBarWidget().title.text() == "Problems (3)"
        for action in (window.scene_workspace_action, window.play_action, window.stop_action):
            assert not action.icon().isNull()
        roles = {b.text(): b.property("role") for b in window.findChildren(QPushButton)}
        assert roles.get("Delete") == "danger" and roles.get("Apply Rule") == "primary"
        assert all(
            not window.ui_workspace.tabIcon(i).isNull() for i in range(window.ui_workspace.count())
        )
    finally:
        window.close()
        window.deleteLater()


def test_compact_pass_keeps_panels_narrow():
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QHBoxLayout,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    from asteria.editor.decor import compact
    from asteria.editor.flow_layout import FlowLayout

    QApplication.instance() or QApplication([])
    page = QWidget()
    column = QVBoxLayout(page)
    combo = QComboBox()
    combo.addItems(["battle.combatant.a_very_long_asset_identifier_for_testing"])
    column.addWidget(combo)
    row = QHBoxLayout()
    for text in ("Add Socket", "Key at Frame", "Remove"):
        row.addWidget(QPushButton(text))
    column.addLayout(row)
    wide = page.minimumSizeHint().width()
    compact(page)
    assert isinstance(column.itemAt(1).layout(), FlowLayout)  # the button row wraps when narrow
    assert combo.minimumWidth() > 0 and page.minimumSize().width() < wide


def test_record_editor_shows_readable_field_names_and_keeps_the_data():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.authoring_hub_widget import StructuredRecordEditor, field_label

    QApplication.instance() or QApplication([])
    assert field_label("display_name") == "Display Name"
    assert field_label("actor_id") == "Actor ID"
    assert field_label("max_hp") == "Max HP"
    data = {
        "schema": "asteria.rpg.actor",
        "version": 2,
        "actor_id": "hero_01",
        "display_name": "Hero 01",
        "class_assignments": [{"class_id": "fighter", "level": 1}],
        "base_stats": {"power": 40.0},
    }
    editor = StructuredRecordEditor()
    editor.set_record(data)
    root = editor.topLevelItem(0)
    assert root.text(0) == "hero_01" and "asteria.rpg.actor" in root.toolTip(0)
    labels = [root.child(i).text(0) for i in range(root.childCount())]
    assert labels == [
        "Actor ID",
        "Display Name",
        "Class Assignments",
        "Base Stats",
    ]  # no schema / version rows
    assignments = root.child(2)
    assert assignments.text(1) == "1 item" and assignments.child(0).text(0) == "#1 · fighter"
    root.child(1).setText(1, "Aria")
    record = editor.record()
    assert (
        record["display_name"] == "Aria"
        and record["schema"] == "asteria.rpg.actor"
        and record["version"] == 2
    )


def test_tag_lists_are_editable_and_optional_dot_tags_show_in_the_editor():
    """BTL-02: damage over time is fixed by default or uses the interaction rules when the author
    gives it
    tags; both are reachable from the editor (the empty field is shown, a list is typed as
    text)."""
    from PySide6.QtWidgets import QApplication

    from asteria.editor.authoring_hub_widget import StructuredRecordEditor, with_optional_fields
    from asteria.rpg.battle_states import BattleStatePolicy

    QApplication.instance() or QApplication([])
    policy = BattleStatePolicy("scorch", tick_trigger="rpg.battle.turn_ended")
    data = with_optional_fields(policy.to_data(), policy)
    assert data["interaction_tags"] == [] and "interaction_tags" not in policy.to_data()
    editor = StructuredRecordEditor()
    editor.set_record(data)
    root = editor.topLevelItem(0)
    tags = next(
        root.child(i)
        for i in range(root.childCount())
        if root.child(i).toolTip(0) == "interaction_tags"
    )
    tags.setText(1, "element.fire, dot.burn")
    edited = BattleStatePolicy.from_data(editor.record())
    assert set(edited.interaction_tags) == {
        "element.fire",
        "dot.burn",
    }  # DOT now resolved through the rules
    tags.setText(1, "")
    assert (
        BattleStatePolicy.from_data(editor.record()).interaction_tags == ()
    )  # back to fixed damage
    assert "interaction_tags" not in BattleStatePolicy.from_data(editor.record()).to_data()
