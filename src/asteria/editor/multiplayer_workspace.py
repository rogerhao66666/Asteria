"""Standalone Multiplayer workspace for configuring and trying Asteria sessions."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Qt, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from asteria.multiplayer import MultiplayerClient, MultiplayerClientError
from asteria.multiplayer.protocol import clean_guest_id
from asteria.multiplayer.rules import default_rules, load_rules, save_rules, validate_rules

from .flow_layout import FlowLayout
from .icons import icon

_PROFILE_SCHEMA = "asteria.multiplayer.profile"
_PROFILE_VERSION = 1


class _NetworkPositionPreview(QWidget):
    """Draw player positions published by adapters that include x/y coordinates."""

    _COLORS = ("#55aeb8", "#8f78df", "#e2a84a", "#62b67b", "#e17872", "#5e9dde")

    def __init__(self, parent=None):
        super().__init__(parent)
        self._players = ()
        self._boss = None
        self._boss_label = "Boss"
        self.setMinimumHeight(190)

    def set_state(self, state):
        players = state.get("players", ()) if isinstance(state, dict) else ()
        normalized = []
        if isinstance(players, (list, tuple)):
            for item in players:
                if not isinstance(item, dict):
                    continue
                try:
                    x, y = float(item["x"]), float(item["y"])
                except (KeyError, TypeError, ValueError):
                    continue
                if not math.isfinite(x) or not math.isfinite(y):
                    continue
                normalized.append((str(item.get("display_name", "Player")), x, y))
        self._players = tuple(normalized)
        self._boss = None
        self._boss_label = "Boss"
        boss = state.get("boss") if isinstance(state, dict) else None
        if isinstance(boss, dict):
            try:
                boss_x, boss_y = float(boss["x"]), float(boss["y"])
            except (KeyError, TypeError, ValueError):
                pass
            else:
                if math.isfinite(boss_x) and math.isfinite(boss_y):
                    self._boss = (boss_x, boss_y)
                    hp, maximum = boss.get("hp"), boss.get("max_hp")
                    if isinstance(hp, (int, float)) and isinstance(maximum, (int, float)):
                        self._boss_label = f"Boss · {int(hp)}/{int(maximum)}"
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        palette = self.palette()
        border = palette.color(QPalette.ColorRole.Mid)
        base = palette.color(QPalette.ColorRole.Base)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        painter.setPen(QPen(border, 1))
        painter.setBrush(base)
        painter.drawRoundedRect(rect, 7, 7)

        area = rect.adjusted(12, 12, -12, -12)
        painter.save()
        painter.setClipRect(area)
        grid = palette.color(QPalette.ColorRole.Mid)
        grid.setAlpha(65)
        painter.setPen(QPen(grid, 1))
        spacing = 28
        first_x = int(area.left()) - (int(area.left()) % spacing)
        first_y = int(area.top()) - (int(area.top()) % spacing)
        for x in range(first_x, int(area.right()) + spacing, spacing):
            painter.drawLine(x, int(area.top()), x, int(area.bottom()))
        for y in range(first_y, int(area.bottom()) + spacing, spacing):
            painter.drawLine(int(area.left()), y, int(area.right()), y)

        if not self._players and self._boss is None:
            painter.setPen(muted)
            painter.drawText(
                area,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                "Adapter player positions with x/y coordinates appear here.",
            )
            painter.restore()
            return

        xs = [item[1] for item in self._players]
        ys = [item[2] for item in self._players]
        if self._boss is not None:
            xs.append(self._boss[0])
            ys.append(self._boss[1])
        span_x = max(max(xs) - min(xs), 8.0)
        span_y = max(max(ys) - min(ys), 8.0)
        scale = min(
            max(1.0, area.width() - 84) / span_x,
            max(1.0, area.height() - 52) / span_y,
        )
        center_x = (min(xs) + max(xs)) / 2
        center_y = (min(ys) + max(ys)) / 2
        origin = area.center()
        if self._boss is not None:
            boss_x = origin.x() + (self._boss[0] - center_x) * scale
            boss_y = origin.y() - (self._boss[1] - center_y) * scale
            boss_color = QColor("#e17872")
            painter.setPen(QPen(base, 2))
            painter.setBrush(boss_color)
            painter.drawRect(int(boss_x - 8), int(boss_y - 8), 16, 16)
            width = painter.fontMetrics().horizontalAdvance(self._boss_label) + 12
            label = self.rect().adjusted(0, 0, 0, 0)
            label.setLeft(int(boss_x + 11))
            label.setTop(int(boss_y - 11))
            label.setWidth(width)
            label.setHeight(22)
            painter.setPen(QPen(boss_color, 1))
            painter.setBrush(base)
            painter.drawRoundedRect(label, 5, 5)
            painter.setPen(palette.color(QPalette.ColorRole.Text))
            painter.drawText(
                label.adjusted(6, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                self._boss_label,
            )

        for index, (name, x, y) in enumerate(self._players):
            point_x = origin.x() + (x - center_x) * scale
            point_y = origin.y() - (y - center_y) * scale
            color = QColor(self._COLORS[index % len(self._COLORS)])
            painter.setPen(QPen(base, 2))
            painter.setBrush(color)
            painter.drawEllipse(int(point_x - 7), int(point_y - 7), 14, 14)
            label_width = painter.fontMetrics().horizontalAdvance(name) + 12
            label = self.rect().adjusted(0, 0, 0, 0)
            label.setLeft(int(point_x + 11))
            label.setTop(int(point_y - 11))
            label.setWidth(label_width)
            label.setHeight(22)
            painter.setPen(QPen(color, 1))
            painter.setBrush(base)
            painter.drawRoundedRect(label, 5, 5)
            painter.setPen(palette.color(QPalette.ColorRole.Text))
            painter.drawText(
                label.adjusted(6, 0, -4, 0),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                name,
            )
        painter.restore()


def _make_card(title):
    card = QFrame()
    card.setObjectName("Card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 11, 12, 12)
    layout.setSpacing(9)
    heading = QLabel(title)
    heading.setObjectName("CardTitle")
    layout.addWidget(heading)
    return card, layout


class _NetworkClientWorker(QObject):
    connected = Signal(dict)
    messageReceived = Signal(dict)
    disconnected = Signal(str)
    failed = Signal(str)
    left = Signal()
    commandSent = Signal(str)
    inputSent = Signal(int)

    def __init__(self):
        super().__init__()
        self.client: MultiplayerClient | None = None

    @Slot(str, int, str, str)
    def connect_to(self, host, port, display_name, guest_id):
        self.close_client(emit_left=False)
        client = MultiplayerClient(
            on_message=lambda value: self.messageReceived.emit(dict(value)),
            on_disconnect=lambda reason: self.disconnected.emit(str(reason)),
        )
        try:
            welcome = client.connect(host, port, display_name, guest_id=guest_id)
        except (MultiplayerClientError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.client = client
        self.connected.emit(welcome)

    @Slot()
    def close_client(self, emit_left=True):
        client, self.client = self.client, None
        if client is not None:
            client.close()
        if emit_left:
            self.left.emit()

    @Slot()
    def ping(self):
        if self.client is None:
            self.failed.emit("Join a session before sending a ping")
            return
        try:
            self.client.send_ping()
        except MultiplayerClientError as exc:
            self.failed.emit(str(exc))

    @Slot(str, dict)
    def send_command(self, command, payload):
        if self.client is None:
            self.failed.emit("Join a session before sending a game command")
            return
        try:
            command_id = self.client.send_command(command, payload)
        except (MultiplayerClientError, TypeError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.commandSent.emit(command_id)

    @Slot(dict)
    def send_input(self, input_state):
        if self.client is None:
            self.failed.emit("Join a session before sending real-time input")
            return
        try:
            sequence = self.client.send_input(input_state)
        except (MultiplayerClientError, TypeError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        self.inputSent.emit(sequence)


class MultiplayerWorkspaceWidget(QWidget):
    """Host a local lobby or join a server without changing game/editor state."""

    _joinRequested = Signal(str, int, str, str)
    _leaveRequested = Signal()
    _pingRequested = Signal()
    _commandRequested = Signal(str, dict)
    _inputRequested = Signal(dict)

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self._profile_key = None
        self._rules_key = None
        self._stdout_pending = ""
        self._closing = False

        self._client_thread = QThread(self)
        self._client_worker = _NetworkClientWorker()
        self._client_worker.moveToThread(self._client_thread)
        self._joinRequested.connect(self._client_worker.connect_to)
        self._leaveRequested.connect(self._client_worker.close_client)
        self._pingRequested.connect(self._client_worker.ping)
        self._commandRequested.connect(self._client_worker.send_command)
        self._inputRequested.connect(self._client_worker.send_input)
        self._client_worker.connected.connect(self._on_connected)
        self._client_worker.messageReceived.connect(self._on_message)
        self._client_worker.disconnected.connect(self._on_disconnected)
        self._client_worker.failed.connect(self._on_network_error)
        self._client_worker.left.connect(self._on_left)
        self._client_worker.commandSent.connect(self._on_command_sent)
        self._client_worker.inputSent.connect(self._on_input_sent)
        self._client_thread.start()

        self._server_process = QProcess(self)
        self._server_process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._server_process.readyReadStandardOutput.connect(self._read_server_output)
        self._server_process.finished.connect(self._server_finished)
        self._server_process.errorOccurred.connect(self._server_error)

        self._build_ui()
        self.refresh_profile()
        self.refresh_rules()

    def _build_ui(self):
        header_icon = QLabel()
        header_icon.setPixmap(icon("multiplayer").pixmap(30, 30))
        header_icon.setFixedSize(36, 36)
        title = QLabel("Multiplayer")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Connect players in any game through Asteria's network adapter API.")
        subtitle.setObjectName("MutedLabel")
        subtitle.setWordWrap(True)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header = QHBoxLayout()
        header.setSpacing(10)
        header.addWidget(header_icon, 0, Qt.AlignmentFlag.AlignTop)
        header.addLayout(heading, 1)
        header.addStretch(1)

        self.session_name = QLineEdit("Asteria Session")
        self.session_name.setPlaceholderText("Session name")
        self.listen_address = QComboBox()
        self.listen_address.setEditable(True)
        self.listen_address.setMinimumContentsLength(15)
        self.listen_address.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.listen_address.ensurePolished()
        self.listen_address.setMinimumWidth(
            self.listen_address.fontMetrics().horizontalAdvance("255.255.255.255") + 64
        )
        self.listen_address.addItems(["127.0.0.1", "0.0.0.0"])
        self.listen_address.setCurrentText("127.0.0.1")
        self.max_players = QSpinBox()
        self.max_players.setRange(2, 64)
        self.max_players.setValue(4)
        self.adapter_factory = QLineEdit()
        self.adapter_factory.setPlaceholderText("package.module:build_adapter")
        self.counter_demo_button = QPushButton("Use Counter Demo")
        self.counter_demo_button.setIcon(icon("multiplayer"))
        self.movement_demo_button = QPushButton("Use Movement Demo")
        self.movement_demo_button.setIcon(icon("multiplayer"))
        self.boss_demo_button = QPushButton("Use Boss Co-op Demo")
        self.boss_demo_button.setIcon(icon("multiplayer"))
        # the box level with its label, its examples under it (beside the box, the stack of
        # three pushed the box down to their middle and squeezed its text)
        adapter_row = QVBoxLayout()
        adapter_row.setSpacing(6)
        adapter_row.addWidget(self.adapter_factory)
        adapter_examples = FlowLayout(spacing=6)  # more lines in a narrow panel
        adapter_examples.addWidget(self.counter_demo_button)
        adapter_examples.addWidget(self.movement_demo_button)
        adapter_examples.addWidget(self.boss_demo_button)
        adapter_row.addLayout(adapter_examples)
        host_form = QFormLayout()
        host_form.addRow("Session Name", self.session_name)
        host_form.addRow("Listen Address", self.listen_address)
        host_form.addRow("Maximum Players", self.max_players)
        host_form.addRow("Game Adapter", adapter_row)
        host_hint = QLabel(
            "127.0.0.1 is local only. Use 0.0.0.0 for LAN play. Add a server-side "
            "adapter as package.module:factory to run game rules."
        )
        host_hint.setObjectName("MutedLabel")
        host_hint.setWordWrap(True)
        self.start_server_button = QPushButton("Start Local Server")
        self.start_server_button.setIcon(icon("play"))
        self.start_server_button.setProperty("role", "primary")
        self.stop_server_button = QPushButton("Stop Server")
        self.stop_server_button.setIcon(icon("stop"))
        self.stop_server_button.setEnabled(False)
        server_buttons = QHBoxLayout()
        server_buttons.addWidget(self.start_server_button)
        server_buttons.addWidget(self.stop_server_button)
        host_box, host_layout = _make_card("Host a Session")
        host_layout.addLayout(host_form)
        host_layout.addWidget(host_hint)
        host_layout.addLayout(server_buttons)

        self.server_address = QLineEdit("127.0.0.1")
        self.server_address.setPlaceholderText("127.0.0.1")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(8765)
        self.player_name = QLineEdit("Player")
        self.player_name.setMaxLength(40)
        self.guest_id = QLineEdit(uuid.uuid4().hex[:16])
        self.guest_id.setMaxLength(64)
        self.guest_id.setPlaceholderText("Persistent project guest ID")
        self.new_guest_id_button = QPushButton("New ID")
        guest_id_row = QHBoxLayout()
        guest_id_row.addWidget(self.guest_id, 1)
        guest_id_row.addWidget(self.new_guest_id_button)
        join_form = QFormLayout()
        join_form.addRow("Server Address", self.server_address)
        join_form.addRow("Port", self.port)
        join_form.addRow("Player Name", self.player_name)
        join_form.addRow("Guest ID", guest_id_row)
        self.join_button = QPushButton("Join Session")
        self.join_button.setIcon(icon("multiplayer"))
        self.join_button.setProperty("role", "primary")
        self.leave_button = QPushButton("Leave Session")
        self.leave_button.setIcon(icon("stop"))
        self.leave_button.setEnabled(False)
        self.ping_button = QPushButton("Ping Server")
        self.ping_button.setIcon(icon("events"))
        self.ping_button.setEnabled(False)
        join_buttons = QHBoxLayout()
        join_buttons.addWidget(self.join_button)
        join_buttons.addWidget(self.leave_button)
        join_buttons.addWidget(self.ping_button)
        client_box, client_layout = _make_card("Connect to a Session")
        client_layout.addLayout(join_form)
        client_layout.addLayout(join_buttons)

        profile_box, profile_layout = _make_card("Connection Profile")
        self.connect_runtime = QCheckBox("Connect Run Project to this multiplayer session")
        self.connect_runtime.setObjectName("ConnectRuntimeCheckbox")
        self.connect_runtime.setToolTip(
            "When enabled, Run Project joins the configured server and shows network players "
            "in the game field."
        )
        profile_layout.addWidget(self.connect_runtime)
        self.profile_path_label = QLabel("Profile is stored with the current project.")
        self.profile_path_label.setObjectName("MutedLabel")
        self.profile_path_label.setWordWrap(True)
        self.save_profile_button = QPushButton("Save Profile")
        self.save_profile_button.setIcon(icon("save", "#ffffff"))
        profile_layout.addWidget(self.profile_path_label)
        profile_layout.addWidget(self.save_profile_button, 0, Qt.AlignmentFlag.AlignHCenter)

        self.rules_editor = QPlainTextEdit(
            json.dumps(default_rules(), indent=2, ensure_ascii=False)
        )
        self.rules_editor.setObjectName("MultiplayerRulesEditor")
        self.rules_editor.setMinimumHeight(210)
        self.rules_editor.setPlaceholderText("Versioned project-owned game rules JSON")
        rules_hint = QLabel(
            "Boss template: every player who deals accepted damage receives the full XP amount; "
            "each drop goes to one eligible player. Custom adapters can define other rules."
        )
        rules_hint.setObjectName("MutedLabel")
        rules_hint.setWordWrap(True)
        self.use_boss_rules_button = QPushButton("Use Boss Reward Template")
        self.use_boss_rules_button.setIcon(icon("events"))
        self.save_rules_button = QPushButton("Save Project Rules")
        self.save_rules_button.setIcon(icon("save"))
        rules_buttons = QHBoxLayout()
        rules_buttons.addWidget(self.use_boss_rules_button)
        rules_buttons.addWidget(self.save_rules_button)
        rules_box, rules_layout = _make_card("Game Rules Template")
        rules_layout.addWidget(rules_hint)
        rules_layout.addWidget(self.rules_editor)
        rules_layout.addLayout(rules_buttons)
        self.local_server_status = QLabel("● Local server stopped")
        self.local_server_status.setObjectName("MultiplayerServerStatus")
        self.connection_status = QLabel("● Not connected")
        self.connection_status.setObjectName("MultiplayerConnectionStatus")

        left_column = QVBoxLayout()
        left_column.setSpacing(12)
        left_column.addWidget(host_box)
        left_column.addWidget(client_box)
        left_column.addWidget(profile_box)
        left_column.addWidget(rules_box)
        left_column.addStretch(1)

        self.players = QListWidget()
        self.players.setAlternatingRowColors(True)
        self.players.setMinimumHeight(130)
        player_box, player_layout = _make_card("Players in Session")
        player_header = QHBoxLayout()
        player_header.addWidget(self.connection_status, 1)
        player_layout.addLayout(player_header)
        player_layout.addWidget(self.players, 1)

        position_preview_box, position_preview_layout = _make_card("Network Position Preview")
        position_preview_hint = QLabel(
            "Shows adapter players that publish x/y positions; game art stays in the game view."
        )
        position_preview_hint.setObjectName("MutedLabel")
        position_preview_hint.setWordWrap(True)
        position_preview_layout.addWidget(position_preview_hint)
        self.position_preview = _NetworkPositionPreview()
        position_preview_layout.addWidget(self.position_preview)

        playground_box, playground_layout = _make_card("Adapter Playground")
        playground_hint = QLabel(
            "Send a game-specific command to the server adapter and inspect "
            "its authoritative reply."
        )
        playground_hint.setObjectName("MutedLabel")
        playground_hint.setWordWrap(True)
        playground_layout.addWidget(playground_hint)
        self.command_name = QLineEdit("increment")
        self.command_name.setPlaceholderText("Command name")
        self.command_payload = QLineEdit('{"amount": 1}')
        self.command_payload.setPlaceholderText('JSON object, for example {"amount": 1}')
        command_form = QFormLayout()
        command_form.addRow("Command", self.command_name)
        command_form.addRow("Payload", self.command_payload)
        playground_layout.addLayout(command_form)
        self.send_command_button = QPushButton("Send Game Command")
        self.send_command_button.setIcon(icon("events"))
        self.send_command_button.setEnabled(False)
        playground_layout.addWidget(self.send_command_button, 0, Qt.AlignmentFlag.AlignLeft)
        self.input_state = QLineEdit('{"move_x": 1, "move_y": 0}')
        self.input_state.setPlaceholderText('JSON object, for example {"move_x": 1, "move_y": 0}')
        input_form = QFormLayout()
        input_form.addRow("Real-time Input", self.input_state)
        playground_layout.addLayout(input_form)
        input_hint = QLabel(
            "Input values stay active until replaced. Send zero axes to stop moving; "
            "each frame is acknowledged, and the server limits each player to 60 frames/sec."
        )
        input_hint.setObjectName("MutedLabel")
        input_hint.setWordWrap(True)
        playground_layout.addWidget(input_hint)
        input_buttons = QHBoxLayout()
        self.send_input_button = QPushButton("Send Input State")
        self.send_input_button.setIcon(icon("events"))
        self.send_input_button.setEnabled(False)
        self.stop_input_button = QPushButton("Stop Input")
        self.stop_input_button.setIcon(icon("stop"))
        self.stop_input_button.setEnabled(False)
        input_buttons.addWidget(self.send_input_button)
        input_buttons.addWidget(self.stop_input_button)
        input_buttons.addStretch(1)
        playground_layout.addLayout(input_buttons)
        self.game_state_preview = QPlainTextEdit()
        self.game_state_preview.setReadOnly(True)
        self.game_state_preview.setMaximumHeight(132)
        self.game_state_preview.setPlaceholderText(
            "Authoritative state and events from the adapter will appear here."
        )
        playground_layout.addWidget(self.game_state_preview)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(250)
        self.log.setPlaceholderText("Session activity will appear here.")
        log_box, log_layout = _make_card("Connection Log")
        log_layout.addWidget(self.log)
        right_column = QVBoxLayout()
        right_column.setSpacing(12)
        right_column.addWidget(player_box, 1)
        right_column.addWidget(position_preview_box, 2)
        right_column.addWidget(playground_box, 2)
        right_column.addWidget(log_box, 2)

        body_content = QWidget()
        body = QHBoxLayout(body_content)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(16)
        body.addLayout(left_column, 1)
        body.addLayout(right_column, 1)
        body_scroll = QScrollArea()
        body_scroll.setWidgetResizable(True)
        body_scroll.setFrameShape(QFrame.Shape.NoFrame)
        body_scroll.setWidget(body_content)
        footer = QLabel(
            "The local server provides session and lobby networking. A game adapter supplies "
            "authoritative rules and synchronized game state."
        )
        footer.setObjectName("MutedLabel")
        footer.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addLayout(header)
        layout.addWidget(self.local_server_status)
        layout.addWidget(body_scroll, 1)
        layout.addWidget(footer)

        self.start_server_button.clicked.connect(self.start_local_server)
        self.stop_server_button.clicked.connect(self.stop_local_server)
        self.join_button.clicked.connect(self.join_session)
        self.leave_button.clicked.connect(self.leave_session)
        self.ping_button.clicked.connect(self._pingRequested.emit)
        self.send_command_button.clicked.connect(self._send_game_command)
        self.send_input_button.clicked.connect(self._send_input_state)
        self.stop_input_button.clicked.connect(self._stop_input)
        self.save_profile_button.clicked.connect(self.save_profile)
        self.counter_demo_button.clicked.connect(self.use_counter_demo_adapter)
        self.movement_demo_button.clicked.connect(self.use_movement_demo_adapter)
        self.boss_demo_button.clicked.connect(self.use_boss_demo_adapter)
        self.new_guest_id_button.clicked.connect(self.regenerate_guest_id)
        self.use_boss_rules_button.clicked.connect(self.use_boss_rules_template)
        self.save_rules_button.clicked.connect(self.save_project_rules)

    def _send_game_command(self):
        command = self.command_name.text().strip()
        if not command:
            self._on_network_error("Enter a game command name")
            return False
        try:
            payload = json.loads(self.command_payload.text() or "{}")
        except json.JSONDecodeError as exc:
            self._on_network_error(f"Command payload is not valid JSON: {exc.msg}")
            return False
        if not isinstance(payload, dict):
            self._on_network_error("Command payload must be a JSON object")
            return False
        self._commandRequested.emit(command, payload)
        return True

    def _send_input_state(self):
        try:
            input_state = json.loads(self.input_state.text() or "{}")
        except json.JSONDecodeError as exc:
            self._on_network_error(f"Input state is not valid JSON: {exc.msg}")
            return False
        if not isinstance(input_state, dict):
            self._on_network_error("Input state must be a JSON object")
            return False
        self._inputRequested.emit(input_state)
        return True

    def _stop_input(self):
        self.input_state.setText('{"move_x": 0, "move_y": 0}')
        return self._send_input_state()

    def use_counter_demo_adapter(self):
        self.adapter_factory.setText("asteria.multiplayer.examples:build_counter_adapter")
        self.command_name.setText("increment")
        self.command_payload.setText('{"amount": 1}')

    def use_movement_demo_adapter(self):
        self.adapter_factory.setText("asteria.multiplayer.examples:build_movement_adapter")
        self.input_state.setText('{"move_x": 1, "move_y": 0}')

    def use_boss_demo_adapter(self):
        self.adapter_factory.setText("asteria.multiplayer.boss_demo:build_boss_adapter")
        self.input_state.setText('{"move_x": 0, "move_y": 0, "attack": true}')
        self.use_boss_rules_template()

    def use_boss_rules_template(self):
        self.rules_editor.setPlainText(json.dumps(default_rules(), indent=2, ensure_ascii=False))
        return True

    def regenerate_guest_id(self):
        self.guest_id.setText(uuid.uuid4().hex[:16])
        return self.guest_id.text()

    def _project_profile_path(self):
        project_path = getattr(self.document, "file_path", None)
        if project_path is None:
            return None
        return Path(project_path).expanduser().resolve().parent / ".asteria" / "multiplayer.json"

    def _project_settings_dir(self):
        project_path = getattr(self.document, "file_path", None)
        if project_path is None:
            return None
        return Path(project_path).expanduser().resolve().parent / ".asteria"

    def _project_rules_path(self):
        settings_dir = self._project_settings_dir()
        return settings_dir / "multiplayer-rules.json" if settings_dir is not None else None

    def refresh_profile(self, force=False):
        path = self._project_profile_path()
        key = str(path) if path is not None else None
        if key == self._profile_key and not force:
            return
        self._profile_key = key
        if path is None:
            self.profile_path_label.setText("Save the project to store a multiplayer profile.")
            return
        self.profile_path_label.setText(f"Profile: {path}")
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or data.get("schema") != _PROFILE_SCHEMA
                or data.get("version") != _PROFILE_VERSION
            ):
                raise ValueError("unsupported multiplayer profile")
            self.session_name.setText(str(data.get("session_name", "Asteria Session")))
            self.listen_address.setCurrentText(str(data.get("listen_address", "127.0.0.1")))
            self.max_players.setValue(max(2, min(64, int(data.get("max_players", 4)))))
            self.adapter_factory.setText(str(data.get("adapter_factory", "")))
            self.server_address.setText(str(data.get("server_address", "127.0.0.1")))
            self.port.setValue(max(1, min(65535, int(data.get("port", 8765)))))
            self.player_name.setText(str(data.get("player_name", "Player")))
            self.connect_runtime.setChecked(bool(data.get("connect_on_run", False)))
            guest_id = data.get("guest_id")
            if guest_id:
                self.guest_id.setText(clean_guest_id(guest_id))
            self._append_log(f"Loaded profile {path}")
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self._append_log(f"Could not load profile: {exc}")

    def save_profile(self):
        path = self._project_profile_path()
        if path is None:
            self.profile_path_label.setText(
                "Save the project before saving a multiplayer profile."
            )
            return False
        try:
            guest_id = clean_guest_id(self.guest_id.text())
        except ValueError as exc:
            self._append_log(f"Could not save profile: {exc}")
            return False
        payload = {
            "schema": _PROFILE_SCHEMA,
            "version": _PROFILE_VERSION,
            "session_name": self.session_name.text().strip() or "Asteria Session",
            "listen_address": self.listen_address.currentText().strip() or "127.0.0.1",
            "max_players": self.max_players.value(),
            "adapter_factory": self.adapter_factory.text().strip(),
            "server_address": self.server_address.text().strip() or "127.0.0.1",
            "port": self.port.value(),
            "player_name": self.player_name.text().strip() or "Player",
            "guest_id": guest_id,
            "connect_on_run": self.connect_runtime.isChecked(),
        }
        temp_path = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temp_path = Path(name)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except OSError as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
            self._append_log(f"Could not save profile: {exc}")
            return False
        self._profile_key = str(path)
        self.profile_path_label.setText(f"Profile saved: {path}")
        self._append_log(f"Saved profile {path}")
        return True

    def refresh_rules(self, force=False):
        path = self._project_rules_path()
        self._rules_key = str(path) if path is not None else None
        if path is None or not path.exists():
            return
        try:
            rules = load_rules(path)
            self.rules_editor.setPlainText(json.dumps(rules, indent=2, ensure_ascii=False))
        except (OSError, ValueError, TypeError) as exc:
            self._append_log(f"Could not load project rules: {exc}")

    def save_project_rules(self):
        path = self._project_rules_path()
        if path is None:
            self._append_log("Save the project before saving multiplayer rules.")
            return False
        try:
            value = json.loads(self.rules_editor.toPlainText())
            rules = validate_rules(value)
            save_rules(path, rules)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
            self._append_log(f"Could not save project rules: {exc}")
            return False
        self.rules_editor.setPlainText(json.dumps(rules, indent=2, ensure_ascii=False))
        self._rules_key = str(path)
        self._append_log(f"Saved project rules {path}")
        return True

    def start_local_server(self):
        if self._server_process.state() != QProcess.ProcessState.NotRunning:
            return False
        host = self.listen_address.currentText().strip() or "127.0.0.1"
        session = self.session_name.text().strip() or "Asteria Session"
        self._server_process.setProgram(sys.executable)
        arguments = [
            "-m",
            "asteria.multiplayer.server",
            "--host",
            host,
            "--port",
            str(self.port.value()),
            "--max-players",
            str(self.max_players.value()),
            "--session-name",
            session,
        ]
        adapter = self.adapter_factory.text().strip()
        if adapter:
            arguments.extend(("--adapter", adapter))
        if host not in ("127.0.0.1", "localhost", "::1"):
            # Choosing a LAN address here is the explicit decision the server asks for: it listens
            # beyond this machine without TLS or tokens (trusted network only).
            arguments.append("--insecure-lan")
            self._append_log("Listening beyond this machine without encryption (trusted LAN only)")
        self._server_process.setArguments(arguments)
        project_path = getattr(self.document, "file_path", None)
        if project_path is not None:
            arguments.extend(("--project", str(Path(project_path).expanduser().resolve())))
        settings_dir = self._project_settings_dir() or (Path.cwd() / ".asteria")
        arguments.extend(
            (
                "--database",
                str(settings_dir / "multiplayer.sqlite3"),
                "--rules",
                str(settings_dir / "multiplayer-rules.json"),
            )
        )
        self._server_process.setArguments(arguments)
        working_directory = (
            Path(project_path).expanduser().resolve().parent
            if project_path is not None
            else Path.cwd()
        )
        self._server_process.setWorkingDirectory(str(working_directory))
        self._stdout_pending = ""
        self._set_server_status("starting", "● Starting local server…")
        self.start_server_button.setEnabled(False)
        self.stop_server_button.setEnabled(True)
        self._server_process.start()
        self._append_log(f"Starting server on {host}:{self.port.value()}")
        return True

    def stop_local_server(self):
        if self._server_process.state() == QProcess.ProcessState.NotRunning:
            return False
        self.stop_server_button.setEnabled(False)
        self._server_process.terminate()
        QTimer.singleShot(1500, self, self._kill_local_server_if_running)
        return True

    def _kill_local_server_if_running(self):
        if self._server_process.state() != QProcess.ProcessState.NotRunning:
            self._server_process.kill()

    def join_session(self):
        if not self.join_button.isEnabled():
            return False
        host = self.server_address.text().strip()
        if not host:
            self._on_network_error("Enter a server address")
            return False
        self.join_button.setEnabled(False)
        self._set_connection_status("connecting", "● Connecting…")
        self._append_log(f"Connecting to {host}:{self.port.value()}")
        display_name = self.player_name.text().strip() or "Player"
        self._joinRequested.emit(
            host,
            self.port.value(),
            display_name,
            self.guest_id.text().strip(),
        )
        return True

    def leave_session(self):
        if self.leave_button.isEnabled():
            self._leaveRequested.emit()
            return True
        return False

    def _on_connected(self, welcome):
        self.join_button.setEnabled(False)
        self.leave_button.setEnabled(True)
        self.ping_button.setEnabled(True)
        self._set_connection_status(
            "connected", f"● Connected · {welcome.get('session_name', 'Session')}"
        )
        self.players.clear()
        for player in welcome.get("players", ()):
            self._add_player(player)
        self._append_log(
            f"Joined session {welcome.get('session_id', '')} as {welcome.get('player_id', '')}"
        )
        if welcome.get("state") is not None:
            self._append_log("Received initial game state")
            self._show_game_state(welcome.get("state"), revision=welcome.get("revision", 0))
        else:
            self._show_game_state(None, revision=welcome.get("revision", 0))
        self.send_command_button.setEnabled(True)
        self.send_input_button.setEnabled(True)
        self.stop_input_button.setEnabled(True)

    def _on_message(self, value):
        kind = value.get("type")
        if kind == "peer_joined":
            self._add_player(value.get("player", {}))
            self._append_log(f"{value.get('player', {}).get('display_name', 'Player')} joined")
        elif kind == "peer_left":
            player_id = str(value.get("player_id", ""))
            for row in range(self.players.count() - 1, -1, -1):
                item = self.players.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == player_id:
                    name = item.text()
                    self.players.takeItem(row)
                    self._append_log(f"{name} left")
                    break
        elif kind == "pong":
            sent_at = value.get("client_time")
            if (
                isinstance(sent_at, (int, float))
                and not isinstance(sent_at, bool)
                and math.isfinite(float(sent_at))
                and float(sent_at) <= time.monotonic()
            ):
                elapsed_ms = (time.monotonic() - float(sent_at)) * 1000
                self._append_log(f"Ping: {elapsed_ms:.1f} ms round trip")
            else:
                self._append_log("Server responded to ping")
        elif kind == "input_ack":
            sequence = value.get("sequence", "?")
            if value.get("accepted") is True:
                self._append_log(f"Input frame {sequence} accepted")
            else:
                reason = value.get("reason") or "unknown reason"
                self._append_log(f"Input frame {sequence} rejected: {reason}")
        elif kind == "game_update":
            revision = value.get("revision", 0)
            self._append_log(f"Received authoritative update · revision {revision}")
            if value.get("state") is not None or value.get("events"):
                self._show_game_state(
                    value.get("state"),
                    events=value.get("events", ()),
                    revision=revision,
                )
        elif kind == "server_error":
            self._append_log(f"Server: {value.get('message', 'error')}")
        else:
            self._append_log(f"Received {kind or 'message'}")

    def _on_disconnected(self, reason):
        self.join_button.setEnabled(True)
        self.leave_button.setEnabled(False)
        self.ping_button.setEnabled(False)
        self.send_command_button.setEnabled(False)
        self.send_input_button.setEnabled(False)
        self.stop_input_button.setEnabled(False)
        self._show_game_state(None)
        self._set_connection_status("offline", "● Not connected")
        self.players.clear()
        self._append_log(f"Disconnected: {reason}")

    def _on_left(self):
        self.join_button.setEnabled(True)
        self.leave_button.setEnabled(False)
        self.ping_button.setEnabled(False)
        self.send_command_button.setEnabled(False)
        self.send_input_button.setEnabled(False)
        self.stop_input_button.setEnabled(False)
        self._show_game_state(None)
        self._set_connection_status("offline", "● Not connected")
        self.players.clear()
        self._append_log("Left session")

    def _on_network_error(self, reason):
        self.join_button.setEnabled(True)
        self._set_connection_status("error", f"● {reason}")
        self._append_log(f"Network: {reason}")

    def _on_command_sent(self, command_id):
        self._append_log(f"Sent game command {command_id}")

    def _on_input_sent(self, sequence):
        self._append_log(f"Sent input frame {sequence}")

    def _show_game_state(self, state, *, events=(), revision=None):
        self.position_preview.set_state(state)
        display = {"state": state, "events": list(events)}
        if revision is not None:
            display["revision"] = revision
        self.game_state_preview.setPlainText(
            json.dumps(display, indent=2, ensure_ascii=False, default=str)
        )

    def _add_player(self, player):
        if not isinstance(player, dict):
            return
        player_id = str(player.get("player_id", ""))
        if not player_id:
            return
        for row in range(self.players.count()):
            if self.players.item(row).data(Qt.ItemDataRole.UserRole) == player_id:
                return
        from PySide6.QtWidgets import QListWidgetItem

        item = QListWidgetItem(str(player.get("display_name", "Player")))
        item.setData(Qt.ItemDataRole.UserRole, player_id)
        self.players.addItem(item)

    def _read_server_output(self):
        self._stdout_pending += bytes(self._server_process.readAllStandardOutput()).decode(
            "utf-8", errors="replace"
        )
        while "\n" in self._stdout_pending:
            line, self._stdout_pending = self._stdout_pending.split("\n", 1)
            line = line.strip()
            if line.startswith("READY "):
                try:
                    ready = json.loads(line[6:])
                    self._set_server_status(
                        "running", f"● Server running · {ready['host']}:{ready['port']}"
                    )
                    self._append_log(f"Server ready · session {ready.get('session_id', '')}")
                except (KeyError, json.JSONDecodeError) as exc:
                    self._append_log(f"Could not read server status: {exc}")
            elif line.startswith("ERROR "):
                self._append_log(line)
                self._set_server_status("error", f"● {line[6:]}")
            elif line:
                self._append_log(line)

    def _server_finished(self, exit_code, _exit_status):
        self.start_server_button.setEnabled(True)
        self.stop_server_button.setEnabled(False)
        if not self._closing:
            self._set_server_status("offline", "● Local server stopped")
            self._append_log(f"Server stopped · exit code {exit_code}")

    def _server_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self.start_server_button.setEnabled(True)
            self.stop_server_button.setEnabled(False)
            self._set_server_status("error", "● Could not start local server")
            self._append_log(self._server_process.errorString())

    def _set_server_status(self, state, text):
        self.local_server_status.setProperty("status", state)
        self.local_server_status.setText(text)
        self.local_server_status.style().unpolish(self.local_server_status)
        self.local_server_status.style().polish(self.local_server_status)

    def _set_connection_status(self, state, text):
        self.connection_status.setProperty("status", state)
        self.connection_status.setText(text)
        self.connection_status.style().unpolish(self.connection_status)
        self.connection_status.style().polish(self.connection_status)

    def _append_log(self, text):
        self.log.appendPlainText(str(text))

    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        self._client_worker.close_client(emit_left=False)
        self._client_thread.quit()
        self._client_thread.wait(5000)
        if self._server_process.state() != QProcess.ProcessState.NotRunning:
            self._server_process.terminate()
            if not self._server_process.waitForFinished(1500):
                self._server_process.kill()
                self._server_process.waitForFinished(1000)
