"""Pet evolution, learned moves, affinity and the optional battle-unit mode."""

import pytest
from test_octopath_demo import BOSS, demo  # noqa: F401  (pytest fixture)

from asteria.rpg.pets import PetEvolution, PetMove, PetRecord, PetSpeciesDefinition


def _species(**extra):
    return PetSpeciesDefinition(
        "cub", "Cub", stats={"power": 10}, growth={"power": 2}, max_level=10, **extra
    )


def test_defaults_serialise_exactly_as_before():
    data = _species().to_data()
    for key in ("evolutions", "learnset", "affinity_per_battle", "battle_unit", "resources"):
        assert key not in data
    assert PetSpeciesDefinition.from_data(data).to_data() == data
    assert "affinity" not in PetRecord("p1", "cub").to_data()


def test_species_round_trip_with_new_fields():
    species = _species(
        evolutions=[PetEvolution("lion", min_level=5, min_affinity=20, item_id="moon_stone")],
        learnset=[PetMove("roar", 3), PetMove("bite", 1)],
        affinity_per_battle=2.5,
        max_affinity=50,
        battle_unit=True,
        resources={"vitality": 30},
        battle_abilities=["bite"],
    )
    data = species.to_data()
    again = PetSpeciesDefinition.from_data(data)
    assert again.to_data() == data
    assert [m.ability_id for m in again.learnset] == ["bite", "roar"]
    assert again.evolutions[0].item_id == "moon_stone"


def test_learnset_depends_on_level_and_affinity():
    species = _species(learnset=[PetMove("roar", 3, min_affinity=10)])
    assert not species.knows("roar", 3, 0)
    assert not species.knows("roar", 2, 50)
    assert species.knows("roar", 3, 10)
    assert species.gated("roar") and not species.gated("bite")


def test_affinity_is_clamped_and_evolution_needs_every_condition():
    species = _species(
        evolutions=[PetEvolution("lion", min_level=3, min_affinity=10)], max_affinity=15
    )
    pet = PetRecord("p1", "cub", level=3)
    assert pet.evolution_for(species) is None
    assert pet.add_affinity(species, 99) == 15
    evolution = pet.evolution_for(species)
    assert evolution is not None
    pet.nickname = "Fluff"
    pet.evolve(evolution)
    assert pet.species_id == "lion" and pet.nickname == "Fluff" and pet.level == 3
    assert pet.add_affinity(species, -99) == -15


def test_item_evolutions_wait_for_their_item():
    species = _species(evolutions=[PetEvolution("lion", item_id="moon_stone")])
    pet = PetRecord("p1", "cub")
    assert pet.evolution_for(species) is None
    assert pet.evolution_for(species, item_id="moon_stone") is not None


def _win(game):
    for enemy in list(game.active_enemy_ids()):
        game.battle.remove_combatant(enemy, state_id="defeated", reason="test")
    game.finish_victory()


def test_a_won_battle_raises_affinity_and_evolves_automatically(demo):  # noqa: F811
    _runtime, game, _commands = demo
    db = game.project.rpg_database
    base = db.pet_species["frost_lynx"]
    db.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {
            **base.to_data(),
            "affinity_per_battle": 6,
            "evolutions": [{"to_species_id": "ember_hound", "min_affinity": 5}],
        }
    )
    pet = game.active_pet()
    game._pets_sent.add(pet.instance_id)
    _win(game)
    assert pet.affinity == pytest.approx(6)
    assert pet.species_id == "ember_hound"


def test_unlearned_pet_abilities_are_blocked_until_learned(demo):  # noqa: F811
    _runtime, game, _commands = demo
    db = game.project.rpg_database
    base = db.pet_species["frost_lynx"]
    db.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {**base.to_data(), "learnset": [{"ability_id": "send_frost_lynx", "level": 9}]}
    )
    hero = "hero_02"
    assert "not learned" in game.ability_unavailable(hero, "send_frost_lynx")
    game.active_pet().level = 9
    assert game.ability_unavailable(hero, "send_frost_lynx") == ""
    assert game.pet_abilities() == ("send_frost_lynx",)


def test_item_evolution_spends_the_item(demo):  # noqa: F811
    _runtime, game, _commands = demo
    db = game.project.rpg_database
    item_id = next(iter(db.items))
    base = db.pet_species["frost_lynx"]
    db.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {
            **base.to_data(),
            "evolutions": [
                {"to_species_id": "ember_hound", "item_id": item_id, "automatic": False}
            ],
        }
    )
    pet = game.active_pet()
    with pytest.raises(Exception):
        game.evolve_pet(pet.instance_id)
    inventory = game.save.rpg_state.inventory
    inventory.add(item_id, 1)
    before = inventory.count(item_id)
    assert game.evolve_pet(pet.instance_id, item_id=item_id) == "ember_hound"
    assert inventory.count(item_id) == before - 1


def test_battle_unit_pets_join_the_heroes_when_enabled(demo):  # noqa: F811
    _runtime, game, _commands = demo
    db = game.project.rpg_database
    assert game._pet_member() is None  # off by default
    base = db.pet_species["frost_lynx"]
    db.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {
            **base.to_data(),
            "battle_unit": True,
            "resources": {"vitality": 40},
            "stats": {**base.stats, "speed": 7},
        }
    )
    member = game._pet_member()
    assert member is not None and member.side == "heroes"
    assert member.subject.resources.current("vitality") == 40
    assert member.member_id.startswith("pet:")


def test_region_chooses_the_battle_background(demo):  # noqa: F811
    from asteria.core import Transform
    from asteria.rpg.map_rules import AreaRule, MapRuleSet

    _runtime, game, _commands = demo
    game.project.rpg_database.map_rule_sets["m"] = MapRuleSet(
        "m", [AreaRule("region:3", battle_background="bg.swamp")]
    )
    transform = game.player.get(Transform)
    where = {"x": 0.0}

    def keys_at(x, y):
        return ("region:3",) if x == where["x"] else ()

    game.bind_map_rules(keys_at)
    transform.x = 5.0
    assert game._area_battle_background() == ""
    where["x"] = 5.0
    assert game._area_battle_background() == "bg.swamp"
    assert AreaRule.from_data(AreaRule("tag:x", battle_background="b").to_data()).battle_background


def test_party_gauges_fill_from_battle_events_and_persist(demo):  # noqa: F811
    from asteria.rpg.battle_extensions import BattleExtensionRules, ResourceGain

    _runtime, game, _commands = demo
    base = game.extension_rules
    rules = BattleExtensionRules(
        "gauge_rules",
        damage_resource=base.damage_resource if base else "vitality",
        gains=[ResourceGain("action", "limit", flat=10, shared=True)],
        shared_gauges={"limit": 100},
    )
    game.project.rpg_database.battle_extension_rules.clear()
    game.project.rpg_database.battle_extension_rules["gauge_rules"] = rules
    assert game.change_party_gauge("limit", 250) == 100  # clamped to the maximum
    assert game.party_gauge("limit") == 100
    assert game.change_party_gauge("limit", -30) == -30
    assert game.world.counters["gauge.limit"] == 70
    with pytest.raises(Exception):
        game.change_party_gauge("nope", 1)
    again = BattleExtensionRules.from_data(rules.to_data())
    assert again.shared_gauges == (("limit", 100.0),)
    assert again.gains[0].shared


def test_states_are_removed_by_category():
    from asteria.gameplay import ResourcePool, StatBlock, TagSet
    from asteria.gameplay.states import StateDefinition, StateRegistry, StateRuntime

    registry = StateRegistry(
        [
            StateDefinition("poison", 10, contributed_tags=["category.curse", "category.dot"]),
            StateDefinition("weak", 10, contributed_tags=["category.curse"]),
            StateDefinition("haste", 10, contributed_tags=["category.buff"]),
        ]
    )
    states = StateRuntime(registry, StatBlock({}), ResourcePool(), TagSet())
    for state_id in ("poison", "weak", "haste"):
        states.apply(state_id)
    assert [a.state_id for a in states.in_category("curse")] == ["poison", "weak"]
    assert states.remove_category("curse", count=1) == ("poison",)
    assert states.get("weak") is not None and states.get("haste") is not None
    assert states.remove_category("curse") == ("weak",)
    assert states.remove_category("curse") == ()


def test_auto_battle_picks_a_usable_ability_and_acts(demo):  # noqa: F811
    _runtime, game, _commands = demo
    hero = game.active_hero_ids()[0]
    choice = game.auto_battle_choice(hero)
    assert choice is not None
    ability_id, targets = choice
    assert game.ability_unavailable(hero, ability_id) == ""
    assert targets
    result = game.auto_battle_act(hero)
    assert result is not None


def test_project_menu_entries_queue_their_event_program(demo):  # noqa: F811
    from asteria.rpg.extras import MenuEntry

    runtime, game, _commands = demo
    entry = MenuEntry("hello", "Hello", "greet", visible_switch="show.hello", order=2)
    assert MenuEntry.from_data(entry.to_data()) == entry
    game.project.rpg_database.add_menu_entry(entry)
    runtime._run_menu_entry("hello")  # hidden: its switch is off
    assert "greet" not in game.pending_followups
    game.save.event_context.set_switch("show.hello", True)
    runtime._run_menu_entry("hello")
    assert "greet" in game.pending_followups
    data = game.project.rpg_database.to_data()
    assert data["menu_entries"][0]["entry_id"] == "hello"


def test_abilities_can_name_their_own_menu_category(demo):  # noqa: F811
    from asteria.gameplay.abilities import AbilityDefinition

    _runtime, game, commands = demo
    hero = game.active_hero_ids()[0]
    skills = [r.action_id for r in commands.skill_rows(hero)]
    assert commands.custom_categories(hero) == ()
    chosen = next(a for a in skills if a not in ("boost", "capture"))
    registry = game.battle.ability_runtime.registry
    data = registry.get(chosen).to_data()
    assert "menu_category" not in data  # nothing written unless set
    registry._definitions[chosen] = AbilityDefinition.from_data({**data, "menu_category": "Magic"})
    assert commands.custom_categories(hero) == ("Magic",)
    assert chosen not in [r.action_id for r in commands.skill_rows(hero)]
    assert [r.action_id for r in commands.skill_rows(hero, "Magic")] == [chosen]
    assert "Magic" in commands.categories_for(hero)
    assert commands.categories_for(hero)[-1] == "Items"
    commands.mode, commands.category = "command", "Skills"
    commands.press("category", hero)
    assert commands.category == "Magic"
    assert [r.action_id for r in commands.entries(hero)] == [chosen]


def test_ability_slots_limit_learned_abilities_to_the_equipped_ones(demo):  # noqa: F811
    from asteria.rpg.ability_loadout import AbilityLoadoutRules

    _runtime, game, _commands = demo
    hero = game.active_hero_ids()[0]
    known = set(game.resolve_actor_build(hero).abilities)
    spare = [a for a in game.project.gameplay_library.abilities.ids() if a not in known][:2]
    assert len(spare) == 2
    for ability_id in spare:
        game.learn_ability(hero, ability_id)
    assert set(spare) <= set(game.resolve_actor_build(hero).abilities)  # no rules: all usable
    rules = AbilityLoadoutRules("slots", 1, capacity_by_level={"99": 2})
    game.project.rpg_database.add_ability_loadout_rules(rules)
    usable = set(game.resolve_actor_build(hero).abilities)
    assert not set(spare) & usable  # learned but not equipped
    assert game.ability_slots(hero) == ((), 1)
    game.equip_ability(hero, spare[0])
    assert spare[0] in game.resolve_actor_build(hero).abilities
    with pytest.raises(Exception):
        game.equip_ability(hero, spare[1])  # slots are full
    game.unequip_ability(hero, spare[0])
    assert spare[0] not in game.resolve_actor_build(hero).abilities
    assert AbilityLoadoutRules.from_data(rules.to_data()) == rules
    assert rules.capacity_at(98) == 1 and rules.capacity_at(99) == 2
    assert game.project.rpg_database.to_data()["ability_loadout_rules"]


def test_field_windows_are_off_unless_the_manifest_asks(demo):  # noqa: F811
    runtime, game, _commands = demo
    drawn = []
    runtime.panel = lambda rect, *a, **k: drawn.append(rect)
    runtime._draw_field_windows()
    assert drawn == []
    runtime.manifest.setdefault("field", {})["hud"] = {"gold": True, "quest_tracker": True}
    game.save.rpg_state.currencies["gold"] = 120.0
    runtime._draw_field_windows()
    assert drawn and drawn[0][0] == 14


def test_actor_variables_are_saved_with_the_event_variables(demo):  # noqa: F811
    _runtime, game, _commands = demo
    hero = game.active_hero_ids()[0]
    assert game.actor_variable(hero, "kills") == 0
    game.set_actor_variable(hero, "kills", 3)
    assert game.actor_variable(hero, "kills") == 3
    assert game.save.event_context.get_variable(f"actor.{hero}.kills") == 3
    with pytest.raises(Exception):
        game.set_actor_variable("nobody", "kills", 1)
