from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EditorTheme:
    name: str = "Asteria Dusk"
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    radius_sm: int = 5
    radius_md: int = 8
    # surfaces, darkest to lightest
    base: str = "#15171d"
    panel: str = "#1b1e26"
    raised: str = "#232733"
    hover: str = "#2b3040"
    border: str = "#2c3140"
    border_strong: str = "#3a4155"
    text: str = "#e6e9f2"
    text_dim: str = "#a7afc0"
    text_muted: str = "#7d8597"
    accent: str = "#6c8cff"
    selection: str = "#33407a"


ASTERIA_DARK = EditorTheme()

# Workspace accents (match ``icons.ACCENTS``): the toolbar button of the active workspace and its panel
# title stripe use them, so where you are reads at a glance (RPG Maker and Godot colour-code their
# editors the same way).
WORKSPACE_ACCENTS = {
    "scene": "#3fd0a8",
    "rpg": "#f4b545",
    "battle": "#f06a6a",
    "ui": "#a98bff",
    "events": "#56c1f5",
    "code": "#7f9dff",
}


def _workspace_rules():
    rules = []
    for name, colour in WORKSPACE_ACCENTS.items():
        r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
        rules.append(
            f'QToolButton[workspace="{name}"]:checked {{ background: rgba({r}, {g}, {b}, 0.2); '
            f"border: 1px solid {colour}; "
            f"color: #ffffff; }}"
        )
        rules.append(f'QToolButton[workspace="{name}"]:hover:!checked {{ color: {colour}; }}')
    return "\n".join(rules)


ASTERIA_DARK_QSS = (
    """
QMainWindow, QDialog { background: #15171d; color: #e6e9f2; }
QToolTip { background: #232733; color: #e6e9f2; border: 1px solid #3a4155; padding: 5px 8px; border-radius: 5px; }

/* -- docks ------------------------------------------------------------------------------------- */
QDockWidget { color: #c9cfdc; font-weight: 600; }
QDockWidget::title {
    background: #1b1e26; border-bottom: 1px solid #2c3140;
    padding: 7px 10px 7px 62px; text-align: left;
}
QWidget#DockTitleBar { background: #1b1e26; border-bottom: 1px solid #2c3140; }
QLabel#DockTitle { color: #e6e9f2; font-weight: 700; padding: 0 2px; }
QToolButton#DockTitleButton { background: transparent; border: 0; border-radius: 5px; padding: 3px; }
QToolButton#DockTitleButton:hover { background: #2b3040; }
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent; border: 0; border-radius: 4px;
    position: absolute; top: 5px; width: 20px; height: 20px;
}
QDockWidget::close-button { subcontrol-position: top left; left: 6px; }
QDockWidget::float-button { subcontrol-position: top left; left: 29px; }
QDockWidget::close-button:hover, QDockWidget::float-button:hover {
    background: #2b3040;
}

/* -- tabs ---------------------------------------------------------------------------------------- */
QTabWidget::pane { border: 1px solid #2c3140; border-radius: 8px; top: -1px; background: #1b1e26; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: #1b1e26; color: #a7afc0;
    border: 0; border-left: 1px solid #292e36;
    border-right: 1px solid #292e36;
    border-bottom: 2px solid transparent;
    min-width: 92px; padding: 7px 12px; margin: 0;
}
QMainWindow > QTabBar::tab { min-width: 0; padding: 6px 12px; background: #181b22; }
QTabBar::tab:selected { background: #262b38; color: #ffffff; border-bottom: 2px solid #6c8cff; }
QTabBar::tab:hover:!selected { background: #2b3040; color: #e6e9f2; }

/* -- lists, trees, tables ------------------------------------------------------------------------ */
QTreeWidget, QListWidget, QTableWidget, QTreeView, QListView, QTableView {
    background: #1b1e23; alternate-background-color: #1e2129;
    border: 1px solid #292e36; border-radius: 6px; outline: 0; color: #e6e9f2;
}
QTreeWidget::item, QListWidget::item { min-height: 24px; padding: 2px 5px; }
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
    background: #33407a; color: #ffffff;
}
QTreeWidget::item:hover, QListWidget::item:hover { background: #262b38; }
QHeaderView::section {
    background: #20242e; color: #a7afc0; border: 0; border-right: 1px solid #2c3140;
    border-bottom: 1px solid #2c3140; padding: 5px 7px; font-weight: 600;
}
QTableCornerButton::section { background: #20242e; border: 0; }

/* -- console ------------------------------------------------------------------------------------- */
QWidget#ConsolePanel { background: #15171d; }
QTextEdit#ConsoleOutput {
    background: #1b1e23; color: #d9dde5;
    border: 1px solid #343a44; border-radius: 6px;
    padding: 8px; selection-background-color: #33407a;
}

/* -- menus --------------------------------------------------------------------------------------- */
QMenuBar { background: #15171d; color: #e6e9f2; }
QMenuBar::item:selected { background: #2b3040; border-radius: 4px; }
QMenu { background: #1f232c; color: #e6e9f2; border: 1px solid #3a4155; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 26px; border-radius: 5px; }
QMenu::item:selected { background: #33407a; }
QMenu::separator { height: 1px; background: #2c3140; margin: 4px 8px; }

/* -- inputs -------------------------------------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #20242e; border: 1px solid #343a44; border-radius: 6px;
    padding: 5px 8px; color: #e6e9f2;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: #46506a; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #6c8cff; background: #232836;
}
QComboBox QAbstractItemView {
    background: #1f232c; border: 1px solid #3a4155; selection-background-color: #33407a; outline: 0;
}
QGroupBox {
    border: 1px solid #2c3140; border-radius: 8px; margin-top: 14px; padding: 10px 8px 8px 8px;
    background: #191c23;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #a7afc0; font-weight: 700;
}

/* -- buttons ------------------------------------------------------------------------------------- */
QPushButton {
    background: #262b36; border: 1px solid #383f50; border-radius: 6px;
    padding: 6px 12px; color: #e6e9f2;
}
QPushButton:hover { background: #2f3543; border-color: #4a5369; }
QPushButton:pressed { background: #1f232c; }
QPushButton:disabled { color: #636b7c; background: #1e2128; border-color: #2a2f3a; }
QPushButton#PrimaryButton, QPushButton[role="primary"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5f7ff0, stop:1 #4d6bd8);
    border: 1px solid #7590ff; color: #ffffff; font-weight: 600;
}
QPushButton#PrimaryButton { padding: 8px 12px; }
QPushButton#PrimaryButton:hover, QPushButton[role="primary"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #6f8cff, stop:1 #5877e6);
}
QPushButton[role="success"] {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3fb87f, stop:1 #2f9d69);
    border: 1px solid #55d196; color: #ffffff; font-weight: 600;
}
QPushButton[role="success"]:hover { background: #46c58a; }
QPushButton[role="danger"] { background: #2a2025; border: 1px solid #6b3640; color: #ff9aa0; }
QPushButton[role="danger"]:hover { background: #4a2229; border-color: #ef5f67; color: #ffffff; }
QPushButton[role="primary"]:disabled, QPushButton[role="success"]:disabled, QPushButton[role="danger"]:disabled {
    color: #636b7c; background: #1e2128; border-color: #2a2f3a;
}

QToolButton {
    background: transparent; border: 1px solid transparent; border-radius: 6px;
    padding: 5px 9px; color: #c9cfdc;
}
QToolButton:hover { background: #262b36; }
QToolButton:checked { background: #33407a; border-color: #4f62b0; color: #ffffff; }

/* -- layers panel -------------------------------------------------------------------------------- */
QWidget#LayerListGroup {
    background: #1b1e23; border: 1px solid #292e36; border-radius: 6px;
}
QLabel#LayerSectionLabel {
    background: #20242e; color: #a7afc0;
    border: 0; border-bottom: 1px solid #292e36;
    font-size: 10px; font-weight: 700; padding: 7px 8px;
}
QListWidget#LayerList {
    border: 0; border-radius: 0; background: #1b1e23;
}
QWidget#LayerControlRow {
    background: #20242e; border: 0; border-top: 1px solid #292e36;
}
QToolButton#LayerControlButton {
    background: transparent; border: 0; border-right: 1px solid #292e36;
    border-radius: 0; padding: 7px 9px;
}
QToolButton#LayerControlButton:hover {
    background: #2c333d;
}
QToolButton#LayerControlButton:pressed { background: #181c21; }

/* -- labels -------------------------------------------------------------------------------------- */
QLabel#SectionLabel { color: #c9cfdc; font-size: 11px; font-weight: 800; padding: 3px 1px; }
QLabel#MutedLabel { color: #8b93a5; padding: 2px 1px; }
QLabel#EmptyStateTitle { color: #c9cfdc; font-size: 14px; font-weight: 700; }
QLabel#EmptyStateHint { color: #7d8597; }
QListWidget#TilePaletteList::item { min-height: 26px; padding: 3px 6px; }

/* -- toolbar and status bar ---------------------------------------------------------------------- */
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1f2330, stop:1 #191c24);
    border-bottom: 1px solid #2c3140; spacing: 3px; padding: 5px 6px;
}
QToolBar::separator { background: #2c3140; width: 1px; margin: 4px 8px; }
QStatusBar { background: #15171d; color: #a7afc0; border-top: 1px solid #2c3140; }
QLabel#StatusChip {
    background: #232733; border: 1px solid #3a4155; border-radius: 9px; padding: 1px 9px; color: #c9cfdc;
}

/* -- scroll bars --------------------------------------------------------------------------------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: #3a4155; border-radius: 3px; }
QScrollBar::handle:vertical { min-height: 24px; }
QScrollBar::handle:horizontal { min-width: 24px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #4f5a74; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: #1f232c; }
QSplitter::handle:hover { background: #6c8cff; }
"""
    + _workspace_rules()
    + "\n"
)


def apply_asteria_theme(app):
    app.setStyleSheet(ASTERIA_DARK_QSS)
    from .decor import install

    install(app)
