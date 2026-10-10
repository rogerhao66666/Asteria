"""CB11: shops (RPG-05) and quests (WLD-01) in data, save state and the game session."""

import json

import pytest

from asteria.events import EventInstruction
from asteria.rpg import (
    QuestDefinition,
    QuestLog,
    QuestObjective,
    QuestProgress,
    RpgDatabase,
    RpgRuntimeState,
    ShopDefinition,
    ShopEntry,
    ShopError,
)
from asteria.rpg.enemies import LootEntry, RewardDefinition
from asteria.rpg.items import Inventory
from asteria.runtime.game_save import GameRuntimeSave
from test_session_events import BOSS_PROGRAM, _interact, _replace_program, _session


def _shop():
    return ShopDefinition("apothecary", "Apothecary", [
        ShopEntry("ether_leaf", buy_prices={"gold": 30}, sell_prices={"gold": 12}, stock=3),
        ShopEntry("fire_dust", buy_prices={"gold": 10, "renown": 1}),
        ShopEntry("boss_emblem", sell_prices={"gold": 500}),
    ])


def _quests():
    return [
        QuestDefinition("hunt", "Hunt the Tyrant", objectives=[
            QuestObjective("tyrant", "defeat_enemy", target="astral_tyrant"),
            QuestObjective("wisps", "defeat_enemy", target="mender_wisp", required=2),
        ], reward=RewardDefinition(currencies={"renown": 5}), next_quest_ids=["report"]),
        QuestDefinition("report", "Report Back", objectives=[QuestObjective("talk")],
                        prerequisites=["hunt"], reward=RewardDefinition(loot=[LootEntry("focus_stone", minimum=2, maximum=2)])),
        QuestDefinition("gather", "Gather Leaves", objectives=[
            QuestObjective("leaves", "item", target="ether_leaf", required=2),
            QuestObjective("asked", "switch", target="herbalist_asked"),
        ], auto_complete=False),
    ]


def _with_content(project):
    project.rpg_database.add_shop(_shop())
    for quest in _quests():
        project.rpg_database.add_quest(quest)
    return project


def test_shop_buys_sells_and_tracks_limited_stock():
    project, game = _session()
    _with_content(project)
    state = game.save.rpg_state
    gold, leaves = state.currencies["gold"], state.inventory.count("ether_leaf")
    game.open_shop("apothecary")
    game.buy("ether_leaf", 2)
    assert state.currencies["gold"] == gold - 60 and state.inventory.count("ether_leaf") == leaves + 2
    assert game.shops.remaining("apothecary", "ether_leaf") == 1
    with pytest.raises(ShopError):
        game.buy("ether_leaf", 2)                       # only 1 left
    game.sell("ether_leaf", 1)
    assert game.shops.remaining("apothecary", "ether_leaf") == 2
    assert state.currencies["gold"] == gold - 60 + 12
    game.buy("fire_dust", 4)                            # multi-currency price
    assert state.currencies["renown"] == 0
    with pytest.raises(ShopError):
        game.buy("fire_dust")                           # renown exhausted
    with pytest.raises(ShopError):
        game.buy("boss_emblem")                         # buy-back only
    assert game.shops.remaining("apothecary", "fire_dust") is None


def test_quest_prerequisites_counters_items_and_switch_objectives():
    progress = {}
    inventory = Inventory()
    switches = set()
    rewards = []
    log = QuestLog({q.quest_id: q for q in _quests()}, progress, inventory=inventory,
                   switches=switches.__contains__, grant_reward=rewards.append)
    assert not log.can_start("report")                  # needs "hunt" completed
    log.start("gather")
    inventory.add("ether_leaf", 2)
    log.refresh()
    assert not log.is_ready("gather")                   # switch still off
    switches.add("herbalist_asked")
    assert log.is_ready("gather") and log.status("gather") == "active"  # not auto-complete
    log.complete("gather")
    assert log.status("gather") == "completed" and len(rewards) == 1
    log.start("hunt")
    log.record_defeat("mender_wisp", 5)
    assert progress["hunt"].counts["wisps"] == 2         # clamped to required
    log.record_defeat("astral_tyrant")
    assert log.status("hunt") == "completed" and log.status("report") == "active"  # chained
    assert log.advance("report", "talk") == 1 and log.status("report") == "completed"
    with pytest.raises(ValueError):
        log.start("hunt")


def test_victory_advances_defeat_objectives_and_events_drive_quests():
    project, game = _session()
    _with_content(project)
    _replace_program(project, BOSS_PROGRAM, [
        EventInstruction("WORLD", {"command": "START_QUEST", "args": {"quest_id": "hunt"}}),
        EventInstruction("WORLD", {"command": "START_ENCOUNTER", "args": {"encounter_id": "boss_room"}}),
        EventInstruction("END"),
    ])
    _interact(game)
    assert game.save.event_context.get_switch("quest.hunt.active")
    assert game.mode == "battle"
    for enemy_id in tuple(game.active_enemy_ids()):
        while enemy_id in game.active_enemy_ids():
            for hero_id in tuple(game.active_hero_ids()):
                if enemy_id in game.active_enemy_ids():
                    game.execute(hero_id, "strike", (enemy_id,))
    renown = game.save.rpg_state.currencies["renown"]
    focus = game.save.rpg_state.inventory.count("focus_stone")
    game.finish_victory()
    state = game.save.rpg_state
    assert state.quests["hunt"].status == "completed" and state.currencies["renown"] >= renown + 5
    assert game.save.event_context.get_switch("quest.hunt.completed")
    assert game.save.event_context.get_switch("quest.report.active")
    game.advance_quest("report", "talk")
    assert state.inventory.count("focus_stone") == focus + 2


def test_database_and_save_round_trip_shops_and_quests(tmp_path):
    project, game = _session()
    _with_content(project)
    db = project.rpg_database
    data = json.loads(json.dumps(db.to_data()))
    assert data["version"] == 25
    loaded = RpgDatabase.from_data(data)
    assert loaded.shops == db.shops and loaded.quests == db.quests
    game.open_shop("apothecary")
    game.buy("ether_leaf")
    game.start_quest("gather")
    path = tmp_path / "save.json"
    game.sync_world_state().save_json(path)
    restored = GameRuntimeSave.load_json(path, project)
    assert restored.rpg_state.shop_stock == {"apothecary": {"ether_leaf": 2}}
    assert restored.rpg_state.quests == {"gather": QuestProgress("active", {})}
    bad = dict(data, quests=[dict(data["quests"][0], prerequisites=["nope"])])
    with pytest.raises(ValueError):
        RpgDatabase.from_data(bad).validate()
    with pytest.raises(ValueError):
        RpgRuntimeState(shop_stock={"apothecary": {"ether_leaf": -1}})
