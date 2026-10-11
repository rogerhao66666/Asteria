from asteria.editor.theme import ASTERIA_DARK, ASTERIA_DARK_QSS, WORKSPACE_ACCENTS


def test_theme_has_coherent_tokens_and_nonempty_qss():
    assert ASTERIA_DARK.spacing_sm < ASTERIA_DARK.spacing_lg
    for selector in (
        "QMainWindow",
        "QTreeWidget::item:selected",
        "QTextEdit#ConsoleOutput",
        "QToolButton#LayerControlButton",
        "QWidget#LayerListGroup",
        "QWidget#LayerControlRow",
        "QLabel#LayerSectionLabel",
        "QWidget#DockTitleBar",
        "QHeaderView::section",
        "QScrollBar:vertical",
    ):
        assert selector in ASTERIA_DARK_QSS, selector


def test_buttons_have_colour_roles_and_each_workspace_its_accent():
    for role in ("primary", "success", "danger"):
        assert f'QPushButton[role="{role}"]' in ASTERIA_DARK_QSS
    assert set(WORKSPACE_ACCENTS) == {"scene", "rpg", "battle", "ui", "events", "code"}
    for name, colour in WORKSPACE_ACCENTS.items():
        assert f'QToolButton[workspace="{name}"]:checked' in ASTERIA_DARK_QSS
        assert colour in ASTERIA_DARK_QSS
