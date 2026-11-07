"""What carrying a Property (tag) does, in the editor's language: the words beside a tag row and
in its drop-down's hover come from the engine (``rpg.tag_definitions.BUILT_IN``, the prefix
sentences of ``record_vocabulary.tag_meaning``) or from the project's own definitions (Game
Systems ▸ Properties), whose translation is the project's locale table (D60)."""

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QLabel  # noqa: E402

from asteria.editor.project.data_translation import data_groups  # noqa: E402
from asteria.editor.records.form_chips import ChipList
from asteria.editor.records.vocabulary import (  # noqa: E402
    _TAG_MEANINGS,
    ProjectVocabulary,
    tag_label,
    tag_meaning,
)
from asteria.editor.ui import i18n
from asteria.project import Project  # noqa: E402
from asteria.rpg.data.tag_definitions import BUILT_IN  # noqa: E402
from asteria.rpg.text.data_text import key  # noqa: E402
from asteria.runtime.component_registry import default_component_registry

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
# English words left in a translation; codes an author types (``scheduler:<id>``) stay as they are
_ENGLISH = re.compile(r"[A-Za-z]{3,}")
_CODES = re.compile(r"[\w.:]*<\w+>|\b\w+:\S*")


def _english_left(text):
    return _ENGLISH.findall(_CODES.sub("", text))


@pytest.fixture
def chinese():
    app = QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    i18n.use_project(project)
    i18n.install(app, "zh_TW")
    try:
        yield project
    finally:
        i18n.set_language(i18n.DEFAULT)
        i18n.use_project(None)


def test_every_engine_tag_meaning_has_a_chinese_entry():
    for tag, meaning in BUILT_IN.items():
        shown = i18n.translate(meaning, "zh_TW")
        assert shown != meaning and not _english_left(shown), tag
    for prefix, sentence in _TAG_MEANINGS:  # "Can equip {} weapons" with a name in it
        shown = i18n.translate(sentence.format("Sword"), "zh_TW")
        assert "劍" in shown and not _english_left(shown), prefix


def test_every_tag_of_the_demo_says_what_it_does_in_chinese(chinese):
    project = chinese
    vocabulary = ProjectVocabulary(project)
    names = vocabulary.names()
    definitions = project.rpg_database.tag_definitions
    tags = {*vocabulary.tags(), *definitions, *BUILT_IN}
    meanings = {tag: tag_meaning(tag, names, definitions) for tag in tags}
    assert sum(1 for m in meanings.values() if m) > 300  # the demo's tags really were read
    shown = {tag: i18n.translate(meaning) for tag, meaning in meanings.items() if meaning}
    untranslated = {
        tag: meanings[tag]
        for tag, text in shown.items()
        if text == meanings[tag] or _english_left(text)
    }
    assert untranslated == {}


def test_a_tag_row_shows_its_meaning_in_the_editor_s_language(chinese):
    project = chinese
    vocabulary = ProjectVocabulary(project)
    names, definitions = vocabulary.names(), project.rpg_database.tag_definitions
    tag = "rune.charm.echo"
    english = tag_meaning(tag, names, definitions)
    assert english.startswith("Given by a skill-tree rune node")
    chips = ChipList(
        [tag],
        [],
        noun="tag",
        namer=lambda t: tag_label(t, names),
        meaning=lambda t: tag_meaning(t, names, definitions),
    )
    said = [w for w in chips.findChildren(QLabel) if w.objectName() == "FormTagEffect"]
    assert said and said[0].text() == said[0].toolTip() == i18n.translate(english)
    assert not _english_left(said[0].text())
    content = [w for w in chips.findChildren(QComboBox) if w.objectName() == "FormTagContent"]
    assert content and content[0].toolTip().endswith("\n" + said[0].text())  # its hover too
    chips.deleteLater()


def test_the_translations_page_lists_each_property_once(chinese):
    project = chinese
    groups = dict(data_groups(project))
    rows = dict(groups["Data: properties"])
    rune = project.rpg_database.tag_definitions["rune.*"]
    assert rows[key("tag", "rune.*", "description")] == rune.description
    assert rows[key("tag", "rune.*")] == rune.display_name
    keys = [k for _title, listed in data_groups(project) for k, _english in listed]
    assert len(keys) == len(set(keys))  # a defined property is not listed again for the menus


def test_the_first_page_of_an_editor_opened_on_the_demo_says_it_in_chinese():
    from asteria.editor.project.workspace import WorkspaceMode
    from asteria.editor.records.hub import AdapterFamilyWidget
    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    i18n.install(app, "zh_TW")
    try:
        window = AsteriaEditorWindow(project)  # the project given at once: its page built first
        window.workspace.set_mode(WorkspaceMode.RPG)
        family = window.rpg_authoring.findChild(AdapterFamilyWidget)
        family.category.setCurrentIndex(family.category.findData("actors"))
        app.processEvents()
        said = [
            w.text()
            for w in window.rpg_authoring.findChildren(QLabel)
            if w.objectName() == "FormTagEffect"
        ]
        assert said and not [text for text in said if _english_left(text)]
        window.close()
        window.deleteLater()
    finally:
        i18n.set_language(i18n.DEFAULT)
        i18n.use_project(None)
