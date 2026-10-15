"""Consistent record browsers for authoring workspaces."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


def authoring_sidebar(title, view, *, header=None, footer=None):
    card = QFrame()
    card.setObjectName("AuthoringSidebarCard")
    card.setMinimumWidth(220)
    card.setMaximumWidth(280)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(10)
    heading = QLabel(title)
    heading.setObjectName("AuthoringSidebarTitle")
    layout.addWidget(heading)
    if header is not None:
        layout.addWidget(header)
    layout.addWidget(view, 1)
    if footer is not None:
        layout.addLayout(footer)
    return card
