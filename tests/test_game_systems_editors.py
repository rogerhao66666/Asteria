"""CB10h: Shop, Quest, Faction, Achievement, Equipment Set and Capture Rule editors.

The Python API and the Qt forms edit the same canonical definitions through
one undoable controller; these tests drive both.
"""

import pytest

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import (
    FORMS, KINDS, GameSystemsAuthoringController, GameSystemsAuthoringError,
)
from asteria.rpg import QuestDefinition, ShopDefinition, ShopEntry
from test_session_events import _project


def _controller():
    document = EditorDocument(_project())
    return document, GameSystemsAuthoringController(document)


def test_python_api_create_edit_duplicate_delete_with_undo():
    document, api = _controller()
    db = document.project.rpg_database
    api.create("shops", ShopDefinition("apothecary", "Apothecary", [ShopEntry("ether_leaf", buy_prices={"gold": 30})]))
    api.edit("shops", "apothecary", dict(db.shops["apothecary"].to_data(), display_name="Herbalist"))
    assert db.shops["apothecary"].display_name == "Herbalist"
    api.duplicate("shops", "apothecary", "apothecary_2")
    assert set(api.ids("shops")) == {"apothecary", "apothecary_2"}
    document.undo()
    document.undo()
    assert db.shops["apothecary"].display_name == "Apothecary" and "apothecary_2" not in db.shops
    document.redo()
    assert db.shops["apothecary"].display_name == "Herbalist"
    api.delete("shops", "apothecary")
    assert "apothecary" not in db.shops
    document.undo()
    assert "apothecary" in db.shops


def test_every_kind_can_be_created_from_the_new_template():
    document, api = _controller()
    for kind in KINDS:
        key = "astral_tyrant" if kind.kind_id == "capture_rules" else f"new_{kind.kind_id}"
        api.create_new(kind.kind_id, key)
        assert key in api.ids(kind.kind_id)
        data = api.form_data(kind.kind_id, key)
        assert {f.key for f in FORMS[kind.kind_id]} <= set(data)
    document.project.rpg_database.validate()


def test_validation_and_reference_protection():
    _, api = _controller()
    with pytest.raises(GameSystemsAuthoringError):
        api.create("shops", ShopDefinition("bad", entries=[ShopEntry("no_such_item")]))
    with pytest.raises(GameSystemsAuthoringError):
        api.create("capture_rules", {"schema": "asteria.rpg.capture_rule", "version": 1, "enemy_id": "nobody",
                                     "actor_id": "hero_01", "base_chance": 0.5, "low_health_bonus": 0, "item_id": ""})
    api.create("quests", QuestDefinition("first"))
    api.create("quests", QuestDefinition("second", prerequisites=["first"]))
    assert api.where_used("quests", "first") == ("quest second",)
    with pytest.raises(GameSystemsAuthoringError):
        api.delete("quests", "first")
    with pytest.raises(GameSystemsAuthoringError):
        api.edit("quests", "first", dict(api.get("quests", "first").to_data(), quest_id="renamed"))
    with pytest.raises(GameSystemsAuthoringError):
        api.create("quests", QuestDefinition("first"))


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(_project())
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def _field(form, key):
    return form.widgets[key]


def test_shop_editor_form_adds_stock_rows_and_applies(window):
    editor = window.game_systems_editor
    db = window.document.project.rpg_database
    editor.set_kind("shops")
    assert editor.new_record("apothecary")
    form = editor.form
    _field(form, "display_name").setText("Apothecary")
    entries = _field(form, "entries")
    row = entries.add_row()
    row.widgets["item_id"].setCurrentText("ether_leaf")
    row.widgets["buy_prices"].add_row("gold", "30")
    row.widgets["sell_prices"].add_row("gold", "12")
    row.widgets["stock"].check.setChecked(True)
    row.widgets["stock"].spin.setValue(5)
    assert editor.apply(), editor.status.text()
    shop = db.shops["apothecary"]
    assert shop.display_name == "Apothecary"
    assert shop.entries == (ShopEntry("ether_leaf", buy_prices={"gold": 30}, sell_prices={"gold": 12}, stock=5),)
    window.document.undo()
    assert db.shops["apothecary"].entries == ()


def test_quest_editor_objectives_chain_and_reward(window):
    editor = window.game_systems_editor
    db = window.document.project.rpg_database
    editor.set_kind("quests")
    editor.new_record("hunt")
    editor.new_record("report")
    editor.refresh("hunt")
    form = editor.form
    objectives = _field(form, "objectives")
    objectives.set_rows([])
    row = objectives.add_row()
    row.widgets["objective_id"].setText("tyrant")
    row.widgets["kind"].setCurrentText("defeat_enemy")
    row.widgets["target"].setText("astral_tyrant")
    assert _field(form, "next_quest_ids").set_checked("report")
    reward = _field(form, "reward").form
    reward.widgets["currencies"].add_row("renown", "5")
    loot = reward.widgets["loot"].add_row()
    loot.widgets["item_id"].setCurrentText("focus_stone")
    assert editor.apply(), editor.status.text()
    quest = db.quests["hunt"]
    assert [(o.kind, o.target) for o in quest.objectives] == [("defeat_enemy", "astral_tyrant")]
    assert quest.next_quest_ids == ("report",) and quest.reward.currencies == {"renown": 5.0}
    assert quest.reward.loot[0].item_id == "focus_stone"
    assert editor.used_by.text() == ""
    editor.refresh("report")
    assert "quest hunt" in editor.used_by.text()                      # reverse reference shown
    assert not editor.delete_selected() and "used by" in editor.status.text()


def test_faction_achievement_set_and_capture_editors(window):
    editor = window.game_systems_editor
    db = window.document.project.rpg_database

    editor.set_kind("factions")
    editor.new_record("guild")
    ranks = _field(editor.form, "ranks")
    ranks.add_row("0", "Neutral")
    ranks.add_row("20", "Friendly")
    _field(editor.form, "maximum").setValue(50)
    assert editor.apply(), editor.status.text()
    assert db.factions["guild"].ranks == ((0.0, "Neutral"), (20.0, "Friendly")) and db.factions["guild"].maximum == 50

    editor.set_kind("achievements")
    editor.new_record("friend")
    _field(editor.form, "kind").setCurrentText("reputation")
    _field(editor.form, "target").setText("guild")
    _field(editor.form, "value").setValue(20)
    assert editor.apply(), editor.status.text()
    assert (db.achievements["friend"].kind, db.achievements["friend"].target) == ("reputation", "guild")
    _field(editor.form, "target").setText("no_such_faction")
    assert not editor.apply() and "unknown" in editor.status.text()  # canonical validation surfaces in the UI

    editor.set_kind("equipment_sets")
    editor.new_record("ember")
    for equipment_id in ("accessory_01", "weapon_01"):
        assert _field(editor.form, "equipment_ids").set_checked(equipment_id)
    bonus = _field(editor.form, "bonuses").add_row()
    bonus.widgets["pieces"].setValue(2)
    modifier = bonus.widgets["modifiers"].add_row()
    modifier.widgets["stat"].setText("power")
    modifier.widgets["value"].setValue(10)
    bonus.widgets["tags"].setText("set.ember")
    assert editor.apply(), editor.status.text()
    ember = db.equipment_sets["ember"]
    assert ember.equipment_ids == ("accessory_01", "weapon_01")
    assert ember.bonuses[0].modifiers[0].value == 10 and ember.bonuses[0].tags == ("set.ember",)

    editor.set_kind("capture_rules")
    assert editor.new_record("mender_wisp")
    _field(editor.form, "actor_id").setCurrentText("hero_02")
    _field(editor.form, "item_id").setCurrentText("ether_leaf")
    _field(editor.form, "base_chance").setValue(0.4)
    assert editor.apply(), editor.status.text()
    rule = db.capture_rules["mender_wisp"]
    assert (rule.actor_id, rule.item_id, rule.base_chance) == ("hero_02", "ether_leaf", 0.4)
    db.validate()


def test_apply_without_changes_round_trips_every_kind(window):
    editor = window.game_systems_editor
    api = editor.controller
    for kind in KINDS:
        key = "iron_guard" if kind.kind_id == "capture_rules" else f"rt_{kind.kind_id}"
        api.create_new(kind.kind_id, key)
        before = api.get(kind.kind_id, key)
        editor.set_kind(kind.kind_id)
        editor.refresh(key)
        assert editor.apply(), (kind.kind_id, editor.status.text())
        assert api.get(kind.kind_id, key) == before
