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


def test_bottom_panel_tabs_are_joined_square_tabs_like_the_sidebar():
    rules = ASTERIA_DARK_QSS.split("}")
    for name in ("BottomPanelDockTabs", "LeftSceneDockTabs"):
        selector = f"QTabBar#{name}::tab"
        rule = next(item for item in rules if selector in item)
        styles = rule.split("{", 1)[1]
        assert "border-top: 1px solid" in styles
        assert "border-right: 1px solid" in styles
        assert "border-bottom: 2px solid transparent" in styles
        assert "border-left: 0" in styles
        assert "border-radius: 0" in styles
        assert "margin: 0;" in styles
    assert "QTabBar#BottomPanelDockTabs::tab:first" in ASTERIA_DARK_QSS


def test_scene_sidebar_tabs_use_a_compact_joined_style():
    expected = (
        f"QTabBar#LeftSceneDockTabs::tab {{\n"
        f"    background: {ASTERIA_DARK.panel}; color: {ASTERIA_DARK.text_dim};\n"
        f"    border-top: 1px solid {ASTERIA_DARK.border_strong};"
    )
    assert expected in ASTERIA_DARK_QSS
    assert "border-bottom: 2px solid transparent; border-left: 0; border-radius: 0;" in (
        ASTERIA_DARK_QSS
    )
    assert "min-width: 0; padding: 6px 6px; margin: 0;" in ASTERIA_DARK_QSS


def test_workspace_and_dock_tab_labels_use_bold_weight():
    assert "QToolButton[workspace] { font-weight: 700; }" in ASTERIA_DARK_QSS
    for name in ("BottomPanelDockTabs", "LeftSceneDockTabs"):
        selector = f"QTabBar#{name}::tab"
        rules = ASTERIA_DARK_QSS.split("}")
        rule = next(item for item in rules if selector in item)
        assert "font-weight: 700" in rule


def test_dock_content_cards_have_a_visible_square_frame():
    assert "QFrame#DockContentCard" in ASTERIA_DARK_QSS
    dock_card_rule = next(
        rule for rule in ASTERIA_DARK_QSS.split("}") if "QFrame#DockContentCard" in rule
    )
    assert "border-radius: 0;" in dock_card_rule
    assert f"background: {ASTERIA_DARK.raised};" in dock_card_rule
    assert "QFrame#ProfilerMetricCard" in ASTERIA_DARK_QSS
    assert "QGroupBox#DebugActionsCard" in ASTERIA_DARK_QSS


def test_database_presentation_and_event_tabs_use_cards_with_square_content_panes():
    for name in ("Database", "Presentation", "Events"):
        tab_selector = f"QTabBar#{name}WorkspaceTabBar::tab"
        selected_selector = f"{tab_selector}:selected"
        pane_selector = f"QTabWidget#{name}WorkspaceTabs::pane"
        assert tab_selector in ASTERIA_DARK_QSS
        assert selected_selector in ASTERIA_DARK_QSS
        assert pane_selector in ASTERIA_DARK_QSS
        rules = ASTERIA_DARK_QSS.split("}")
        tab_rule = next(rule for rule in rules if tab_selector in rule)
        selected_rule = next(rule for rule in rules if selected_selector in rule)
        pane_rule = next(rule for rule in rules if pane_selector in rule)
        tab_styles = tab_rule.split("{", 1)[1]
        selected_styles = selected_rule.split("{", 1)[1]
        pane_styles = pane_rule.split("{", 1)[1]
        assert "border: 1px solid" in tab_styles
        assert "border-bottom: 1px solid" in tab_styles
        assert "border-bottom: 2px solid" in selected_styles
        assert "border-radius: 4px" in tab_styles
        assert "border-radius: 0" in pane_styles
        assert "top: -1px" in pane_styles
        assert "border-bottom: 1px solid" in pane_styles


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
