"""Project data in the player's language (rpg/data_text.py, D60): record names and
descriptions, dialogue lines and choices, speakers and map names come from the locale tables
under ``data.<kind>.<id>.<field>`` (and a line's ``text_key``); without such keys every screen
draws the records' own text, as before."""

import ast
from pathlib import Path

import pytest

from asteria.events.dialogue import ChoiceRequest, DialogueChoice, DialogueLine
from asteria.rpg import data_text
from asteria.rpg.localization import LocaleTable, Localizer

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "asteria"
DEMO = REPO / "reference_projects" / "full_verification_demo"

ZH = {
    "data.item.healing_herb.name": "療傷草",
    "data.shop.trial_shop.name": "裝備與雜貨",
    "data.quest.q_patrol.name": "清理道路",
    "data.objective.slingers.description": "擊退投石兵",
    "data.enemy.goblin_slinger.name": "哥布林投石兵",
    "data.actor.hero_01.name": "羅傑",
    "data.ability.aegis.name": "神盾",
    "data.ability.aegis.description": "輔助：施放者獲得守護",
    "data.state.attack_up.name": "攻擊提升",
    "data.achievement.beast_slayer.name": "巨獸殺手",
    "data.skill_tree.archmage_tree.name": "大魔導師之樹",
    "data.map.4ca2db1c-f03a-51a8-aac9-3f85718155ee.name": "爐心鎮",
    "data.speaker.Warden Thessaly.name": "守衛瑟莎莉",
    "dlg.test.line": "你好，旅人。",
    "dlg.test.choice": "好的",
    "dlg.test.prompt": "要幫忙嗎？",
    "data.currency.gold.name": "金幣",
}


# -- the key rules --------------------------------------------------------------------------


def test_every_kind_names_a_real_record_class_and_its_id_field():
    classes = {}
    for path in SRC.rglob("*.py"):
        if "editor" in path.parts:
            continue
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.ClassDef):
                fields = {
                    s.target.id
                    for s in node.body
                    if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
                }
                classes[node.name] = fields
    kinds = set()
    # a stat's definition and its formula name the same stat: one name for both (D91)
    shared = {"StatDefinition"}
    for class_name, (kind, attribute) in data_text.KINDS.items():
        assert class_name in classes, class_name
        assert attribute in classes[class_name], (class_name, attribute)
        if class_name not in shared:
            assert kind not in kinds, kind  # one kind per class: keys never collide
        kinds.add(kind)


def test_keys_and_lookups_fall_back_to_the_records_own_text():
    from asteria.rpg.items import ItemDefinition

    herb = ItemDefinition("healing_herb", "Healing Herb")
    assert data_text.kind_of(herb) == ("item", "healing_herb")
    assert data_text.record_key(herb) == "data.item.healing_herb.name"
    assert data_text.key("quest", "q", "description") == "data.quest.q.description"
    with pytest.raises(ValueError):
        data_text.key("quest", "q", "title")
    assert data_text.kind_of(object()) is None
    assert data_text.name_of(None, herb) == "Healing Herb"  # no tables: no lookup at all
    lookup = Localizer([LocaleTable("zh-TW", ZH)], locale="zh-TW").lookup
    assert data_text.name_of(lookup, herb) == "療傷草"
    other = ItemDefinition("ether_leaf", "Ether Leaf")
    assert data_text.name_of(lookup, other) == "Ether Leaf"  # untranslated: as written
    assert data_text.name_of(lookup, None, "fallback") == "fallback"
    assert data_text.map_name(lookup, "nowhere", "Nowhere") == "Nowhere"
    assert data_text.speaker_name(lookup, "Warden Thessaly") == "守衛瑟莎莉"
    assert data_text.text_by_key(lookup, "", "as written") == "as written"
    assert data_text.text_by_key(lookup, "dlg.test.line", "Hello") == "你好，旅人。"


def test_dialogue_keys_are_written_only_when_set_and_old_data_still_reads():
    plain = DialogueLine("Hello")
    assert "text_key" not in plain.to_data()
    assert DialogueLine.from_data(plain.to_data()) == plain
    keyed = DialogueLine("Hello", "Warden", text_key="dlg.test.line")
    assert keyed.to_data()["text_key"] == "dlg.test.line"
    assert DialogueLine.from_data(keyed.to_data()) == keyed
    choice = DialogueChoice("Yes", 1, "dlg.test.choice")
    assert DialogueChoice.from_data(choice.to_data()) == choice
    assert DialogueChoice("Yes", 1).to_data() == {"text": "Yes", "value": 1}
    request = ChoiceRequest("Help?", [choice], prompt_key="dlg.test.prompt")
    assert ChoiceRequest.from_data(request.to_data()) == request
    assert "prompt_key" not in ChoiceRequest("Help?", [choice]).to_data()
    with pytest.raises(ValueError):
        DialogueLine.from_data({**plain.to_data(), "surprise": 1})


def _plain(project):
    """The demo as it was before its own Chinese (T3): no data keys in the tables, no keys on
    the dialogue, so the tests below start from an untranslated project."""
    from asteria.events.program import EventInstruction, EventProgram

    for locale, table in list(project.rpg_database.locale_tables.items()):
        entries = {
            k: v for k, v in dict(table.entries).items() if not k.startswith(("data.", "dlg."))
        }
        project.rpg_database.locale_tables[locale] = LocaleTable(locale, entries)
    programs = project.event_programs
    for program_id in programs.ids():
        old = programs.require(program_id)
        instructions = []
        for instruction in old.instructions:
            args = {
                k: v for k, v in instruction.args.items() if k not in ("text_key", "prompt_key")
            }
            if isinstance(args.get("choices"), list):
                args["choices"] = [
                    {k: v for k, v in c.items() if k != "text_key"} if isinstance(c, dict) else c
                    for c in args["choices"]
                ]
            instructions.append(EventInstruction(instruction.opcode, args))
        programs.replace(program_id, EventProgram(instructions, name=old.name))
    return project


# -- the screens ----------------------------------------------------------------------------


@pytest.fixture
def host(monkeypatch):
    pytest.importorskip("pygame")
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    _plain(project)
    zh = project.rpg_database.locale_tables["zh-TW"]
    project.rpg_database.locale_tables["zh-TW"] = LocaleTable("zh-TW", {**dict(zh.entries), **ZH})
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    yield runtime
    runtime.close()


def test_names_follow_the_players_language(host):
    from asteria.runtime.game_menus import achievement_rows, bestiary_rows

    game, db = host.game, host.project.rpg_database
    assert game.name_of(db.items["healing_herb"]) == "Healing Herb"  # English first
    game.set_locale("zh-TW")
    assert game.name_of(db.items["healing_herb"]) == "療傷草"
    assert game.name_of(db.items["ether_leaf"]) == "Ether Leaf"  # not in the table
    assert game.name_of(db.actors["hero_01"]) == "羅傑"
    aegis = host.project.gameplay_library.abilities.require("aegis")
    assert game.name_of(aegis) == "神盾" and game.description_of(aegis) == "輔助：施放者獲得守護"
    states = host.project.gameplay_library.states
    assert game.name_of(states.require("attack_up")) == "攻擊提升"
    assert game.map_name(game.scene.id, game.scene.name) == "爐心鎮"
    assert any(name == "巨獸殺手" for name, _d, _u in achievement_rows(game))
    game.world.note_enemy("goblin_slinger", "seen", 1)
    assert any(row[0] == "哥布林投石兵" for row in bestiary_rows(game))
    assert game.currency_names() == {"gold": "金幣"}
    game.set_locale("en")
    assert game.name_of(db.items["healing_herb"]) == "Healing Herb"


def test_the_shop_quest_log_and_messages_use_the_translation(host):
    from asteria.runtime.game_menus import ShopScreen, quest_rows

    game = host.game
    game.set_locale("zh-TW")
    game.open_shop_id = "trial_shop"
    screen = ShopScreen(game)
    assert any(row.name == "療傷草" for row in screen.rows())
    assert game.name_of(screen.shop) == "裝備與雜貨"
    game.quest_log.start("q_patrol")
    row = next(r for r in quest_rows(game) if r.quest_id == "q_patrol")
    assert row.name == "清理道路" and row.objectives[0][0] == "擊退投石兵"
    assert game.expand_message("\\N[hero_01]", plain=True) == "羅傑"


def test_dialogue_lines_choices_and_speakers_are_looked_up_by_key(host):
    game = host.game
    line = DialogueLine("Hello", "Warden Thessaly", text_key="dlg.test.line")
    unkeyed = DialogueLine("Hello", "Somebody")
    assert game.line_text(line) == "Hello" and game.speaker_of(line) == "Warden Thessaly"
    game.set_locale("zh-TW")
    assert game.line_text(line) == "你好，旅人。"
    assert game.speaker_of(line) == "守衛瑟莎莉"
    assert game.line_text(unkeyed) == "Hello" and game.speaker_of(unkeyed) == "Somebody"
    choice = DialogueChoice("OK", 1, "dlg.test.choice")
    assert game.line_text(choice) == "好的"
    assert game.prompt_of(ChoiceRequest("Help?", [choice], prompt_key="dlg.test.prompt")) == (
        "要幫忙嗎？"
    )


def test_battle_menus_use_translated_names(host):
    game = host.game
    game.set_locale("zh-TW")
    game.start_encounter("woods_patrol")
    commands = host.battle_commands
    names = {commands.display_name(m) for m in game.battle.members}
    assert any(n.startswith("哥布林投石兵") for n in names)
    assert "羅傑" in names
    assert commands._name("aegis") == "神盾"


def test_a_project_without_data_keys_never_looks_anything_up(host, monkeypatch):
    game = host.game
    tables = dict(game.localizer.tables)
    game.localizer.tables = {}
    try:
        assert game.data_lookup is None  # no tables: the screens skip the lookups entirely
        herb = host.project.rpg_database.items["healing_herb"]
        assert game.name_of(herb) == herb.display_name
        assert game._defeated_label("goblin_slinger:2") == "goblin_slinger:2"  # as before
        assert game.currency_names() == {}
    finally:
        game.localizer.tables = tables


# -- nothing is left drawing a record's own name ----------------------------------------------

# Reads of ``display_name`` that are not drawn, or are deliberately left in English:
# developer errors (D52 keeps them English), data being copied, the pet battle unit (it carries
# the species' name for the logic), the editor-side character view and the inventory profile.
ALLOWED = {
    "runtime/session/party.py",  # GameSessionError messages (developer errors)
    "runtime/session/builds.py",  # copies an actor definition
    "runtime/session/pets.py",  # the pet unit's own attribute
    "runtime/creature_battle.py",  # another batch's screen (not part of D60)
    "runtime/playtest/multiplayer.py",  # network players' names
    "presentation/rpg_character_screen.py",  # its own view model
    "presentation/rpg_inventory_screen.py",  # profile default; the status menu translates
    "presentation/battle_screen.py",  # the screen's names dict, filled translated
    "presentation/workspace.py",  # editor workspace search
    "runtime/battle_presentation_adapters.py",  # assigns the translated names dict
}


def test_no_screen_reads_a_records_own_name_directly():
    offenders = []
    for folder in ("runtime", "presentation"):
        for path in (SRC / folder).rglob("*.py"):
            rel = path.relative_to(SRC).as_posix()
            if rel in ALLOWED:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                code, _, note = line.partition("#")
                if "no session: as written" in note:  # a fallback when no game is attached
                    continue
                if ".display_name" in code and "display_name=" not in code:
                    if "def display_name" in code or "self.display_name(" in code:
                        continue
                    if ".display_name(" in code:  # BattleCommands.display_name(member) (ours)
                        continue
                    offenders.append(f"{rel}:{number}: {line.strip()}")
    assert not offenders, "\n".join(offenders)


# -- the editor's Translations page (T2) -----------------------------------------------------


def _demo_project(plain=True):
    from asteria.editor import EditorDocument
    from asteria.project import Project

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    return _plain(project) if plain else project


def test_the_data_groups_list_every_records_name_and_description():
    from asteria.editor import data_translation as dt

    project = _demo_project()
    groups = dict(dt.data_groups(project))
    items = dict(groups["Data: items"])
    assert items["data.item.healing_herb.name"] == "Healing Herb"
    skills = dict(groups["Data: skills"])
    assert skills["data.ability.aegis.name"] == "Aegis (Divine)"
    assert skills["data.ability.aegis.description"].startswith("Support")
    assert "data.enemy.goblin_slinger.name" in dict(groups["Data: enemies"])
    assert "data.quest.q_patrol.name" in dict(groups["Data: quests"])
    maps = dict(groups[dt.MAPS_GROUP])
    assert maps["data.map.4ca2db1c-f03a-51a8-aac9-3f85718155ee.name"] == "Hearthfold"
    assert dict(groups[dt.CURRENCY_GROUP]) == {
        "data.currency.gold.name": "gold",
        "data.currency.star_stones.name": "star_stones",  # the bounties and the chest's (U5)
    }
    assert "data.speaker.Warden Thessaly.name" in dict(groups[dt.SPEAKERS_GROUP])
    every = [k for _t, rows in groups.items() for k, _e in rows]
    assert len(every) == len(set(every))  # one row per key
    assert dt.data_groups(None) == []


def test_giving_dialogue_keys_is_one_undoable_step_and_keeps_existing_keys():
    from asteria.editor import EditorDocument
    from asteria.editor import data_translation as dt

    project = _demo_project()
    programs = project.event_programs
    missing = dt.dialogue_without_keys(project)
    assert missing > 0
    changes = dt.keyed_programs(project)
    first, new, before = next(
        c for c in changes if any(i.opcode == "DIALOGUE" for i in c[1].instructions)
    )
    assert programs.require(first) == before  # nothing changed yet
    spoken = [i for i in new.instructions if i.opcode == "DIALOGUE" and "text_key" in i.args]
    keys = [i.args["text_key"] for i in spoken]
    assert keys and all(k.startswith("dlg.") for k in keys) and len(keys) == len(set(keys))
    texts = [i.args["text"] for i in spoken]
    assert [i.args.get("text") for i in new.instructions] == [
        i.args.get("text") for i in before.instructions
    ]  # the words themselves never change
    document = EditorDocument(project)
    from asteria.editor.translation_table import TranslationTable

    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    page = TranslationTable(document)
    page.set_rows([], "zh-TW")
    assert page.keys.isEnabled()
    assert page.give_dialogue_keys() == len(changes)
    assert dt.dialogue_without_keys(project) == 0 and not page.keys.isEnabled()
    lines = dict(dict(dt.data_groups(project))[dt.LINES_GROUP])
    assert lines[keys[0]] == texts[0]  # the line is now a row of the page
    assert dt.keyed_programs(project) == []  # a second press changes nothing
    document.undo()
    assert programs.require(first) == before and dt.dialogue_without_keys(project) == missing
    app.processEvents()


def test_the_page_lists_project_data_collapsed_and_finds_it_by_search():
    pytest.importorskip("PySide6")
    from types import SimpleNamespace

    from PySide6.QtWidgets import QApplication

    from asteria.editor.translation_table import OWN_GROUP, TranslationTable

    app = QApplication.instance() or QApplication([])
    page = TranslationTable(SimpleNamespace(project=_demo_project()))
    page.set_rows(
        [
            {"key": "data.item.healing_herb.name", "text": "療傷草"},
            {"key": "data.item.gone_item.name", "text": "已刪除"},  # its record is gone
        ],
        "zh-TW",
    )
    groups = {
        page.tree.topLevelItem(i).data(0, 0x0101): page.tree.topLevelItem(i)
        for i in range(page.tree.topLevelItemCount())
    }
    assert "Data: items" in groups and not groups["Data: items"].isExpanded()
    assert "Title screen" in groups and groups["Title screen"].isExpanded()
    own = [
        groups[OWN_GROUP].child(i).data(0, 0x0100) for i in range(groups[OWN_GROUP].childCount())
    ]
    assert own == ["data.item.gone_item.name"]  # kept, listed with the project's own keys
    page.search.setText("Healing Herb")
    assert groups["Data: items"].isExpanded() and not groups["Data: items"].isHidden()
    page.search.setText("")
    page.show_box.setCurrentIndex(page.show_box.findData("Project data"))
    shown = [i for i in page._items() if not i.isHidden()]
    assert shown and all(i.data(0, 0x0100).startswith(("data.", "dlg.")) for i in shown)
    assert "data texts" in page.count.text()
    assert {"key": "data.item.healing_herb.name", "text": "療傷草"} in page.values()
    app.processEvents()


def test_the_new_page_words_have_chinese():
    import json

    from asteria.editor import data_translation as dt
    from asteria.editor.i18n import translate

    zh = json.loads((SRC / "editor" / "translations" / "zh_TW.json").read_text("utf-8"))
    words = [t for t, _ in dt.DATA_GROUPS]
    words += [dt.MAPS_GROUP, dt.CURRENCY_GROUP, dt.SPEAKERS_GROUP, dt.LINES_GROUP]
    words += [dt.SLOTS_GROUP]
    words += ["Project data", "Give dialogue lines keys", "Give Dialogue Lines Keys"]
    assert [w for w in words if w not in zh["exact"]] == []
    count = "1 engine words · 2 translated · 3 project keys · 4 data texts · 5 translated"
    assert translate(count, "zh_TW") == (
        "引擎字詞 1 個 · 已翻譯 2 個 · 專案自訂鍵 3 個 · 資料文字 4 個 · 已翻譯 5 個"
    )


def test_the_page_follows_an_undo_of_the_dialogue_keys():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor import data_translation as dt
    from asteria.editor.translation_table import TranslationTable

    app = QApplication.instance() or QApplication([])
    document = EditorDocument(_demo_project())
    page = TranslationTable(document)
    page.set_rows([], "zh-TW")
    before = sum(len(rows) for _t, rows in page._data())
    page.give_dialogue_keys()
    assert sum(len(rows) for _t, rows in page._data()) > before
    document.undo()
    page._filter()
    assert sum(len(rows) for _t, rows in page._data()) == before
    assert dt.LINES_GROUP not in dict(page._data())
    assert page.keys.isEnabled()
    app.processEvents()


def test_lines_that_only_name_table_keys_need_no_key_of_their_own():
    from asteria.editor import data_translation as dt

    assert not dt._translatable("\\T[area.bog]")
    assert not dt._translatable(" \\T[a] \\T[b] ")
    assert dt._translatable("Go to \\T[area.bog] now")
    assert not dt._translatable("   ")
    project = _demo_project()
    for _pid, new, _old in dt.keyed_programs(project):
        for instruction in new.instructions:
            if instruction.opcode == "DIALOGUE" and "text_key" in instruction.args:
                assert dt._translatable(instruction.args["text"])


# -- the Full Verification demo's Chinese (T3) ------------------------------------------------


def test_the_demo_translates_every_data_text_and_every_line_has_a_key():
    import sys

    sys.path.insert(0, str(DEMO))
    import trial_zh_data

    from asteria.editor import data_translation as dt

    project = _demo_project(plain=False)
    assert dt.dialogue_without_keys(project) == 0  # the build gave every line its key
    assert trial_zh_data.missing(project) == []
    table = dict(project.rpg_database.locale_tables["zh-TW"].entries)
    rows = trial_zh_data.rows(project)
    assert len(rows) > 1500 and all(key in table for key, _english in rows)
    assert trial_zh_data.apply(project) == 0  # applying again adds nothing
    english = dict(project.rpg_database.locale_tables["en"].entries)
    assert not any(k.startswith(("data.", "dlg.")) for k in english)  # English: as written


def test_the_demo_glossary_reads_naturally_for_the_shapes():
    import sys

    sys.path.insert(0, str(DEMO))
    import trial_zh_data as zh

    assert zh.translate_name("Rune: Siphon (Holy Blade)") == "符文：虹吸（聖劍）"
    assert zh.translate_name("Fire Bolt (Echo)") == "火焰箭（回響）"
    assert zh.translate_name("Vigor-Might Crossing") == "活力與力交會"
    assert zh.translate_name("Archmage Skill Book") == "大魔導師技能書"
    assert zh.translate_name("Craft amethyst_item") == "製作紫水晶"
    assert zh.translate_description("Physical / Fire: inflicts Stun, Burn") == (
        "物理／火：施加暈眩、燃燒"
    )
    assert (
        zh.translate_description("Physical + Magic / Light: 4 hits") == "物理＋魔法／光：4 段攻擊"
    )
    assert zh.translate_name("Unknown Thing") is None
