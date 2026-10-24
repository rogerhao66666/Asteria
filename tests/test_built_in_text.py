"""The engine's own words go through the project's translation tables (rpg/built_in_text.py):
every word a runtime screen draws is listed with the English it draws, a table entry changes the
word drawn, a project without one draws the English it always did, and Chinese text gets the
room and the line it needs."""

import ast
import string
import sys
from collections import Counter
from pathlib import Path

import pytest

from asteria.presentation.text_cells import cells, cut, wrap
from asteria.rpg.built_in_text import (
    BUILT_IN_TEXT,
    GROUPS,
    Words,
    engine_locales,
    engine_translations,
    group_of,
    translated,
)
from asteria.rpg.localization import LocaleTable, MessageSettings

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "asteria"
DEMO = ROOT / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


# -- the list and the code agree ---------------------------------------------------------------
def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _literal(node.left), _literal(node.right)
        return None if a is None or b is None else a + b
    return None


def _drawn_words():
    """``{key: [(english, where)]}`` of every ``tr(key, english)`` / ``Words(key, english)``
    call with written-out text in the engine (the editor's own interface is not a game's)."""
    found = {}
    for path in sorted(SRC.rglob("*.py")):
        if "editor" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or len(node.args) < 2:
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            if name not in ("tr", "_tr", "Words"):
                continue
            key, english = _literal(node.args[0]), _literal(node.args[1])
            if key is not None and english is not None:
                where = f"{path.relative_to(SRC)}:{node.lineno}"
                found.setdefault(key, []).append((english, where))
    return found


def _keyed_tables():
    """The words drawn from a table of ids (menu options, statuses...): ``{key: english}``."""
    from asteria.runtime.battle_commands import COMMAND_WORDS
    from asteria.runtime.game_menus import GAME_OVER_OPTIONS, PAUSE_OPTIONS, GameSettings
    from asteria.runtime.playable_test_runtime import BESTIARY_TAG_KINDS
    from asteria.runtime.skill_tree_screen import STATUS_WORDS
    from asteria.runtime.status_menu import TAB_WORDS, USE_REASONS

    words = {f"pause.{k}": v for k, v in PAUSE_OPTIONS}
    words.update({f"game_over.{k}": v for k, v in GAME_OVER_OPTIONS})
    words.update({f"settings.{k}": v for k, v in GameSettings.OPTIONS})
    words.update({key: name for name, key in COMMAND_WORDS.items()})
    words.update({key: tab.title() for tab, key in TAB_WORDS.items()})
    words.update({key: code for code, key in USE_REASONS.items()})
    words.update({key: status for status, key in STATUS_WORDS.items()})
    words.update({f"quests.status.{s}": s for s in ("active", "completed", "failed")})
    words.update({f"bestiary.tag.{kind}": kind for kind in BESTIARY_TAG_KINDS})
    words.update({"shop.buy": "Buy", "shop.sell": "Sell", "language.name": "English"})
    # put together where they are drawn: a plural, a reason used twice, a rank change
    words["battle.reason.cooldown_one"] = "Ready in {turns} turn"
    words["battle.reason.cooldown"] = "Ready in {turns} turns"
    words["battle.reason.short"] = "Needs {amount} {resource} (has {have})"
    words["battle.result.rank"] = "Rank {old} → {new}"
    words.update(  # a result headline by outcome; the English is the default profile label
        {
            "battle.result.victory": "Victory",
            "battle.result.defeat": "Defeat",
            "battle.result.escape": "Escaped",
            "battle.result.complete": "Battle Complete",
        }
    )
    return words


def test_every_drawn_word_is_listed_with_the_english_it_draws():
    found = _drawn_words()
    assert len(found) > 250
    for key, uses in found.items():
        assert key in BUILT_IN_TEXT, f"{key} ({uses[0][1]}) is not in rpg/built_in_text.py"
        for english, where in uses:
            assert BUILT_IN_TEXT[key] == english, (key, where)
    for key, english in _keyed_tables().items():
        assert BUILT_IN_TEXT.get(key) == english, key


def test_every_listed_word_is_drawn_somewhere_and_listed_once():
    used = set(_drawn_words()) | set(_keyed_tables()) | {"pause.pets", "pause.backlog"}
    used |= {"pause.skill_slots", "pause.music", "pause.credits", "settings.language"}
    used |= {"pause.equipment", "pause.enhance"}  # offered when the project has gear
    assert sorted(set(BUILT_IN_TEXT) - used) == []
    keys = [key for _, rows in GROUPS for key, _ in rows]
    assert len(keys) == len(set(keys)) == len(BUILT_IN_TEXT)
    assert group_of("battle.command.attack") == "Battle commands" and group_of("area.bog") == ""


def _fields(text):
    return sorted(name for _, name, _, _ in string.Formatter().parse(text) if name)


def test_the_engine_translation_covers_every_word_and_keeps_its_placeholders():
    assert "zh-TW" in engine_locales()
    chinese = engine_translations("zh-TW")
    assert set(chinese) == set(BUILT_IN_TEXT)
    for key, english in BUILT_IN_TEXT.items():
        assert _fields(chinese[key]) == _fields(english), key
    assert chinese["battle.command.attack"] == "攻擊" and chinese["language.name"] == "繁體中文"
    assert engine_translations("zh-TW-x-custom") == chinese  # a child locale: its parent's
    assert engine_translations("fr") == {} and engine_translations("") == {}
    chinese["battle.command.attack"] = "changed"  # a copy: the engine's own table stays
    assert engine_translations("zh-TW")["battle.command.attack"] == "攻擊"


# -- the game draws the table's words ----------------------------------------------------------
def _battle(tables=None, default_locale="en"):
    """The Full Verification boss fight, its translations replaced by ``tables``."""
    import run_trial_smoke as smoke

    project, game = smoke.load()
    db = project.rpg_database
    if tables is not None:
        db.locale_tables.clear()
        db.locale_tables.update({t.locale: t for t in tables})
        settings = db.message_settings[sorted(db.message_settings)[0]]
        data = settings.to_data()
        data["default_locale"] = default_locale
        db.message_settings[settings.settings_id] = MessageSettings.from_data(data)
    game._localizer = None
    smoke.prepare(game, Counter(), "hero")
    game.start_encounter("boss_room")
    return game


def _root_rows(game):
    from asteria.runtime.battle_commands import BattleCommands

    commands = BattleCommands(game, style="root")
    hero = game.active_hero_ids()[0]
    return commands, hero, commands.root_rows(hero)


def test_a_project_without_tables_shows_the_words_in_english():
    game = _battle(tables=(), default_locale="")
    commands, hero, rows = _root_rows(game)
    shown = {r.action_id: (r.label, r.detail) for r in rows}
    assert shown["root:Attack"] == ("Attack", "Choose a weapon")
    assert shown["root:Skills"] == ("Skills", "Abilities, concoct, capture")
    assert shown["root:Items"] == ("Items", "Use an item from the bag")
    assert shown["root:Combo"] == ("Combo", "Abilities")  # the project's own group
    assert commands.category_label("Target") == "Target"
    assert game.escape_unavailable() == "This battle has no_escape: there is no running away"
    assert game.tr("pause.resume", "Resume") == "Resume"


def test_a_table_entry_changes_the_word_drawn():
    table = LocaleTable(
        "zh-TW",
        {
            "battle.command.attack": "攻擊",
            "battle.hint.attack": "選擇武器",
            "battle.escape.blocked": "這場戰鬥無法逃跑",
            "battle.menu.target": "目標",
        },
    )
    game = _battle(tables=(table,), default_locale="zh-TW")
    commands, hero, rows = _root_rows(game)
    assert (rows[0].label, rows[0].detail) == ("攻擊", "選擇武器")
    assert rows[0].action_id == "root:Attack"  # the id stays English
    assert rows[1].label == "Skills"  # a word the table leaves out keeps its English
    assert commands.category_label("Target") == "目標"
    assert game.escape_unavailable() == "這場戰鬥無法逃跑"


def test_a_default_locale_table_renames_a_word():
    game = _battle(tables=(LocaleTable("en", {"battle.command.attack": "Fight"}),))
    assert _root_rows(game)[2][0].label == "Fight"


def test_command_menu_page_names_and_skill_groups_follow_the_table():
    from asteria.runtime.battle_commands import BattleCommands

    def rows(game):
        pages = game.project.battle_presentation_library.require("interaction", "trial_commands")
        commands = BattleCommands(game, style="root", pages=pages)
        hero = game.active_hero_ids()[0]
        shown = {r.action_id: r.label for r in commands.root_rows(hero)}
        return commands, shown

    commands, shown = rows(_battle(tables=(), default_locale=""))
    assert shown["root:Attack"] == "Fight"  # the pages' own name, as the project wrote it
    assert commands.category_label("Combo") == "Combo"
    zh = LocaleTable(
        "zh-TW",
        {
            "battle.layer.Attack": "攻擊",
            "battle.group.Combo": "連段",
            "battle.command.attack": "打",
        },
    )
    commands, shown = rows(_battle(tables=(zh,), default_locale="zh-TW"))
    assert shown["root:Attack"] == "攻擊"  # the page's name wins over the built-in word
    assert shown["root:Skills"] == "Skills"  # a name the table leaves out: as written
    assert commands.category_label("Combo") == "連段"
    assert commands.category_label("Skills") == "Skills"


def test_victory_pages_and_settings_values_follow_the_table():
    from asteria.rpg.victory import ActorAftermath, VictoryAftermath
    from asteria.runtime.game_menus import GameSettings

    aftermath = VictoryAftermath(
        currencies=(("gold", 30.0),),
        items=(("potion", 2),),
        actors=(ActorAftermath("hero", "Aldric", 40.0, 1, 2, (), ("fire",)),),
        defeated=("Slime",),
    )
    english = aftermath.pages()
    assert [p.title for p in english] == ["Victory", "Aldric", "Spoils"]
    assert english[0].lines[0] == "Defeated: Slime"
    assert english[1].lines == ("EXP  +40", "Level 1 -> 2", "Learned fire")
    assert english[1].highlights == (1, 2)
    zh = engine_translations("zh-TW")

    def tr(key, default, **params):
        return zh.get(key, default).format(**params)

    shown = aftermath.pages(tr=tr)
    assert [p.title for p in shown] == ["勝利", "Aldric", "戰利品"]
    assert shown[1].lines == ("經驗值  +40", "等級 1 → 2", "學會了 fire")
    settings = GameSettings()
    assert settings.value_text("show_battle_log") == "On"
    assert settings.value_text("show_battle_log", tr) == "開"


def test_a_refused_deal_is_english_text_that_a_shop_can_translate():
    from asteria.rpg.economy import ShopError

    error = ShopError(
        Words("shop.error.afford", "cannot afford {count} {item}", count=2, item="x")
    )
    assert str(error) == "cannot afford 2 x"
    zh = engine_translations("zh-TW")
    assert translated(error, lambda key, default, **p: zh[key].format(**p)) == "錢不夠買 2 個 x"
    assert translated(ValueError("plain"), None) == "plain"


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
    zh = project.rpg_database.locale_tables["zh-TW"]
    entries = {**engine_translations("zh-TW"), **dict(zh.entries)}
    project.rpg_database.locale_tables["zh-TW"] = LocaleTable("zh-TW", entries)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    yield runtime
    runtime.close()


def _drawn(host, draw):
    shown = []
    original = host.text

    def record(value, *args, **kwargs):
        shown.append(str(value))
        return original(value, *args, **kwargs)

    host.text = record
    try:
        draw()
    finally:
        host.text = original
    return shown


def test_the_pause_and_settings_menus_draw_the_players_language(host):
    english = _drawn(host, lambda: host._draw_overlay_menu("Paused", host._pause_menu))
    assert "Resume" in english and "Settings" in english
    assert "Make Camp" in english  # the project's own entry, as it wrote it
    for key, label in host._pause_menu.options:  # what the list says each built-in one is
        if not key.startswith("entry:"):
            assert BUILT_IN_TEXT[f"pause.{key}"] == label
    host.game.set_locale("zh-TW")
    title = host.game.tr("pause.heading", "Paused")
    chinese = _drawn(host, lambda: host._draw_overlay_menu(title, host._pause_menu))
    assert "暫停" in chinese and "繼續遊戲" in chinese and "設定" in chinese
    assert "紮營" in chinese  # the demo's table words its own entry (pause.entry.camp)
    settings = _drawn(host, host._draw_settings)
    assert "語言" in settings and "繁體中文" in settings and "音樂音量" in settings


def test_the_title_and_game_over_screens_draw_the_players_language(host):
    host.game.set_locale("zh-TW")
    shown = _drawn(host, host._draw_title)
    assert "N   新遊戲" in shown and "L   讀取進度" in shown
    title = host.game.tr("game_over.heading", "Game Over")
    shown = _drawn(host, lambda: host._draw_overlay_menu(title, host._game_over_menu, "field"))
    assert "遊戲結束" in shown and "讀取上次的存檔" in shown and "回到標題畫面" in shown


# -- Chinese text gets its room and its line ---------------------------------------------------
def test_full_width_characters_take_two_cells_and_english_keeps_its_count():
    assert cells("Attack") == 6 and cells("攻擊") == 4 and cells("HP 回復") == 7
    assert cut("攻擊技能", 5) == "攻擊" and cut("Attack", 3) == "Att"
    assert wrap("對一名敵人造成大量火焰傷害，並使其燃燒。", 16) == [
        "對一名敵人造成大",
        "量火焰傷害，並使",
        "其燃燒。",
    ]
    assert wrap("Deals heavy fire damage to one foe", 16) == [
        "Deals heavy fire",
        "damage to one",
        "foe",
    ]


def test_the_battle_menu_gives_a_chinese_row_the_room_of_two_letters_a_character():
    from asteria.presentation.battle_action_menu import BattleActionEntry, BattleActionMenuView
    from asteria.presentation.battle_ui import (
        BattleUiComposer,
        BattleUiLayoutProfile,
        _category_strip,
    )

    def width(label):  # the side-list menu is as wide as its longest row needs
        entry = BattleActionEntry("a", label, category="Skills")
        view = BattleActionMenuView(("Skills",), "Skills", "", (entry,), 0, 1, 1, 0, 0)
        layout = BattleUiLayoutProfile(party_hud="side_list")
        composer = BattleUiComposer(_scene(), layout)
        composer._camera, composer._focus, composer._member_heights = None, None, {}
        panels, _texts, _icons = composer._action_menu_layout(view)
        return next(p for p in panels if p.panel_id == "action_menu").width

    fourteen = "攻擊技能火焰冰霜雷電大地之力"
    assert width(fourteen) == width("A" * 28)  # 14 characters take the room of 28 letters
    assert width(fourteen) > width("A" * 14)
    assert BattleUiComposer._fit("格里姆加德", 6) == "格里."
    assert BattleUiComposer._fit("Grimgarde", 6) == "Grimg."  # as it always was
    row = _category_strip(["Attack", "Skills", "Items"], "Skills", 90.0, {"Skills": "技能"})
    assert "[技能]" in row and cells(row) * 3.8 <= 90.0


def _scene():
    from asteria.presentation.battle import BattlePresentationScene

    return BattlePresentationScene("scene", "background", (), None)


def test_a_chinese_menu_label_sits_level_with_its_cursor(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from asteria.platform.pygame_battle_ui import cjk_font_path
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    pygame.init()
    if cjk_font_path(pygame) is None:
        pytest.skip("no CJK system font")
    runtime = PlayableTestRuntime.__new__(PlayableTestRuntime)
    runtime.pg = pygame
    runtime._fonts, runtime._cjk_fonts, runtime._glyphs = {}, {}, {}
    for size in (20, 24, 30):
        runtime.screen = pygame.Surface((400, 120))
        runtime.menu_row("攻擊技能", 20, 30, selected=True, size=size, color=(255, 0, 0))

        def rows(x0, x1):
            return [
                y
                for y in range(120)
                if any(runtime.screen.get_at((x, y))[:3] == (255, 0, 0) for x in range(x0, x1))
            ]

        room = runtime.menu_mark_room(size)
        mark, text = rows(20, 20 + room - 2), rows(20 + room, 400)
        assert abs((mark[0] + mark[-1]) / 2 - (text[0] + text[-1]) / 2) <= 1.5, size
        # the width a screen measures is the width drawn, in the face that draws it
        assert runtime.text_width("攻擊技能", size) == runtime.text_size("攻擊技能", size)[0]
        assert runtime.text_width("攻擊技能", size) > runtime.text_width("Attack", size)
        # a Chinese line stands about a quarter taller than an English one, not 45 % or more
        chinese, english = (
            runtime.text_size("繼續遊戲", size)[1],
            runtime.text_size("Resume", size)[1],
        )
        assert english < chinese <= english * 1.4, size


def test_the_battle_screen_draws_chinese_at_its_face_size_level_with_the_cursor(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from asteria.platform.pygame_battle_ui import PygameBattleUiBackend, cjk_font_path
    from asteria.presentation.battle_ui import BattleUiText

    pygame.init()
    if cjk_font_path(pygame) is None:
        pytest.skip("no CJK system font")
    font = DEMO / "playable_assets" / "lucifer" / "ui" / "font.ttf"
    for name, scale in ((None, 1.0), (str(font), 0.62)):
        screen = pygame.Surface((420, 120))
        backend = PygameBattleUiBackend(screen, scale=2.0, font_name=name, font_scale=scale)
        backend.draw_text(
            BattleUiText("▶", 10, 20, "action_selected:mark"), color=(255, 0, 0), size=10
        )
        backend.draw_text(
            BattleUiText("攻擊", 30, 20, "action_selected"), color=(255, 0, 0), size=10
        )
        face = backend._font(10)
        assert {size for _id, size in backend._cjk_fonts} == {face.point_size}  # not 20 px

        def rows(x0, x1, screen=screen):
            return [
                y
                for y in range(120)
                if any(screen.get_at((x, y))[:3] == (255, 0, 0) for x in range(x0, x1))
            ]

        mark, text = rows(18, 40), rows(60, 420)
        assert abs((mark[0] + mark[-1]) / 2 - (text[0] + text[-1]) / 2) <= 1.5, name


# -- the editor lists every word -----------------------------------------------------------------
def test_the_translations_page_lists_every_engine_word_and_fills_from_the_engine():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.translation_table import TranslationTable

    app = QApplication.instance() or QApplication([])
    table = TranslationTable()
    table.set_rows(
        [{"key": "greet", "text": "你好"}, {"key": "pause.resume", "text": "繼續"}], "zh-TW"
    )
    listed = {item.data(0, 0x0100): item for item in table._items()}  # Qt.UserRole
    assert set(BUILT_IN_TEXT) <= set(listed) and "greet" in listed
    assert listed["battle.command.attack"].text(1) == "Attack"  # the English beside it
    assert listed["controls.action.reset_all"].text(1) == "reset_all"
    assert sorted(r["key"] for r in table.values()) == ["greet", "pause.resume"]
    listed["battle.command.attack"].setText(2, "攻擊")
    listed["pause.resume"].setText(2, "")  # cleared: the English comes back
    values = {r["key"]: r["text"] for r in table.values()}
    assert values == {"greet": "你好", "battle.command.attack": "攻擊"}
    listed["greet"].setText(0, "hello")  # a project's own key can be renamed
    listed["battle.command.attack"].setText(0, "attack")  # a built-in one stays as it is
    assert listed["battle.command.attack"].text(0) == "battle.command.attack"
    values = {r["key"]: r["text"] for r in table.values()}
    assert values == {"hello": "你好", "battle.command.attack": "攻擊"}
    assert table.fill_from_engine() == len(BUILT_IN_TEXT) - 1
    values = {r["key"]: r["text"] for r in table.values()}
    assert values["battle.command.attack"] == "攻擊" and values["pause.resume"] == "繼續遊戲"
    assert all(text != "" for text in values.values())
    french = TranslationTable()
    french.set_rows([], "fr")
    assert not french.fill.isEnabled() and french.fill_from_engine() == 0
    table.show_box.setCurrentIndex(1)  # not translated yet: only the project's input actions
    hidden = [i.isHidden() for i in table._items() if i.data(0, 0x0100) in BUILT_IN_TEXT]
    assert all(hidden)
    app.processEvents()


def test_the_translations_page_speaks_the_editor_language():
    import json

    table = json.loads(
        (SRC / "editor" / "translations" / "zh_TW.json").read_text(encoding="utf-8")
    )["exact"]
    from asteria.editor.translation_table import (
        ACTIONS_GROUP,
        ENTRIES_GROUP,
        LAYERS_GROUP,
        OWN_GROUP,
        SHOWN,
        SKILL_GROUPS,
    )

    titles = [title for title, _ in GROUPS]
    titles += [OWN_GROUP, ACTIONS_GROUP, LAYERS_GROUP, SKILL_GROUPS, ENTRIES_GROUP]
    labels = [label for label, _ in SHOWN] + ["Fill empty rows", "Add key", "Remove key"]
    assert [x for x in titles + labels + ["English", "Search keys, English or text"]
            if x not in table] == []  # fmt: skip


def test_the_demo_shows_the_engine_words_and_its_own_menu_names_in_chinese():
    import run_trial_smoke as smoke
    import trial_world

    project, _game = smoke.load()
    tables = project.rpg_database.locale_tables
    chinese, english = dict(tables["zh-TW"].entries), dict(tables["en"].entries)
    assert set(BUILT_IN_TEXT) <= set(chinese)  # a word the engine adds must be added here too
    pages = project.battle_presentation_library.require("interaction", "trial_commands")
    assert all(f"battle.layer.{layer.layer_id}" in chinese for layer in pages.layers)
    assert all(f"pause.entry.{key}" in chinese for key in project.rpg_database.menu_entries)
    assert all(chinese[key] == zh for key, (_en, zh) in trial_world.TEXT.items())
    assert set(english) & set(BUILT_IN_TEXT) == {"language.name"}  # English: as written


def test_the_translations_page_lists_the_names_the_battle_menu_draws():
    pytest.importorskip("PySide6")
    from types import SimpleNamespace

    import run_trial_smoke as smoke
    from PySide6.QtWidgets import QApplication

    from asteria.editor.translation_table import LAYERS_GROUP, SKILL_GROUPS, TranslationTable

    app = QApplication.instance() or QApplication([])
    project, _game = smoke.load()
    table = TranslationTable(SimpleNamespace(project=project))
    table.set_rows([], "zh-TW")
    titles = [
        table.tree.topLevelItem(i).data(0, 0x0101) for i in range(table.tree.topLevelItemCount())
    ]
    assert LAYERS_GROUP in titles and SKILL_GROUPS in titles
    listed = {item.data(0, 0x0100): item.text(1) for item in table._items()}
    assert listed["battle.layer.Attack"] == "Fight" and listed["battle.group.Combo"] == "Combo"
    assert listed["controls.action.move_up"] == "move_up"
    assert listed["pause.entry.camp"] == "Make Camp"
    table.fill_from_engine()
    values = {r["key"]: r["text"] for r in table.values()}
    assert values["battle.layer.Skills"] == "技能"  # the page names it with a built-in word
    assert "battle.layer.Attack" not in values  # "Fight" is the project's own: for its author
    app.processEvents()


def test_the_key_list_page_is_up_to_date():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "built_in_text_keys", ROOT / "scripts" / "built_in_text_keys.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    written = module.PAGE.read_text(encoding="utf-8")
    assert written == module.page(), "run scripts/built_in_text_keys.py"
    assert all(f"`{key}`" in written for key in BUILT_IN_TEXT)


def test_a_skin_face_with_chinese_characters_draws_them_itself(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from asteria.platform.pygame_battle_ui import PygameBattleUiBackend, cjk_font_path
    from asteria.presentation.battle_ui import BattleUiText

    pygame.init()
    face = cjk_font_path(pygame)  # a face with Chinese in it, chosen as the skin's own
    if face is None:
        pytest.skip("no Chinese-capable face to try")
    backend = PygameBattleUiBackend(pygame.Surface((200, 60)), scale=2.0, font_name=str(face))
    backend.draw_text(BattleUiText("攻擊", 4, 4, "action_entry"), color=(255, 0, 0), size=10)
    assert backend._cjk_fonts == {}  # no system fallback: the author's face drew it
    pixel = DEMO / "playable_assets" / "lucifer" / "ui" / "font.ttf"  # Latin only
    backend = PygameBattleUiBackend(pygame.Surface((200, 60)), scale=2.0, font_name=str(pixel))
    backend.draw_text(BattleUiText("攻擊", 4, 4, "action_entry"), color=(255, 0, 0), size=10)
    assert len(backend._cjk_fonts) == 1
