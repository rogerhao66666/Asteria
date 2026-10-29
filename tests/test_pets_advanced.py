"""Pet evolution, learned moves, affinity and the optional battle-unit mode."""

import pytest
from test_party_rpg_demo import BOSS, demo  # noqa: F401  (pytest fixture)

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


def test_low_health_combatants_rest_in_a_weak_pose(demo):  # noqa: F811
    from asteria.rpg.pets import PetSpeciesDefinition

    runtime, game, _commands = demo
    adapter = runtime._battle_presentation
    base = game.project.rpg_database.pet_species["frost_lynx"]
    game.project.rpg_database.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {**base.to_data(), "battle_unit": True, "resources": {"vitality": 100}}
    )
    member = game._pet_member()
    game.battle.summon(member)
    adapter._show_new_combatants(game)  # a pet has no authored profile: a generated sheet
    animation = adapter.screen.animation.combatant(member.member_id)
    pool = member.subject.resources

    def role():
        return getattr(animation.role, "value", animation.role)

    adapter._sync_lifecycle()
    assert role() == "idle"  # off unless the manifest asks
    runtime.manifest["battle"]["weak_below"] = 0.5
    pool.change("vitality", -80)
    adapter._sync_lifecycle()
    assert role() == "weak" and animation.clip_name == "weak"
    pool.change("vitality", 80)
    adapter._sync_lifecycle()
    assert role() == "idle" and animation.clip_name == "idle"
    # combatants whose authored profile has no weak clip are left alone
    hero = game.active_hero_ids()[0]
    pool_h = game.battle.member(hero).subject.resources
    pool_h.change(game.rules.knockout_resource_id, -pool_h.current("vitality") * 0.9)
    adapter._sync_lifecycle()
    assert getattr(adapter.screen.animation.combatant(hero).role, "value", "idle") == "idle"


def test_states_with_a_tint_colour_the_battler(demo):  # noqa: F811
    from asteria.gameplay.states import StateDefinition

    runtime, game, _commands = demo
    adapter = runtime._battle_presentation
    hero = game.active_hero_ids()[0]
    states = game.battle.member(hero).subject.states
    states.registry.register(StateDefinition("verdigris", 5, tint="#80ff80"))
    adapter._sync_lifecycle()
    assert hero not in adapter.screen.animation.state_tints
    states.apply("verdigris")
    adapter._sync_lifecycle()
    assert adapter.screen.animation.state_tints[hero] == (0x80, 0xFF, 0x80)
    from asteria.runtime import Camera2D

    frame = adapter.screen.animation.build_frame(Camera2D(960, 540))
    assert any(d.tint == (0x80, 0xFF, 0x80) for d in frame.combatant_draws)
    states.remove("verdigris")
    adapter._sync_lifecycle()
    assert hero not in adapter.screen.animation.state_tints
    plain = StateDefinition("plain", 5)
    assert "tint" not in plain.to_data()
    assert StateDefinition.from_data(StateDefinition("t", 5, tint="#102030").to_data()).tint
    import pytest as _pytest

    with _pytest.raises(ValueError):
        StateDefinition("bad", 5, tint="green")


def test_the_skill_slots_screen_equips_and_removes_abilities():
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.rpg.ability_loadout import AbilityLoadoutRules
    from asteria.runtime.extras_screens import AbilitySlotsScreen
    from asteria.runtime.game_session import GameSessionRuntime

    root = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    project.rpg_database.add_ability_loadout_rules(AbilityLoadoutRules("slots", 1))
    hero = game.save.rpg_state.party_actor_ids[0]
    known = set(game.resolve_actor_build(hero).abilities)
    spare = [a for a in project.gameplay_library.abilities.ids() if a not in known][:2]
    for ability_id in spare:
        game.learn_ability(hero, ability_id)

    class Input:
        def __init__(self):
            self.pressed = set()

        def just_pressed(self, name):
            return name in self.pressed

    class Host:
        def __init__(self):
            self.game, self.input = game, Input()

    host = Host()
    screen = AbilitySlotsScreen(host)
    host.input.pressed = {"confirm"}
    screen.handle()
    assert game.ability_slots(hero)[0] == (spare[0],)
    host.input.pressed = {"move_down"}
    screen.handle()
    host.input.pressed = {"confirm"}
    screen.handle()  # slots are full: a message, nothing changes
    assert game.ability_slots(hero)[0] == (spare[0],) and screen.message
    host.input.pressed = {"move_up"}
    screen.handle()
    host.input.pressed = {"confirm"}
    screen.handle()  # the highlighted equipped ability is removed again
    assert game.ability_slots(hero)[0] == ()


def test_the_auto_key_plays_the_turn_through_the_menu_controller(demo):  # noqa: F811
    _runtime, game, commands = demo
    hero = game.active_hero_ids()[0]
    commands.mode = "command"
    assert commands.press("auto", hero) is True  # an action was taken: the host ends the turn
    assert commands.mode in ("command", "root") and commands.pending is None


def test_a_pet_unit_alone_does_not_keep_the_heroes_in_the_fight(demo):  # noqa: F811
    from asteria.rpg.pets import PetSpeciesDefinition

    _runtime, game, _commands = demo
    base = game.project.rpg_database.pet_species["frost_lynx"]
    game.project.rpg_database.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {**base.to_data(), "battle_unit": True, "resources": {"vitality": 100}}
    )
    game.finish_victory() if False else None
    member = game._pet_member()
    game.battle.summon(member)
    game.battle.outcome_exempt.add(member.member_id)
    for hero in game.active_hero_ids():
        if not hero.startswith("pet:"):
            game.battle.remove_combatant(hero, state_id="defeated", reason="test")
    assert "heroes" in game.battle.resolve_outcome().defeated_sides


def test_a_pet_unit_is_called_by_its_nickname_in_battle(demo):  # noqa: F811
    from asteria.rpg.pets import PetSpeciesDefinition

    runtime, game, commands = demo
    base = game.project.rpg_database.pet_species["frost_lynx"]
    game.project.rpg_database.pet_species["frost_lynx"] = PetSpeciesDefinition.from_data(
        {**base.to_data(), "battle_unit": True, "resources": {"vitality": 100}}
    )
    pet = game.active_pet()
    game.rename_pet(pet.instance_id, "Snowball")
    member = game._pet_member()
    game.battle.summon(member)
    assert commands.display_name(member.member_id) == "Snowball"
    names = runtime._battle_presentation._display_names(game)
    assert names[member.member_id] == "Snowball"


def test_battle_options_in_the_project_override_the_manifest(demo):  # noqa: F811
    from asteria.rpg.extras import BattleOptions

    runtime, game, _commands = demo
    runtime.manifest["battle"]["weak_below"] = 0.4
    assert runtime.battle_option("weak_below") == 0.4 and not runtime.battle_option("auto_key")
    game.project.rpg_database.add_battle_options(
        BattleOptions("main", auto_key=True, weak_below=0.25)
    )
    assert runtime.battle_option("weak_below") == 0.25 and runtime.battle_option("auto_key")
    assert runtime._battle_presentation._weak_fraction() == 0.25
    assert runtime._COMMAND_KEYS[runtime.pg.K_t] == "auto"
    assert BattleOptions.from_data(BattleOptions("x", weak_below=0.5).to_data()).weak_below == 0.5
    with pytest.raises(ValueError):
        BattleOptions("bad", weak_below=2)
    assert "auto_key" not in BattleOptions("plain").to_data()


def test_battle_menu_rows_carry_the_skill_icons_and_the_menu_draws_them(demo):  # noqa: F811
    from asteria.presentation.battle_action_menu import BattleActionEntry

    runtime, game, commands = demo
    hero = game.active_hero_ids()[0]
    rows = commands.skill_rows(hero)
    with_icon = [r for r in rows if r.icon_asset_id]
    assert with_icon and all("skill_" in r.icon_asset_id for r in with_icon)
    adapter = runtime._battle_presentation
    assert adapter._ui_backend.resolve_icon is not None
    assert adapter._resolve_icon(with_icon[0].icon_asset_id) is not None
    assert adapter._resolve_icon("no/such/icon.png") is None
    entry = BattleActionEntry("x", "Long skill name here", icon_asset_id="a.png", cost_text="9SP")
    assert entry.to_data()["icon_asset_id"] == "a.png"
