"""The creature party (PetRules): data, the party and storage, the bench and switching, species
foes, capture by rate, moves with uses, experience from foes and level-up moves. Built on the
Full Verification demo with rules injected at runtime, so the demo itself is unchanged."""

import random
import sys
from pathlib import Path

import pytest

from asteria.gameplay.abilities import AbilityDefinition
from asteria.rpg.capture import CaptureRule
from asteria.rpg.enemies import EncounterDefinition, EncounterMember
from asteria.rpg.pets import (
    PetExpCurve,
    PetMove,
    PetRecord,
    PetRules,
    PetSpeciesDefinition,
    PetStatFormula,
)
from asteria.rpg.save_state import RpgRuntimeState

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

HP = "vitality"
FORMULA = PetStatFormula(gene_terms={"iv": 1.0}, multiplier_gene="nature")
HP_FORMULA = PetStatFormula(gene_terms={"iv": 1.0}, level_term=1.0, flat=10.0)


# -- data -----------------------------------------------------------------------------------
def test_stat_formula_matches_the_well_known_creature_formula():
    genes = {"iv.attack": 31, "ev.attack": 252, "nature.attack": 1.1, "iv.hp": 31, "ev.hp": 252}
    attack = PetStatFormula(gene_terms={"iv": 1, "ev": 0.25}, multiplier_gene="nature")
    hp = PetStatFormula(gene_terms={"iv": 1, "ev": 0.25}, level_term=1, flat=10)
    assert attack.value(49, 50, "attack", genes) == 111
    assert hp.value(45, 50, "hp", genes) == 152
    assert attack.value(49, 50, "attack", {}) == 54  # no genes: the base alone


def test_exp_curves_give_the_experience_between_levels():
    cubic = PetExpCurve(cubic=(1, 0, 0, 0))
    assert cubic.total_at(10) == 1000 and cubic.to_next(9) == 271
    table = PetExpCurve(table=(0, 10, 30, 60))
    assert table.total_at(4) == 60 and table.total_at(6) == 120 and table.to_next(1) == 10
    with pytest.raises(ValueError):
        PetExpCurve()
    with pytest.raises(ValueError):
        PetExpCurve(cubic=(1, 2))


def test_species_stats_follow_the_rules_formulas_and_old_data_is_unchanged():
    species = PetSpeciesDefinition(
        "cub", "Cub", stats={"power": 10, HP: 45}, growth={"power": 2}, resources={HP: 1}
    )
    assert species.stats_at(5) == {"power": 18.0, HP: 45.0}
    formulas = {"*": FORMULA, HP: HP_FORMULA}
    genes = {"iv.power": 31, "nature.power": 1.1}
    assert species.stats_at(5, genes, formulas)["power"] == int((int(51 * 5 / 100) + 5) * 1.1)
    assert species.resources_at(5, genes, formulas)[HP] == int(90 * 5 / 100) + 5 + 10
    assert "exp_curve" not in species.to_data()
    full = PetSpeciesDefinition.from_data(
        {
            **species.to_data(),
            "exp_curve": {"cubic": [1, 0, 0, 0]},
            "exp_yield": 64,
            "capture_rate": 45,
            "visual_profile_id": "cub_front",
            "back_visual_profile_id": "cub_back",
        }
    )
    assert full.exp_to_next(1) == 7 and full.exp_yield == 64 and full.capture_rate == 45
    assert PetSpeciesDefinition.from_data(full.to_data()).to_data() == full.to_data()


def test_pet_records_keep_their_battle_state_and_moves():
    pet = PetRecord("p1", "cub", level=3)
    assert pet.to_data() == {
        "instance_id": "p1",
        "species_id": "cub",
        "nickname": "",
        "level": 3,
        "experience": 0.0,
    }
    pet = PetRecord(
        "p1",
        "cub",
        resources={HP: 12},
        states=["poison"],
        moves=["bite", "growl"],
        pp={"bite": 2},
        held_item_id="berry",
        genes={"iv.power": 7},
    )
    assert PetRecord.from_data(pet.to_data()).to_data() == pet.to_data()
    species = PetSpeciesDefinition(
        "cub",
        "Cub",
        stats={"power": 10},
        growth={},
        battle_abilities=("bite",),
        learnset=(PetMove("growl", 2), PetMove("roar", 5)),
    )
    assert pet.known_moves(species) == ("bite", "growl")
    implicit = PetRecord("p2", "cub", level=5)
    assert implicit.known_moves(species) == ("bite", "growl", "roar")
    assert implicit.known_moves(species, max_moves=2) == ("growl", "roar")


def test_pet_rules_round_trip_roll_genes_and_reject_bad_values():
    rules = PetRules(
        "creature",
        party_size=6,
        battle_slots=1,
        storage=True,
        actors_fight=False,
        pets_decide_outcome=True,
        exp_share="split",
        exp_divisor=7,
        max_moves=4,
        stat_formulas={"*": FORMULA, HP: HP_FORMULA},
        gene_ranges={"iv": [0, 31]},
        gene_sets={"nature": [{"power": 1.1, "speed": 0.9}, {}]},
    )
    assert PetRules.from_data(rules.to_data()).to_data() == rules.to_data()
    assert PetRules("plain").to_data() == {
        "schema": "asteria.rpg.pet_rules",
        "version": 1,
        "rules_id": "plain",
    }
    genes = rules.roll_genes(["power", "speed"], random.Random(3))
    assert set(genes) >= {"iv.power", "iv.speed"} and all(
        0 <= genes[k] <= 31 for k in genes if k.startswith("iv")
    )
    with pytest.raises(ValueError):
        PetRules("bad", exp_share="half")
    with pytest.raises(ValueError):
        PetRules("bad", gene_ranges={"iv": [5, 1]})


def test_capture_rules_in_rate_mode_use_rate_item_and_state_bonuses():
    rule = CaptureRule(
        "*",
        mode="rate",
        item_id="ball",
        item_bonuses={"great_ball": 1.5},
        state_bonuses={"sleep": 2.0},
    )
    assert rule.capture_items() == {"ball": 1.0, "great_ball": 1.5}
    assert rule.chance(1.0, rate=255) == pytest.approx(1 / 3)
    assert rule.chance(0.0, rate=255, item_id="great_ball") == pytest.approx(1.0)
    assert rule.chance(1.0, rate=45, state_ids=("sleep",)) == pytest.approx(45 * 2 / (3 * 255))
    assert rule.chance(0.5) == 0.0  # no rate: nothing to catch with
    assert CaptureRule.from_data(rule.to_data()).to_data() == rule.to_data()
    linear = CaptureRule("goblin", "goblin_actor")
    assert "mode" not in linear.to_data() and linear.chance(0.0) == 0.75
    with pytest.raises(ValueError):
        CaptureRule("goblin")  # not a species rule: it needs somewhere to put the catch


def test_encounter_members_can_be_creatures_of_a_species():
    member = EncounterMember(pet_species_id="cub", level=5, level_max=8, reserve=True)
    assert member.kind_id == "cub" and member.to_data()["level_max"] == 8
    assert EncounterMember.from_data(member.to_data()).to_data() == member.to_data()
    assert EncounterMember("goblin").to_data() == {"enemy_id": "goblin", "count": 1, "weight": 1.0}
    with pytest.raises(ValueError):
        EncounterMember()
    encounter = EncounterDefinition("wild", members=[member])
    assert EncounterDefinition.from_data(encounter.to_data()).members[0].reserve


def test_abilities_and_saves_carry_the_new_optional_fields():
    bite = AbilityDefinition("bite", max_uses=15)
    assert bite.max_uses == 15 and bite.to_data()["max_uses"] == 15
    assert AbilityDefinition.from_data(bite.to_data()).max_uses == 15
    assert "max_uses" not in AbilityDefinition("plain").to_data()
    with pytest.raises(ValueError):
        AbilityDefinition("bad", max_uses=-1)
    state = RpgRuntimeState(
        pets=[PetRecord("a", "cub"), PetRecord("b", "cub")], party_pet_ids=("b", "zzz")
    )
    assert state.party_pet_ids == ("b",)
    from asteria.rpg import RpgDatabase

    db = RpgDatabase()
    db.add_pet_species(PetSpeciesDefinition("cub", "Cub", stats={"power": 1}, growth={}))
    again = RpgRuntimeState.from_data(state.to_data(), db)
    assert again.party_pet_ids == ("b",)
    assert "party_pet_ids" not in RpgRuntimeState().to_data()


# -- the session ----------------------------------------------------------------------------
def _creature_game(monkeypatch, **rules):
    """The Full Verification game with the creature party laid over it (trial_creatures)."""
    import run_trial_smoke as smoke
    import trial_creatures

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project, game = smoke.load()
    trial_creatures.install(project, **rules)
    return game


def _ko(game, member_id):
    game.battle.member(member_id).subject.resources.set_current(HP, 0.0)


def test_the_party_keeps_its_size_and_the_rest_goes_into_storage(monkeypatch):
    game = _creature_game(monkeypatch)
    first = game.add_pet("cub", level=5, nickname="Fang")
    game.add_pet("cub", level=5)
    third = game.add_pet("wolf", level=6)
    assert [p.instance_id for p in game.party_pets()] == ["cub#1", "cub#2"]
    assert [p.instance_id for p in game.stored_pets()] == ["wolf#1"]
    assert game.party_full() and set(first.genes) == {
        "iv." + s for s in game.pet_species(first).stats
    }
    assert first.moves == ["pet_shot", "pet_bandage"]  # max_moves: the moves are its own now
    with pytest.raises(Exception):
        game.move_pet_to_party(third.instance_id)
    game.move_pet_to_storage("cub#2")
    game.move_pet_to_party(third.instance_id)
    assert [p.instance_id for p in game.party_pets()] == ["cub#1", "wolf#1"]
    game.reorder_party_pets(["wolf#1", "cub#1"])
    assert game.party_pets()[0].instance_id == "wolf#1"
    data = game.save.rpg_state.to_data()
    assert data["party_pet_ids"] == ["wolf#1", "cub#1"]
    assert game.pet_stats_at(first)[HP] == int((90 + first.genes["iv." + HP]) * 5 / 100) + 15


def test_creatures_fight_from_the_bench_and_the_trainer_stays_out(monkeypatch):
    game = _creature_game(monkeypatch)
    game.add_pet("cub", level=5)
    game.add_pet("wolf", level=6)
    battle = game.start_encounter("wild_cubs")
    assert "hero_01" not in battle.members  # the characters watch
    assert game.stage_ids("heroes") == ("pet:cub#1",)
    assert game.bench_ids("heroes") == ("pet:wolf#1",)
    assert game.stage_ids("enemies") == ("cub:1",) and game.bench_ids("enemies") == ("wolf:2",)
    assert game.foe_record("wolf:2").level == 6 and game.foe_record("cub:1").genes
    assert battle.member("pet:cub#1").ability_ids == ("pet_shot", "pet_bandage")
    assert game.battle_profile_key("pet:cub#1") == "pet"
    assert game.battle_profile_key("cub:1") == "pet"
    assert game.foe_definition("cub").display_name == "Cub"
    from asteria.runtime.battle_commands import BattleCommands

    commands = BattleCommands(game)
    assert commands.display_name("cub:1") == "Cub" and commands.display_name("wolf:2") == "Wolf"
    assert [r.action_id for r in commands.switch_rows("pet:cub#1")] == ["switch:pet:wolf#1"]
    assert "Switch" in commands.categories_for("pet:cub#1")
    # the foe's bench fills its slot the moment the stage empties
    _ko(game, "cub:1")
    game.end_turn()
    assert game.stage_ids("enemies") == ("wolf:2",) and not game.bench_ids("enemies")
    # switching is an action: the stage creature goes to the bench, the other comes in
    assert game.switch_pet("pet:cub#1", "pet:wolf#1") is True
    assert game.stage_ids("heroes") == ("pet:wolf#1",)
    assert game.bench_ids("heroes") == ("pet:cub#1",)
    assert not battle.is_active(battle.member("pet:cub#1"))  # not targetable, no turns
    assert battle.resolve_outcome().finished is False
    # a fallen creature: the host must send the next one in before anyone else acts
    _ko(game, "pet:wolf#1")
    assert game.switch_needed("heroes") and game.active_hero_ids() == ()
    hero, _log = game.run_enemy_turns()
    assert hero is None and game.battle is not None  # not lost: the bench can still fight
    game.send_in_pet("pet:cub#1")
    assert game.stage_ids("heroes") == ("pet:cub#1",) and not game.switch_needed("heroes")
    # with every creature down the side is beaten (pets decide the outcome)
    _ko(game, "pet:cub#1")
    assert battle.resolve_outcome().defeated_sides == ("heroes",)


def test_moves_spend_their_uses_and_keep_them_between_battles(monkeypatch):
    game = _creature_game(monkeypatch, exp_share="none")  # no level up: health stays as left
    pet = game.add_pet("cub", level=5)
    game.start_encounter("wild_cubs")
    assert (
        game.pet_uses_left(pet, "pet_shot") == 3 and game.pet_uses_left(pet, "pet_bandage") is None
    )
    for _ in range(3):
        game.use_ability("pet:cub#1", "pet_shot", ("cub:1",))
    assert pet.pp == {"pet_shot": 0}
    assert game.ability_unavailable("pet:cub#1", "pet_shot") == "No uses left"
    with pytest.raises(Exception):
        game.use_ability("pet:cub#1", "pet_shot", ("cub:1",))
    game.battle.member("pet:cub#1").subject.resources.set_current(HP, 3.0)
    for foe in ("cub:1", "wolf:2"):
        _ko(game, foe)
    game.finish_victory()
    assert pet.resources[HP] == 3.0 and pet.pp["pet_shot"] == 0  # kept out of battle
    assert game.pet_standing(pet)
    game.heal_pets()
    assert pet.resources == {} and pet.pp == {}


def test_beaten_foes_give_experience_levels_and_new_moves(monkeypatch):
    game = _creature_game(monkeypatch)
    pet = game.add_pet("cub", level=5)
    other = game.add_pet("wolf", level=6)
    game.start_encounter("wild_cubs")
    for foe in ("cub:1", "wolf:2"):
        _ko(game, foe)
    game.end_turn()  # wolf:2 came in
    for foe in ("cub:1", "wolf:2"):
        _ko(game, foe)
    before = game.pet_resources_at(pet)[HP]
    game.finish_victory()
    # split: 50 x 5 + 50 x 6 = 550 to the one creature that fought; the benched one got nothing
    assert other.level == 6 and other.experience == 0
    assert pet.level == 8 and pet.experience == 550 - 8**3 + 5**3
    assert game.pet_resources_at(pet)[HP] > before
    assert game.pending_pet_moves() == (("cub#1", "pet_volley"),)  # two moves known already
    assert game.learn_pet_move("cub#1", "pet_volley", "pet_bandage") is True
    assert pet.moves == ["pet_shot", "pet_volley"] and game.pending_pet_moves() == ()


def test_species_foes_are_caught_as_they_stand_with_the_chosen_item(monkeypatch):
    game = _creature_game(monkeypatch)
    game.add_pet("cub", level=5)
    inventory = game.save.rpg_state.inventory
    inventory.add("pet_ball", 2)
    inventory.add("great_ball", 1)
    game.start_encounter("wild_cubs")
    assert game.capture_targets() == (("cub:1", pytest.approx(1 / 3), "pet_ball"),)
    items = dict(game.capture_items("cub:1"))
    assert items["pet_ball"] == pytest.approx(1 / 3) and items["great_ball"] == pytest.approx(0.5)
    game.battle.member("cub:1").subject.resources.set_current(HP, 1.0)
    assert game.capture_chance("cub:1", "great_ball") == pytest.approx(1.0, abs=0.01)
    assert game.attempt_capture("pet:cub#1", "cub:1", item_id="great_ball")
    assert inventory.count("great_ball") == 0 and inventory.count("pet_ball") == 2
    caught = game.pets()[-1]
    assert caught.species_id == "cub" and caught.level == 5 and caught.resources[HP] == 1.0
    assert caught.genes == game.foe_record("cub:1").genes and caught.moves == [
        "pet_shot",
        "pet_bandage",
    ]
    assert [p.instance_id for p in game.party_pets()] == ["cub#1", "cub#2"]
    game.end_turn()
    assert game.stage_ids("enemies") == ("wolf:2",)
    _ko(game, "wolf:2")
    applied = game.finish_victory()
    assert applied and game.world.bestiary["cub"]["captured"] >= 1


def test_trainer_battles_refuse_capture_and_the_old_linear_rules_still_work(monkeypatch):
    game = _creature_game(monkeypatch)
    db = game.project.rpg_database
    db.add_encounter(
        EncounterDefinition(
            "trainer",
            members=[EncounterMember(pet_species_id="cub", level=5)],
            tags=("no_capture", "no_escape"),
        )
    )
    game.add_pet("cub", level=5)
    game.start_encounter("trainer")
    assert game.capture_targets() == () and game.capture_rule_for("cub:1") is None
    with pytest.raises(Exception):
        game.attempt_capture("pet:cub#1", "cub:1")


def test_a_creature_with_no_move_uses_left_struggles_and_hurts_itself(monkeypatch):
    game = _creature_game(monkeypatch, exp_share="none")
    pet = game.add_pet("cub", level=5)
    game.start_encounter("wild_cubs")
    mine, foe = "pet:cub#1", "cub:1"
    assert game.out_of_uses_move(mine) == ""  # Bandage has no use limit: it can still act
    game.battle.set_member_abilities(mine, ("pet_shot",))
    pet.pp["pet_shot"] = 0
    assert game.out_of_uses_move(mine) == "struggle"
    pool = game.battle.member(mine).subject.resources
    top, before = pool.maximum(HP), pool.current(HP)
    foe_before = game.battle.member(foe).subject.resources.current(HP)
    game.use_out_of_uses_move(mine)
    assert game.battle.member(foe).subject.resources.current(HP) < foe_before
    assert pool.current(HP) == pytest.approx(max(0.0, before - top * 0.25))
    assert game.battle.granted_abilities == set()
    record = game.foe_record(foe)
    game.battle.set_member_abilities(foe, ("pet_shot",))
    record.pp["pet_shot"] = 0
    foe_pool = game.battle.member(foe).subject.resources
    foe_pool.set_current(HP, foe_pool.maximum(HP))  # it may have fallen to our Struggle
    foe_top, foe_now = foe_pool.maximum(HP), foe_pool.current(HP)
    game.enemy_act(foe)
    assert foe_pool.current(HP) == pytest.approx(max(0.0, foe_now - foe_top * 0.25))
    with pytest.raises(Exception):
        game.battle.set_member_abilities(mine, ("pet_bandage",))
        game.use_out_of_uses_move(mine)
    assert PetRules.from_data(game.pet_rules.to_data()).out_of_uses_ability == "struggle"


def test_the_creature_screen_picks_music_by_the_kind_of_battle(monkeypatch):
    from types import SimpleNamespace

    from asteria.runtime.creature_battle import CreatureBattleScreen

    tracks = {
        "wild": "w.ogg",
        "trainer": "t.ogg",
        "legendary": "l.ogg",
        "victory_wild": "vw.ogg",
        "victory_trainer": "vt.ogg",
        "gym": "g.ogg",
    }
    screen = CreatureBattleScreen.__new__(CreatureBattleScreen)
    screen.settings = {"music": tracks}
    for tags, trainer, start, win in (
        (set(), {}, "w.ogg", "vw.ogg"),
        ({"legendary"}, {}, "l.ogg", "vw.ogg"),
        (set(), {"name": "A"}, "t.ogg", "vt.ogg"),
        ({"music:gym"}, {"name": "B"}, "g.ogg", "vt.ogg"),
        (
            set(),
            {"name": "C", "music": "own.ogg", "victory_music": "own_win.ogg"},
            "own.ogg",
            "own_win.ogg",
        ),
    ):
        screen.tags, screen.trainer = tags, trainer
        assert screen.music("start") == start and screen.music("victory") == win
    screen.settings = {}
    screen.tags, screen.trainer = set(), {}
    assert screen.music("start") == "" and SimpleNamespace  # no tracks: the manifest's one


def test_a_creature_called_back_loses_its_battle_counters(monkeypatch):
    from asteria.rpg.battle_session_rules import BattleSessionRules

    game = _creature_game(monkeypatch)
    db = game.project.rpg_database
    old = db.battle_session_rules[sorted(db.battle_session_rules)[0]].to_data()
    old["battle_counters"] = {"stage_attack": [-6, 6, 0]}
    db.battle_session_rules.clear()
    db.add_battle_session_rules(BattleSessionRules.from_data(old))
    game.add_pet("cub", level=5)
    game.add_pet("wolf", level=6)
    battle = game.start_encounter("wild_cubs")
    pool = battle.member("pet:cub#1").subject.resources
    pool.set_current("stage_attack", 2)
    game.switch_pet("pet:cub#1", "pet:wolf#1")
    assert pool.current("stage_attack") == 0.0  # back to its start when it comes out again


def test_the_creature_screen_tells_effectiveness_by_its_rules_and_switch_lines():
    from types import SimpleNamespace

    from asteria.runtime.creature_battle import _effectiveness

    outcome = SimpleNamespace(
        value=SimpleNamespace(trace=(("type.water_vs_fire", 10.0, 20.0), ("crit_x", 20.0, 40.0)))
    )
    assert _effectiveness(outcome) == 4.0  # every rule
    assert _effectiveness(outcome, "type.") == 2.0  # the type chart only
    immune = SimpleNamespace(value=SimpleNamespace(trace=(("type.normal_vs_ghost", 5.0, 0.0),)))
    assert _effectiveness(immune, "type.") == 0.0
