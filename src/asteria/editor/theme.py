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
QDockWidget::title {
    background: #1d2025; border-bottom: 1px solid #292e36;
    padding: 7px 10px 7px 62px; text-align: left;
}
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent; border: 0; border-radius: 4px;
    position: absolute; top: 5px; width: 20px; height: 20px;
}
QDockWidget::close-button { subcontrol-position: top left; left: 6px; }
QDockWidget::float-button { subcontrol-position: top left; left: 29px; }
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background: #343a44;
}
QTabBar { background: #17191d; }
QTabBar::tab {
    background: #1d2025; color: #aeb5c1;
    border: 0; border-left: 1px solid #292e36;
    border-right: 1px solid #292e36;
    min-width: 92px; padding: 6px 10px; margin: 0;
}
QTabBar::tab:selected { background: #34465f; color: #ffffff; }
QTabBar::tab:hover:!selected { background: #252b33; color: #d9dde5; }
QTreeWidget, QListWidget, QTableWidget {
    background: #1b1e23; alternate-background-color: #1e2228;
    border: 1px solid #292e36; outline: 0; color: #d9dde5;
}
QTreeWidget::item, QListWidget::item { min-height: 24px; padding: 2px 5px; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #34465f; }
QTreeWidget::item:hover, QListWidget::item:hover { background: #252b33; }
QWidget#ConsolePanel { background: #17191d; }
QTextEdit#ConsoleOutput {
    background: #1b1e23; color: #d9dde5;
    border: 1px solid #343a44; border-radius: 4px;
    padding: 8px; selection-background-color: #34465f;
}
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
