try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QComboBox,
        QHBoxLayout,
        QLabel,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Signal = None
    Qt = None


class AnimationWidget(QWidget):
    if Signal is not None:
        clipChanged = Signal(str)
        playToggled = Signal()
        restartRequested = Signal()

    def __init__(self, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        title = QLabel("Animation Preview")
        title.setObjectName("SectionLabel")
        layout.addWidget(title)
        self.clip = QComboBox()
        layout.addWidget(self.clip)
        row = QHBoxLayout()
        self.play = QToolButton()
        self.play.setText("Play / Pause")
        self.restart = QToolButton()
        self.restart.setText("Restart")
        row.addWidget(self.play)
        row.addWidget(self.restart)
        layout.addLayout(row)
        self.status = QLabel("Pick a character in the Scene to play its animations here.")
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.clip.currentTextChanged.connect(self.clipChanged.emit)
        self.play.clicked.connect(self.playToggled.emit)
        self.restart.clicked.connect(self.restartRequested.emit)

    def set_clips(self, names, current=None):
        self.clip.blockSignals(True)
        self.clip.clear()
        self.clip.addItems(list(names))
        if current and current in names:
            self.clip.setCurrentText(current)
        self.clip.blockSignals(False)

    def set_status(self, text):
        self.status.setText(text)
