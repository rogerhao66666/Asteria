from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EditorTheme:
    name: str = "Asteria Dark"
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    radius_sm: int = 4
    radius_md: int = 6


ASTERIA_DARK = EditorTheme()

ASTERIA_DARK_QSS = """
QMainWindow, QDialog { background: #17191d; color: #d9dde5; }
QDockWidget { color: #bfc5d0; font-weight: 600; }
QDockWidget::title { background: #1d2025; padding: 7px 10px; }
QTreeWidget, QListWidget, QTableWidget {
    background: #1b1e23; alternate-background-color: #1e2228;
    border: 1px solid #292e36; outline: 0; color: #d9dde5;
}
QTreeWidget::item, QListWidget::item { min-height: 24px; padding: 2px 5px; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #34465f; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #252b33; }
QMenuBar, QMenu { background: #1d2025; color: #d9dde5; }
QMenu::item:selected { background: #34465f; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #20242a; border: 1px solid #343a44; border-radius: 4px;
    padding: 5px 7px; color: #e4e7ed;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6385ad;
}
QPushButton {
    background: #292f38; border: 1px solid #3a424e; border-radius: 4px;
    padding: 6px 11px; color: #e4e7ed;
}
QPushButton:hover { background: #323a45; }
QPushButton:pressed { background: #22272e; }

QToolButton {
    background: transparent; border: 1px solid transparent; border-radius: 4px;
    padding: 5px 9px; color: #cbd1dc;
}
QToolButton:hover { background: #272d35; }
QToolButton:checked { background: #34465f; border-color: #4a6484; color: #ffffff; }
QLabel#SectionLabel { color: #aab2bf; font-size: 10px; font-weight: 700; padding: 3px 1px; }
QLabel#MutedLabel { color: #858e9d; padding: 2px 1px; }
QListWidget#TilePaletteList::item { min-height: 26px; padding: 3px 6px; }
QToolBar { background: #1d2025; border-bottom: 1px solid #292e36; spacing: 4px; padding: 4px; }
QStatusBar { background: #1b1e23; color: #9098a6; }
"""


def apply_asteria_theme(app):
    app.setStyleSheet(ASTERIA_DARK_QSS)
