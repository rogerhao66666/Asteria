"""An Octopath-Traveler-style battle built only from authored data on the reference project
(BTL-02 / BTL-03 /
GP-02): weapon and element weaknesses with any multiplier, resistances, shields broken by weakness
hits, a
Break that delays the enemy and makes it take more damage, Boost that repeats attacks or powers
spells, two
weapons carried at once, a secondary job, and a poison that hurts more every turn. No engine rule
is
special-cased: everything is interaction rules, tags, gauges, states and options a designer
sets."""

import dataclasses

import pytest
from test_session_events import _session

from asteria.gameplay import Effect, EffectOperation, EffectOperationKind
from asteria.gameplay.states import PeriodicEffect, StateDefinition
from asteria.rpg import BattleStatePolicy
from asteria.rpg.interactions import InteractionRule
from asteria.rpg.items import EquipmentSlotDefinition, ItemDefinition

DAMAGE = "vitality"
BP = "momentum"  # the reference project's boost resource


def _project():
    project, _ = _session()
    db, library = project.rpg_database, project.gameplay_library
    abilities = library.abilities
    strike = abilities.get("strike")
    for ability_id, tags in (
        ("oct_sword", ("weapon.sword",)),
        ("oct_bow", ("weapon.bow",)),
        ("oct_fire", ("damage.fire", "boost.power")),  # spells grow stronger with boost
    ):
        abilities._definitions[ability_id] = dataclasses.replace(
            strike, ability_id=ability_id, tags=tags
        )
    base_targeting = db.battle_targeting.get("strike")
    if base_targeting is not None:
        for ability_id in ("oct_sword", "oct_bow", "oct_fire"):
            db.battle_targeting[ability_id] = dataclasses.replace(
                base_targeting, ability_id=ability_id
            )
    weapon = db.equipment["weapon_12"]
    # The attack names its weapon type (ability tag weapon.sword); the item only says what is
    # carried
    # (equip.sword). Item tags join the wielder's tags, so with two weapons both would apply to
    # every hit.
    db.equipment["oct_sword_item"] = dataclasses.replace(
        weapon,
        equipment_id="oct_sword_item",
        granted_abilities=("oct_sword",),
        tags=("weapon", "equip.sword"),
    )
    db.equipment["oct_bow_item"] = dataclasses.replace(
        weapon,
        equipment_id="oct_bow_item",
        granted_abilities=("oct_bow", "oct_fire"),
        tags=("weapon", "equip.bow"),
    )
    for rule in (
        InteractionRule(
            "oct_weak_sword",
            source_tags_all=("weapon.sword",),
            target_tags_all=("weak.sword",),
            multiplier=1.5,
            outcome_tags=("outcome.weak",),
        ),
        InteractionRule(
            "oct_resist_bow",
            source_tags_all=("weapon.bow",),
            target_tags_all=("resist.bow",),
            multiplier=0.5,
        ),
        InteractionRule(
            "oct_broken", target_tags_all=("state.broken",), multiplier=2.0, priority=-1
        ),
        InteractionRule("oct_boost_2", source_tags_all=("boost.2", "boost.power"), multiplier=2.5),
    ):
        db.interaction_rules[rule.rule_id] = rule
    states = library.states
    states._definitions["broken"] = dataclasses.replace(
        states.get("broken"), contributed_tags=("state.broken",)
    )
    states._definitions["oct_venom"] = StateDefinition(
        "oct_venom",
        10,
        periodic=(
            PeriodicEffect(
                1,
                Effect(
                    "oct_venom.tick",
                    (EffectOperation(EffectOperationKind.RESOURCE_DELTA, DAMAGE, -10),),
                ),
                growth=1.0,  # 10, 20, 30... a poison that worsens every turn
            ),
        ),
    )
    db.battle_state_policies["oct_venom"] = BattleStatePolicy(
        "oct_venom", tick_trigger="rpg.battle.turn_ended"
    )
    return project


def _battle(project=None):
    project, game = _session(project or _project())
    hero = game.save.rpg_state.party_active_actor_ids[0]
    loadout = game.save.rpg_state.loadouts[hero]
    loadout._slots["weapon"] = EquipmentSlotDefinition(
        "weapon", capacity=2
    )  # this class carries two weapons
    loadout._equipped.setdefault("weapon", [])
    loadout._equipped["weapon"].clear()
    game.equip_definition(hero, "oct_sword_item", replace=False)
    game.equip_definition(hero, "oct_bow_item", replace=False)
    game.start_encounter("boss_room")
    boss = next(e for e in game.active_enemy_ids() if e.startswith("astral_tyrant"))
    tags = game.battle.member(boss).subject.tags
    tags.add("weak.sword")
    tags.add("resist.bow")
    return game, hero, boss


def _hit(game, hero, boss, ability_id, **kwargs):
    pool = game.battle.member(boss).subject.resources
    pool.set_current(
        DAMAGE, max(pool.current(DAMAGE), 8000)
    )  # never let the boss fall mid-measurement
    before = pool.current(DAMAGE)
    game.use_ability(hero, ability_id, (boss,), **kwargs)
    return before - pool.current(DAMAGE)


def test_two_weapons_weapon_weakness_and_resistance():
    game, hero, boss = _battle()
    abilities = set(game.resolve_actor_build(hero).abilities)
    assert {"oct_sword", "oct_bow"} <= abilities  # both weapons usable at once
    sword = _hit(game, hero, boss, "oct_sword")
    bow = _hit(game, hero, boss, "oct_bow")
    assert sword == pytest.approx(bow * 3)  # x1.5 weakness against x0.5 resistance


def test_weakness_hits_break_the_shield_and_the_break_doubles_damage():
    game, hero, boss = _battle()
    resources = game.battle.battle_resources
    shield = resources.current(boss, "stagger")
    plain = _hit(game, hero, boss, "oct_sword")
    assert resources.current(boss, "stagger") == shield - 1  # one shield point per weakness hit
    for _ in range(int(shield) + 2):
        if game.battle.member(boss).subject.tags.contains("state.broken"):
            break
        _hit(game, hero, boss, "oct_sword")
    assert game.battle.member(boss).subject.tags.contains("state.broken")
    pool = game.battle.member(boss).subject.resources
    pool.set_current(DAMAGE, 9000)  # room for the measured hit
    assert _hit(game, hero, boss, "oct_sword") == pytest.approx(plain * 2)  # broken: x2 damage


def test_boost_repeats_attacks_and_powers_spells():
    game, hero, boss = _battle()
    rules = game.rules
    game.battle.battle_resources.change(hero, rules.boost_resource_id, 10)
    level = min(2, game.max_boost_level(hero))
    assert level == 2
    single = _hit(game, hero, boss, "oct_bow")
    game.battle.battle_resources.change(hero, rules.boost_resource_id, 10)
    assert _hit(game, hero, boss, "oct_bow", boost_level=2) == pytest.approx(
        single * 3
    )  # attack: 3 hits
    plain = _hit(game, hero, boss, "oct_fire")
    game.battle.battle_resources.change(hero, rules.boost_resource_id, 10)
    assert _hit(game, hero, boss, "oct_fire", boost_level=2) == pytest.approx(
        plain * 2.5
    )  # spell: one, x2.5
    assert not game.battle.member(hero).subject.tags.contains(
        "boost.2"
    )  # boost tags last one action


def test_secondary_job_and_a_poison_that_worsens_every_turn():
    game, hero, boss = _battle()
    progress = game.save.rpg_state.actor_progression[hero]
    alternate = next(
        (c for c in progress.unlocked_class_ids if c not in progress.active_class_ids), None
    )
    if alternate is not None:  # the secondary job is active and its build applies
        game.set_secondary_class(hero, alternate)
        assert game.save.rpg_state.actor_progression[hero].active_class_ids[-1] == alternate
        assert {"oct_sword", "oct_bow"} <= set(game.resolve_actor_build(hero).abilities)
    battle = game.battle
    battle.apply_state("oct_venom", hero, boss)
    pool = battle.member(boss).subject.resources
    losses = []
    for _ in range(3):
        before = pool.current(DAMAGE)
        battle.battle_states.apply_trigger("rpg.battle.turn_ended", (battle.member(boss),))
        losses.append(before - pool.current(DAMAGE))
    assert losses == pytest.approx([10, 20, 30])


def test_status_definitions_and_poison_growth_are_editable_in_game_data():
    from asteria.editor import EditorDocument
    from asteria.editor.authoring_hub_widget import with_optional_fields
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    project = _project()
    document = EditorDocument(project)
    adapter = next(
        a
        for a in IntegratedAuthoringControllers(document).rpg_categories()
        if a.category_id == "states"
    )
    assert adapter.label == "Status Definitions" and "oct_venom" in adapter.ids()
    plain = StateDefinition(
        "oct_burn",
        3,
        periodic=(
            PeriodicEffect(
                1, Effect("b", (EffectOperation(EffectOperationKind.RESOURCE_DELTA, DAMAGE, -5),))
            ),
        ),
    )
    adapter.create("oct_burn", plain)
    shown = with_optional_fields(adapter.encode(adapter.get("oct_burn")), adapter.get("oct_burn"))
    assert (
        shown["periodic"][0]["growth"] == 0.0 and shown["periodic"][0]["growth_mode"] == "add"
    )  # discoverable
    shown["periodic"][0].update(growth=2.0, growth_mode="multiply", growth_cap=8.0)
    adapter.edit("oct_burn", adapter.decode(shown))
    edited = project.gameplay_library.states.get("oct_burn").periodic[0]
    assert [edited.factor(n) for n in (1, 2, 3, 4, 5)] == [1, 2, 4, 8, 8]  # doubling, capped at x8
    document.undo()
    assert project.gameplay_library.states.get("oct_burn").periodic[0].growth == 0.0


# -- divine skills, weapon requirements, mixed hits, giving boost, pets, concoct, ailments --------


def _with(project, ability_id, **changes):
    """A copy of strike with ``changes``, granted by the sword (so the hero knows it), before the
    battle starts."""
    db, abilities = project.rpg_database, project.gameplay_library.abilities
    abilities._definitions[ability_id] = dataclasses.replace(
        abilities.get("strike"), ability_id=ability_id, **changes
    )
    if "strike" in db.battle_targeting:
        db.battle_targeting[ability_id] = dataclasses.replace(
            db.battle_targeting["strike"], ability_id=ability_id
        )
    sword = db.equipment["oct_sword_item"]
    db.equipment["oct_sword_item"] = dataclasses.replace(
        sword, granted_abilities=(*sword.granted_abilities, ability_id)
    )
    return project


def test_a_divine_skill_costs_several_boost_points_and_says_why_it_waits():
    game, hero, boss = _battle(
        _with(_project(), "oct_divine", tags=("weapon.sword",), battle_costs={BP: 3})
    )
    bp = game.battle.battle_resources
    bp.change(hero, BP, -bp.current(hero, BP))
    bp.change(hero, BP, 2)
    assert game.ability_unavailable(hero, "oct_divine") == f"Needs 3 {BP} (has 2)"
    with pytest.raises(Exception, match="Needs 3"):
        game.use_ability(hero, "oct_divine", (boss,))
    bp.change(hero, BP, 1)
    assert game.ability_unavailable(hero, "oct_divine") == ""
    assert _hit(game, hero, boss, "oct_divine") > 0
    assert bp.current(hero, BP) == 0  # all three spent


def test_a_skill_can_require_two_kinds_of_weapon_equipped():
    from asteria.gameplay.conditions import ConditionGroup, TagCondition

    both = ConditionGroup(
        (TagCondition("source", "equip.sword"), TagCondition("source", "equip.bow"))
    )
    game, hero, boss = _battle(_with(_project(), "oct_twin", conditions=both))
    assert game.ability_unavailable(hero, "oct_twin") == ""
    assert _hit(game, hero, boss, "oct_twin") > 0
    game.battle.member(hero).subject.tags.remove("equip.bow")  # as if the bow were taken off
    assert game.ability_unavailable(hero, "oct_twin") == "Needs sword + bow"
    with pytest.raises(Exception, match="sword \\+ bow"):
        game.use_ability(hero, "oct_twin", (boss,))


def test_one_skill_lands_several_hits_of_different_damage_types():
    hits = [
        {"tags": ["weapon.sword"]},
        {"tags": ["weapon.bow"]},
        {"tags": ["weapon.sword"], "power": 0.5},
    ]
    game, hero, boss = _battle(_with(_project(), "oct_flurry", tags=(), hits=hits))
    sword = _hit(game, hero, boss, "oct_sword")
    shield = game.battle.battle_resources.current(boss, "stagger")
    total = _hit(game, hero, boss, "oct_flurry")
    bow = sword / 3  # x1.5 weakness against x0.5 resistance
    assert total == pytest.approx(sword + bow + sword * 0.5)
    assert (
        game.battle.battle_resources.current(boss, "stagger") == shield - 2
    )  # each weak hit breaks a shield point
    assert (
        len([e for e in game.battle_log if e.kind == "action" and e.ability_id == "oct_flurry"])
        == 3
    )


def test_a_skill_gives_boost_points_to_an_ally():
    project = _with(
        _project(),
        "oct_donate",
        effects=(),
        battle_costs={BP: 1},
        battle_resource_gains=[{"to": "targets", "resource": BP, "amount": 2}],
    )
    project.rpg_database.battle_targeting.pop("oct_donate", None)  # its own targeting: one ally
    game, hero, boss = _battle(project)
    ally = next(h for h in game.active_hero_ids() if h != hero)
    bp = game.battle.battle_resources
    bp.change(hero, BP, 1)
    mine, theirs = bp.current(hero, BP), bp.current(ally, BP)
    game.use_ability(hero, "oct_donate", (ally,))
    assert bp.current(hero, BP) == mine - 1 and bp.current(ally, BP) == theirs + 2


def test_a_skill_calls_a_pet_into_the_battle():
    project = _project()
    pet = "hero_07"  # in the roster, kept in reserve (the test save fields hero_01..06)
    _with(
        project,
        "oct_unleash",
        commands=[{"command": "SUMMON", "args": {"actor_id": pet, "owner_id": "@actor"}}],
    )
    game, hero, boss = _battle(project)
    _hit(game, hero, boss, "oct_unleash")
    assert pet in game.active_hero_ids()
    assert game.battle.combatants.state(pet).summon_owner_id == hero


def test_concoct_combines_ingredients_into_an_item_that_acts_at_once():
    from asteria.rpg.composition import (
        CompositionOutput,
        CompositionRecipeDefinition,
        CompositionSelection,
    )

    project = _with(
        _with(_project(), "oct_bomb_blast", tags=("damage.fire",)),
        "oct_concoct",
        concoct_station="concoct",
    )
    db = project.rpg_database
    db.items["oct_fire_bomb"] = ItemDefinition(
        "oct_fire_bomb", "Fire Bomb", battle_ability="oct_bomb_blast"
    )
    db.composition_recipes["oct_fire_bomb"] = CompositionRecipeDefinition(
        "oct_fire_bomb",
        selections=[
            CompositionSelection("base", ["healing_herb"]),
            CompositionSelection("catalyst", ["fire_dust"]),
        ],
        outputs=[CompositionOutput("oct_fire_bomb")],
        station="concoct",
    )
    game, hero, boss = _battle(project)
    inventory = game.save.rpg_state.inventory
    for item in ("healing_herb", "fire_dust"):
        inventory.remove(item, inventory.count(item)) if inventory.count(item) else None
    assert game.ability_unavailable(hero, "oct_concoct") == "No ingredients"
    inventory.add("healing_herb", 1)
    inventory.add("fire_dust", 1)
    assert game.ability_unavailable(hero, "oct_concoct") == ""
    pool = game.battle.member(boss).subject.resources
    pool.set_current(DAMAGE, 8000)
    game.concoct(
        hero, "oct_concoct", {"base": ["healing_herb"], "catalyst": ["fire_dust"]}, (boss,)
    )
    assert pool.current(DAMAGE) < 8000  # the bomb went off on the boss
    assert (
        inventory.count("healing_herb")
        == inventory.count("fire_dust")
        == inventory.count("oct_fire_bomb")
        == 0
    )
    inventory.add("healing_herb", 1)
    inventory.add("iron_ore", 1)
    with pytest.raises(Exception, match="make nothing"):  # no recipe of the station combines these
        game.concoct(
            hero, "oct_concoct", {"base": ["healing_herb"], "catalyst": ["iron_ore"]}, (boss,)
        )


def test_ailments_sleep_and_silence_come_from_authored_policies():
    project = _with(_project(), "oct_spell", tags=("magic", "damage.fire"))
    db, library = project.rpg_database, project.gameplay_library
    for state_id, policy in (
        ("oct_sleep", BattleStatePolicy("oct_sleep", prevent_action=True)),
        ("oct_silence", BattleStatePolicy("oct_silence", blocked_ability_tags=("magic",))),
    ):
        library.states._definitions[state_id] = StateDefinition(state_id, 99)
        db.battle_state_policies[state_id] = policy
    game, hero, boss = _battle(project)
    game.battle.apply_state("oct_silence", boss, hero)
    assert game.ability_unavailable(hero, "oct_spell").startswith("Blocked by")
    assert game.ability_unavailable(hero, "oct_sword") == ""  # only magic is silenced
    ally = next(h for h in game.active_hero_ids() if h != hero)
    game.battle.apply_state("oct_sleep", boss, ally)
    assert game.turn_prevented(ally) == ("oct_sleep",)
    for _ in range(40):  # whenever the sleeper's turn comes, it passes
        actor = game.current_turn_actor()
        assert actor != ally
        if actor is None:
            break
        game.end_turn()
    assert any(e.kind == "turn_skipped" and e.member_id == ally for e in game.battle_log)


def test_an_ability_can_require_items_and_a_capture_can_give_a_pet_item():
    from asteria.gameplay.abilities import AbilityDefinition
    from asteria.rpg.capture import CaptureRule

    ability = AbilityDefinition("send_pet", requires_items={"pet_x": 1})
    assert AbilityDefinition.from_data(ability.to_data()).requires_items == {"pet_x": 1}
    assert "requires_items" not in AbilityDefinition("plain").to_data()
    with pytest.raises(ValueError):
        AbilityDefinition("bad", requires_items={"pet_x": 0})
    rule = CaptureRule("wolf", pet_item_id="pet_wolf")
    again = CaptureRule.from_data(rule.to_data())
    assert (again.actor_id, again.pet_item_id) == ("", "pet_wolf")
    with pytest.raises(ValueError):  # a capture must give the roster an actor or the bag a pet
        CaptureRule("wolf")
