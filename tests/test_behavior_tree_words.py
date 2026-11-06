"""The Behavior Trees page says what a tree does in plain words, in both editor languages."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from asteria.editor import i18n
from asteria.editor.behavior_tree_authoring import PARAMS, parse_points
from asteria.editor.behavior_tree_words import (
    KIND_NAMES,
    SETTING_CHOICES,
    describe,
    kind_name,
    param_label,
)
from asteria.rpg.behavior_tree import ACTIONS, CONDITIONS, NODE_KINDS, BehaviorNode, BehaviorTree

ROOT = Path(__file__).parents[1]
DEMO = ROOT / "reference_projects/full_verification_demo/project.asteria.json"
ZH = json.loads((ROOT / "src/asteria/editor/translations/zh_TW.json").read_text("utf-8"))["exact"]
ENGINE_CODE = re.compile(r"[a-z]+_[a-z_]+|\w+=|\d+,\d+;")
LEAVES = CONDITIONS + ACTIONS
SAMPLES = (  # every wording a node's values can give, with values unlike the defaults
    ("parallel", {"success_count": 2}),
    ("repeater", {"count": 0}),
    ("repeater", {"count": 1}),
    ("repeater", {"count": 3}),
    ("cooldown", {"seconds": 2.5}),
    ("chase", {"arrive": 6.0, "lose_radius": 160.0, "speed": 55.0}),
    ("flee", {"radius": 90.0, "speed": 55.0}),
    ("move_to", {"x": 10.0, "y": -20.0, "arrive": 3.0, "speed": 55.0}),
    ("return_home", {"arrive": 3.0, "speed": 55.0}),
    ("patrol", {"points": "0,0; 32,0; 32,32; 0,32", "arrive": 3.0}),
    ("wander", {"radius": 40.0, "arrive": 3.0}),
    ("set_switch", {"name": "gate_open", "value": True}),
    ("set_switch", {"name": "gate_open", "value": False}),
    ("use_ability", {"ability": "fire_bolt", "wait": True}),
    ("strafe", {"direction": 1, "seconds": 2.0}),
    ("strafe", {"direction": -1, "seconds": 2.0}),
    ("side_patrol", {"seconds": 0.0}),
    ("side_patrol", {"seconds": 4.0}),
    ("apply_state", {"state": "burn", "to": "self"}),
    ("apply_state", {"state": "burn", "to": "player"}),
)


def _node(kind, params=None):
    children = ()
    if kind not in LEAVES:
        children = (BehaviorNode("wait", {"seconds": 1.0}),)
    if params is None:
        params = dict(PARAMS[kind])
    return BehaviorNode(kind, params, children)


def _all_nodes():
    yield from (_node(kind) for kind in NODE_KINDS)
    yield from (_node(kind, params) for kind, params in SAMPLES)


@pytest.fixture
def chinese():
    i18n.CURRENT["language"] = "zh_TW"
    yield
    i18n.CURRENT["language"] = "en"


def _untranslated_template_words(text):
    return re.findall(r"[A-Za-z]{2,}", text.replace("px", "").replace("sec", ""))


def test_every_kind_has_a_name_and_every_setting_a_label():
    assert set(KIND_NAMES) == set(NODE_KINDS) == set(PARAMS)
    for kind, params in PARAMS.items():
        assert KIND_NAMES[kind] != kind
        for name, _default in params:
            label = param_label(kind, name)
            assert label != name or len(name) == 1, (kind, name)
            assert label in ZH or label == label.upper(), label


def test_no_node_reads_as_an_engine_code_in_english():
    for node in _all_nodes():
        text = describe(node)
        assert not ENGINE_CODE.search(text), text
        assert text not in NODE_KINDS


def test_no_node_reads_as_an_engine_code_in_chinese(chinese):
    for node in _all_nodes():
        text = describe(node, lambda _setting, _value: "名稱")
        assert not ENGINE_CODE.search(text), text
        assert not _untranslated_template_words(text), text
    for kind in NODE_KINDS:
        assert not re.search(r"[A-Za-z]", kind_name(kind)), kind


def test_a_sequence_is_not_a_cutscene(chinese):
    """``translate("sequence")`` would find the table's ``Sequence``, which is a cutscene."""
    assert kind_name("sequence") == "依序全部做"
    assert describe(_node("sequence")) == "依序全部做"
    assert "演出" not in {kind_name(kind) for kind in NODE_KINDS}


def test_sentences_say_what_the_node_holds():
    assert describe(_node("player_within", {"radius": 56})) == "Player within 56 px"
    assert describe(_node("chance", {"probability": 0.25})) == "25% chance"
    assert describe(_node("hp_below", {"fraction": 0.3, "resource": "hp"})) == "HP below 30%"
    assert describe(_node("repeater", {"count": 0})) == "Repeat forever"
    # a chase without a distance to give up at never gives up: the sentence doesn't claim one
    assert describe(_node("chase", {"arrive": 6})) == "Chase the player, stop within 6 px"
    assert describe(_node("chase", {"arrive": 4.0})) == "Chase the player"
    assert (
        describe(_node("chase", {"lose_radius": 160.0})) == "Chase the player, give up past 160 px"
    )
    assert describe(_node("patrol", {"points": "0,0; 32,0"})) == "Patrol (0, 0) → (32, 0)"
    assert describe(_node("use_ability", {"ability": ""})) == "Use (none)"
    named = describe(_node("use_ability", {"ability": "x"}), lambda _s, _v: "Fire Bolt")
    assert named == "Use Fire Bolt"


def test_circling_the_player_turns_the_way_the_sentence_says():
    """The player stands at the middle; y grows down the screen. Standing on the player's right
    and moving up the screen goes counter-clockwise."""
    from asteria.core import Entity, Scene, Transform
    from asteria.runtime.behavior_tree import BehaviorTreeSystem
    from asteria.runtime.character_control import AIController2DComponent

    scene = Scene("Arena")
    player = scene.add_entity(Entity("Player"))
    player.add_component(Transform(x=0.0, y=0.0))
    foe = scene.add_entity(Entity("Foe"))
    foe.add_component(Transform(x=50.0, y=0.0))
    ai = AIController2DComponent()
    ai.driver, ai.tree_id = "behavior_tree", "circle"
    foe.add_component(ai)
    node = BehaviorNode("strafe", {"direction": 1, "seconds": 9.0, "speed": 40.0})
    system = BehaviorTreeSystem({"circle": BehaviorTree("circle", node)}, target_id=player.id)
    system.update(scene, 0.1)
    assert foe.get(Transform).y < 0.0  # up the screen
    assert "counter-clockwise" in describe(node)
    assert dict(SETTING_CHOICES["direction"])[1] == "Counter-clockwise"


@pytest.fixture
def page(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.behavior_tree_widget import BehaviorTreeEditorWidget
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    document = EditorDocument()
    document.set_project(Project.load_json(DEMO, document.component_registry), file_path=DEMO)
    return BehaviorTreeEditorWidget(document)


def _rows(page):
    from PySide6.QtWidgets import QTreeWidgetItemIterator

    rows, walk = [], QTreeWidgetItemIterator(page.nodes)
    while walk.value():
        rows.append(walk.value().text(0))
        walk += 1
    return rows


def test_foe_patrol_reads_in_plain_words_in_both_languages(page):
    assert page.tree_list.currentItem().text() == "Foe Patrol"
    assert _rows(page) == [
        "Do the first that works",
        "Do all in order",
        "Player within 56 px",
        "Chase the player, stop within 6 px",
        "Wander within 40 px of home",
    ]
    i18n.CURRENT["language"] = "zh_TW"
    try:
        page.refresh()
        assert _rows(page) == [
            "做第一個行得通的",
            "依序全部做",
            "玩家在 56 像素內",
            "追玩家，到 6 像素內停下",
            "在原位 40 像素內四處走動",
        ]
    finally:
        i18n.CURRENT["language"] = "en"


def test_the_kind_lists_are_in_words_and_their_group_lines_cannot_be_picked(page):
    for combo in (page.kind, page.add_kind):
        shown = [combo.itemText(row) for row in range(combo.count())]
        assert not any(ENGINE_CODE.search(text) for text in shown), shown
        assert not set(shown) & set(NODE_KINDS)
        for row in range(combo.count()):
            assert combo.model().item(row).isEnabled() == bool(combo.itemData(row))
    assert page.add_kind.currentData() == "sequence"
    assert page.add_kind.itemText(1) == "Do all in order"


def _on_a_new_node(page, kind):
    page.create_tree("every_kind")
    assert page.add_child(kind), page.last_error
    assert page.select_node((1,))
    return page.api.get("every_kind").node((1,))


def test_a_new_node_works_as_it_is_and_every_setting_is_picked(page):
    from PySide6.QtWidgets import QLineEdit

    from asteria.editor.behavior_tree_widget import PatrolPlaces
    from asteria.editor.record_form import NumberBox

    node = _on_a_new_node(page, "use_ability")
    assert node.params["ability"], "the project's first skill"
    assert page.fields["ability"].value() == node.params["ability"]
    assert page.fields["wait"].currentData() is False
    assert page.apply_params()
    assert page.api.get("every_kind").node((1,)).params == node.params
    for kind in NODE_KINDS:
        page.select_node(())
        assert page.add_child(kind), page.last_error
        count = len(page.api.get("every_kind").root.children)
        assert page.select_node((count - 1,))
        assert set(page.fields) == {name for name, _ in PARAMS[kind]}
        for name, field in page.fields.items():
            typed_code = isinstance(field, QLineEdit)
            assert not typed_code, (kind, name)
            assert not (isinstance(field, NumberBox) and name == "points")
        assert page.apply_params_button.isVisibleTo(page) == bool(page.fields), kind
        if kind == "patrol":
            assert isinstance(page.fields["points"], PatrolPlaces)
        assert page.apply_params(), (kind, page.last_error)


def test_settings_are_saved_under_their_own_keys_and_values(page):
    """What is picked in words is stored as the data always was."""
    node = _on_a_new_node(page, "strafe")
    combo = page.fields["direction"]
    combo.setCurrentIndex(combo.findData(-1))
    page.fields["seconds"].set_value(2.5)
    assert page.apply_params()
    saved = page.api.get("every_kind").node((1,))
    assert saved.to_data() == {
        "kind": "strafe",
        "params": {"direction": -1, "seconds": 2.5, "speed": 40.0},
    }
    assert node.params["direction"] == 1

    page.select_node(())
    assert page.add_child("set_switch") and page.select_node((2,))
    combo = page.fields["value"]
    combo.setCurrentIndex(combo.findData(False))
    assert page.apply_params()
    assert page.api.get("every_kind").node((2,)).params["value"] is False

    page.select_node(())
    assert page.add_child("hp_below") and page.select_node((3,))
    page.fields["fraction"].setValue(25.0)  # as shown: 25 %
    assert page.apply_params()
    assert page.api.get("every_kind").node((3,)).params["fraction"] == 0.25


def test_what_a_setting_refers_to_is_listed_by_name_not_by_id(page):
    for kind, setting in (
        ("use_ability", "ability"),
        ("has_state", "state"),
        ("start_encounter", "encounter_id"),
        ("summon", "prefab"),
        ("hp_below", "resource"),
    ):
        if "every_kind" not in page.api.ids():
            page.create_tree("every_kind")
        page.select_node(())
        assert page.add_child(kind), page.last_error
        last = len(page.api.get("every_kind").root.children) - 1
        assert page.select_node((last,))
        field = page.fields[setting]
        shown = [field.itemText(row) for row in range(field.count())]
        assert shown[0] == "(none)" and len(shown) > 1, kind
        assert not any(ENGINE_CODE.search(text) for text in shown), shown
    assert "Start encounter Acolyte Vigil" in _rows(page), "an encounter without a name of its own"
    # two skills the demo gives one name are told apart in words
    page.select_node(())
    assert page.add_child("use_ability")
    last = len(page.api.get("every_kind").root.children) - 1
    assert page.select_node((last,))
    field = page.fields["ability"]
    shown = [field.itemText(row) for row in range(field.count())]
    assert {"Smoke Bomb (Bomb Smoke)", "Smoke Bomb (Smoke Bomb)"} <= set(shown)


def test_the_status_line_does_not_stay_in_the_other_language(page):
    page.create_tree("every_kind")
    assert page.status.text() == "Created Every Kind"
    i18n.CURRENT["language"] = "zh_TW"
    try:
        page.refresh()
        assert page.status.text() == ""
        assert page.add_child("wait")
        assert page.status.text() == "已新增「等待」"
    finally:
        i18n.CURRENT["language"] = "en"


def test_a_patrols_places_are_rows_and_the_data_stays_as_it_was(page):
    _on_a_new_node(page, "patrol")
    places = page.fields["points"]
    assert places.places() == [(0.0, 0.0), (32.0, 0.0)]
    assert places.text() == "0,0; 32,0"
    places.add_place()
    assert places.places()[-1] == (64.0, 0.0), "a new place is one of its own"
    assert page.apply_params()
    saved = page.api.get("every_kind").node((1,)).params["points"]
    assert saved == "0,0; 32,0; 64,0"
    assert parse_points(saved) == [(0.0, 0.0), (32.0, 0.0), (64.0, 0.0)]
    # the page was built again from what was saved
    places = page.fields["points"]
    for _row, _boxes, remove in places.rows[1:]:
        remove.click()
    assert not places.rows[0][2].isEnabled(), "a patrol keeps one place"
    assert places.text() == "0,0"


def test_an_edit_keeps_its_node_selected_when_the_page_is_refreshed(page):
    """The window refreshes every page after an edit: the node edited stays selected."""
    assert page.select_node((0, 1))
    page.refresh()
    assert page.path == (0, 1)
    assert page.fields["arrive"].number() == 6.0


def test_the_rows_stay_whole_when_the_page_is_narrow(page):
    """The rows are sentences: the list keeps room and scrolls sideways, it never cuts them."""
    from PySide6.QtWidgets import QApplication

    page.resize(845, 700)  # the page in a 1500 wide window with the side panels open
    page.show()
    for _ in range(4):
        QApplication.processEvents()
    page.select_node(())  # the rows are measured again now that they are drawn
    for language in ("en", "zh_TW"):
        i18n.CURRENT["language"] = language
        try:
            page.refresh()
            assert page.nodes.parentWidget().width() >= 240
            assert page.nodes.columnWidth(0) >= page.nodes.sizeHintForColumn(0) > 0
        finally:
            i18n.CURRENT["language"] = "en"
    page.resize(500, 700)
    QApplication.processEvents()
    assert page.nodes.parentWidget().width() >= 240  # dragged or squeezed, it never folds away
    page.hide()


def test_every_kinds_form_fits_beside_the_rows(page):
    """The form never pushes a button or a setting past the page's edge, whatever the kind."""
    from PySide6.QtWidgets import QApplication, QPushButton

    page.resize(845, 700)
    page.show()
    too_wide = {}
    assert page.select_node((0, 0))
    for kind in NODE_KINDS:
        assert page.api.set_kind(page.tree_id, (0, 0), kind) is not None
        page.select_node((0, 0))
        for _ in range(3):
            QApplication.processEvents()
        view = page.kind.parentWidget().parentWidget()
        for button in view.findChildren(QPushButton):
            if button.isVisible():
                edge = button.mapTo(view, button.rect().topRight()).x()
                if edge > view.width():
                    too_wide[kind, button.text()] = (edge, view.width())
    page.hide()
    assert not too_wide


def test_a_setting_left_out_reads_as_what_the_game_does_and_stays_left_out(page):
    """Foe Patrol's chase never gives up. The field says so, and Apply does not change that."""
    assert page.select_node((0, 1))
    assert "lose_radius" not in page.api.get(page.tree_id).node((0, 1)).params
    box = page.fields["lose_radius"]
    assert box.number() == 0 and box.specialValueText() == "Never"
    assert page.apply_params()
    node = page.api.get(page.tree_id).node((0, 1))
    assert "lose_radius" not in node.params and node.params["arrive"] == 6.0

    page.fields["lose_radius"].set_value(90)
    assert page.apply_params()
    assert page.api.get(page.tree_id).node((0, 1)).params["lose_radius"] == 90.0
    page.fields["lose_radius"].set_value(0)  # back to never: left out again, not "give up at 0"
    assert page.apply_params()
    assert "lose_radius" not in page.api.get(page.tree_id).node((0, 1)).params


def test_a_parallel_with_no_count_needs_all_of_its_nodes(page):
    assert page.api.set_kind(page.tree_id, (), "parallel") is not None
    assert page.api.set_params(page.tree_id, (), success_count=0) is not None
    root = page.api.get(page.tree_id).root
    assert "success_count" not in root.params  # the runtime then needs every node inside
    assert describe(root) == "Do all at once"
    page.select_node(())
    box = page.fields["success_count"]
    assert box.number() == 0 and box.specialValueText() == "All"


def test_a_patrol_can_be_set_to_go_round_once(page):
    """``once`` was readable only in the data: now it is picked, and said in the row."""
    assert page.api.set_kind(page.tree_id, (0, 1), "patrol") is not None
    assert "once" not in page.api.get(page.tree_id).node((0, 1)).params
    page.select_node((0, 1))
    rounds = page.fields["once"]
    assert [rounds.itemText(i) for i in range(rounds.count())] == ["Over and over", "One round"]
    rounds.setCurrentIndex(1)
    assert page.apply_params()
    node = page.api.get(page.tree_id).node((0, 1))
    assert node.params["once"] is True
    assert describe(node) == "Patrol (0, 0) → (32, 0) once"
    page.fields["once"].setCurrentIndex(0)
    assert page.apply_params()
    assert "once" not in page.api.get(page.tree_id).node((0, 1)).params  # as the data always was


def test_a_node_that_cannot_lose_its_only_child_says_so_in_words(page):
    assert page.select_node((0, 1)) and page.remove_node()
    assert page.select_node((0, 0))
    assert page.remove_node() is None
    assert "sequence" not in page.status.text()
    assert page.status.text() == "The node around it needs one inside: add another one first"
    assert not page.add_child_button.isEnabled(), "a condition holds no nodes"


def test_the_saved_tree_is_unchanged_by_being_shown(page):
    before = page.api.get("foe_patrol").to_data()
    page.refresh()
    page.select_node((0, 1))
    assert page.api.get("foe_patrol").to_data() == before
    assert before["root"]["children"][0]["children"][1] == {
        "kind": "chase",
        "params": {"arrive": 6},
    }


def _broken_tree_document():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    document = EditorDocument()
    document.set_project(Project.load_json(DEMO, document.component_registry), file_path=DEMO)
    root = BehaviorNode(
        "selector",
        {},
        (
            BehaviorNode("use_ability", {"ability": "no_such_skill"}),
            BehaviorNode("use_ability", {"ability": ""}),
            BehaviorNode("has_state", {"state": "no_such_state"}),
            BehaviorNode("summon", {"prefab": "no_such_prefab"}),
            BehaviorNode("start_encounter", {"encounter_id": "no_such_fight"}),
        ),
    )
    document.project.rpg_database.add_behavior_tree(BehaviorTree("broken_brain", root))
    return document


def test_a_broken_tree_is_a_problem_in_plain_words_in_both_languages(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.problems_widget import ProblemsWidget

    QApplication.instance() or QApplication([])
    panel = ProblemsWidget(_broken_tree_document())
    panel.refresh()
    panel.area.setCurrentIndex(panel.area.findData("Real-Time Combat"))

    def rows():
        items = [panel.tree.topLevelItem(i) for i in range(panel.tree.topLevelItemCount())]
        return [
            (item.text(1), item.text(2), item.text(3)) for item in items if "Brain" in item.text(2)
        ]

    assert rows() == [
        ("Real-Time Combat", message, "Broken Brain")
        for message in (
            "Behavior tree Broken Brain: the skill No Such Skill is not in the project",
            "Behavior tree Broken Brain: no skill is picked",
            "Behavior tree Broken Brain: the state No Such State is not in the project",
            "Behavior tree Broken Brain: the prefab No Such Prefab is not in the project",
        )
    ]
    target = next(p for p in panel.visible_problems() if "Brain" in p.message).target
    assert target == ("behavior_tree", "broken_brain"), "the jump still finds the tree by its id"
    fight = next(p for p in panel.problems if "No Such Fight" in p.message)
    assert fight.area == "Game Data" and fight.target == target
    assert not [p for p in panel.problems if "broken_brain" in p.message], "no wrapped repeat"
    assert (
        fight.message
        == "Behavior tree Broken Brain: the encounter No Such Fight is not in the project"
    )
    assert (
        i18n.translate(fight.message, "zh_TW")
        == "行為樹「Broken Brain」：專案裡沒有遭遇戰「No Such Fight」"
    )
    i18n.CURRENT["language"] = "zh_TW"
    try:
        panel.refresh()
        assert panel.area.currentData() == "Real-Time Combat"
        items = [panel.tree.topLevelItem(i) for i in range(panel.tree.topLevelItemCount())]
        shown = [item.text(2) for item in items if "行為樹" in item.text(2)]
        assert shown == [
            "行為樹「Broken Brain」：專案裡沒有技能「No Such Skill」",
            "行為樹「Broken Brain」：有節點還沒選技能",
            "行為樹「Broken Brain」：專案裡沒有狀態「No Such State」",
            "行為樹「Broken Brain」：專案裡沒有預製物件「No Such Prefab」",
        ]
    finally:
        i18n.CURRENT["language"] = "en"
