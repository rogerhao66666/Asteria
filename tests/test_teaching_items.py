"""Items that teach a move (tag ``teaches:<ability>``, a TM): only to species that list it in
``teachable``; used up once learned (unless ``reusable``); with the moves full the game asks
which to forget and the item goes only when a move is given up."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


def _game(monkeypatch, max_moves=0):
    import run_trial_smoke as smoke
    import trial_creatures

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project, game = smoke.load()
    trial_creatures.install(project, **({"max_moves": max_moves} if max_moves else {}))
    return project, game


def _teacher(project, game, *tags):
    from dataclasses import replace

    from asteria.rpg.items import ItemDefinition

    pet = game.add_pet("cub", level=5)
    known = set(game.pet_moves(pet))
    move = next(a for a in sorted(project.gameplay_library.abilities.ids()) if a not in known)
    species = project.rpg_database.pet_species["cub"]
    project.rpg_database.pet_species["cub"] = replace(species, teachable=(move,))
    project.rpg_database.add_item(ItemDefinition("test_tm", "TM", tags=(f"teaches:{move}", *tags)))
    game.save.rpg_state.inventory.add("test_tm", 1)
    return pet, move


def test_a_teaching_item_teaches_able_species_and_is_used_up(monkeypatch):
    from asteria.rpg.pets import PetSpeciesDefinition as PetSpecies

    project, game = _game(monkeypatch, max_moves=4)
    pet, move = _teacher(project, game)
    data = project.rpg_database.pet_species["cub"].to_data()
    assert data["teachable"] == [move] and PetSpecies.from_data(data).teachable == (move,)
    assert game.teaching_check(pet, "test_tm") == "able"
    wolf = game.add_pet("wolf", level=5)
    assert game.teaching_check(wolf, "test_tm") == "not_able"
    assert not game.use_item_on_pet(wolf, "test_tm")
    assert game.use_item_on_pet(pet, "test_tm")
    assert move in game.pet_moves(pet) and game.teaching_check(pet, "test_tm") == "learned"
    assert game.save.rpg_state.inventory.count("test_tm") == 0
    assert game.teaching_check(pet, "potion") == ""


def test_a_reusable_teaching_item_stays(monkeypatch):
    project, game = _game(monkeypatch, max_moves=4)
    pet, move = _teacher(project, game, "reusable")
    assert game.use_item_on_pet(pet, "test_tm")
    assert game.save.rpg_state.inventory.count("test_tm") == 1


def test_with_the_moves_full_the_item_goes_only_when_a_move_is_given_up(monkeypatch):
    project, game = _game(monkeypatch)
    pet, move = _teacher(project, game)
    rules = game.pet_rules
    pet.moves = list(game.pet_moves(pet))[: rules.max_moves] if rules.max_moves else []
    if not rules.max_moves or len(pet.moves) < rules.max_moves:
        import pytest

        pytest.skip("the demo's creatures do not fill their moves")
    assert game.use_item_on_pet(pet, "test_tm")
    assert (pet.instance_id, move) in game.pending_pet_moves()
    assert game.save.rpg_state.inventory.count("test_tm") == 1
    assert not game.learn_pet_move(pet.instance_id, move, "")  # gave nothing up: kept
    assert game.save.rpg_state.inventory.count("test_tm") == 1
    assert game.use_item_on_pet(pet, "test_tm")
    forget = pet.moves[0]
    assert game.learn_pet_move(pet.instance_id, move, forget)
    assert move in pet.moves and forget not in pet.moves
    assert game.save.rpg_state.inventory.count("test_tm") == 0
