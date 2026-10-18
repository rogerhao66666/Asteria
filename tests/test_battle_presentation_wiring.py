"""Battle presentation records the battle really uses (Boss Trial phase 5): Command Input Steps,
Command Menu Pages, Side-View / Portrait staging, ability slots and a field strike that opens a
fight preemptive."""

import sys
from collections import Counter
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "boss_trial_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.presentation.battle import BattleCombatantVisual, BattleVisualAnchor  # noqa: E402
from asteria.presentation.battle_sideview_template import (  # noqa: E402
    BattleSideviewTemplateProfile,
    BattleSideviewTemplateRuntime,
    BattleSideviewZone,
)
from asteria.runtime.battle_commands import BattleCommands  # noqa: E402
from asteria.runtime.game_session import GameSessionError  # noqa: E402

VESPER = "hero_03"


def _game(encounter="woods_patrol", *, vesper=False):
    _project, game = smoke.load()
    smoke.prepare(game, Counter(), tier=1)
    if vesper:
        game.join_party(VESPER)
    game.start_encounter(encounter)
    return game


def test_input_steps_add_their_options_tags_power_and_costs():
    game = _game(vesper=True)
    foe = game.active_enemy_ids()[0]
    pool = game.battle.member(VESPER).subject.resources
    before = pool.current("technique")
    game.use_ability(
        VESPER, "elemental_weave", (foe,), choices={"element": ["storm"], "focus": ["overcharge"]}
    )
    assert before - pool.current("technique") == 8 + 12  # the skill, then Overcharge
    for bad in (
        {"element": ["shadow"]},  # no such option
        {"element": ["fire", "frost"]},  # one element only
    ):
        with pytest.raises(GameSessionError):
            game.use_ability(VESPER, "elemental_weave", (foe,), choices=bad)
    with pytest.raises(GameSessionError):  # a skill without steps takes no choices
        game.use_ability(VESPER, "soul_burst", None, choices={"element": ["fire"]})


def test_the_command_menu_walks_the_input_steps_then_acts():
    game = _game(vesper=True)
    library = game.project.battle_presentation_library
    pages = library.require("interaction", "trial_commands")
    commands = BattleCommands(game, style="root", pages=pages)

    def choose(action_id):
        ids = [r.action_id for r in commands.entries(VESPER)]
        commands.cursor = ids.index(action_id)
        return commands.press("confirm", VESPER)

    choose("root:Skills")
    choose("elemental_weave")
    assert commands.mode == "steps"
    assert [r.action_id for r in commands.entries(VESPER)] == ["fire", "frost", "storm"]
    choose("frost")
    assert [r.action_id for r in commands.entries(VESPER)][-1] == "step:done"
    choose("echo")
    assert commands.entries(VESPER)[1].label.startswith("* ")  # picked
    commands.press("cancel", VESPER)  # the focus picks are dropped...
    commands.press("cancel", VESPER)  # ...then back to the element
    assert [r.action_id for r in commands.entries(VESPER)] == ["fire", "frost", "storm"]
    choose("fire")
    acted = choose("step:done")
    if not acted:
        acted = choose(commands.entries(VESPER)[0].action_id)  # the target
    assert acted


def test_command_pages_order_rename_and_page_the_top_commands():
    import dataclasses

    game = _game()
    library = game.project.battle_presentation_library
    pages = library.require("interaction", "trial_commands")
    assert pages.max_primary_layers == 6 and pages.page_size == 6
    pages = dataclasses.replace(pages, max_primary_layers=3)  # this early hero has fewer
    commands = BattleCommands(game, style="root", pages=pages)
    rows = commands.entries(smoke.HERO)
    labels = [r.label for r in rows]
    assert labels[0] == "Fight" and labels[-1] == "More" and len(rows) == 3
    commands.cursor = len(rows) - 1
    commands.press("confirm", smoke.HERO)
    more = {r.action_id: r.label for r in commands.entries(smoke.HERO)}
    assert more["root:Items"] == "Bag" and more["root:Escape"] == "Run" and "root:Back" in more
    plain = BattleCommands(game, style="root")  # without pages: every command, own names
    assert "root:More" not in {r.action_id for r in plain.entries(smoke.HERO)}


def test_staging_zones_stagger_and_hidden_bodies_round_trip():
    profile = BattleSideviewTemplateProfile(
        "ranks",
        BattleSideviewZone("l", 100.0, 200.0, -40.0, "right", x_step=-30.0),
        BattleSideviewZone("r", 300.0, 120.0, 34.0, "left", x_step=20.0),
    )
    result = BattleSideviewTemplateRuntime(profile).resolve(
        left_member_ids=("a", "b"), right_member_ids=("c", "d")
    )
    spots = {p.member_id: (p.x, p.y) for p in result.placements}
    assert spots == {"a": (100, 200), "b": (70, 160), "c": (300, 120), "d": (320, 154)}
    anchor = BattleVisualAnchor(1, 2)
    visual = BattleCombatantVisual("m", "sheet", "sheet", anchor, body_hidden=True)
    assert BattleCombatantVisual.from_data(visual.to_data()).body_hidden


def test_the_trial_fights_name_their_staging_and_slots_hold_the_arts():
    game = _game()
    tags = game.project.rpg_database.encounters["crypt_guard"].tags
    assert "stage:crypt_ranks" in tags
    assert "stage:vigil_portrait" in game.project.rpg_database.encounters["acolyte_vigil"].tags
    _project, game = smoke.load()
    for art in ("art_rending_gale", "art_whirlwind", "art_dawn_edge"):
        game.learn_ability(smoke.HERO, art)
    equipped, capacity = game.ability_slots(smoke.HERO)
    assert capacity == 2
    game.equip_ability(smoke.HERO, "art_rending_gale")
    game.equip_ability(smoke.HERO, "art_whirlwind")
    with pytest.raises(GameSessionError):
        game.equip_ability(smoke.HERO, "art_dawn_edge")
    usable = game.resolve_actor_build(smoke.HERO).abilities
    assert "art_whirlwind" in usable and "art_dawn_edge" not in usable


def test_a_field_strike_opens_the_fight_preemptive():
    from asteria.core import Transform

    _project, game = smoke.load()
    woods = next(s for s in game.project.scenes() if s.name == "Whispering Woods")
    game.transfer_player(woods.id)
    foe = next(e for e in game.scene.entities() if e.name == "Goblin Slinger 3")
    spot = foe.get(Transform)
    player = game.player.get(Transform)
    player.x, player.y = spot.x - 16, spot.y
    game.set_player_facing("right")
    game.action_combat.use(game.player, "field_slash")
    for _ in range(20):
        game.field_update(0.03)
        if game.mode == "battle":
            break
    assert game.mode == "battle" and game.opening == "preemptive"
    assert game.struck_encounters == 1
