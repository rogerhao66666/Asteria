"""Editor-facing checks for the multiplayer authoring workspace."""

from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QProcessEnvironment
from PySide6.QtTest import QTest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

from asteria.editor.multiplayer_workspace import MultiplayerWorkspaceWidget


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_boss_demo_selection_input_ack_and_position_preview(app):
    widget = MultiplayerWorkspaceWidget(SimpleNamespace(file_path=None))
    try:
        widget.use_boss_demo_adapter()
        assert widget.adapter_factory.text() == (
            "asteria.multiplayer.boss_demo:build_boss_adapter"
        )
        assert widget.input_state.text() == '{"move_x": 0, "move_y": 0, "attack": true}'

        widget._on_message({"type": "input_ack", "sequence": 7, "accepted": True, "reason": ""})
        assert "Input frame 7 accepted" in widget.log.toPlainText()

        widget._on_message(
            {
                "type": "game_update",
                "revision": 12,
                "state": {
                    "boss": {"x": 0, "y": 0, "hp": 120, "max_hp": 240},
                    "players": [{"player_id": "p1", "display_name": "Ranger", "x": -3, "y": 0}],
                },
                "events": [],
            }
        )
        assert widget.position_preview._boss == (0.0, 0.0)
        assert widget.position_preview._players == (("Ranger", -3.0, 0.0),)
    finally:
        widget.shutdown()
        widget.close()


def test_counter_movement_selectors_and_profile_round_trip(app, tmp_path):
    project_file = tmp_path / "Project.asteria.json"
    document = SimpleNamespace(file_path=project_file)
    writer = MultiplayerWorkspaceWidget(document)
    reader = None
    try:
        writer.use_counter_demo_adapter()
        assert writer.adapter_factory.text().endswith("build_counter_adapter")
        assert writer.command_name.text() == "increment"
        writer.use_movement_demo_adapter()
        assert writer.adapter_factory.text().endswith("build_movement_adapter")

        writer.session_name.setText("Co-op Check")
        writer.listen_address.setCurrentText("127.0.0.1")
        writer.max_players.setValue(3)
        writer.server_address.setText("127.0.0.1")
        writer.port.setValue(9012)
        writer.player_name.setText("Ranger")
        writer.guest_id.setText("stable-ranger-id")
        writer.connect_runtime.setChecked(True)
        assert writer.save_profile()

        reader = MultiplayerWorkspaceWidget(document)
        assert reader.session_name.text() == "Co-op Check"
        assert reader.max_players.value() == 3
        assert reader.port.value() == 9012
        assert reader.player_name.text() == "Ranger"
        assert reader.guest_id.text() == "stable-ranger-id"
        assert reader.connect_runtime.isChecked()
        assert reader.adapter_factory.text().endswith("build_movement_adapter")
    finally:
        writer.shutdown()
        writer.close()
        if reader is not None:
            reader.shutdown()
            reader.close()


def test_project_boss_rules_template_is_editable_and_persisted(app, tmp_path):
    from asteria.multiplayer.rules import default_rules

    document = SimpleNamespace(file_path=tmp_path / "Project.asteria.json")
    writer = MultiplayerWorkspaceWidget(document)
    reader = None
    try:
        writer.use_boss_demo_adapter()
        rules = default_rules()
        rules["rewards"]["boss"]["experience"]["amount"] = 250
        writer.rules_editor.setPlainText(json.dumps(rules))
        assert writer.save_project_rules()

        reader = MultiplayerWorkspaceWidget(document)
        loaded = json.loads(reader.rules_editor.toPlainText())
        assert loaded["rewards"]["boss"]["experience"]["amount"] == 250
        assert "full_amount_per_eligible_player" in reader.rules_editor.toPlainText()
    finally:
        writer.shutdown()
        writer.close()
        if reader is not None:
            reader.shutdown()
            reader.close()


def test_editor_launches_project_server_with_sqlite_and_rule_files(app, tmp_path):
    widget = MultiplayerWorkspaceWidget(
        SimpleNamespace(file_path=tmp_path / "Project.asteria.json")
    )
    try:
        widget.use_boss_demo_adapter()
        assert widget.save_project_rules()
        process = widget._server_process
        environment = QProcessEnvironment.systemEnvironment()
        source_root = Path(__file__).resolve().parents[1] / "src"
        current_pythonpath = environment.value("PYTHONPATH")
        environment.insert(
            "PYTHONPATH",
            os.pathsep.join(
                str(path)
                for path in (
                    source_root,
                    Path(current_pythonpath) if current_pythonpath else None,
                )
                if path is not None
            ),
        )
        process.setProcessEnvironment(environment)
        assert widget.start_local_server()
        assert process.waitForStarted(5000)
        QTest.qWait(300)
        assert "Server running" in widget.local_server_status.text()
        assert "Server ready" in widget.log.toPlainText()
        assert (tmp_path / ".asteria" / "multiplayer.sqlite3").exists()
    finally:
        widget.stop_local_server()
        widget._server_process.waitForFinished(5000)
        widget.shutdown()
        widget.close()


def test_ping_response_shows_round_trip_time(app):
    import time

    widget = MultiplayerWorkspaceWidget(SimpleNamespace(file_path=None))
    try:
        widget._on_message({"type": "pong", "client_time": time.monotonic() - 0.025})
        assert "Ping:" in widget.log.toPlainText()
        assert "ms" in widget.log.toPlainText()
    finally:
        widget.shutdown()
        widget.close()


def test_save_profile_icon_is_visible_on_primary_button(app):
    widget = MultiplayerWorkspaceWidget(SimpleNamespace(file_path=None))
    try:
        icon_image = widget.save_profile_button.icon().pixmap(24, 24).toImage()
        opaque_pixels = [
            icon_image.pixelColor(x, y)
            for y in range(icon_image.height())
            for x in range(icon_image.width())
            if icon_image.pixelColor(x, y).alpha() > 240
        ]

        assert any(
            color.red() >= 230 and color.green() >= 230 and color.blue() >= 230
            for color in opaque_pixels
        )
    finally:
        widget.shutdown()
        widget.close()
