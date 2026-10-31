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


def test_project_and_asset_lists_have_no_outer_border():
    assert "QTreeWidget#ProjectHierarchyTree, QListWidget#AssetList" in ASTERIA_DARK_QSS
    assert f"QDockWidget {{ color: {ASTERIA_DARK.text_dim}; font-weight: 600; border: 0; }}" in (
        ASTERIA_DARK_QSS
    )
    assert "border: 0; border-radius: 0;" in ASTERIA_DARK_QSS
    assert "QTabBar#BottomPanelDockTabs::tab," in ASTERIA_DARK_QSS
    assert "QTabBar#LeftSceneDockTabs::tab {" in ASTERIA_DARK_QSS


def test_dock_tab_bar_fills_the_unoccupied_strip_with_the_window_base():
    expected = f"QMainWindow > QTabBar {{ background: {ASTERIA_DARK.base}; }}"
    assert expected in ASTERIA_DARK_QSS


def test_panel_tabs_are_a_strip_of_names_with_the_open_one_underlined():
    rules = ASTERIA_DARK_QSS.split("}")
    for name in ("BottomPanelDockTabs", "LeftSceneDockTabs"):
        selector = f"QTabBar#{name}::tab"
        styles = next(item for item in rules if selector in item).split("{", 1)[1]
        assert "background: transparent" in styles
        assert "border: 0; border-bottom: 2px solid transparent; border-radius: 0" in styles
        assert "font-weight: 600" in styles
        selected = next(item for item in rules if f"{selector}:selected" in item)
        assert f"border-bottom: 2px solid {ASTERIA_DARK.primary}" in selected


def test_workspace_buttons_are_the_top_level():
    # the workspace switch is the top level: larger type than the tabs inside a workspace
    workspace = "QToolButton[workspace] { font-size: 13px; font-weight: 600; padding: 6px 11px; }"
    assert workspace in ASTERIA_DARK_QSS
    assert "QToolButton#PlayButton {" in ASTERIA_DARK_QSS


def test_dock_content_cards_have_a_visible_square_frame():
    assert "QFrame#DockContentCard" in ASTERIA_DARK_QSS
    dock_card_rule = next(
        rule for rule in ASTERIA_DARK_QSS.split("}") if "QFrame#DockContentCard" in rule
    )
    assert "border-radius: 0;" in dock_card_rule
    assert f"background: {ASTERIA_DARK.raised};" in dock_card_rule
    assert "QFrame#ProfilerMetricCard" in ASTERIA_DARK_QSS
    assert "QGroupBox#DebugActionsCard" in ASTERIA_DARK_QSS


def test_workspace_page_tabs_are_underlined_in_the_workspace_colour():
    rules = ASTERIA_DARK_QSS.split("}")
    for name, accent in (("Database", "rpg"), ("Presentation", "ui"), ("Events", "events")):
        tab_selector = f"QTabBar#{name}WorkspaceTabBar::tab"
        tab_styles = next(rule for rule in rules if tab_selector in rule).split("{", 1)[1]
        assert "background: transparent" in tab_styles
        assert "border: 0; border-bottom: 2px solid transparent" in tab_styles
        colour = WORKSPACE_ACCENTS[accent]
        underline = f"{tab_selector}:selected {{ border-bottom: 2px solid {colour}; }}"
        assert underline in ASTERIA_DARK_QSS
        pane_selector = f"QTabWidget#{name}WorkspaceTabs::pane"
        pane_styles = next(rule for rule in rules if pane_selector in rule).split("{", 1)[1]
        assert "border: 0; border-top: 1px solid" in pane_styles
        assert "border-radius: 0" in pane_styles and "top: -1px" in pane_styles


def test_workspace_overflow_arrows_have_visible_scoped_controls():
    for name in ("Database", "Presentation", "Events"):
        for direction in ("Left", "Right"):
            selector = f"QTabBar#{name}WorkspaceTabBar QToolButton#Scroll{direction}Button"
            assert selector in ASTERIA_DARK_QSS
    assert "border: 1px solid" in ASTERIA_DARK_QSS


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


def test_tooltips_show_quickly_and_the_theme_can_be_applied_again(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QStyle

    from asteria.editor.theme import TOOLTIP_DELAY_MS, apply_asteria_theme

    app = QApplication.instance() or QApplication([])
    apply_asteria_theme(app)
    wrapped = app._asteria_quick_tips
    apply_asteria_theme(app)  # another palette: the style is not wrapped twice
    assert app._asteria_quick_tips is wrapped
    assert app.style().styleHint(QStyle.SH_ToolTip_WakeUpDelay) == TOOLTIP_DELAY_MS < 700


def test_a_padded_label_has_no_hidden_indent(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel

    from asteria.editor.theme import apply_asteria_theme

    app = QApplication.instance() or QApplication([])
    apply_asteria_theme(app)
    title = QLabel("BP")
    title.setObjectName("FormTitle")  # its padding counts as a frame: Qt would indent it
    title.ensurePolished()
    assert title.frameWidth() > 0 and title.indent() == 0  # level with the line under it
