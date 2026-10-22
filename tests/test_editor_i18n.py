"""Editor languages: interface text is shown translated, project data never is, and the
language switches live (English is the source and the default)."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QWidget,
)

from asteria.editor import i18n  # noqa: E402

TABLE = (
    {
        "Save": "儲存",
        "Delete": "刪除",
        "Actors": "角色",
        "Stats": "屬性",
        "stat": "屬性",
        "Name": "名稱",
        "Down": "下",
        "Advanced": "進階",
    },
    [
        (__import__("re").compile(r"(?P<h>.+) · (?P<n>\d+) records"), "{h!t} · {n} 筆資料"),
        (__import__("re").compile(r"\+ Add (?P<noun>.+)"), "+ 新增{noun!t}"),
    ],
)


@pytest.fixture
def chinese(monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setitem(i18n._tables, "test", TABLE)
    monkeypatch.setitem(i18n.LANGUAGES, "test", "Test")
    monkeypatch.setattr(i18n, "_reverse", {})
    i18n.install(app, i18n.DEFAULT)
    yield app
    i18n.set_language(i18n.DEFAULT)


def test_exact_text_and_built_text_are_translated_unknown_text_stays(chinese):
    assert i18n.translate("Save", "test") == "儲存"
    assert i18n.translate("Actors · 12 records", "test") == "角色 · 12 筆資料"
    assert i18n.translate("+ Add stat", "test") == "+ 新增屬性"
    assert i18n.translate("Aldric", "test") == "Aldric"  # a name: no table has it
    assert i18n.translate("Save", "en") == "Save"


def test_widgets_show_the_language_and_switch_back_live(chinese):
    i18n.set_language("test")
    root = QWidget()
    made = QPushButton("Save", root)  # text given when made: translated when polished
    label = QLabel(root)
    label.setText("Actors · 3 records")  # set later: translated as it is set
    box = QGroupBox("Stats", root)
    box.setToolTip("Delete")
    tabs = QTabWidget(root)
    tabs.addTab(QWidget(), "Advanced")
    edit = QLineEdit("Save", root)  # what the author typed: never translated
    edit.setPlaceholderText("Name")
    root.show()
    QApplication.processEvents()
    assert made.text() == "儲存" and label.text() == "角色 · 3 筆資料"
    assert box.title() == "屬性" and box.toolTip() == "刪除"
    assert tabs.tabText(0) == "進階"
    assert edit.text() == "Save" and edit.placeholderText() == "名稱"
    assert i18n.english(tabs.tabText(0)) == "Advanced"  # code that picks by title
    i18n.set_language("en")
    assert made.text() == "Save" and label.text() == "Actors · 3 records"
    assert box.title() == "Stats" and tabs.tabText(0) == "Advanced"
    assert edit.placeholderText() == "Name"
    i18n.set_language("test")
    assert made.text() == "儲存"
    root.deleteLater()


def test_fixed_choices_are_translated_typed_in_lists_and_data_are_not(chinese):
    i18n.set_language("test")
    choices = QComboBox()
    choices.addItem("Down", "down")  # a fixed choice: its value is the data
    choices.addItem("Save")  # no data: the text is the value, left alone
    typed = QComboBox()
    typed.setEditable(True)
    typed.addItem("Down", "down")
    assert choices.itemText(0) == "下" and choices.itemData(0) == "down"
    assert choices.itemText(1) == "Save"
    assert typed.itemText(0) == "Down"
    i18n.set_language("en")
    assert choices.itemText(0) == "Down"


def test_the_saved_language_is_read_with_english_as_the_fallback():
    class Settings:
        def __init__(self, value):
            self.value_ = value

        def value(self, key, default=None):
            return self.value_ if self.value_ is not None else default

    assert i18n.language_name(Settings("zh_TW")) == "zh_TW"
    assert i18n.language_name(Settings("klingon")) == "en"
    assert i18n.language_name(Settings(None)) == "en"
    assert i18n.language_name(None) == "en"


def test_the_shipped_table_loads_and_the_editor_window_switches_language_live():
    """The real Traditional Chinese table: the editor's own words change, the project's data
    does not, and English comes back without a restart."""
    from pathlib import Path

    from PySide6.QtWidgets import QMenuBar

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    i18n._tables.pop("zh_TW", None)
    exact, patterns = i18n._table("zh_TW")
    assert len(exact) > 2000 and patterns
    assert i18n.translate("Actors · 5 records", "zh_TW") == "角色 · 5 筆資料"
    assert i18n.translate("+ Add stat", "zh_TW") == "+ 新增屬性"
    assert i18n.translate("Support: inflicts Burn", "zh_TW") == "Support: inflicts Burn"  # data
    i18n.install(app, "en")
    root = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    try:
        bar = window.findChild(QMenuBar)
        menus = [a.text() for a in bar.actions()]
        tabs = [window.rpg_workspace.tabText(i) for i in range(window.rpg_workspace.count())]
        assert "&File" in menus and "Game Data" in tabs
        window.set_language("zh_TW")
        assert "檔案(&F)" in [a.text() for a in bar.actions()]
        assert "遊戲資料" in [
            window.rpg_workspace.tabText(i) for i in range(window.rpg_workspace.count())
        ]
        assert project.name == "Asteria Full Verification Demo"  # the data is untouched
        import sys

        sys.path.insert(0, str(root.parents[1] / "scripts"))
        import editor_ui_audit as audit  # the audit names pages in English in any language

        assert "rpg_game_start" in dict(audit.surfaces(window))
        window.set_language("en")
        assert [a.text() for a in bar.actions()] == menus
        assert [
            window.rpg_workspace.tabText(i) for i in range(window.rpg_workspace.count())
        ] == tabs
    finally:
        i18n.set_language("en")
        window.document.mark_saved()
        window.close()
        window.deleteLater()
