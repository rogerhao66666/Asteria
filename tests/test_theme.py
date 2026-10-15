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
    assert set(WORKSPACE_ACCENTS) == {
        "scene",
        "rpg",
        "battle",
        "ui",
        "events",
        "code",
        "multiplayer",
    }
    for name, colour in WORKSPACE_ACCENTS.items():
        assert f'QToolButton[workspace="{name}"]:checked' in ASTERIA_DARK_QSS
        assert colour in ASTERIA_DARK_QSS


def test_every_palette_fills_the_whole_style_sheet():
    from asteria.editor.theme import PALETTES, build_qss

    for key, palette in PALETTES.items():
        qss = build_qss(palette)
        assert "$" not in qss, key  # every token substituted
        assert palette.base in qss and palette.primary in qss


def test_saved_palette_name_falls_back_to_the_default():
    from asteria.editor.theme import DEFAULT_PALETTE, palette_name

    class Settings(dict):
        def value(self, key, default=None):
            return self.get(key, default)

    assert palette_name(None) == DEFAULT_PALETTE
    assert palette_name(Settings({"editor/theme": "twilight"})) == "twilight"
    assert palette_name(Settings({"editor/theme": "neon"})) == DEFAULT_PALETTE
