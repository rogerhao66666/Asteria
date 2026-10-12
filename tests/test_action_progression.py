"""ASTERIA_SPEC §20, §21 (D22 A7): classes, levels and skill trees in real-time play — a field entity linked to an RPG
actor fights with that actor's build; kills give experience; skill points, classes and rolled equipment change the
fight; skill ranks scale abilities through stats; respec."""

import random

import pytest

from asteria.core import Entity, Transform
from asteria.gameplay.abilities import AbilityDefinition
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.rpg.loot import RolledAffix
from asteria.runtime.action_combat import ActionCombatComponent
from asteria.runtime.actor_link import ActorLinkComponent
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    Hitbox2DComponent,
    HitEvent,
    Hurtbox2DComponent,
    PlayerInput2DComponent,
)
from asteria.runtime.combat import CombatantComponent

HERO = "hero_01"


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def _linked_player(game):
    game.set_player_position(0.0, 0.0)
    player = game.player
    player.add_component(_set(ActorLinkComponent(), actor_id=HERO)) if not player.has(ActorLinkComponent) else None
    player.get(ActorLinkComponent).actor_id = HERO
    for component in (
        _set(CombatantComponent(), team="hero"),
        _set(Hurtbox2DComponent(), team="hero"),
        _set(Hitbox2DComponent(), team="hero", width=40, height=20, offset_x=20, follow_facing=True),
        PlayerInput2DComponent(),
    ):
        if not player.has(type(component)):
            player.add_component(component)
    controller = player.try_get(CharacterController2DComponent) or player.add_component(
        CharacterController2DComponent()
    )
    controller.facing = "right"
    return player


def _foe(game, name, x, **combatant):
    foe = game.scene.add_entity(Entity(name))
    foe.add_component(Transform(x, 0.0))
    foe.add_component(_set(Hurtbox2DComponent(), team="foe"))
    foe.add_component(_set(CombatantComponent(), team="foe", **combatant))
    return foe


def test_a_linked_player_fights_with_its_actors_build(runtime):
    game = runtime.game
    player = _linked_player(game)
    build = game.resolve_actor_build(HERO)
    state = game.combat.state(player)
    assert state.stats.get("power") == build.stats.get("power") > 0
    assert set(state.resources.names()) == set(build.resources.names())
    state.resources.set_current(state.resources.names()[0], 1.0)
    graph = "vanguard_tree"
    node = game.project.rpg_database.progression_graphs[graph].nodes[0]
    bonus = node.rewards[0].stat_bonuses
    before = {k: state.stats.get(k) for k in bonus}
    game.allocate_progression(HERO, graph, node.node_id)
    after = game.combat.state(player)
    assert {k: after.stats.get(k) for k in bonus} == {k: before[k] + v for k, v in bonus.items()}
    assert after.resources.current(after.resources.names()[0]) == 1.0  # the refresh keeps current values
    refund = game.reset_progression(HERO, cost={"test_gold": 0})  # every spent point comes back (the save had some)
    reset = game.combat.state(player).stats
    assert refund.get("ap", 0) >= 1 and all(reset.get(k) <= before[k] for k in bonus)
    assert all(not ranks for ranks in game.save.rpg_state.progression_allocations[HERO].allocations.values())
    with pytest.raises(Exception):
        game.reset_progression(HERO, cost={"test_gold": 5})  # cannot pay


def test_kills_give_experience_and_level_ups_raise_the_fight(runtime):
    game = runtime.game
    player = _linked_player(game)
    game.project.gameplay_library.add_attack(AttackDefinition("test_finish", damage=ValueFormula.constant(9999)))
    game.action_progression = {"level_threshold": 1000.0, "ap_per_level": 3.0, "ability_points_per_level": 0.0}
    progress = game.ensure_actor_progression(HERO)
    level = progress.level
    need = level * 1000.0 - progress.experience  # what the next level still needs
    ap = game.save.rpg_state.progression_allocations[HERO].balance("ap")
    power = game.combat.state(player).stats.get("power")
    for k in range(3):
        foe = _foe(game, f"TestBandit{k}", 30, experience=need / 2.5)
        game.combat.pending.append(HitEvent(player.id, foe.id, "test_finish", "hero"))
        game.field_update(1 / 60)
        assert any(e["levels_gained"] for e in game.progression_events) == (k == 2)  # the third kill levels up
    progress = game.save.rpg_state.actor_progression[HERO]
    assert progress.level == level + 1 and game.save.rpg_state.progression_allocations[HERO].balance("ap") == ap + 3
    assert game.combat.state(player).stats.get("power") >= power  # rebuilt at the new level
    stranger = _foe(game, "TestStranger", 30, experience=500)
    unlinked = game.scene.add_entity(Entity("TestTurret"))
    unlinked.add_component(Transform(0, 0))
    game.combat.pending.append(HitEvent(unlinked.id, stranger.id, "test_finish", "hero"))
    game.field_update(1 / 60)
    assert game.save.rpg_state.actor_progression[HERO].level == level + 1  # only a linked actor gains experience


def test_rolled_equipment_from_the_bag_changes_the_fight(runtime):
    from asteria.rpg.items import EquipmentDefinition, EquippedItem

    game = runtime.game
    player = _linked_player(game)
    db = game.project.rpg_database
    slot = next(iter(game.save.rpg_state.loadouts[HERO]._slots.values()))
    db.add_equipment(EquipmentDefinition("test_blade", "Test Blade", slot=slot.slot_id))
    blade = EquippedItem(
        db.equipment["test_blade"],
        instance_id="test_blade#1",
        rarity="rare",
        rolled_affixes=(RolledAffix("x", (("power", "add", 25.0),)),),
    )
    game.save.rpg_state.equipment_bag.append(blade)
    power = game.combat.state(player).stats.get("power")
    game.equip_from_bag(HERO, len(game.save.rpg_state.equipment_bag) - 1)
    assert game.combat.state(player).stats.get("power") == power + 25
    game.unequip_to_bag(HERO, slot.slot_id)
    assert game.combat.state(player).stats.get("power") == power and game.save.rpg_state.equipment_bag[-1] is blade


def test_skill_ranks_scale_damage_cooldown_and_projectile_count_through_stats(runtime):
    game = runtime.game
    player = _linked_player(game)
    library = game.project.gameplay_library
    library.add_attack(
        AttackDefinition("test_bolt", damage=ValueFormula([FormulaTerm("source_stat", "bolt_rank", 10.0)]))
    )
    library.add_projectile(ProjectileDefinition("test_bolt", attack_id="test_bolt", speed=400, pierce=-1))
    library.add_timeline(
        ActionTimeline(
            "test_bolt",
            [
                ActionCue(
                    "cast",
                    0.0,
                    "projectile",
                    {"projectile_id": "test_bolt", "count": 1, "count_stat": "bolt_rank", "spread": 10},
                )
            ],
        )
    )
    library.add_ability(
        AbilityDefinition(
            "test_bolt",
            timeline_id="test_bolt",
            cooldown_formula=ValueFormula(
                [FormulaTerm.constant(2.0), FormulaTerm("source_stat", "bolt_rank", -0.5)], minimum=0.2
            ),
        )
    )
    state = game.combat.state(player)
    state.stats.set("bolt_rank", 2.0)  # what a skill-tree node's stat bonus would give
    player.add_component(_set(ActionCombatComponent(), bindings="attack=test_bolt"))
    target = _foe(game, "TestDummy", 60, resources="hp=1000")
    game.set_field_input({"attack": 1.0})
    game.field_update(1 / 60)
    game.set_field_input({"attack": 0.0})
    assert len(game.projectiles) == 3  # 1 + rank 2
    for _ in range(20):
        game.field_update(1 / 60)
    assert game.combat.state(target).resources.current("hp") == 1000 - 3 * 20  # 10 per rank, three bolts
    assert game.action_combat.cooldown(player, "test_bolt") == pytest.approx(1.0 - 20 / 60, abs=0.02)  # 2 - 0.5 x 2


def test_require_known_limits_abilities_to_what_the_actor_has_learned(runtime):
    game = runtime.game
    player = _linked_player(game)
    library = game.project.gameplay_library
    library.add_timeline(ActionTimeline("test_swing", [ActionCue("end", 0.1, "gameplay_event", {"name": "end"})]))
    library.add_ability(AbilityDefinition("test_secret", timeline_id="test_swing"))
    known = sorted(game.resolve_actor_build(HERO).abilities)
    library_known = [a for a in known if library.abilities.get(a) is not None]
    assert library_known
    spec = player.add_component(_set(ActionCombatComponent(), require_known=True))
    assert game.action_combat.use(player, "test_secret") == "not_known"
    spec.require_known = False
    assert game.action_combat.use(player, "test_secret") == "used"
    random.Random(0)
