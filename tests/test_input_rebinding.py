"""ENG-15: rebinding — player overrides (in-game Controls screen) over the project's input map (editor)."""

import pygame
import pytest

from asteria.runtime.game_menus import GameSettings
from asteria.runtime.input_map import InputActionMap, InputBinding, RawInputState
from asteria.runtime.input_rebinding import ControlsMenu, effective_input_map


def test_capture_rebinds_exclusively_and_reset_restores_defaults():
    base = InputActionMap.default()
    menu = ControlsMenu(base)
    menu.row = [r[0] for r in menu.rows()].index("interact")
    assert menu.select() == "interact" and menu.capturing == "interact"
    menu.capture(InputBinding("key", "space"))
    current = menu.input_map
    assert InputBinding("key", "space") in current.bindings("interact")
    assert all(InputBinding("key", "space") not in current.bindings(a) for a in current.actions() if a != "interact")
    assert "interact" in menu.overrides and base.bindings("interact") != current.bindings("interact")
    menu.reset("interact")
    assert menu.input_map.bindings("interact") == base.bindings("interact")
    menu.row = len(menu.rows()) - 1
    menu.select()  # Reset all
    assert menu.overrides == {}


def test_settings_store_overrides_and_old_settings_still_load(tmp_path):
    settings = GameSettings(input_overrides={"interact": [InputBinding("key", "x").to_data()]})
    loaded = GameSettings.load(settings.save(tmp_path / "s.json"))
    assert loaded.input_overrides == settings.input_overrides
    old = settings.to_data()
    old["version"] = 1
    old.pop("input_overrides")
    assert GameSettings.from_data(old).input_overrides == {}
    snapshot = effective_input_map(InputActionMap.default(), loaded.input_overrides).evaluate(RawInputState(keys={"x"}))
    assert snapshot.actions["interact"] == 1.0


def test_in_game_controls_screen_rebinds_and_the_new_key_works(runtime):
    def key(k):
        runtime._frame([pygame.event.Event(pygame.KEYDOWN, key=k, mod=0)], 0.016)
        runtime._frame([pygame.event.Event(pygame.KEYUP, key=k, mod=0)], 0.016)

    runtime._ui_mode = "settings"
    runtime._settings_menu.index = [k for k, _ in GameSettings.OPTIONS].index("controls")
    key(pygame.K_RETURN)
    assert runtime._ui_mode == "controls"
    menu = runtime.controls_menu
    menu.row = [r[0] for r in menu.rows()].index("interact")
    key(pygame.K_RETURN)
    assert menu.capturing == "interact"
    key(pygame.K_x)
    assert menu.capturing is None and runtime.settings.input_overrides["interact"][0]["code"] == "x"
    key(pygame.K_ESCAPE)
    assert runtime._ui_mode == "settings"
    saved = GameSettings.load(runtime._settings_path())
    assert saved.input_overrides == runtime.settings.input_overrides  # kept for the next session
    runtime._ui_mode = "field"
    runtime.game.set_player_position(36.0, 0.0)  # next to the boss
    runtime.game.set_player_facing("right")
    key(pygame.K_x)
    assert runtime.game.pending_dialogue is not None  # X now interacts


def test_editor_input_map_tab_edits_project_defaults_with_undo():
    pytest.importorskip("PySide6")
    from pathlib import Path

    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.input_map_widget import InputMapWidget
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    ref = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    widget = InputMapWidget(document)
    widget.refresh(select="interact")
    before = widget.bindings.count()
    widget.device.setCurrentText("key")
    widget.code.setText("f")
    assert widget.add_binding_from_form() and widget.bindings.count() == before + 1
    assert InputBinding("key", "f") in document.project.input_map.bindings("interact")
    widget.bindings.setCurrentRow(widget.bindings.count() - 1)
    assert widget.remove_selected_binding() and widget.bindings.count() == before
    document.undo()
    assert InputBinding("key", "f") in document.project.input_map.bindings("interact")
    roundtrip = Project.from_data(document.project.to_data(), document.component_registry)
    assert InputBinding("key", "f") in roundtrip.input_map.bindings("interact")
