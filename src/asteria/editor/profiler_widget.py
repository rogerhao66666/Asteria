"""Profiler panel (EDT-19): the running game's RuntimeProfiler over the debug channel.

Shows frame time and pacing, time per section (update, render, AI, collision,
animation, VFX, asset loading...), counters (entities, particles, assets),
memory, and — explicitly — the metrics this backend cannot measure.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.runtime.debug_server import DebugClientError


class ProfilerWidget(QWidget):
    def __init__(self, client_provider, parent=None):
        """``client_provider()`` returns the attached ``DebugClient`` (shared with the Debugger dock) or None."""
        super().__init__(parent)
        self.client_provider = client_provider
        self.report = None
        self.summary = QLabel("Not attached — start Run Project to profile the game.")
        self.summary.setWordWrap(True)
        refresh, reset = QPushButton("Refresh"), QPushButton("Reset")
        refresh.clicked.connect(self.refresh)
        reset.clicked.connect(self.reset)
        self.auto = QCheckBox("Live (1 s)")
        self.auto.toggled.connect(lambda on: self.timer.start() if on else self.timer.stop())
        top = QHBoxLayout()
        top.addWidget(self.summary, 1)
        top.addWidget(self.auto)
        top.addWidget(refresh)
        top.addWidget(reset)
        self.sections = QTableWidget(0, 5)
        self.sections.setHorizontalHeaderLabels(["Section", "Mean ms", "p95 ms", "Max ms", "Share of frame"])
        self.sections.verticalHeader().hide()
        self.counters = QTableWidget(0, 3)
        self.counters.setHorizontalHeaderLabels(["Counter", "Last", "Max"])
        self.counters.verticalHeader().hide()
        self.unsupported = QListWidget()
        self.unsupported.setMaximumHeight(70)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        body = QHBoxLayout()
        body.addWidget(self.sections, 3)
        body.addWidget(self.counters, 2)
        layout.addLayout(body, 1)
        layout.addWidget(QLabel("Not measurable on this backend (reported, never invented)"))
        layout.addWidget(self.unsupported)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.refresh)

    def _client(self):
        client = self.client_provider()
        if client is None:
            raise DebugClientError("not attached to a running game")
        if not client.connected:
            client.connect()
        return client

    def refresh(self):
        try:
            report = self._client().request("profile")
        except DebugClientError as exc:
            self.summary.setText(str(exc))
            return None
        self.report = report
        frame, pacing = report.get("frame") or {}, report.get("pacing") or {}
        memory = report.get("memory") or {}
        rss = memory.get("peak_rss_bytes")
        self.summary.setText(
            f"{report.get('frames', 0)} frames · {pacing.get('measured_fps', 0)} fps (target "
            f"{pacing.get('target_fps', 60)}) · frame mean {frame.get('mean_ms', 0)} ms, "
            f"p95 {frame.get('p95_ms', 0)} ms, "
            f"max {frame.get('max_ms', 0)} ms · jitter {pacing.get('interval_jitter_ms', 0)} ms"
            + (f" · memory {rss / 1e6:.0f} MB" if rss else "")
        )
        frame_mean = float(frame.get("mean_ms") or 0.0)
        sections = sorted((report.get("sections") or {}).items(), key=lambda kv: -kv[1].get("mean_ms", 0))
        self.sections.setRowCount(len(sections))
        for row, (name, values) in enumerate(sections):
            share = (values.get("mean_ms", 0) / frame_mean * 100) if frame_mean else 0.0
            cells = (name, values.get("mean_ms", 0), values.get("p95_ms", 0), values.get("max_ms", 0), f"{share:.0f}%")
            for col, value in enumerate(cells):
                self.sections.setItem(row, col, QTableWidgetItem(str(value)))
        counters = sorted((report.get("counters") or {}).items())
        self.counters.setRowCount(len(counters))
        for row, (name, values) in enumerate(counters):
            for col, value in enumerate((name, values.get("last"), values.get("max"))):
                self.counters.setItem(row, col, QTableWidgetItem(str(value)))
        self.unsupported.clear()
        self.unsupported.addItems([f"{k}: {v}" for k, v in (report.get("unsupported") or {}).items()])
        return report

    def reset(self):
        try:
            self._client().request("profile_reset")
        except DebugClientError as exc:
            self.summary.setText(str(exc))
            return False
        return True
