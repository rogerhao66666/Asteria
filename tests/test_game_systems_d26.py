"""Game Systems forms for the D26 rules: rich records survive the form round trip and edit."""

import pytest
from test_session_events import _project

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import (
    FORMS,
    GameSystemsAuthoringController,
    GameSystemsAuthoringError,
)
from asteria.rpg.battle_extensions import (
    BattleExtensionRules,
    ResourceGain,
    StealEntry,
    StealTable,
)
from asteria.rpg.disassembly import DisassemblyRecipe, DisassemblyYield
from asteria.rpg.doodads import DoodadDefinition
from asteria.rpg.durability import DurabilityRules, WearEvent
from asteria.rpg.enemy_levels import DifficultyLevel, EnemyLevelRules
from asteria.rpg.extras import CreditsPage, MusicTrack
from asteria.rpg.job_points import JobPointRules
from asteria.rpg.localization import LocaleTable, MessageSettings
from asteria.rpg.map_rules import AreaRule, MapRuleSet
from asteria.rpg.new_game_plus import NewGamePlusRules

SHEET = "sheet"
RICH = {
    "battle_extension_rules": BattleExtensionRules(
        "ext",
        damage_resource="vitality",
        taunt_tag="taunt",
        lifesteal_stat="leech",
        overkill_rate=0.5,
        overkill_cap=2.0,
        use_limits={"attack_sword": 3},
        mastery={"attack_sword": (2, 5, 9)},
        preemptive_chance=0.1,
        surprise_chance=0.2,
        steal_tables=(
            StealTable(
                "slime", (StealEntry("ether_leaf", 0.5, 2), StealEntry("fire_bomb")), False
            ),
        ),
        row_tag_prefix="row.",
        gains=(ResourceGain("dealt", "tp", per_damage=0.1, ability_tag="melee"),),
    ),
    "enemy_level_rules": EnemyLevelRules(
        "lv",
        stat_growth={"power": 0.1},
        resource_growth={"vitality": 0.5},
        reward_growth=0.2,
        map_levels={"cave": (3, 6), "plains": (1, 2)},
        party_level_offset=2,
        max_level=50,
        difficulties=(DifficultyLevel("easy", 0.5, 0.5, -1), DifficultyLevel("hard", 2, 1.5, 2)),
        default_difficulty="easy",
    ),
    "map_rule_sets": MapRuleSet(
        "map",
        (
            AreaRule(
                "region:3", damage_resource="vitality", damage_per_second=2, blocks=("enemy",)
            ),
            AreaRule("tag:ice", slippery=True, slip_seconds=0.8, footstep_cue="crunch"),
        ),
        region_layer="zones",
        crouch_visibility=0.5,
        still_visibility=0.8,
    ),
    "durability_rules": DurabilityRules(
        "wear",
        max_durability={"w_sword": 40},
        default_max=10,
        wear=(WearEvent("attack", ["weapon"], 2), WearEvent("hit", ["accessory", "armor"])),
        on_break="destroy",
        repair_currency="gold",
        repair_cost_per_point=3,
    ),
    "disassembly_recipes": DisassemblyRecipe(
        "fire_bomb",
        (DisassemblyYield("alchemy_salt", 1, 3, 0.75), DisassemblyYield("ether_leaf", 1)),
        fee_currency="gold",
        fee=5,
    ),
    "job_point_rules": JobPointRules(
        "jp", prefix="job", per_battle=5, per_enemy=1, secondary=0.25
    ),
    "new_game_plus_rules": NewGamePlusRules(
        "ngp",
        carry=("levels", "inventory"),
        carry_switches=("ending.", "secret."),
        level_cap=40,
        keep_currency_share=0.5,
    ),
    "locale_tables": LocaleTable("zh-TW", {"greet": "你好", "bye": "再見"}),
    "message_settings": MessageSettings(
        "msg",
        macros={"hello": r"Hail, \N[hero_01]!"},
        currency_label="leaves",
        backlog_limit=50,
        default_locale="en",
        icons={"12": "icon_potion"},
    ),
    "music_tracks": MusicTrack("theme", "Main Theme", "bgm_main", unlock_switch="s", note="n"),
    "credits_pages": CreditsPage("art", "Art", ("Ann, lead", "Bob", "Cy"), order=2),
    "doodads": DoodadDefinition(
        "tree",
        SHEET,
        frame=3,
        solid_width=10,
        solid_height=6,
        layer=2,
        depth=1.5,
        snap=8,
        tags=("nature", "tall"),
    ),
}


def _controller():
    document = EditorDocument(_project())
    return document, GameSystemsAuthoringController(document)


@pytest.mark.parametrize("kind_id", sorted(RICH))
def test_a_rich_record_survives_the_form_round_trip(kind_id):
    document, api = _controller()
    record = RICH[kind_id]
    api.create(kind_id, record)
    key = getattr(record, api.kind(kind_id).key)
    data = api.form_data(kind_id, key)
    assert {f.key for f in FORMS[kind_id]} <= set(data)
    api.edit(kind_id, key, data)  # what Apply Changes does with untouched fields
    assert api.get(kind_id, key) == record
    document.undo()
    assert api.get(kind_id, key) == record  # the edit was one step; the create remains
    document.undo()
    assert key not in api.ids(kind_id)


def test_every_new_kind_is_in_the_picker_and_the_database_round_trips():
    document, api = _controller()
    for kind_id, record in RICH.items():
        api.create(kind_id, record)
    from asteria.rpg.actors import RpgDatabase

    restored = RpgDatabase.from_data(document.project.rpg_database.to_data())
    for kind_id, record in RICH.items():
        assert (
            getattr(restored, api.kind(kind_id).store)[getattr(record, api.kind(kind_id).key)]
            == record
        )


def test_bad_form_data_is_refused_with_a_clear_error():
    _, api = _controller()
    api.create_new("durability_rules", "d")
    data = api.form_data("durability_rules", "d")
    data["on_break"] = "explode"
    with pytest.raises(GameSystemsAuthoringError, match="invalid durability_rules"):
        api.edit("durability_rules", "d", data)
    api.create_new("enemy_level_rules", "e")
    data = api.form_data("enemy_level_rules", "e")
    data["map_levels"] = [{"map_id": "cave", "lowest": 5, "highest": 2}]
    with pytest.raises(GameSystemsAuthoringError):
        api.edit("enemy_level_rules", "e", data)
    api.create_new("new_game_plus_rules", "n")
    data = api.form_data("new_game_plus_rules", "n")
    data["carry"] = ["souls"]
    with pytest.raises(GameSystemsAuthoringError):
        api.edit("new_game_plus_rules", "n", data)


def test_references_offer_the_new_choices():
    _, api = _controller()
    assert "levels" in api.references("carry_parts") and "world" in api.references("carry_parts")


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


def test_the_qt_form_shows_and_applies_every_rich_record(window):
    editor = window.game_systems_editor
    api = editor.controller
    for kind_id, record in RICH.items():
        api.create(kind_id, record)
        key = getattr(record, api.kind(kind_id).key)
        editor.set_kind(kind_id)
        editor.refresh(key)
        assert editor.selected_id == key
        assert editor.apply(), (kind_id, editor.status.text())
        assert api.get(kind_id, key) == record


def test_editing_a_table_row_and_a_number_through_the_form(window):
    editor = window.game_systems_editor
    api = editor.controller
    api.create("map_rule_sets", RICH["map_rule_sets"])
    editor.set_kind("map_rule_sets")
    editor.refresh("map")
    form = editor.form
    form.widgets["crouch_visibility"].setValue(0.25)
    table = form.widgets["rules"]
    table.set_rows([*table.values(), {**table.values()[0], "key": "region:9", "slippery": True}])
    assert editor.apply(), editor.status.text()
    updated = api.get("map_rule_sets", "map")
    assert updated.crouch_visibility == 0.25
    assert [r.key for r in updated.rules] == ["region:3", "tag:ice", "region:9"]
    window.document.undo()
    assert api.get("map_rule_sets", "map") == RICH["map_rule_sets"]


def test_a_translation_table_is_edited_as_key_text_rows(window):
    editor = window.game_systems_editor
    api = editor.controller
    api.create("locale_tables", RICH["locale_tables"])
    editor.set_kind("locale_tables")
    editor.refresh("zh-TW")
    table = editor.form.widgets["entries"]
    assert {r["key"] for r in table.values()} == {"greet", "bye"}
    table.set_rows([{"key": "greet", "text": "哈囉"}])
    assert editor.apply(), editor.status.text()
    assert dict(api.get("locale_tables", "zh-TW").entries) == {"greet": "哈囉"}
