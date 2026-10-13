"""ASTERIA_SPEC §20 (D22 A1): combat core — facing, knockback push, control lock, facing hitboxes,
attack
definitions, damage formulas, poise / stagger, hitstun, super armor, knockdown, hitstop, i-frames,
death and drops."""

import random

import pytest

from asteria.core import (
    ComponentRegistry,
    Entity,
    Scene,
    Transform,
    deserialize_component,
    serialize_component,
)
from asteria.gameplay import GameplayLibrary
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.formulas import (
    ConditionalMultiplier,
    FormulaCondition,
    FormulaTerm,
    ValueFormula,
)
from asteria.rpg.drop_tables import DropEntry, DropTable
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    CharacterControllerSystem,
    Hitbox2DComponent,
    HitboxSystem,
    Hurtbox2DComponent,
    facing_box,
    register_character_components,
)
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.combat import CombatantComponent, CombatSystem, parse_values
from asteria.runtime.entity_actions import EntityActionSystem

DT = 1 / 60


def _entity(scene, name, x, y, *components):
    entity = scene.add_entity(Entity(name))
    entity.add_component(Transform(x, y))
    for component in components:
        entity.add_component(component)
    return entity


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def _run(scene, seconds):
    for _ in range(round(seconds / DT)):
        scene.update(DT)


class Arena:
    """A scene with the field combat systems wired like GameSession does."""

    def __init__(self, *attacks, formulas=None, drop_tables=None, seed=0):
        self.scene = Scene("Arena")
        self.hits = HitboxSystem()
        self.combat = CombatSystem(
            {a.attack_id: a for a in attacks},
            hits=self.hits,
            formulas=formulas,
            drop_tables=drop_tables,
            rng=random.Random(seed),
        )
        self.actions = EntityActionSystem(
            hitboxes=self.hits, paused=self.combat.paused, armor=self.combat
        )
        self.combat.actions = self.actions
        self.controllers = CharacterControllerSystem(paused=self.combat.paused)
        for system in (self.actions, self.controllers, self.hits, self.combat):
            self.scene.scheduler.add(system)
        self.log = []
        self.combat.listeners.append(self.log.append)

    def fighter(self, name, x, *, team, combatant=None, hitbox=None, controller=None, y=0.0):
        hurt = _set(Hurtbox2DComponent(), team=team)
        parts = [_set(CharacterController2DComponent(), **(controller or {})), hurt]
        parts.append(_set(CombatantComponent(), team=team, **(combatant or {})))
        if hitbox is not None:
            parts.append(_set(Hitbox2DComponent(), team=team, **hitbox))
        return _entity(self.scene, name, x, y, *parts)

    def swing(self, attacker, attack_id, *, duration=0.05, extra=()):
        cues = [
            ActionCue("hit", 0.0, "hitbox", {"duration": duration, "hit_tag": attack_id}),
            *extra,
        ]
        self.actions.play(attacker.id, ActionTimeline(f"swing_{attack_id}", cues))

    def kinds(self):
        return [e.kind for e in self.log]

    def hp(self, entity, resource="hp"):
        return self.combat.state(entity).resources.current(resource)


def _power(stat="attack", minus="defense"):
    return ValueFormula(
        [FormulaTerm("source_stat", stat), FormulaTerm("target_stat", minus, -1.0)], minimum=1.0
    )


# -- controller v2 --------------------------------------------------------------------------------
def test_facing_follows_movement_and_side_view_only_turns_left_or_right():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    top = _entity(scene, "Top", 0, 0, CharacterController2DComponent())
    side = _entity(
        scene, "Side", 0, 0, _set(CharacterController2DComponent(), mode="side", facing="right")
    )
    _entity(scene, "Floor", 0, 20, _set(Collider2DComponent(), width=400, height=8))
    for intent, top_facing, side_facing in (
        ((0, -1), "up", "right"),
        ((-1, 0.2), "left", "left"),
        ((0, 0), "left", "left"),
    ):
        top.get(CharacterController2DComponent).set_intent(*intent)
        side.get(CharacterController2DComponent).set_intent(*intent)
        scene.update(DT)
        assert top.get(CharacterController2DComponent).facing == top_facing
        assert side.get(CharacterController2DComponent).facing == side_facing


def test_push_fades_stops_at_walls_and_control_lock_ignores_intent():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    _entity(scene, "Wall", -60, 0, _set(Collider2DComponent(), width=10, height=200))
    hero = _entity(
        scene,
        "Hero",
        0,
        0,
        _set(CharacterController2DComponent(), speed=60.0, knockback_decay=8.0),
    )
    c = hero.get(CharacterController2DComponent)
    c.apply_impulse(200.0, 0.0)
    _run(scene, 1.0)
    pushed = hero.get(Transform).x
    assert 20.0 < pushed < 30.0 and c.push_x == 0.0  # fades out (sum of 200 dt e^-8t ~ 26.7)
    c.apply_impulse(-900.0, 0.0)
    _run(scene, 1.0)
    assert (
        hero.get(Transform).x == pytest.approx(-60 + 5 + 6, abs=1.6) and c.push_x == 0.0
    )  # the wall stops it
    c.lock_control(0.5)
    c.set_intent(1, 0)
    start = hero.get(Transform).x
    _run(scene, 0.5)
    assert hero.get(Transform).x == pytest.approx(start) and c.controllable
    scene.update(DT)
    assert hero.get(Transform).x > start


def test_side_view_impulse_launches_upward():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    _entity(scene, "Floor", 0, 20, _set(Collider2DComponent(), width=400, height=8))
    hero = _entity(scene, "Hero", 0, 7.5, _set(CharacterController2DComponent(), mode="side"))
    scene.update(DT)
    assert hero.get(CharacterController2DComponent).grounded
    hero.get(CharacterController2DComponent).apply_impulse(0.0, -200.0)
    _run(scene, 0.2)
    assert hero.get(Transform).y < 0 and not hero.get(CharacterController2DComponent).grounded


def test_hitbox_follows_facing_mirrored_left_and_turned_for_up_down():
    scene = Scene("S")
    box = _set(
        Hitbox2DComponent(), width=20, height=8, offset_x=16, offset_y=2, follow_facing=True
    )
    hero = _entity(scene, "Hero", 100, 100, CharacterController2DComponent(), box)
    c = hero.get(CharacterController2DComponent)
    expected = {
        "right": (106, 98, 126, 106),
        "left": (74, 98, 94, 106),
        "down": (94, 106, 102, 126),
        "up": (98, 74, 106, 94),
    }
    for facing, bounds in expected.items():
        c.facing = facing
        assert facing_box(hero, box) == pytest.approx(bounds)
    box.follow_facing = False
    assert facing_box(hero, box) == pytest.approx((106, 98, 126, 106))


def test_old_component_versions_load_with_neutral_defaults():
    registry = register_character_components(ComponentRegistry())
    old = {
        "type": "asteria.CharacterController2D",
        "version": 1,
        "fields": {"mode": "side", "speed": 70.0},
    }
    c = deserialize_component(old, registry)
    assert (c.mode, c.speed, c.facing, c.knockback_decay) == ("side", 70.0, "down", 10.0)
    hit = deserialize_component(
        {"type": "asteria.Hitbox2D", "version": 1, "fields": {"width": 4.0}}, registry
    )
    assert hit.width == 4.0 and hit.follow_facing is False
    registry.register(CombatantComponent)
    combatant = _set(
        CombatantComponent(), resources="hp=50; mp=10", armor=2, stagger_result="knocked_down"
    )
    back = deserialize_component(serialize_component(combatant), registry)
    assert (back.resources, back.armor, back.stagger_result) == ("hp=50; mp=10", 2, "knocked_down")


# -- data -----------------------------------------------------------------------------------------
def test_attack_definitions_round_trip_and_live_in_the_gameplay_library():
    attack = AttackDefinition(
        "slash",
        damage=_power(),
        tags=["Element.Fire"],
        poise_damage=5,
        knockback=120,
        knockback_direction="attacker_facing",
        hitstop=0.05,
        hitstop_scope="global",
        armor_break=1,
        knockdown=True,
        knockdown_time=0.8,
    )
    assert AttackDefinition.from_data(attack.to_data()) == attack
    library = GameplayLibrary()
    library.add_attack(attack)
    data = library.to_data()
    assert data["version"] == 3 and GameplayLibrary.from_data(data).attacks["slash"] == attack
    old = {k: v for k, v in data.items() if k not in ("attacks", "projectiles")} | {"version": 1}
    assert GameplayLibrary.from_data(old).attacks == {}
    with pytest.raises(ValueError):
        AttackDefinition("x", knockback_direction="sideways")
    with pytest.raises(ValueError):
        parse_values("hp")


# -- resolution -----------------------------------------------------------------------------------
def test_damage_uses_the_formula_tags_and_criticals():
    weakness = ConditionalMultiplier(
        2.0,
        FormulaCondition(
            required_source_tags=["Element.Fire"], required_target_tags=["Creature.Plant"]
        ),
    )
    fire = AttackDefinition(
        "fire",
        damage=ValueFormula([FormulaTerm("source_stat", "magic")], multipliers=[weakness]),
        tags=["Element.Fire"],
    )
    crit = AttackDefinition(
        "crit", damage_formula_id="power", critical_chance_stat="luck", critical_multiplier=3.0
    )
    heal = AttackDefinition("mend", damage=ValueFormula.constant(-15), damage_resource="hp")
    arena = Arena(fire, crit, heal, formulas={"power": _power()})
    mage = arena.fighter(
        "Mage",
        0,
        team="hero",
        combatant={"stats": "magic=7; attack=10; luck=100"},
        hitbox={"width": 40},
    )
    plant = arena.fighter(
        "Plant", 10, team="foe", combatant={"stats": "defense=4", "tags": "Creature.Plant"}
    )
    arena.swing(mage, "fire")
    _run(arena.scene, 0.1)
    assert arena.hp(plant) == 100 - 14
    arena.swing(mage, "crit")
    _run(arena.scene, 0.1)
    damage = [e for e in arena.log if e.kind == "damage"][-1]
    assert damage.critical and damage.amount == (10 - 4) * 3 and arena.hp(plant) == 86 - 18
    arena.swing(mage, "mend")
    _run(arena.scene, 0.1)
    assert arena.hp(plant) == 83


def test_poise_breaks_into_stagger_and_hitstun_only_lands_without_poise():
    jab = AttackDefinition("jab", damage=ValueFormula.constant(1), poise_damage=6, hitstun=0.3)
    arena = Arena(jab)
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 40})
    knight = arena.fighter("Knight", 10, team="foe", combatant={"poise": 10, "stagger_time": 0.7})
    imp = arena.fighter("Imp", -10, team="foe")
    knight_controller = knight.get(CharacterController2DComponent)
    arena.actions.play(
        knight.id,
        ActionTimeline("windup", [ActionCue("w", 0.0, "movement", {"x": 0, "duration": 5})]),
    )
    arena.swing(hero, "jab")
    _run(arena.scene, 0.1)
    assert knight_controller.controllable and arena.actions.active(
        knight.id
    )  # poise 4 left: no flinch
    assert not imp.get(CharacterController2DComponent).controllable  # no poise: hitstun
    arena.swing(hero, "jab")
    _run(arena.scene, 0.1)
    assert "staggered" in arena.kinds() and not arena.actions.active(knight.id)
    assert knight_controller.control_lock > 0.5 and arena.combat.state(knight).poise == 10


def test_super_armor_takes_damage_but_ignores_reactions_until_broken():
    shove = AttackDefinition(
        "shove", damage=ValueFormula.constant(10), hitstun=0.4, knockback=300, knockdown=True
    )
    breaker = AttackDefinition(
        "breaker", damage=ValueFormula.constant(10), hitstun=0.4, knockback=300, armor_break=1
    )
    arena = Arena(shove, breaker)
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 40})
    golem = arena.fighter(
        "Golem", 10, team="foe", combatant={"armor": 1, "armor_damage_multiplier": 0.5}
    )
    arena.swing(hero, "shove")
    _run(arena.scene, 0.1)
    c = golem.get(CharacterController2DComponent)
    assert (
        arena.hp(golem) == 95 and c.controllable and c.push_x == 0 and golem.get(Transform).x == 10
    )
    assert arena.combat.down_phase(golem) == "" and arena.log[0].data["armored"]
    arena.swing(hero, "breaker")
    _run(arena.scene, 0.1)
    assert arena.hp(golem) == 85 and golem.get(Transform).x > 10


def test_action_armor_cue_gives_super_armor_only_while_the_action_runs():
    shove = AttackDefinition("shove", damage=ValueFormula.constant(1), hitstun=0.4)
    arena = Arena(shove)
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 40})
    brute = arena.fighter("Brute", 10, team="foe")
    charge = ActionTimeline(
        "charge",
        [ActionCue("armor", 0.0, "armor", {"duration": 2.0, "level": 2})]
        + [ActionCue("end", 0.5, "gameplay_event", {"name": "done"})],
    )
    arena.actions.play(brute.id, charge)
    scene = arena.scene
    scene.update(DT)
    assert arena.combat.armor_level(brute) == 2
    arena.swing(hero, "shove")
    _run(scene, 0.1)
    assert brute.get(CharacterController2DComponent).controllable and arena.actions.active(
        brute.id
    )
    _run(scene, 0.5)
    assert not arena.actions.active(brute.id)
    scene.update(DT)
    assert arena.combat.armor_level(brute) == 0  # the armor ended with the action
    arena.swing(hero, "shove")
    _run(scene, 0.1)
    assert not brute.get(CharacterController2DComponent).controllable


def test_knockdown_lies_down_invincible_then_gets_up_with_iframes():
    trip = AttackDefinition(
        "trip", damage=ValueFormula.constant(5), knockdown=True, knockdown_time=0.5
    )
    poke = AttackDefinition("poke", damage=ValueFormula.constant(5))
    arena = Arena(trip, poke)
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 40})
    ogre = arena.fighter(
        "Ogre", 10, team="foe", combatant={"getup_time": 0.4, "getup_iframes": 0.2}
    )
    arena.swing(hero, "trip")
    _run(arena.scene, 0.1)
    assert arena.combat.down_phase(ogre) == "down" and "knocked_down" in arena.kinds()
    arena.swing(hero, "poke")
    _run(arena.scene, 0.1)
    assert arena.hp(ogre) == 95  # hits pass over it while it is down
    _run(arena.scene, 0.35)
    assert arena.combat.down_phase(ogre) == "getting_up" and "got_up" in arena.kinds()
    assert arena.hits.invincible(ogre.id)
    _run(arena.scene, 0.45)
    assert (
        arena.combat.down_phase(ogre) == ""
        and ogre.get(CharacterController2DComponent).controllable
    )
    arena.swing(hero, "poke")
    _run(arena.scene, 0.1)
    assert arena.hp(ogre) == 90


def test_poise_break_can_knock_down_instead_of_stagger():
    bash = AttackDefinition("bash", damage=ValueFormula.constant(1), poise_damage=20)
    arena = Arena(bash)
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 40})
    wolf = arena.fighter(
        "Wolf",
        10,
        team="foe",
        combatant={"poise": 15, "stagger_result": "knocked_down", "down_invincible": False},
    )
    arena.swing(hero, "bash")
    _run(arena.scene, 0.1)
    assert "knocked_down" in arena.kinds() and "staggered" not in arena.kinds()
    assert arena.combat.down_phase(wolf) == "down" and not arena.hits.invincible(wolf.id)


def test_knockback_directions_and_resistance():
    away = AttackDefinition("away", knockback=100)
    facing = AttackDefinition("facing", knockback=100, knockback_direction="attacker_facing")
    fixed = AttackDefinition(
        "fixed", knockback=100, knockback_direction="fixed", knockback_angle=90
    )
    arena = Arena(away, facing, fixed)
    hero = arena.fighter(
        "Hero", 0, team="hero", hitbox={"width": 40}, controller={"facing": "left"}
    )
    left = arena.fighter("Left", -10, team="foe", controller={"knockback_decay": 0.0})
    tank = arena.fighter(
        "Tank",
        10,
        team="foe",
        combatant={"knockback_resistance": 0.75},
        controller={"knockback_decay": 0.0},
    )
    for attack_id in ("away", "facing", "fixed"):
        for target, x in ((left, -10.0), (tank, 10.0)):
            target.get(CharacterController2DComponent).push_x = target.get(
                CharacterController2DComponent
            ).push_y = 0
            target.get(Transform).x, target.get(Transform).y = x, 0.0
        arena.hits.iframes.clear()
        arena.swing(hero, attack_id)
        arena.scene.update(DT)
        pushes = [
            (
                round(t.get(CharacterController2DComponent).push_x),
                round(t.get(CharacterController2DComponent).push_y),
            )
            for t in (left, tank)
        ]
        assert (
            pushes
            == {
                "away": [(-100, 0), (25, 0)],
                "facing": [(-100, 0), (-25, 0)],
                "fixed": [(0, 100), (0, 25)],
            }[attack_id]
        )
        _run(arena.scene, 0.1)


def test_hitstop_freezes_attacker_and_target_or_the_whole_scene():
    heavy = AttackDefinition("heavy", damage=ValueFormula.constant(1), hitstop=0.1)
    quake = AttackDefinition(
        "quake", damage=ValueFormula.constant(1), hitstop=0.1, hitstop_scope="global"
    )
    arena = Arena(heavy, quake)
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 40})
    foe = arena.fighter("Foe", 10, team="foe")
    runner = arena.fighter("Runner", 0, team="other", y=200)
    runner.get(CharacterController2DComponent).set_intent(1, 0)
    arena.swing(hero, "heavy")
    arena.scene.update(DT)
    assert (
        arena.combat.paused(hero.id)
        and arena.combat.paused(foe.id)
        and not arena.combat.paused(runner.id)
    )
    _run(arena.scene, 0.15)
    assert not arena.combat.paused(hero.id)
    arena.hits.iframes.clear()
    arena.swing(hero, "quake")
    arena.scene.update(DT)
    x = runner.get(Transform).x
    arena.scene.update(DT)
    assert arena.combat.paused(runner.id) and runner.get(Transform).x == x


def test_max_targets_iframes_death_behaviours_and_drops():
    cleave = AttackDefinition(
        "cleave", damage=ValueFormula.constant(60), max_targets=2, target_iframes=0.5
    )
    table = DropTable("bones", entries=[DropEntry("bone")], rolls=1)
    arena = Arena(cleave, drop_tables={"bones": table})
    hero = arena.fighter("Hero", 0, team="hero", hitbox={"width": 80})
    a = arena.fighter(
        "A", 5, team="foe", combatant={"drop_table_id": "bones", "death_event": "skeleton_down"}
    )
    b = arena.fighter("B", 10, team="foe", combatant={"death": "disable"})
    c = arena.fighter("C", 15, team="foe", combatant={"death": "keep"})
    arena.swing(hero, "cleave")
    _run(arena.scene, 0.1)
    assert sorted(e.target_id for e in arena.log if e.kind == "damage") == sorted([a.id, b.id])
    assert arena.hits.invincible(a.id) and arena.hp(c) == 100
    _run(arena.scene, 0.5)
    arena.swing(hero, "cleave")
    _run(arena.scene, 0.1)
    deaths = [e for e in arena.log if e.kind == "death"]
    assert {e.target_id for e in deaths} == {a.id, b.id}
    assert [e.data["event"] for e in deaths if e.target_id == a.id] == ["skeleton_down"]
    assert [e.data["items"] for e in arena.log if e.kind == "drop"] == [{"bone": 1}]
    assert arena.scene.get_entity(a.id) is None
    assert arena.scene.get_entity(b.id) is not None and not b.get(Hurtbox2DComponent).enabled
    arena.swing(hero, "cleave")
    _run(arena.scene, 0.1)
    assert arena.hp(c) == 40 and arena.scene.get_entity(c.id) is not None


# -- integration ----------------------------------------------------------------------------------
def test_combat_runs_in_the_game_session_field_update(runtime):
    """A real session: the player's action timeline hits a field enemy — damage, knockback,
    knockdown, death, drop."""
    game = runtime.game
    library = game.project.gameplay_library
    library.add_attack(
        AttackDefinition(
            "test_smash",
            damage=ValueFormula.constant(30),
            knockback=150,
            knockdown=True,
            knockdown_time=0.3,
            hitstop=0.05,
        )
    )
    library.add_timeline(
        ActionTimeline(
            "test_smash",
            [ActionCue("hit", 0.0, "hitbox", {"duration": 0.1, "hit_tag": "test_smash"})],
        )
    )
    item_id = next(iter(game.project.rpg_database.items))
    game.project.rpg_database.add_drop_table(
        DropTable("test_slime_drop", guaranteed=[DropEntry(item_id)])
    )
    table_id = "test_slime_drop"
    game.set_player_position(0.0, 0.0)
    player = game.player
    player.add_component(_set(Hitbox2DComponent(), team="hero", width=60.0, height=30.0))
    player.add_component(_set(CombatantComponent(), team="hero"))
    slime = _entity(
        game.scene,
        "TestSlime",
        20.0,
        0.0,
        _set(CharacterController2DComponent(), speed=0.0),
        _set(Hurtbox2DComponent(), team="foe"),
        _set(
            CombatantComponent(),
            team="foe",
            resources="hp=50",
            drop_table_id=table_id,
            getup_time=0.1,
            getup_iframes=0.0,
        ),
    )
    seen = []
    game.combat.listeners.append(seen.append)
    game.play_action(player.id, "test_smash")
    for _ in range(12):
        game.field_update(1 / 60)
    assert [e.kind for e in seen][:2] == ["damage", "knocked_down"]
    assert game.combat.state(slime).resources.current("hp") == 20 and slime.get(Transform).x > 20.0
    for _ in range(40):
        game.field_update(1 / 60)
    assert game.combat.down_phase(slime) == ""
    game.play_action(player.id, "test_smash")
    for _ in range(12):
        game.field_update(1 / 60)
    assert "death" in [e.kind for e in seen] and game.scene.get_entity(slime.id) is None
    assert [e.data["items"] for e in seen if e.kind == "drop"] == [{item_id: 1}]


def test_attacks_are_authored_in_the_editor_with_undo(runtime):
    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    game = runtime.game
    document = EditorDocument()
    document.set_project(game.project)
    adapter = {
        a.category_id: a for a in IntegratedAuthoringControllers(document).rpg_categories()
    }["attacks"]
    adapter.create("test_kick", AttackDefinition("test_kick", damage=ValueFormula.constant(5)))
    data = adapter.encode(adapter.get("test_kick"))
    data.update(knockdown=True, armor_break=2, hitstop_scope="global")
    adapter.edit("test_kick", adapter.decode(data))
    kick = game.project.gameplay_library.attacks["test_kick"]
    assert (kick.knockdown, kick.armor_break, kick.hitstop_scope) == (True, 2, "global")
    assert game.combat.attacks["test_kick"] is kick  # the running session reads the same records
    document.undo()
    assert game.project.gameplay_library.attacks["test_kick"].knockdown is False


# -- A2-2: batched top-down movement --------------------------------------------------------------
def test_topdown_boxes_cannot_slip_through_walls_thinner_than_the_character():
    scene = Scene("S")
    scene.scheduler.add(CharacterControllerSystem())
    _entity(
        scene, "Pole", 30, 0, _set(Collider2DComponent(), width=2, height=4)
    )  # thinner than the 16-high hero
    hero = _entity(scene, "Hero", 0, 0, _set(CharacterController2DComponent(), speed=60.0))
    hero.get(CharacterController2DComponent).set_intent(1, 0)
    _run(scene, 1.0)
    assert (
        hero.get(Transform).x <= 30 - 1 - 6 + 1e-6
        and hero.get(CharacterController2DComponent).hit_wall
    )


def test_batched_moves_match_one_by_one_checks_and_keep_the_shared_world_current():
    from asteria.runtime.collision import CollisionWorld

    rng = random.Random(3)
    scene = Scene("S")
    for k in range(25):
        shape = "circle" if k % 4 == 0 else "box"
        _entity(
            scene,
            f"Rock{k}",
            rng.uniform(-200, 200),
            rng.uniform(-200, 200),
            _set(
                Collider2DComponent(),
                shape=shape,
                width=rng.uniform(4, 40),
                height=rng.uniform(4, 40),
                radius=rng.uniform(3, 15),
            ),
        )
    walkers = [
        _entity(
            scene,
            f"W{k}",
            rng.uniform(-200, 200),
            rng.uniform(-200, 200),
            _set(CharacterController2DComponent(), speed=rng.uniform(30, 90)),
            _set(Collider2DComponent(), width=8, height=8, layer=1),
        )
        for k in range(60)
    ]
    shared = {"world": None}
    system = CharacterControllerSystem(world=lambda: shared["world"])
    for frame in range(90):
        for k, walker in enumerate(walkers):
            walker.get(CharacterController2DComponent).set_intent(
                ((k + frame // 20) % 3) - 1, ((k * 7 + frame // 15) % 3) - 1
            )
        shared["world"] = CollisionWorld.from_scene(scene)
        expected = {}
        for walker in walkers:  # what the one-by-one check says about each first x step
            c, t = walker.get(CharacterController2DComponent), walker.get(Transform)
            step = c.intent_x * c.speed * DT
            if step:
                expected[walker.id] = system._box_blocked(
                    shared["world"], walker.id, c, t.x + step, t.y
                )
        system.update(scene, DT)
        for walker in walkers:
            if walker.id in expected:
                assert walker.get(CharacterController2DComponent).hit_wall >= expected[walker.id]
        fresh = CollisionWorld.from_scene(scene)
        assert {
            k: (round(v.cx, 9), round(v.cy, 9)) for k, v in system.last_world.shapes.items()
        } == {k: (round(v.cx, 9), round(v.cy, 9)) for k, v in fresh.shapes.items()}
