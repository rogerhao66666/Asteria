import pytest

from asteria.core import Scene
from asteria.editor.record_editing import (
    MappingTable, RecordListTable, ScalarListTable, format_cell, parse_cell,
)
from asteria.editor.workspace import WorkspaceMode
from asteria.project import Project


def project():
    p = Project("Game")
    p.add_scene(Scene("Main"))
    return p


def hub_window():
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow(project())
    window.workspace.set_mode(WorkspaceMode.RPG)
    return app, window, window.rpg_authoring.child


def test_cell_text_round_trips_through_the_type_it_came_from():
    assert parse_cell("12", 0) == 12
    assert parse_cell("12.5", 0.0) == 12.5
    assert parse_cell("true", False) is True
    assert parse_cell("a, b", ["x"]) == ["a", "b"]
    assert parse_cell("hp=10, mp=4", {"hp": 0.0}) == {"hp": 10.0, "mp": 4.0}
    assert format_cell({"hp": 10.0, "mp": 4.0}) == "hp=10, mp=4"


def test_every_rpg_category_can_create_a_record_from_the_ui():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    # Seeded in dependency order: a few records name another record type.
    order = [
        "abilities", "classes", "units", "passives", "tracks", "graphs",
        "evolutions", "items", "equipment", "attachments", "growth", "recipes",
        "parties", "formations", "party_ui", "encounters", "ai",
    ]
    # An encounter must name an enemy, and a Unit is created as an actor.
    units = hub.adapters["units"]
    units.create("probe_monster")
    monster = units.encode(units.get("probe_monster"))
    monster["kind"] = "enemy"
    units.edit("probe_monster", units.decode(monster))
    assert "probe_monster" in window.document.project.rpg_database.enemies

    for category in order:
        adapter = hub.adapters[category]
        assert adapter.create is not None, category
        key = f"probe_{category}"
        adapter.create(key)
        hub.category.setCurrentIndex(hub.category.findData(category))
        hub.refresh()
        assert key in hub._ids, category
        hub.browser.setCurrentRow(hub._ids.index(key))
        assert hub.apply_selected(), category
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_reference_fields_offer_existing_ids_and_the_record_id_is_read_only():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QComboBox, QLineEdit

    app, window, hub = hub_window()
    hub.adapters["classes"].create("knight")
    hub.adapters["units"].create("hero")
    hub.category.setCurrentIndex(hub.category.findData("units"))
    hub.refresh()
    hub.browser.setCurrentRow(hub._ids.index("hero"))

    editor = hub.editor
    assert editor._catalog["classes"] == ("knight",)
    id_field = editor._build_scalar_widget({"actor_id": "hero"}, "actor_id")
    assert isinstance(id_field, QLineEdit) and id_field.isReadOnly()

    mapping = {"class_id": ""}
    combo = editor._build_scalar_widget(mapping, "class_id")
    assert isinstance(combo, QComboBox)
    combo.setCurrentIndex(combo.findText("knight"))
    assert mapping["class_id"] == "knight"
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_tables_edit_the_record_in_place():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    changes = []
    mapping = {"hp": 10.0}
    table = MappingTable(mapping, lambda: changes.append(1))
    # Blank rows are typed into directly — no add button involved.
    from asteria.editor.record_editing import DEFAULT_BLANK_ROWS

    assert table.rowCount() == DEFAULT_BLANK_ROWS
    table.item(0, 1).setText("42")
    assert mapping == {"hp": 42.0}
    table.item(1, 0).setText("mp")
    table.item(1, 1).setText("7")
    assert mapping == {"hp": 42.0, "mp": 7.0}
    table.remove_row(1)
    assert mapping == {"hp": 42.0}

    owner = {"tags": ["melee"]}
    tags = ScalarListTable(owner, "tags", lambda: None)
    tags.item(0, 0).setText("ranged")
    assert owner["tags"] == ["ranged"]
    tags.item(1, 0).setText("heavy")
    assert owner["tags"] == ["ranged", "heavy"]

    record = {"milestones": [{"rank": 1, "stat_bonuses": {"hp": 5.0}}]}
    rows = RecordListTable(record, "milestones", lambda: None)
    rows.item(0, 0).setText("3")
    assert record["milestones"][0]["rank"] == 3
    rows.item(1, 0).setText("4")
    assert len(record["milestones"]) == 2
    assert changes


def test_filling_the_last_row_grows_the_table_and_clearing_shrinks_it():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.record_editing import DEFAULT_BLANK_ROWS

    QApplication.instance() or QApplication([])
    owner = {"tags": [f"t{i}" for i in range(DEFAULT_BLANK_ROWS)]}
    table = ScalarListTable(owner, "tags", lambda: None)
    assert table.rowCount() == DEFAULT_BLANK_ROWS + 1
    table.item(DEFAULT_BLANK_ROWS, 0).setText("one_more")
    assert len(owner["tags"]) == DEFAULT_BLANK_ROWS + 1
    assert table.rowCount() == DEFAULT_BLANK_ROWS + 2

    owner["tags"][:] = ["only"]
    table.reload()
    assert table.rowCount() == DEFAULT_BLANK_ROWS


def test_an_empty_category_can_still_be_filled_from_the_new_button():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("classes"))
    hub.refresh()
    assert not hub._ids
    assert hub.new_button.isEnabled()
    assert hub.empty_hint.isVisible() or not window.isVisible()
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_generated_character_sprite_is_deterministic_and_varies_by_actor():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.character_generator import generate_character_atlas

    QApplication.instance() or QApplication([])
    from asteria.editor.character_generator import FRAMES, HEIGHT, WIDTH

    first = generate_character_atlas("hero")
    assert (first.width(), first.height()) == (WIDTH * FRAMES, HEIGHT)
    assert first == generate_character_atlas("hero")
    assert first != generate_character_atlas("mage")


def test_generating_a_sprite_registers_assets_and_applies_it_to_the_map(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.character_generator import generate_actor_appearance
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.starter_project import create_new_project
    from asteria.editor.storage import load_document

    app = QApplication.instance() or QApplication([])
    path = create_new_project("Demo", tmp_path)
    window = AsteriaEditorWindow()
    load_document(window.document, path)
    window.refresh_all()

    sheet_id = generate_actor_appearance(window.document, "hero")

    assert (tmp_path / "characters" / "hero_atlas.png").is_file()
    assert window.document.asset_views.sprite_sheet(sheet_id) is not None
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_class_panel_grants_the_capabilities_its_equipment_requires():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from asteria.rpg import EquipmentDefinition

    app, window, hub = hub_window()
    items = window.authoring_controllers.items
    items.create_equipment(
        EquipmentDefinition("sword", "Sword", slot="weapon", required_capabilities=("sword",))
    )
    items.create_equipment(
        EquipmentDefinition("staff", "Staff", slot="weapon", required_capabilities=("staff",))
    )
    hub.category.setCurrentIndex(hub.category.findData("classes"))
    hub.refresh()
    hub.adapters["classes"].create("knight")
    hub.refresh()
    hub.browser.setCurrentRow(hub._ids.index("knight"))

    panel = hub.class_panel
    assert panel.class_id == "knight"
    assert panel.equipment_table.rowCount() == 2
    row = next(
        r for r in range(panel.equipment_table.rowCount())
        if panel.equipment_table.item(r, 0).data(Qt.UserRole) == "sword"
    )
    panel.equipment_table.item(row, 0).setCheckState(Qt.Checked)

    classes = window.document.project.rpg_database.classes
    assert classes["knight"].granted_tags == ("sword",)
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_class_level_table_writes_a_growth_track_and_the_allocation_toggle_owns_a_tree():
    pytest.importorskip("PySide6")
    from asteria.editor.class_design_panel import growth_track_id, skill_tree_id

    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("classes"))
    hub.refresh()
    hub.adapters["classes"].create("mage")
    hub.refresh()
    hub.browser.setCurrentRow(hub._ids.index("mage"))
    panel = hub.class_panel

    panel.level_table.item(0, 0).setText("1")
    panel.level_table.item(0, 1).setText("0")
    panel.level_table.item(1, 0).setText("2")
    panel.level_table.item(1, 1).setText("100")

    db = window.document.project.rpg_database
    track = db.progression_tracks[growth_track_id("mage")]
    assert [(m.rank, m.required_total) for m in track.milestones] == [(1, 0.0), (2, 100.0)]

    panel.allocation_checkbox.setChecked(True)
    assert skill_tree_id("mage") in db.progression_graphs
    panel.allocation_checkbox.setChecked(False)
    assert skill_tree_id("mage") not in db.progression_graphs
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_skill_tree_nodes_can_be_added_duplicated_and_deleted_from_the_graph():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("graphs"))
    hub.refresh()
    hub.adapters["graphs"].create("saber")
    hub.refresh()
    hub.browser.setCurrentRow(hub._ids.index("saber"))
    hub.toggle_skill_tree_view()

    view = hub.graph_view
    assert list(view.node_items) == ["saber_root"]
    assert view.add_node()
    for item in view.node_items.values():
        item.setSelected(True)
    assert len(view.selected_node_ids()) == 2
    assert view.duplicate_selected_nodes()
    assert len(view.node_items) == 4
    for node_id, item in view.node_items.items():
        item.setSelected(node_id.endswith("_copy"))
    assert view.delete_selected_nodes(confirm=False)

    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    assert sorted(n.node_id for n in nodes) == ["node", "saber_root"]
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_generating_a_sprite_needs_no_saved_project_and_rerolls_each_time():
    pytest.importorskip("PySide6")
    from asteria.editor.character_generator import generate_actor_appearance

    app, window, hub = hub_window()
    assert window.document.file_path is None
    hub.adapters["units"].create("hero")
    hub.category.setCurrentIndex(hub.category.findData("units"))
    hub.refresh()
    hub.browser.setCurrentRow(hub._ids.index("hero"))

    generate_actor_appearance(window.document, "hero")
    staged = window.document.staged_assets["characters/hero_atlas.png"]
    first = staged.read_bytes()
    generate_actor_appearance(window.document, "hero")
    assert staged.read_bytes() != first
    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_a_unit_moves_between_the_actor_and_enemy_stores_when_its_kind_changes():
    pytest.importorskip("PySide6")

    app, window, hub = hub_window()
    units = hub.adapters["units"]
    units.create("slime")
    db = window.document.project.rpg_database

    record = units.encode(units.get("slime"))
    assert record["kind"] == "actor"
    record["display_name"] = "Slime"
    record["base_stats"] = {"atk": 3.0}
    record["kind"] = "enemy"
    units.edit("slime", units.decode(record))

    assert "slime" not in db.actors
    assert db.enemies["slime"].display_name == "Slime"
    assert dict(db.enemies["slime"].stats) == {"atk": 3.0}
    assert "slime" in units.ids()

    back = units.encode(units.get("slime"))
    assert back["kind"] == "enemy"
    back["kind"] = "actor"
    units.edit("slime", units.decode(back))
    assert "slime" in db.actors and "slime" not in db.enemies
    assert dict(db.actors["slime"].base_stats) == {"atk": 3.0}

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_placing_a_character_previews_on_the_hovered_cell_before_committing():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.starter_project import build_untitled_project

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow(build_untitled_project())
    window.resize(900, 700)
    viewport = window.viewport
    scene = window.document.project.scenes()[0]
    before = len(scene.entities())

    assert viewport.begin_actor_placement("hero")
    assert viewport._pending_actor_id == "hero"

    point = QPointF(viewport.width() * 0.45, viewport.height() * 0.5)
    viewport.mouseMoveEvent(
        QMouseEvent(QMouseEvent.MouseMove, point, Qt.NoButton, Qt.NoButton, Qt.NoModifier)
    )
    assert viewport._hover_cell is not None
    assert viewport._cell_screen_rect(viewport._hover_cell) is not None
    assert viewport._pending_actor_image() is not None
    assert len(scene.entities()) == before  # still a preview, nothing placed

    viewport.mousePressEvent(
        QMouseEvent(
            QMouseEvent.MouseButtonPress, point, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier
        )
    )
    assert viewport._pending_actor_id is None
    assert len(scene.entities()) == before + 1

    assert viewport.begin_actor_placement("hero")
    assert viewport.cancel_placement()
    assert viewport._pending_actor_id is None

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_the_tile_brush_previews_the_tile_under_the_pointer():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.starter_project import build_untitled_project

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow(build_untitled_project())
    viewport = window.viewport
    viewport.set_tile_mode("paint")
    viewport.set_selected_tile(2)
    assert viewport._active_tile_image() is not None

    viewport.set_tile_mode("select")
    assert viewport._active_tile_image() is None

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_toggling_the_skill_tree_view_switches_back_to_the_list():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("graphs"))
    hub.refresh()
    hub.adapters["graphs"].create("saber")
    hub.refresh()
    hub.browser.setCurrentRow(0)

    assert hub.toggle_skill_tree_view()
    assert hub.detail_stack.currentWidget() is hub.graph_page
    # Regression: this used to set the stack's current widget to the raw
    # TypedRecordEditor (never a registered page of the stack) instead of
    # editor_page, so the call silently did nothing and there was no way
    # back to the list once graph view was opened.
    assert hub.toggle_skill_tree_view()
    assert hub.detail_stack.currentWidget() is hub.editor_page

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_class_panel_and_generic_editor_share_one_scroll_area():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("classes"))
    hub.refresh()
    hub.adapters["classes"].create("knight")
    hub.refresh()
    hub.browser.setCurrentRow(0)

    # Regression: class_panel used to sit outside self.editor's own internal
    # QScrollArea, so the page had two independent scroll regions fighting
    # for height and every table was squeezed into its own tiny scrollbar.
    assert hub.editor._scroll is None
    assert not hub.class_panel.isHidden()

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_skill_tree_add_node_dialog_sets_name_and_icon_tag():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("graphs"))
    hub.refresh()
    hub.adapters["graphs"].create("saber")
    hub.refresh()
    hub.browser.setCurrentRow(0)
    hub.toggle_skill_tree_view()
    view = hub.graph_view

    assert view.add_node(display_name="Fireball", icon_name="flame")
    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    fireball = next(n for n in nodes if n.display_name == "Fireball")
    assert fireball.node_id == "fireball"
    assert fireball.tags == ("icon:flame",)

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_dragging_between_nodes_with_shift_adds_a_prerequisite_and_edge_menu_removes_it():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("graphs"))
    hub.refresh()
    hub.adapters["graphs"].create("saber")
    hub.refresh()
    hub.browser.setCurrentRow(0)
    hub.toggle_skill_tree_view()
    view = hub.graph_view
    view.resize(400, 400)

    view.add_node(display_name="Fireball")
    view.add_node(display_name="Ice Lance")
    from asteria.editor.authoring_hub_widget import _NODE_SIZE

    source_item = view.node_items["fireball"]
    target_item = view.node_items["ice_lance"]
    source_pt = view.mapFromScene(source_item.pos() + QPointF(_NODE_SIZE / 2, _NODE_SIZE / 2))
    target_pt = view.mapFromScene(target_item.pos() + QPointF(_NODE_SIZE / 2, _NODE_SIZE / 2))

    view.mousePressEvent(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(source_pt), Qt.LeftButton,
        Qt.LeftButton, Qt.ShiftModifier,
    ))
    assert view._link_source_id == "fireball"
    view.mouseMoveEvent(QMouseEvent(
        QMouseEvent.MouseMove, QPointF(target_pt), Qt.NoButton, Qt.NoButton, Qt.ShiftModifier,
    ))
    view.mouseReleaseEvent(QMouseEvent(
        QMouseEvent.MouseButtonRelease, QPointF(target_pt), Qt.LeftButton,
        Qt.LeftButton, Qt.ShiftModifier,
    ))
    assert view._link_source_id is None

    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    ice = next(n for n in nodes if n.node_id == "ice_lance")
    assert [p.node_id for p in ice.prerequisites] == ["fireball"]

    # Adding the prerequisite changed ice_lance's depth, so _commit() rebuilt
    # the scene with a fresh item at a new position — re-fetch it instead of
    # reusing the pre-drag `target_item`/`target_pt`, which are now stale.
    # The connector line/arrowhead ends at the target's *top edge*, not its
    # center (which is the node frame itself) — probe a couple pixels above
    # that edge, where the incoming line actually is.
    rebuilt_target = view.node_items["ice_lance"]
    target_top = view.mapFromScene(rebuilt_target.pos() + QPointF(_NODE_SIZE / 2, -2))
    edge = view._edge_at(target_top)
    assert edge == ("fireball", "ice_lance")
    assert view.remove_prerequisite("fireball", "ice_lance")
    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    ice = next(n for n in nodes if n.node_id == "ice_lance")
    assert ice.prerequisites == ()

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_connect_mode_click_click_adds_a_prerequisite_and_fills_the_table():
    pytest.importorskip("PySide6")
    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("graphs"))
    hub.refresh()
    hub.adapters["graphs"].create("saber")
    hub.refresh()
    hub.browser.setCurrentRow(0)
    hub.toggle_skill_tree_view()

    view = hub.graph_view
    view.add_node(display_name="Fire")
    view.add_node(display_name="Fireball")

    hub.graph_connect_button.setChecked(True)
    assert view._connect_mode

    fire_pos = view.mapFromScene(
        view.node_items["fire"].pos()
        + __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(24, 24)
    )
    fireball_pos = view.mapFromScene(
        view.node_items["fireball"].pos()
        + __import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(24, 24)
    )
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtCore import QPointF

    view.mousePressEvent(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(fire_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    ))
    assert view._connect_pending_source == "fire"
    view.mousePressEvent(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(fireball_pos), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    ))
    assert view._connect_pending_source is None
    # Connect mode stays on so several connections can be made in a row.
    assert hub.graph_connect_button.isChecked()

    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    fireball = next(n for n in nodes if n.node_id == "fireball")
    assert [p.node_id for p in fireball.prerequisites] == ["fire"]

    # Switching away from graphs turns connect mode back off automatically.
    hub.category.setCurrentIndex(hub.category.findData("classes"))
    hub.refresh()
    assert not hub.graph_connect_button.isChecked()

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_graph_hint_label_is_an_overlay_not_a_stray_top_level_window():
    pytest.importorskip("PySide6")
    from asteria.editor.authoring_hub_widget import SkillTreeGraphView

    app, window, hub = hub_window()
    view = SkillTreeGraphView()
    # Regression: this used to be constructed as QLabel(text) with no
    # parent, making it a separate top-level window that Qt's own .move()
    # bookkeeping tracked correctly but that never actually rendered as
    # part of the graph view — invisible in every screenshot.
    assert view.hint_label.parent() is view
    assert not view.hint_label.isWindow()
    window.close()
    app.processEvents()


def _graph_hub_with_nodes(*names):
    from PySide6.QtWidgets import QApplication  # noqa: F401

    app, window, hub = hub_window()
    hub.category.setCurrentIndex(hub.category.findData("graphs"))
    hub.refresh()
    hub.adapters["graphs"].create("saber")
    hub.refresh()
    hub.browser.setCurrentRow(0)
    hub.toggle_skill_tree_view()
    for name in names:
        hub.graph_view.add_node(display_name=name)
    return app, window, hub


def test_dragging_a_node_persists_its_position_and_nothing_re_flows_it():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    app, window, hub = _graph_hub_with_nodes("Fire", "Water")
    view = hub.graph_view

    item = view.node_items["fire"]
    start = view.mapFromScene(item.pos() + QPointF(24, 24))
    view.mousePressEvent(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(start), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    ))
    item.setPos(320.0, 260.0)
    view.mouseReleaseEvent(QMouseEvent(
        QMouseEvent.MouseButtonRelease, QPointF(start), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    ))

    stored = window.document.project.rpg_database.progression_graphs["saber"].node_positions
    assert tuple(stored["fire"]) == (320.0, 260.0)

    # Adding another node must not shuffle an already-placed one.
    view.add_node(display_name="Ice")
    assert tuple(view.node_items["fire"].pos().toTuple()) == (320.0, 260.0)

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_connections_follow_a_node_that_moves():
    pytest.importorskip("PySide6")
    app, window, hub = _graph_hub_with_nodes("Fire", "Fireball")
    view = hub.graph_view
    view.add_prerequisite("fire", "fireball")

    def edge_path_points():
        return [
            item.path().elementCount()
            for item in view._edge_items
            if hasattr(item, "path")
        ]

    before = [
        (item.path().elementAt(0).x, item.path().elementAt(0).y)
        for item in view._edge_items if hasattr(item, "path")
    ]
    assert before and edge_path_points()

    view.node_items["fire"].setPos(400.0, 30.0)
    after = [
        (item.path().elementAt(0).x, item.path().elementAt(0).y)
        for item in view._edge_items if hasattr(item, "path")
    ]
    # Regression: edges used to be drawn once and left behind when their
    # node was dragged away, which looked like the connection had broken.
    assert after != before
    assert any(abs(x - (400.0 + 24)) < 2 for x, _ in after)

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_edge_style_and_arrow_toggle_persist_on_the_graph():
    pytest.importorskip("PySide6")
    app, window, hub = _graph_hub_with_nodes("Fire", "Fireball")
    view = hub.graph_view
    view.add_prerequisite("fire", "fireball")

    assert view.edge_style() == "elbow"
    assert view.edge_arrows()

    view.set_edge_style("diagonal")
    view.set_edge_arrows(False)
    assert view.edge_style() == "diagonal"
    assert not view.edge_arrows()

    tags = window.document.project.rpg_database.progression_graphs["saber"].tags
    assert "edge_style:diagonal" in tags
    assert "edge_arrow:off" in tags
    # Arrow heads off means only the line item is drawn for the connection.
    assert len(view._edge_items) == 1

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_graph_edits_land_on_the_undo_stack():
    pytest.importorskip("PySide6")
    app, window, hub = _graph_hub_with_nodes("Fire")
    db = window.document.project.rpg_database
    assert any(n.node_id == "fire" for n in db.progression_graphs["saber"].nodes)

    assert window.document.commands.can_undo
    window.document.undo()
    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    assert not any(n.node_id == "fire" for n in nodes)

    window.document.mark_saved()
    window.close()
    app.processEvents()


def test_destructive_keyboard_shortcuts_are_gone_from_the_canvas():
    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    app, window, hub = _graph_hub_with_nodes("Fire")
    view = hub.graph_view
    view.node_items["fire"].setSelected(True)

    # Delete used to wipe the selected node straight off the canvas with no
    # confirmation — one stray keypress from losing part of a tree.
    view.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier))
    nodes = window.document.project.rpg_database.progression_graphs["saber"].nodes
    assert any(n.node_id == "fire" for n in nodes)

    window.document.mark_saved()
    window.close()
    app.processEvents()
