"""Quest boards, recruiting offices and gacha banners (U5).

Three kinds of project data, each opened by an event command onto its own screen: a board of
quest cards (taken, handed in, timed, repeated), an office of characters for hire (a price, a
rolled level, a party limit, sent away for part of the price) and a gacha banner (weights,
rate-up, hard and soft pity, a multi-pull guarantee, duplicates, history kept in the save).
The demo's Bounty Board, Guild Office and Starfall Chest stand in Hearthfold.
"""

import random
import sys
from pathlib import Path

import pytest

from asteria.rpg.boards import QuestBoardDefinition, RecruitCandidate, RecruitOfficeDefinition
from asteria.rpg.gacha import GachaBanner, GachaPrize, GachaRarity, GachaRuntime, GachaState
from asteria.rpg.quests import QuestDefinition, QuestObjective

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


def _banner(**values):
    return GachaBanner(
        "test",
        rarities=(GachaRarity("n"), GachaRarity("r", color=(0, 0, 255)), GachaRarity("ssr")),
        prizes=(
            GachaPrize("a", weight=90, rarity="n"),
            GachaPrize("b", weight=8, rarity="r"),
            GachaPrize("c", weight=1, rarity="ssr", featured=True),
            GachaPrize("d", weight=1, rarity="ssr"),
        ),
        **values,
    )


def test_the_records_go_to_data_and_back():
    board = QuestBoardDefinition("b", quest_ids=("q1", "q2"), max_active=2, card_style="row")
    assert QuestBoardDefinition.from_data(board.to_data()) == board
    office = RecruitOfficeDefinition(
        "o",
        candidates=(
            RecruitCandidate("hero", "gold", 100, level_min=2, level_max=4, portrait="p.png"),
        ),  # fmt: skip
        party_limit=4,
        dismiss_refund=0.5,
    )
    assert RecruitOfficeDefinition.from_data(office.to_data()) == office
    banner = _banner(hard_pity=20, multi_guarantee="r", featured_multiplier=2)
    assert GachaBanner.from_data(banner.to_data()) == banner
    quest = QuestDefinition(
        "q", objectives=(QuestObjective("g", "counter"),), card_image="c.png", rank="S",
        category="Hunt", repeatable=True, time_limit=5,
    )  # fmt: skip
    assert QuestDefinition.from_data(quest.to_data()) == quest
    plain = QuestDefinition("p").to_data()
    assert "rank" not in plain and "time_limit" not in plain  # written only when set
    with pytest.raises(ValueError):
        GachaBanner("x", rarities=(GachaRarity("n"),), prizes=(GachaPrize("a", rarity="zz"),))
    with pytest.raises(ValueError):
        RecruitOfficeDefinition("o", dismiss_refund=2)
    with pytest.raises(ValueError):
        QuestBoardDefinition("b", card_style="pile")


def test_the_rates_add_up_and_rate_up_counts_twice():
    banner = _banner(featured_multiplier=2)
    rates = {r.rarity_id: c for r, c, _p in banner.rates()}
    assert sum(rates.values()) == pytest.approx(1.0)
    assert rates["ssr"] == pytest.approx(3 / 101)  # c weighs 2, d 1
    ssr = dict((p.prize_id, c) for p, c in banner.rates()[2][2])
    assert ssr["c"] == pytest.approx(2 * ssr["d"])


def test_10000_pulls_keep_the_pity_and_every_multi_pull_has_its_guarantee():
    banner = _banner(hard_pity=30, soft_pity_start=20, soft_pity_step=0.05, multi_guarantee="r")
    runtime = GachaRuntime(banner)
    rng, state, longest, dry = random.Random(7), GachaState(), 0, 0
    for _ in range(1000):
        pulls = runtime.pull(rng, state, 10)
        assert any(banner.rank(p.rarity) >= banner.rank("r") for p in pulls)
        for pull in pulls:
            dry = 0 if pull.rarity == "ssr" else dry + 1
            longest = max(longest, dry)
    assert longest < 30  # the 30th pull is always the top rarity
    assert state.total == 10000 and len(state.history) == GachaState.HISTORY
    spread = runtime.simulate(10000, seed=1)
    assert spread["pulls"] == 10000 and sum(spread["rarity"].values()) == 10000
    assert spread["rarity"]["ssr"] / 10000 > 0.02  # the base 2%, raised by soft and hard pity
    assert spread["pity"] > 0 and spread["guaranteed"] > 0
    assert runtime.simulate(500, seed=3) == runtime.simulate(500, seed=3)  # a seed draws alike


@pytest.fixture
def host(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    runtime._ui_mode = "field"
    yield runtime
    runtime.close()


def _key(host, key, frames=1):
    pg = host.pg
    for kind in (pg.KEYDOWN, pg.KEYUP):
        pg.event.post(pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0))
        host._frame(pg.event.get(), 1 / 60)
    for _ in range(frames):
        host._frame([], 1 / 60)


def _world(game, name, **args):
    from asteria.events import WorldCommand

    return game.world_commands.dispatch(WorldCommand(name, args))


def test_the_bounty_board_takes_hands_in_times_out_and_repeats(host):
    from asteria.runtime.boards_play import QuestBoard

    game = host.game
    _world(game, "OPEN_QUEST_BOARD", board_id="hearthfold_board")
    host._frame([], 1 / 60)
    assert host._ui_mode == "service"
    screen = host._service_screen
    states = {q.quest_id: s for q, s in screen.cards()}
    assert states == {
        "bounty_slingers": "available",
        "bounty_herbs": "available",
        "bounty_hunters": "available",
        "bounty_warlord": "locked",  # after the catacombs
    }
    _key(host, host.pg.K_RETURN)  # take the first card
    assert game.quest_log.status("bounty_slingers") == "active"
    assert screen.message.startswith("Accepted")
    game.quest_log.record_defeat("goblin_slinger", 3)
    screen.refresh()
    assert dict((q.quest_id, s) for q, s in screen.cards())["bounty_slingers"] == "ready"
    stars = game.save.rpg_state.currencies.get("star_stones", 0)
    _key(host, host.pg.K_RETURN)  # hand it in
    assert game.save.rpg_state.currencies["star_stones"] == stars + 30
    assert dict((q.quest_id, s) for q, s in screen.cards())["bounty_slingers"] == "waiting"
    game.world.add_counter("play.seconds", 5 * 60 + 1)  # the board's five minutes
    screen.refresh()
    assert dict((q.quest_id, s) for q, s in screen.cards())["bounty_slingers"] == "available"
    board = QuestBoard(game, "hearthfold_board")
    board.accept("bounty_herbs")  # ten minutes to bring the herbs
    assert board.time_left(game.project.rpg_database.quests["bounty_herbs"]) == 600
    game.world.add_counter("play.seconds", 601)
    assert board.expire() == ["bounty_herbs"]
    assert game.quest_log.status("bounty_herbs") == "failed"
    board.accept("bounty_hunters")
    board.accept("bounty_slingers")
    assert board.state(game.project.rpg_database.quests["bounty_herbs"]) == "available"
    board.accept("bounty_herbs")  # a repeatable quest that failed can be taken again
    assert board.active_count() == 3
    screen.flipped = True
    screen.index = 1
    texts = [w for w, _c, _s in screen.detail_lines()]
    assert any("Time left" in t for t in texts) and any("Healing Herb" in t for t in texts)
    record = game.world.to_data()["systems"]["quest_board.hearthfold_board"]
    assert set(record["taken"]) == {"bounty_hunters", "bounty_slingers", "bounty_herbs"}
    host.capture()


def test_the_guild_office_hires_at_a_rolled_level_and_sends_away(host):
    game = host.game
    _world(game, "OPEN_RECRUIT", office_id="hearthfold_guild")
    host._frame([], 1 / 60)
    screen = host._service_screen
    rows = {c.actor_id: s for c, _a, s in screen.rows()}
    assert rows == {"hero_02": "available", "hero_03": "available", "hero_04": "available"}
    screen.index = 1  # Vesper, Lv 3-5 for 1500 gold
    gold = game.save.rpg_state.currencies["gold"]
    _key(host, host.pg.K_RETURN)
    assert screen.asking and "hero_03" not in game.save.rpg_state.party_actor_ids
    level = screen.confirm(random.Random(0))
    assert "hero_03" in game.save.rpg_state.party_actor_ids
    assert 3 <= level <= 5 and game.ensure_actor_progression("hero_03").level == level
    assert game.save.rpg_state.currencies["gold"] == gold - 1500
    assert {c.actor_id: s for c, _a, s in screen.rows()}["hero_03"] == "hired"
    game.save.rpg_state.currencies["star_stones"] = 0
    assert {c.actor_id: s for c, _a, s in screen.rows()}["hero_04"] == "poor"
    refund = screen.dismiss()
    assert refund == 750 and "hero_03" not in game.save.rpg_state.party_actor_ids
    game.save.rpg_state.currencies["star_stones"] = 1000
    for actor_id in ("hero_02", "hero_03", "hero_04"):
        screen.office.hire(actor_id)
    assert len(game.save.rpg_state.party_actor_ids) == 4  # the office's party limit
    screen.draw()
    assert screen.portrait(screen.office.office.candidate("hero_02")).endswith("hero_02.png")


def test_the_starfall_chest_pays_pulls_gives_and_turns_duplicates(host):
    from asteria.runtime.boards_play import Gacha

    game = host.game
    _world(game, "OPEN_GACHA", banner_id="starfall")
    host._frame([], 1 / 60)
    screen = host._service_screen
    assert game.save.rpg_state.currencies["star_stones"] == 300  # the demo's start
    screen.action = 1  # pull x10 for 270
    results = screen.confirm(random.Random(5))
    assert len(results) == 10 and screen.page == "show"
    assert game.save.rpg_state.currencies["star_stones"] == 30
    assert any(p.rarity in ("rare", "mythical") for p, _d in results)
    state = Gacha(game, "starfall").state()
    assert state.total == 10 and len(state.history) == 10
    for _ in range(40):  # appear, shake, open (a frame's time is capped)
        host._frame([], 0.1)
    assert screen.page == "results"
    host.capture()
    _key(host, host.pg.K_RETURN)
    assert screen.page == "banner"
    game.save.rpg_state.currencies["star_stones"] = 0
    screen.action = 0
    assert screen.confirm() is None and "Not enough" in screen.message
    gacha = Gacha(game, "starfall")
    cael = next(p for p in gacha.banner.prizes if p.kind == "actor")
    game.join_party("hero_04")
    elixirs = game.save.rpg_state.inventory.count("elixir")
    assert gacha._give(cael) is True  # Cael is owned: an Elixir instead
    assert game.save.rpg_state.inventory.count("elixir") == elixirs + 1
    saved = type(game.world).from_data(game.world.to_data())
    assert saved.systems["gacha.starfall"]["total"] == 10  # the pulls are kept in the save


def test_the_rates_page_is_always_there_and_shows_every_rarity(host):
    from asteria.runtime.service_screens import GachaScreen

    screen = GachaScreen(host, "starfall")
    host._service_screen, host._ui_mode = screen, "service"
    host._menu_boxes = {}  # the editor's preview reads where each part was drawn
    host._frame([], 1 / 60)
    assert {"rates", "banner", "buttons", "pity"} <= set(host._menu_boxes["gacha"])
    _key(host, host.pg.K_r)
    assert screen.page == "rates"
    _key(host, host.pg.K_ESCAPE)
    _key(host, host.pg.K_h)
    assert screen.page == "history"


def test_the_editor_edits_the_three_kinds_and_simulates_a_banner(monkeypatch):
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    from asteria.editor import EditorDocument
    from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
    from asteria.editor.menu_layout_authoring import MenuLayoutAuthoringController
    from asteria.editor.storage import load_document
    from asteria.runtime.menu_preview import MenuPreview

    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    systems = GameSystemsAuthoringController(document)
    assert systems.ids("quest_boards") == ("hearthfold_board",)
    assert systems.ids("recruit_offices") == ("hearthfold_guild",)
    data = systems.form_data("gacha_banners", "starfall")
    assert data["rarities"][2]["color"] == "255, 205, 90"  # the colour as words
    data["hard_pity"] = 40
    data["rarities"][2]["color"] = "250, 200, 80"
    systems.edit("gacha_banners", "starfall", systems.decode("gacha_banners", data))
    banner = document.project.rpg_database.gacha_banners["starfall"]
    assert banner.hard_pity == 40 and banner.rarities[2].color == (250, 200, 80)
    spread = systems.simulate_gacha("starfall")
    assert spread["pulls"] == 10000 and spread["longest_dry"] < 40
    document.undo()
    assert document.project.rpg_database.gacha_banners["starfall"].hard_pity == 50
    quest = systems.form_data("quests", "bounty_herbs")
    assert quest["time_limit"] == 10 and quest["repeatable"] and quest["rank"] == "D"
    layouts = MenuLayoutAuthoringController(document)
    ids = [s for s, _t, _c in layouts.screens()]
    for variant in ("quest_board.hearthfold_board", "recruit.hearthfold_guild", "gacha.starfall"):
        assert variant in ids
    preview = MenuPreview(document.project, DEMO)
    try:
        for screen_id in ("quest_board", "recruit", "gacha"):
            _surface, boxes = preview.render(screen_id)
            assert {"title", "frame"} <= set(boxes), screen_id
    finally:
        preview.close()
