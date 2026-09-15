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
QMainWindow::separator {
    background: #20242a; width: 5px; height: 5px;
}
QMainWindow::separator:hover { background: #4a6484; }
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
QTableWidget#RecordTable {
    gridline-color: #3c444f; background: #1b1e23;
    alternate-background-color: #1f242b; border: 1px solid #3c444f;
}
QTableWidget#RecordTable::item { padding: 6px 8px; border: 0; }
QTableWidget#RecordTable::item:selected { background: #34465f; color: #ffffff; }
/* The global QLineEdit rule below (padding+border+border-radius) also
   applies to the inline QLineEdit Qt spawns to edit a table cell, which
   nested its own bordered/rounded box inside the cell instead of filling
   it — text looked like it was sitting inside a smaller floating box. This
   flush, borderless variant fills the cell exactly, at every table in the
   editor since none of them set an objectName the global rule could avoid. */
QTableWidget QLineEdit {
    background: #34465f; color: #ffffff;
    border: none; border-radius: 0; padding: 6px 8px; margin: 0;
    selection-background-color: #4d6f96;
}
QHeaderView::section {
    background: #232830; color: #aeb6c2;
    border: 0; border-right: 1px solid #2b313a; border-bottom: 1px solid #2b313a;
    padding: 4px 6px; font-weight: 600;
}
QTableCornerButton::section { background: #232830; border: 0; }
QLineEdit#RecordIdField { background: #191c21; color: #9098a6; }
QWidget#ConsolePanel { background: #17191d; }
QTextEdit#ConsoleOutput {
    background: #1b1e23; color: #d9dde5;
    border: 1px solid #343a44; border-radius: 4px;
    padding: 8px; selection-background-color: #34465f;
}
QPlainTextEdit#ScriptEditor {
    background: #1b1e23; color: #d9dde5;
    border: 1px solid #343a44; border-radius: 4px;
    padding: 8px; selection-background-color: #34465f;
}
QWidget#ScriptEditorGutter { background: #1b1e23; }
QPlainTextEdit#ScriptQuickReference {
    background: #191c21; color: #9098a6;
    border: 1px solid #292e36; border-radius: 4px;
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
QPushButton:checked {
    background: #4d6f96; border: 1px solid #6385ad; color: #ffffff;
}
QPushButton:checked:hover { background: #5679a2; }

QToolButton {
    background: transparent; border: 1px solid transparent; border-radius: 4px;
    padding: 5px 9px; color: #cbd1dc;
}
QToolButton:hover { background: #272d35; }
QToolButton:checked { background: #34465f; border-color: #4a6484; color: #ffffff; }
QWidget#LayerListGroup {
    background: #1b1e23; border: 1px solid #292e36; border-radius: 4px;
}
QLabel#LayerSectionLabel {
    background: #20242a; color: #aab2bf;
    border: 0; border-bottom: 1px solid #292e36;
    font-size: 10px; font-weight: 700; padding: 7px 8px;
}
QListWidget#LayerList {
    border: 0; border-radius: 0; background: #1b1e23;
}
QWidget#LayerControlRow {
    background: #20242a; border: 0; border-top: 1px solid #292e36;
}
QToolButton#LayerControlButton {
    background: transparent; border: 0; border-right: 1px solid #292e36;
    border-radius: 0; padding: 7px 9px;
}
QToolButton#LayerControlButton:hover {
    background: #2c333d;
}
QToolButton#LayerControlButton:pressed { background: #181c21; }
QLabel#SectionLabel { color: #aab2bf; font-size: 10px; font-weight: 700; padding: 3px 1px; }
QLabel#MutedLabel { color: #858e9d; padding: 2px 1px; }
QListWidget#TilePaletteList::item { min-height: 26px; padding: 3px 6px; }
QToolBar { background: #1d2025; border-bottom: 1px solid #292e36; spacing: 4px; padding: 4px; }
QStatusBar { background: #1b1e23; color: #9098a6; }
"""


def apply_asteria_theme(app):
    app.setStyleSheet(ASTERIA_DARK_QSS)
