"""Items used on creatures (health, ``cures:<state>`` tags, not on a fallen one), a party put
aside and given back, a battle that always ends in the catch, adding to variables, the party's
size in conditions, and whole experience points."""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


def _game(monkeypatch, **rules):
    import run_trial_smoke as smoke
    import trial_creatures

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project, game = smoke.load()
    trial_creatures.install(project, **rules)
    return project, game


def _potion(project, amount=20.0, tags=()):
    from asteria.gameplay import Effect, EffectOperation
    from asteria.gameplay.formulas import ValueFormula
    from asteria.rpg.items import ItemDefinition

    heal = Effect("potion.heal", [EffectOperation("resource_delta", "vitality",
                                                  ValueFormula.constant(amount))])  # fmt: skip
    item = ItemDefinition("test_potion", "Potion", tags=tuple(tags), use_effects=(heal,))
    project.rpg_database.add_item(item)
    return item


def test_a_potion_heals_a_creature_from_the_bag_and_is_used_up(monkeypatch):
    project, game = _game(monkeypatch)
    _potion(project)
    pet = game.add_pet("cub", level=5)
    top = game.pet_resources_at(pet)["vitality"]
    pet.resources["vitality"] = 3.0
    game.save.rpg_state.inventory.add("test_potion", 2)
    assert game.use_item_on_pet(pet, "test_potion")
    assert pet.resources["vitality"] == min(top, 23.0)
    assert game.save.rpg_state.inventory.count("test_potion") == 1
    pet.resources["vitality"] = top
    assert not game.use_item_on_pet(pet, "test_potion")  # full: no effect, kept
    assert game.save.rpg_state.inventory.count("test_potion") == 1
    pet.resources["vitality"] = 0.0
    assert not game.use_item_on_pet(pet, "test_potion")  # fallen: needs ``revives``


def test_an_item_cures_the_states_its_tags_name(monkeypatch):
    from asteria.gameplay import StateDefinition
    from asteria.rpg.items import ItemDefinition

    project, game = _game(monkeypatch)
    if project.gameplay_library.states.get("poison") is None:
        project.gameplay_library.add_state(StateDefinition("poison", 99.0))
    antidote = ItemDefinition("test_antidote", "Antidote", tags=("cures:poison",))
    project.rpg_database.add_item(antidote)
    pet = game.add_pet("cub", level=5)
    pet.states = ["poison"]
    game.save.rpg_state.inventory.add("test_antidote", 1)
    assert game.use_item_on_pet(pet, "test_antidote")
    assert pet.states == [] and game.save.rpg_state.inventory.count("test_antidote") == 0


def test_a_party_put_aside_comes_back_and_what_came_between_goes(monkeypatch):
    project, game = _game(monkeypatch)
    mine = game.add_pet("cub", level=5)
    game.stash_pets()
    assert game.party_pets() == ()
    borrowed = game.add_pet("wolf", level=7)
    assert [p.instance_id for p in game.party_pets()] == [borrowed.instance_id]
    game.restore_pets()
    assert [p.instance_id for p in game.party_pets()] == [mine.instance_id]
    assert borrowed.instance_id not in [p.instance_id for p in game.pets()]


def test_a_sure_capture_battle_and_the_party_size_condition(monkeypatch):
    from asteria.events import EventCondition
    from asteria.rpg.enemies import EncounterDefinition, EncounterMember

    project, game = _game(monkeypatch)
    project.rpg_database.add_encounter(
        EncounterDefinition(
            "tutorial",
            members=[EncounterMember(pet_species_id="cub", level=3)],
            tags=("sure_capture",),
        )  # fmt: skip
    )
    game.add_pet("cub", level=5)
    game.start_encounter("tutorial")
    foe = game.active_enemy_ids()[0]
    assert game.capture_chance(foe) == 1.0
    condition = EventCondition("rpg", "pets", ">=", 1)
    assert condition.evaluate(game.save.event_context)


def test_set_variable_adds(monkeypatch):
    from asteria.events import EventProgram
    from asteria.events.program import EventInstruction

    project, game = _game(monkeypatch)
    project.event_programs.register(
        "count",
        EventProgram(
            (
                EventInstruction("SET_VARIABLE", {"name": "n", "add": 2}),
                EventInstruction("SET_VARIABLE", {"name": "n", "add": -5}),
            ),
            name="count",
        ),
    )
    game.events.start("count")
    game.update_events(0.0)
    assert game.save.event_context.get_variable("n") == -3


@pytest.mark.parametrize("whole,expected_fraction", [(True, 0.0), (False, None)])
def test_whole_experience_points(monkeypatch, whole, expected_fraction):
    from asteria.rpg.pets import PetRules

    rules = PetRules("r", exp_share="split", exp_divisor=7.0, exp_whole=whole)
    assert PetRules.from_data(rules.to_data()) == rules
    assert ("exp_whole" in rules.to_data()) is whole
    project, game = _game(monkeypatch, exp_share="split", exp_divisor=7.0, exp_whole=whole)
    pet = game.add_pet("cub", level=5)
    game.start_encounter("wild_cubs")
    game._pets_sent = {pet.instance_id}
    before = pet.experience
    game._pets_gain_experience(tuple(game.active_enemy_ids()))
    gained = (
        pet.experience
        - before
        + sum(game.pet_species(pet).exp_to_next(level) for level in range(5, pet.level))
    )
    if expected_fraction is not None:
        assert gained == int(gained)
