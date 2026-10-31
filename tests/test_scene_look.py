"""The Scene workspace's LDtk-like look: entities coloured by kind everywhere, layers with eyes,
the panel switch with its keys, and the tool strip over the map."""

from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")


def _entity(*component_types):
    return SimpleNamespace(
        name="x", components=lambda: [type(t, (), {})() for t in component_types]
    )


def test_an_entity_kind_follows_its_components():
    from asteria.editor.entity_kinds import KINDS, kind_of

    assert kind_of(_entity("Transform", "Camera2DComponent")) is KINDS["camera"]
    assert kind_of(_entity("Transform", "TileMap2DComponent")) is KINDS["map"]
    assert (
        kind_of(_entity("Transform", "CharacterController2D", "SpriteRenderer2D"))
        is (KINDS["player"])
    )
    talks = _entity("Transform", "SpriteRenderer2D", "Interaction2DComponent")
    assert kind_of(talks) is KINDS["character"]
    assert kind_of(_entity("Transform", "Interaction2DComponent")) is KINDS["trigger"]
    assert (
        kind_of(_entity("Transform", "SpriteRenderer2D", "Collider2DComponent")) is (KINDS["prop"])
    )
    assert kind_of(_entity("Transform")) is KINDS["entity"]
    assert kind_of(object()) is KINDS["entity"]  # nothing to read: the neutral kind
    assert len({k.colour for k in KINDS.values()}) == len(KINDS)  # every kind its own colour


def test_the_theme_colours_kind_badges_and_panel_switch_buttons():
    from asteria.editor.entity_kinds import KINDS
    from asteria.editor.theme import ASTERIA_DARK_QSS

    for kind in KINDS.values():
        assert f'QLabel#KindBadge[entityKind="{kind.kind}"]' in ASTERIA_DARK_QSS
        assert kind.colour in ASTERIA_DARK_QSS
    for name in ("ProjectSceneDock", "TilePaletteDock", "LayersDock"):
        assert f'QToolButton#PanelSwitchButton[panel="{name}"]' in ASTERIA_DARK_QSS
    assert "QFrame#ToolStrip" in ASTERIA_DARK_QSS


def test_layer_rows_have_an_eye_that_shows_or_hides_the_layer(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.tile_layers_widget import TileLayersWidget, layer_colour

    QApplication.instance() or QApplication([])
    ground = SimpleNamespace(name="Ground", visible=True, collision_enabled=False)
    walls = SimpleNamespace(name="Collision", visible=False, collision_enabled=True)
    tilemap = SimpleNamespace(layers=[ground, walls])
    widget = TileLayersWidget()
    widget.set_tilemap(tilemap, ground)
    assert widget.list.count() == 2 and len(widget.eye_buttons) == 2
    assert widget.eye_buttons[0].isChecked() and not widget.eye_buttons[1].isChecked()
    changes = []
    widget.visibilityChanged.connect(lambda layer, on: changes.append((layer.name, on)))
    widget.eye_buttons[0].click()
    assert changes == [("Ground", False)]
    assert layer_colour(1, collision=True) == "#e06a5c"  # a collision layer is always coral
    assert layer_colour(0) != layer_colour(1)


def test_the_panel_switch_and_its_keys_open_the_left_panels(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QDockWidget

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.show()
        for _ in range(10):
            app.processEvents()
        switch = window.panel_switches[0]
        assert [b.key for b in switch.buttons.values()] == ["P", "T", "L"]
        assert switch.buttons["ProjectSceneDock"].toolTip() == "Project (P)"
        switch.buttons["TilePaletteDock"].click()
        for _ in range(5):
            app.processEvents()
        assert window.current_left_tab() == "TilePaletteDock"
        window.findChild(QDockWidget, "LayersDock").hide()  # closed by the user...
        window.show_left_panel("LayersDock")  # ...the key opens it again
        for _ in range(5):
            app.processEvents()
        assert window.findChild(QDockWidget, "LayersDock").isVisible()
        assert window.current_left_tab() == "LayersDock"
        assert all(s.isEnabled() for s in window.panel_shortcuts)  # Scene's keys
        window.workspace.set_mode(WorkspaceMode.RPG)
        assert not any(s.isEnabled() for s in window.panel_shortcuts)
        window.workspace.set_mode(WorkspaceMode.SCENE)
        assert all(s.isEnabled() for s in window.panel_shortcuts)
    finally:
        window.close()
        window.deleteLater()


def test_the_tool_strip_mirrors_the_tile_palette_mode(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.show()
        app.processEvents()
        strip = window.tool_strip
        assert strip.parent() is window.viewport and strip.pos().x() == 12
        assert strip.buttons["select"].isChecked()
        assert strip.buttons["paint"].key == "B" and strip.buttons["terrain"].key == ""
        strip.buttons["paint"].click()
        assert window.tile_palette.paint_button.isChecked()
        assert window.viewport.tile_tools.mode == "paint"
        assert strip.buttons["paint"].isChecked() and not strip.buttons["select"].isChecked()
        window.tile_palette.handle_tool_key("erase")  # the key over the map: the strip follows
        assert strip.buttons["erase"].isChecked() and not strip.buttons["paint"].isChecked()
        assert not window.tile_palette.tool_hint.isVisibleTo(window.tile_palette)
    finally:
        window.close()
        window.deleteLater()
