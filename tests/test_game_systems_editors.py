"""CB10h: Shop, Quest, Faction, Achievement, Equipment Set and Capture Rule editors.

The Python API and the Qt forms edit the same canonical definitions through
one undoable controller; these tests drive both.
"""

import pytest
from test_session_events import _project

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import (
    FORMS,
    KINDS,
    GameSystemsAuthoringController,
    GameSystemsAuthoringError,
)
from asteria.rpg import QuestDefinition, ShopDefinition, ShopEntry


def _controller():
    document = EditorDocument(_project())
    return document, GameSystemsAuthoringController(document)


def test_python_api_create_edit_duplicate_delete_with_undo():
    document, api = _controller()
    db = document.project.rpg_database
    api.create(
        "shops",
        ShopDefinition(
            "apothecary", "Apothecary", [ShopEntry("ether_leaf", buy_prices={"gold": 30})]
        ),
    )
    api.edit(
        "shops", "apothecary", dict(db.shops["apothecary"].to_data(), display_name="Herbalist")
    )
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
        api.create(
            "capture_rules",
            {
                "schema": "asteria.rpg.capture_rule",
                "version": 1,
                "enemy_id": "nobody",
                "actor_id": "hero_01",
                "base_chance": 0.5,
                "low_health_bonus": 0,
                "item_id": "",
            },
        )
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


def _pick(combo, value):
    """Choose a reference by its id (the list shows names)."""
    index = combo.findData(value)
    assert index >= 0, value
    combo.setCurrentIndex(index)


def test_shop_editor_form_adds_stock_rows_and_applies(window):
    editor = window.game_systems_editor
    db = window.document.project.rpg_database
    editor.set_kind("shops")
    assert editor.new_record("apothecary")
    form = editor.form
    _field(form, "display_name").setText("Apothecary")
    entries = _field(form, "entries")
    row = entries.add_row()
    _pick(row.widgets["item_id"], "ether_leaf")
    row.widgets["buy_prices"].add_row("gold", "30")
    row.widgets["sell_prices"].add_row("gold", "12")
    row.widgets["stock"].check.setChecked(True)
    row.widgets["stock"].spin.setValue(5)
    assert editor.apply(), editor.status.text()
    shop = db.shops["apothecary"]
    assert shop.display_name == "Apothecary"
    assert shop.entries == (
        ShopEntry("ether_leaf", buy_prices={"gold": 30}, sell_prices={"gold": 12}, stock=5),
    )
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
    _pick(row.widgets["kind"], "defeat_enemy")
    row.widgets["target"].setText("astral_tyrant")
    assert _field(form, "next_quest_ids").set_checked("report")
    reward = _field(form, "reward").form
    reward.widgets["currencies"].add_row("renown", "5")
    loot = reward.widgets["loot"].add_row()
    _pick(loot.widgets["item_id"], "focus_stone")
    assert editor.apply(), editor.status.text()
    quest = db.quests["hunt"]
    assert [(o.kind, o.target) for o in quest.objectives] == [("defeat_enemy", "astral_tyrant")]
    assert quest.next_quest_ids == ("report",) and quest.reward.currencies == {"renown": 5.0}
    assert quest.reward.loot[0].item_id == "focus_stone"
    assert editor.used_by.text() == ""
    editor.refresh("report")
    assert "quest hunt" in editor.used_by.text()  # reverse reference shown
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
    assert (
        db.factions["guild"].ranks == ((0.0, "Neutral"), (20.0, "Friendly"))
        and db.factions["guild"].maximum == 50
    )

    editor.set_kind("achievements")
    editor.new_record("friend")
    _pick(_field(editor.form, "kind"), "reputation")
    _field(editor.form, "target").setText("guild")
    _field(editor.form, "value").setValue(20)
    assert editor.apply(), editor.status.text()
    assert (db.achievements["friend"].kind, db.achievements["friend"].target) == (
        "reputation",
        "guild",
    )
    _field(editor.form, "target").setText("no_such_faction")
    assert (
        not editor.apply() and "unknown" in editor.status.text()
    )  # canonical validation surfaces in the UI

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
    _pick(_field(editor.form, "actor_id"), "hero_02")
    _pick(_field(editor.form, "item_id"), "ether_leaf")
    _field(editor.form, "base_chance").setValue(0.4)
    assert editor.apply(), editor.status.text()
    rule = db.capture_rules["mender_wisp"]
    assert (rule.actor_id, rule.item_id, rule.base_chance) == ("hero_02", "ether_leaf", 0.4)
    db.validate()


def test_apply_without_changes_round_trips_every_kind(window):
    editor = window.game_systems_editor
    api = editor.controller
    for kind in KINDS:
        if kind.kind_id in ("menu_rules", "menu_pages", "menu_entries"):
            continue  # one Pause Menu page (D97): test_menu_pages
        key = "iron_guard" if kind.kind_id == "capture_rules" else f"rt_{kind.kind_id}"
        api.create_new(kind.kind_id, key)
        before = api.get(kind.kind_id, key)
        editor.set_kind(kind.kind_id)
        editor.refresh(key)
        assert editor.apply(), (kind.kind_id, editor.status.text())
        assert api.get(kind.kind_id, key) == before


def test_a_menu_kind_or_an_unknown_kind_never_leaves_the_page_without_a_kind(window):
    from asteria.editor.game_systems_widget import MENU_KINDS, PAUSE_MENU

    editor = window.game_systems_editor
    for kind_id in MENU_KINDS:  # merged into the Pause Menu page (D97): no row of their own
        editor.set_kind("shops")
        editor.set_kind(kind_id)
        assert editor.kind_id == PAUSE_MENU
    editor.set_kind("shops")
    editor.set_kind("no_such_kind")
    assert editor.kind_id == "shops"
    editor.kind_box.setCurrentIndex(-1)  # nothing chosen: the first kind, not a KeyError
    assert editor.kind_id == editor.kind_box.itemData(0) and editor.form is not None


def test_ids_are_made_not_typed_and_rows_read_by_name(window):
    from asteria.editor.game_systems_widget import _IdLine

    editor = window.game_systems_editor
    editor.set_kind("quests")
    editor._new_clicked()  # no dialog: the id is made
    key = editor.selected_id
    assert key and key.startswith("new")
    head = _field(editor.form, "quest_id")
    assert isinstance(head, _IdLine) and head.text() == key  # "Internal ID: new  ⓘ"
    objectives = _field(editor.form, "objectives")
    objectives.set_rows([])
    first, second = objectives.add_row(), objectives.add_row()
    ids = [r["objective_id"] for r in objectives.values()]
    assert len(set(ids)) == 2 and not first.widgets["objective_id"].isVisible()
    assert second is not None and editor.apply(), editor.status.text()
    editor._duplicate_clicked()
    assert editor.selected_id not in (None, key)  # a copy with a made id


def test_the_form_shows_no_id_line_and_a_closed_list_is_picked_in_words(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_systems_authoring import FORMS
    from asteria.editor.game_systems_widget import RecordForm
    from asteria.editor.record_form import ChipList

    QApplication.instance() or QApplication([])
    _document, controller = _controller()
    form = RecordForm(
        FORMS["ability_loadout_rules"],
        controller.references,
        icons=controller.icon_library,
        document=controller.document,
        cards=True,
    )
    form.show()
    assert form.head_grid is None  # no name: no card holding only an id
    assert not form.widgets["rules_id"].isVisible()
    sources = form.widgets["limited_sources"]
    assert isinstance(sources, ChipList) and sources.allow_new is False
    assert {c.value for c in sources.choices} >= {"learned", "class", "equipment", "passive"}
    assert "learned" not in [c.label for c in sources.choices]  # words, not the code
    form.set_data({**form.data(), "rules_id": "kept", "limited_sources": ["class"]})
    assert form.data()["rules_id"] == "kept"  # hidden, still carried


def test_hp_and_mp_are_stats_on_pets_and_enemy_levels_and_stay_where_the_engine_keeps_them(window):
    from asteria.rpg import BattleResourceDefinition, PetSpeciesDefinition

    editor = window.game_systems_editor
    database = window.document.project.rpg_database
    database.battle_resources["shield"] = BattleResourceDefinition("shield")
    api = editor.controller
    api.create_new("pet_species", "wolf")
    api.edit(
        "pet_species",
        "wolf",
        PetSpeciesDefinition(
            "wolf",
            "Wolf",
            stats={"power": 5.0},
            growth={},
            resources={"vitality": 40.0, "shield": 3.0},
        ),
    )
    editor.set_kind("pet_species")
    editor.refresh("wolf")
    stats, pools = _field(editor.form, "stats"), _field(editor.form, "resources")
    assert stats.values == {"vitality": 40.0, "power": 5.0} and pools.values == {"shield": 3.0}
    assert "vitality" in {c.value for c in stats.choices}
    assert "shield" in {c.value for c in pools.choices}
    assert "vitality" not in {c.value for c in pools.choices}
    assert "vitality" in {c.value for c in _field(editor.form, "growth").choices}

    assert editor.apply()  # nothing changed: nothing moves
    species = api.get("pet_species", "wolf")
    assert species.stats == {"power": 5.0}
    assert species.resources == {"vitality": 40.0, "shield": 3.0}

    stats = _field(editor.form, "stats")  # applying built the form again
    stats._set("vitality", 60.0)  # HP edited among the stats is the resource the engine reads
    stats._set("speed", 7.0)
    assert editor.apply()
    species = api.get("pet_species", "wolf")
    assert species.stats == {"power": 5.0, "speed": 7.0}
    assert species.resources == {"vitality": 60.0, "shield": 3.0}

    api.create_new("enemy_level_rules", "levels")
    editor.set_kind("enemy_level_rules")
    editor.refresh("levels")
    stats = _field(editor.form, "stat_growth")
    stats._set("vitality", 0.1)
    stats._set("power", 0.05)
    assert editor.apply()
    rules = api.get("enemy_level_rules", "levels")
    assert dict(rules.resource_growth) == {"vitality": 0.1}
    assert dict(rules.stat_growth) == {"power": 0.05}
    editor.refresh("levels")
    assert _field(editor.form, "stat_growth").values == {"vitality": 0.1, "power": 0.05}
    assert _field(editor.form, "resource_growth").values == {}


def test_a_pets_hp_grows_from_its_own_amount_with_only_a_growth():
    from asteria.rpg import PetSpeciesDefinition

    species = PetSpeciesDefinition(
        "wolf", "Wolf", stats={}, growth={"vitality": 5.0}, resources={"vitality": 40.0}
    )
    assert species.resources_at(1) == {"vitality": 40.0}
    assert species.resources_at(3) == {"vitality": 50.0}
    grown = PetSpeciesDefinition(
        "cub", "Cub", stats={"vitality": 9.0}, growth={"vitality": 1.0}, resources={"vitality": 40}
    )
    assert grown.resources_at(3) == {"vitality": 11.0}  # a stat of its name still decides
