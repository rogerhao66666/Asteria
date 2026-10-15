"""Editor theme: palettes (colour tokens) and the one style sheet they fill in.

Three palettes ship with the editor; View ▸ Theme switches between them live and the choice is kept
(QSettings ``Asteria/Editor`` ``editor/theme``):

* ``graphite`` (default) - neutral charcoal surfaces, calm accents (Godot / Blender family)
* ``twilight``           - deep indigo with gold highlights (a fantasy-RPG mood)
* ``daylight``           - a light theme (RPG Maker MZ family)

Workspace accents (Scene teal, Database amber, Battle coral, Presentation violet, Events sky, Code
blue, Multiplayer cyan)
are the same in every palette, so a workspace keeps its colour; they are mid-tones that read on
both
dark and light surfaces.
"""

from dataclasses import dataclass, fields
from string import Template


@dataclass(frozen=True, slots=True)
class EditorTheme:
    name: str = "Graphite"
    spacing_xs: int = 4
    spacing_sm: int = 8
    spacing_md: int = 12
    spacing_lg: int = 16
    radius_sm: int = 5
    radius_md: int = 8
    # surfaces, from the window background up
    base: str = "#1c1d21"
    panel: str = "#232428"
    raised: str = "#2b2d33"
    hover: str = "#33363d"
    input: str = "#18191c"
    list: str = "#1f2024"
    list_alt: str = "#222327"
    header: str = "#292b30"
    border: str = "#2f3137"
    border_strong: str = "#41444c"
    # text
    text: str = "#e4e4e7"
    text_dim: str = "#a3a5ad"
    text_muted: str = "#777a84"
    # interaction
    primary: str = "#6a83e8"
    primary_hi: str = "#7d93ef"
    primary_text: str = "#ffffff"
    selection: str = "#34406b"
    selection_text: str = "#ffffff"
    focus: str = "#6a83e8"
    danger_bg: str = "#33232a"
    danger_border: str = "#6e3a42"
    danger_text: str = "#f59aa0"
    success: str = "#36a874"
    success_hi: str = "#3fb87f"
    toolbar_top: str = "#26282d"
    toolbar_bottom: str = "#222328"
    scroll: str = "#43464f"
    scroll_hi: str = "#5a5e69"
    error: str = "#f07178"
    dark: bool = True


GRAPHITE = EditorTheme()

TWILIGHT = EditorTheme(
    name="Twilight",
    base="#15142a",
    panel="#1c1a35",
    raised="#252247",
    hover="#2e2a57",
    input="#121124",
    list="#191830",
    list_alt="#1d1b37",
    header="#23203f",
    border="#2e2a52",
    border_strong="#433d70",
    text="#ecebff",
    text_dim="#aca8d4",
    text_muted="#7f7ba6",
    primary="#d8a446",
    primary_hi="#e6b65c",
    primary_text="#1d1730",
    selection="#463b88",
    focus="#d8a446",
    danger_bg="#33203a",
    danger_border="#74385a",
    danger_text="#ff9fb2",
    toolbar_top="#221f42",
    toolbar_bottom="#1c1a35",
    scroll="#3e3868",
    scroll_hi="#564e8c",
)

DAYLIGHT = EditorTheme(
    name="Daylight",
    base="#e8ebf0",
    panel="#f5f6f8",
    raised="#ffffff",
    hover="#e2e7ef",
    input="#ffffff",
    list="#ffffff",
    list_alt="#f5f7fa",
    header="#eceff3",
    border="#d4d9e1",
    border_strong="#bac1cd",
    text="#1e222b",
    text_dim="#4c5363",
    text_muted="#7a8090",
    primary="#3c68d6",
    primary_hi="#4a76e0",
    selection="#cddbf7",
    selection_text="#1e222b",
    focus="#3c68d6",
    danger_bg="#fdeef0",
    danger_border="#e3a2a8",
    danger_text="#c13540",
    toolbar_top="#f7f8fa",
    toolbar_bottom="#eceff3",
    scroll="#c3c9d3",
    scroll_hi="#a5adbb",
    error="#c8333d",
    dark=False,
)

PALETTES = {"graphite": GRAPHITE, "twilight": TWILIGHT, "daylight": DAYLIGHT}
DEFAULT_PALETTE = "graphite"
ASTERIA_DARK = GRAPHITE  # kept for existing callers

# Workspace accents (same values as ``icons.ACCENTS``): the active workspace's toolbar button and
# its
# panels' title stripe use them, so where you are reads at a glance.
WORKSPACE_ACCENTS = {
    "scene": "#46b896",
    "rpg": "#dca545",
    "battle": "#e06a5c",
    "ui": "#9a84e0",
    "events": "#4aa9dc",
    "code": "#738ee8",
    "multiplayer": "#55aeb8",
}

_TEMPLATE = Template(
    """
QMainWindow, QDialog { background: $base; color: $text; }
QToolTip { background: $raised; color: $text; border: 1px solid $border_strong; padding: 5px 8px;
border-radius: 5px; }

/* -- docks -------------------------------------------------------------------------------------
*/
QDockWidget { color: $text_dim; font-weight: 600; }
QDockWidget::title {
    background: $panel; border-bottom: 1px solid $border;
    padding: 7px 10px 7px 62px; text-align: left;
}
QWidget#DockTitleBar { background: $panel; border-bottom: 1px solid $border; }
QLabel#DockTitle { color: $text; font-weight: 700; padding: 0 2px; }
QToolButton#DockTitleButton { background: transparent; border: 0; border-radius: 5px; padding:
3px; }
QToolButton#DockTitleButton:hover { background: $hover; }
QDockWidget::close-button, QDockWidget::float-button {
    background: transparent; border: 0; border-radius: 4px;
    position: absolute; top: 5px; width: 20px; height: 20px;
}
QDockWidget::close-button { subcontrol-position: top left; left: 6px; }
QDockWidget::float-button { subcontrol-position: top left; left: 29px; }
QDockWidget::close-button:hover, QDockWidget::float-button:hover { background: $hover; }

/* -- tabs
---------------------------------------------------------------------------------------- */
QTabWidget::pane { border: 1px solid $border; border-radius: 8px; top: -1px; background: $panel;
padding: 10px 12px; }
QTabBar { background: transparent; }
QTabBar::tab {
    background: $panel; color: $text_dim;
    border: 0; border-left: 1px solid $border;
    border-right: 1px solid $border;
    border-bottom: 2px solid transparent;
    min-width: 0; padding: 6px 11px; margin: 0;
}
QMainWindow > QTabBar::tab { min-width: 0; padding: 6px 8px; background: $base; }
QTabBar::tab:selected { background: $raised; color: $text; border-bottom: 2px solid $primary; }
QTabBar::tab:hover:!selected { background: $hover; color: $text; }

QLabel#MultiplayerServerStatus[status="running"],
QLabel#MultiplayerConnectionStatus[status="connected"] { color: $success; font-weight: 600; }
QLabel#MultiplayerServerStatus[status="starting"],
QLabel#MultiplayerConnectionStatus[status="connecting"] { color: $primary; font-weight: 600; }
QLabel#MultiplayerServerStatus[status="error"],
QLabel#MultiplayerConnectionStatus[status="error"] { color: $danger_text; font-weight: 600; }
QLabel#MultiplayerServerStatus[status="offline"],
QLabel#MultiplayerConnectionStatus[status="offline"] { color: $text_muted; }

/* -- lists, trees, tables
------------------------------------------------------------------------ */
QTreeWidget, QListWidget, QTableWidget, QTreeView, QListView, QTableView {
    background: $list; alternate-background-color: $list_alt;
    border: 1px solid $border; border-radius: 6px; outline: 0; color: $text;
}
QTreeWidget::item, QListWidget::item { min-height: 22px; padding: 1px 4px; }
QTreeWidget::item:selected, QListWidget::item:selected, QTableWidget::item:selected {
    background: $selection; color: $selection_text;
}
QTreeWidget::item:hover, QListWidget::item:hover { background: $hover; }
QHeaderView::section {
    background: $header; color: $text_dim; border: 0; border-right: 1px solid $border;
    border-bottom: 1px solid $border; padding: 5px 7px; font-weight: 600;
}
QTableCornerButton::section { background: $header; border: 0; }

/* -- console and text
---------------------------------------------------------------------------- */
QWidget#ConsolePanel { background: $base; }
QTextEdit#ConsoleOutput {
    background: $list; color: $text;
    border: 1px solid $border; border-radius: 6px;
    padding: 8px; selection-background-color: $selection;
}
QPlainTextEdit, QTextEdit { background: $input; color: $text; border: 1px solid $border;
border-radius: 6px; }

/* -- menus
--------------------------------------------------------------------------------------- */
QMenuBar { background: $base; color: $text; padding: 3px 6px; border-bottom: 1px solid $border; }
QMenuBar::item { background: transparent; padding: 4px 10px; margin: 0 1px; border-radius: 5px; }
QMenuBar::item:selected { background: $hover; }
QMenu { background: $raised; color: $text; border: 1px solid $border_strong; padding: 4px; }
QMenu::item { padding: 6px 22px 6px 26px; border-radius: 5px; }
QMenu::item:selected { background: $selection; color: $selection_text; }
QMenu::separator { height: 1px; background: $border; margin: 4px 8px; }

/* -- inputs
-------------------------------------------------------------------------------------- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: $input; border: 1px solid $border_strong; border-radius: 6px;
    padding: 3px 6px; color: $text;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color:
$text_muted; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid $focus;
}
QComboBox::drop-down {
    border: 0; background: transparent; width: 22px;
    subcontrol-origin: padding; subcontrol-position: center right;
}
QComboBox { padding-right: 24px; }
QComboBox QAbstractItemView {
    background: $raised; color: $text; border: 1px solid $border_strong;
    selection-background-color: $selection; selection-color: $selection_text; outline: 0;
}
QCheckBox, QRadioButton { color: $text; }
QGroupBox {
    border: 1px solid $border; border-radius: 8px; margin-top: 12px; padding: 8px 5px 5px 5px;
    background: $panel;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: $text_dim;
font-weight: 700; }

/* -- buttons
------------------------------------------------------------------------------------- */
QPushButton {
    background: $raised; border: 1px solid $border_strong; border-radius: 6px;
    padding: 4px 9px; color: $text;
}
QPushButton:hover { background: $hover; }
QPushButton:pressed { background: $panel; }
QPushButton:disabled { color: $text_muted; background: $panel; border-color: $border; }
QPushButton#PrimaryButton, QPushButton[role="primary"] {
    background: $primary; border: 1px solid $primary_hi; color: $primary_text; font-weight: 600;
}
QPushButton#PrimaryButton { padding: 8px 12px; }
QPushButton#PrimaryButton:hover, QPushButton[role="primary"]:hover { background: $primary_hi; }
QPushButton[role="success"] { background: $success; border: 1px solid $success_hi; color: #ffffff;
font-weight: 600; }
QPushButton[role="success"]:hover { background: $success_hi; }
QPushButton[role="danger"] { background: $danger_bg; border: 1px solid $danger_border; color:
$danger_text; }
QPushButton[role="danger"]:hover { border-color: $danger_text; }
QPushButton[role="primary"]:disabled, QPushButton[role="success"]:disabled,
QPushButton[role="danger"]:disabled {
    color: $text_muted; background: $panel; border-color: $border;
}

QToolButton {
    background: transparent; border: 1px solid transparent; border-radius: 6px;
    padding: 5px 9px; color: $text_dim;
}
QToolButton:hover { background: $hover; color: $text; }
QToolButton:checked { background: $selection; border-color: $primary; color: $selection_text; }

/* -- layers panel
-------------------------------------------------------------------------------- */
QWidget#LayerListGroup { background: $list; border: 1px solid $border; border-radius: 6px; }
QLabel#LayerSectionLabel {
    background: $header; color: $text_dim;
    border: 0; border-bottom: 1px solid $border;
    font-size: 10px; font-weight: 700; padding: 7px 8px;
}
QListWidget#LayerList { border: 0; border-radius: 0; background: $list; }
QWidget#LayerControlRow { background: $header; border: 0; border-top: 1px solid $border; }
QToolButton#LayerControlButton {
    background: transparent; border: 0; border-right: 1px solid $border;
    border-radius: 0; padding: 7px 9px;
}
QToolButton#LayerControlButton:hover { background: $hover; }
QToolButton#LayerControlButton:pressed { background: $panel; }

/* -- labels
-------------------------------------------------------------------------------------- */
QLabel { color: $text; }
QLabel#SectionLabel { color: $text_dim; font-size: 11px; font-weight: 800; padding: 3px 1px; }
QLabel#MutedLabel { color: $text_muted; padding: 2px 1px; }
QLabel#FieldLabel { color: $text_dim; font-size: 11px; font-weight: 600; padding: 0 1px; }
QLabel#EmptyStateTitle { color: $text_dim; font-size: 14px; font-weight: 700; }
QLabel#EmptyStateHint { color: $text_muted; }
QLabel#ErrorLabel { color: $error; }
QListWidget#TilePaletteList::item { min-height: 26px; padding: 3px 6px; }

/* -- cards (designer workspaces: sections of one record) ----------------------------------------
*/
QFrame#Card { background: $raised; border: 1px solid $border; border-radius: 10px; }
QLabel#CardTitle { color: $text; font-size: 13px; font-weight: 800; padding: 0; background:
transparent; }
QLabel#CardHint { color: $text_muted; font-size: 11px; padding: 0 0 2px 0; background:
transparent; }
QFrame#Card QLabel { background: transparent; }
QLabel#RecordHeading { color: $text; font-size: 17px; font-weight: 800; }
QLabel#RecordId { color: $text_muted; font-size: 11px; }
QToolButton#KindButton {
    background: $panel; border: 1px solid $border; border-radius: 8px;
    padding: 7px 10px; color: $text_dim; text-align: left; font-weight: 700;
}
QToolButton#KindButton:hover { background: $hover; color: $text; }
QToolButton#KindButton:checked { background: $selection; border-color: $primary; color:
$selection_text; }
QFrame#PreviewFrame { background: $input; border: 1px solid $border; border-radius: 10px; }
QLabel#ChipLabel { background: $hover; color: $text_dim; border-radius: 9px; padding: 2px 8px;
font-size: 11px; }

/* -- toolbar and status bar
---------------------------------------------------------------------- */
QToolBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 $toolbar_top, stop:1
    $toolbar_bottom);
    border-bottom: 1px solid $border; spacing: 3px; padding: 5px 6px;
}
QToolBar::separator { background: $border; width: 1px; margin: 4px 8px; }
QStatusBar { background: $base; color: $text_dim; border-top: 1px solid $border; }

/* -- scroll bars
--------------------------------------------------------------------------------- */
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: $scroll; border-radius:
3px; }
QScrollBar::handle:vertical { min-height: 24px; }
QScrollBar::handle:horizontal { min-width: 24px; }
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: $scroll_hi; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: $base; }
QSplitter::handle:hover { background: $primary; }
"""
)


def _workspace_rules(palette):
    rules = []
    for name, colour in WORKSPACE_ACCENTS.items():
        r, g, b = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
        alpha = 0.22 if palette.dark else 0.16
        rules.append(
            f'QToolButton[workspace="{name}"]:checked '
            f"{{ background: rgba({r}, {g}, {b}, {alpha}); "
            f"border: 1px solid {colour}; color: {palette.text}; }}"
        )
        rules.append(f'QToolButton[workspace="{name}"]:hover:!checked {{ color: {colour}; }}')
    return "\n".join(rules)


def build_qss(palette):
    tokens = {f.name: getattr(palette, f.name) for f in fields(palette)}
    return _TEMPLATE.substitute(tokens) + _workspace_rules(palette) + "\n"


ASTERIA_DARK_QSS = build_qss(GRAPHITE)


def palette_name(settings=None):
    """The saved palette name (``graphite`` when none is saved or the value is unknown)."""
    if settings is None:
        return DEFAULT_PALETTE
    name = str(settings.value("editor/theme", DEFAULT_PALETTE) or DEFAULT_PALETTE)
    return name if name in PALETTES else DEFAULT_PALETTE


CURRENT = {"palette": GRAPHITE}


def qt_palette(palette):
    from PySide6.QtGui import QColor, QPalette

    qp = QPalette()
    roles = {
        QPalette.Window: palette.base,
        QPalette.WindowText: palette.text,
        QPalette.Base: palette.list,
        QPalette.AlternateBase: palette.list_alt,
        QPalette.ToolTipBase: palette.raised,
        QPalette.ToolTipText: palette.text,
        QPalette.PlaceholderText: palette.text_muted,
        QPalette.Text: palette.text,
        QPalette.Button: palette.raised,
        QPalette.ButtonText: palette.text,
        QPalette.BrightText: palette.error,
        QPalette.Highlight: palette.selection,
        QPalette.HighlightedText: palette.selection_text,
        QPalette.Link: palette.primary,
        QPalette.Light: palette.hover,
        QPalette.Midlight: palette.raised,
        QPalette.Mid: palette.border_strong,
        QPalette.Dark: palette.border,
        QPalette.Shadow: palette.base,
    }
    for role, colour in roles.items():
        qp.setColor(role, QColor(colour))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        qp.setColor(QPalette.Disabled, role, QColor(palette.text_muted))
    return qp


def _branch_rules(palette):
    """Tree expand arrows in the palette's colour (the native ones are drawn for one fixed
    background)."""
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap

    folder = Path(tempfile.gettempdir()) / "asteria-editor-theme"
    folder.mkdir(exist_ok=True)
    paths = {}
    for kind, points in (
        ("closed", ((6, 4), (10, 8), (6, 12))),
        ("open", ((4, 6), (8, 10), (12, 6))),
        ("combo", ((4, 6), (8, 10), (12, 6))),
    ):
        path = folder / f"branch-{kind}-{palette.text_dim.lstrip('#')}.png"
        if not path.exists():
            pm = QPixmap(32, 32)
            pm.fill(Qt.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(palette.text_dim), 3.2)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            painter.drawPolyline([QPointF(x * 2, y * 2) for x, y in points])
            painter.end()
            pm.save(str(path))
        paths[kind] = path.as_posix()
    closed, opened, combo = paths["closed"], paths["open"], paths["combo"]
    return (
        f"QComboBox::down-arrow {{ image: url({combo}); width: 12px; height: 12px; }}\n"
        f"QTreeView::branch:has-children:closed {{ image: url({closed}); }}\n"
        f"QTreeView::branch:has-children:open {{ image: url({opened}); }}\n"
        "QTreeView::branch { background: transparent; }\n"
    )


def apply_asteria_theme(app, name=None):
    palette = PALETTES.get(name or DEFAULT_PALETTE, GRAPHITE)
    CURRENT["palette"] = palette
    app.setPalette(
        qt_palette(palette)
    )  # what the style draws itself (tree arrows, check marks...)
    app.setStyleSheet(build_qss(palette) + _branch_rules(palette))
    from .decor import install

    install(app)
    return palette
