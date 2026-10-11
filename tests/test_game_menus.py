"""CB11 / UI-02: shop, quest log, pause, save/load and game-over screens."""

import pytest

pygame = pytest.importorskip("pygame")

from test_session_events import _session  # noqa: E402

from asteria.rpg import QuestDefinition, QuestObjective, ShopDefinition, ShopEntry  # noqa: E402
from asteria.runtime.game_menus import MenuCursor, ShopScreen, quest_rows  # noqa: E402


def _add_content(project):
    db = project.rpg_database
    db.add_shop(
        ShopDefinition(
            "apothecary",
            "Apothecary",
            [
                ShopEntry("ether_leaf", buy_prices={"gold": 30}, sell_prices={"gold": 12}, stock=1),
                ShopEntry("boss_emblem", sell_prices={"gold": 500}),
            ],
        )
    )
    db.add_quest(
        QuestDefinition(
            "gather",
            "Gather Leaves",
            objectives=[
                QuestObjective("leaves", "item", target="ether_leaf", required=999, description="Collect ether leaves"),
            ],
        )
    )


def test_shop_screen_model_tabs_stock_and_messages():
    project, game = _session()
    _add_content(project)
    game.open_shop("apothecary")
    screen = ShopScreen(game)
    assert [r.item_id for r in screen.rows()] == ["ether_leaf"]  # buy tab hides sell-only entries
    assert screen.rows()[0].stock == "1" and screen.rows()[0].available
    assert screen.confirm() is not None and screen.message.startswith("Bought")
    assert not screen.rows()[0].available and screen.confirm() is None  # sold out
    assert "only 0" in screen.message
    screen.switch_tab()
    assert {r.item_id for r in screen.rows()} == {"ether_leaf", "boss_emblem"}
    assert "gold" in screen.wallet()
    screen.close()
    assert game.open_shop_id is None


def test_quest_rows_and_menu_cursor():
    project, game = _session()
    _add_content(project)
    game.start_quest("gather")
    owned = game.save.rpg_state.inventory.count("ether_leaf")
    (row,) = quest_rows(game)
    assert row.status == "active" and row.objectives[0][:3] == ("Collect ether leaves", owned, 999)
    cursor = MenuCursor((("a", "A"), ("b", "B")))
    assert cursor.move(-1) == "b" and cursor.move(1) == "a"


def _press(rt, key):
    rt._frame([pygame.event.Event(pygame.KEYDOWN, key=key)], 0.016)
    rt._frame([pygame.event.Event(pygame.KEYUP, key=key)], 0.016)


def _choose(rt, key):
    """Move the pause menu cursor to entry ``key`` with Down presses, then confirm."""
    for _ in range(len(rt._pause_menu.options)):
        if rt._pause_menu.selected == key:
            break
        _press(rt, pygame.K_DOWN)
    assert rt._pause_menu.selected == key
    _press(rt, pygame.K_RETURN)


def test_runtime_pause_quests_save_and_title(runtime, resource_root):
    runtime._ui_mode = "field"
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "pause" and runtime.running
    _choose(runtime, "quests")
    assert runtime._ui_mode == "quests"
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "pause"
    _choose(runtime, "save")
    assert runtime._ui_mode == "slots"
    _press(runtime, pygame.K_RETURN)  # slot 1
    assert (resource_root / "saves" / "slot1.asteria-save.json").is_file()
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "pause"
    _choose(runtime, "title")
    assert runtime._ui_mode == "title"


def test_runtime_opens_shop_from_an_event_and_buys(runtime):
    project = runtime.project
    _add_content(project)
    game = runtime.game
    game.open_shop("apothecary")
    runtime._ui_mode = "field"
    runtime._frame([], 0.016)
    assert runtime._ui_mode == "shop"
    gold = game.save.rpg_state.currencies.get("gold", 0.0)
    game.save.rpg_state.currencies["gold"] = gold + 100
    _press(runtime, pygame.K_RETURN)
    assert game.save.rpg_state.currencies["gold"] == gold + 70
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "field" and game.open_shop_id is None


def test_runtime_defeat_shows_game_over_and_returns_to_title(runtime):
    game = runtime.game
    game.start_encounter("boss_room")
    runtime._ui_mode = "field"
    for member_id in tuple(game.active_hero_ids()):
        member = game.battle.member(member_id)
        member.subject.resources.set_current(game.rules.knockout_resource_id, 0)
    runtime._defeat = True
    runtime._frame([], 0.016)
    assert runtime._ui_mode == "game_over"
    _press(runtime, pygame.K_DOWN)
    _press(runtime, pygame.K_RETURN)
    assert runtime._ui_mode == "title" and runtime.game.mode == "field" and not runtime._defeat
