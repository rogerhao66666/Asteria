"""ASTERIA_SPEC §20 (D22 A3): real-time ability use — combos, buffering, cancels, dodge / dash
with i-frames,
cooldowns and resource costs, movement while acting, lock-on and aiming, real-time states."""

import random

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.gameplay.abilities import AbilityCost, AbilityDefinition, AbilityRegistry
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.effects import Effect, EffectOperation
from asteria.gameplay.formulas import FormulaTerm, ValueFormula
from asteria.gameplay.modifiers import StatModifier
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.gameplay.states import PeriodicEffect, StateDefinition, StateRegistry
from asteria.runtime.action_combat import ActionCombatComponent, ActionCombatSystem, parse_bindings
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    CharacterControllerSystem,
    Hitbox2DComponent,
    HitboxSystem,
    Hurtbox2DComponent,
    PlayerInput2DComponent,
    PlayerInputSystem,
)
from asteria.runtime.combat import CombatantComponent, CombatSystem
from asteria.runtime.entity_actions import EntityActionSystem
from asteria.runtime.input import InputSnapshot
from asteria.runtime.projectiles import ProjectileSystem

DT = 1 / 60


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def _hit(attack_id, at=0.0, duration=0.05):
    return ActionCue(
        f"hit_{attack_id}_{at}", at, "hitbox", {"duration": duration, "hit_tag": attack_id}
    )


def _tl(timeline_id, *cues, length=None):
    cues = list(cues)
    if length is not None:
        cues.append(ActionCue(f"end_{timeline_id}", length, "gameplay_event", {"name": "end"}))
    return ActionTimeline(timeline_id, cues)


class Field:
    """A scene wired like GameSession's field, with player input fed from ``press``."""

    def __init__(self, abilities=(), timelines=(), attacks=(), projectiles=(), states=()):
        self.scene = Scene("Field")
        self.input = {}
        library_attacks = {a.attack_id: a for a in attacks}
        registry = StateRegistry()
        for state in states:
            registry.register(state)
        self.hits = HitboxSystem()
        self.combat = CombatSystem(
            library_attacks, hits=self.hits, rng=random.Random(2), states=registry
        )
        self.projectiles = ProjectileSystem(
            {p.projectile_id: p for p in projectiles}, hits=self.hits, combat=self.combat
        )
        self.actions = EntityActionSystem(
            hitboxes=self.hits,
            paused=self.combat.paused,
            armor=self.combat,
            projectiles=self.projectiles,
        )
        self.combat.actions = self.actions
        self.timelines = {t.timeline_id: t for t in timelines}
        self.system = ActionCombatSystem(
            AbilityRegistry(abilities),
            self.timelines,
            actions=self.actions,
            combat=self.combat,
            snapshot_provider=lambda: InputSnapshot(dict(self.input)),
        )
        for system in (
            PlayerInputSystem(lambda: InputSnapshot(dict(self.input))),
            self.system,
            self.actions,
            CharacterControllerSystem(paused=self.combat.paused),
            self.hits,
            self.projectiles,
            self.combat,
        ):
            self.scene.scheduler.add(system)
        self.log = []
        self.system.listeners.append(self.log.append)
        self.combat_log = []
        self.combat.listeners.append(self.combat_log.append)

    def player(self, bindings, x=0.0, y=0.0, *, resources="hp=100", stats="", regen="", **spec):
        hero = self.scene.add_entity(Entity("Hero"))
        hero.add_component(Transform(x, y))
        hero.add_component(_set(CharacterController2DComponent(), speed=60.0, facing="right"))
        hero.add_component(PlayerInput2DComponent())
        hero.add_component(_set(ActionCombatComponent(), bindings=bindings, **spec))
        hero.add_component(
            _set(
                Hitbox2DComponent(),
                team="hero",
                width=30,
                height=20,
                offset_x=15,
                follow_facing=True,
            )
        )
        hero.add_component(_set(Hurtbox2DComponent(), team="hero"))
        hero.add_component(
            _set(CombatantComponent(), team="hero", resources=resources, stats=stats, regen=regen)
        )
        return hero

    def foe(self, name, x, y=0.0, *, hp=100, **combatant):
        foe = self.scene.add_entity(Entity(name))
        foe.add_component(Transform(x, y))
        foe.add_component(_set(CharacterController2DComponent(), speed=0.0))
        foe.add_component(_set(Hurtbox2DComponent(), team="foe"))
        foe.add_component(
            _set(CombatantComponent(), team="foe", resources=f"hp={hp}", **combatant)
        )
        return foe

    def run(self, seconds):
        for _ in range(max(1, round(seconds / DT))):
            self.scene.update(DT)

    def tap(self, action, hold=1):
        self.input[action] = 1.0
        self.run(DT * hold)
        self.input[action] = 0.0
        self.scene.update(DT)

    def hp(self, entity, resource="hp"):
        return self.combat.state(entity).resources.current(resource)

    def kinds(self):
        return [e.kind for e in self.log]


def _combo_field():
    abilities = [AbilityDefinition("slash", timeline_id="slash1")]
    cut = AttackDefinition("cut", damage=ValueFormula.constant(10))
    timelines = [
        _tl(
            "slash1",
            _hit("cut"),
            ActionCue("c1", 0.1, "combo_window", {"duration": 0.2, "next": "slash2"}),
            length=0.3,
        ),
        _tl(
            "slash2",
            _hit("cut"),
            ActionCue("c2", 0.1, "combo_window", {"duration": 0.2, "next": "slash3"}),
            length=0.3,
        ),
        _tl("slash3", _hit("cut"), length=0.4),
    ]
    return Field(abilities, timelines, [cut])


def test_bindings_parse_and_reject_garbage():
    assert parse_bindings("attack=slash; dodge = roll, skill_1=fire") == {
        "attack": "slash",
        "dodge": "roll",
        "skill_1": "fire",
    }
    with pytest.raises(ValueError):
        parse_bindings("attack")


def test_three_presses_chain_a_combo_through_the_windows_and_early_presses_are_buffered():
    f = _combo_field()
    hero = f.player("attack=slash")
    dummy = f.foe("Dummy", 25)
    f.tap("attack")  # slash1
    f.run(0.12)
    f.tap("attack")  # inside the window: slash2
    f.tap("attack")  # too early for slash2's window: buffered, fires when it opens
    f.run(0.6)
    assert [e.data.get("timeline") for e in f.log if e.kind == "combo"] == ["slash2", "slash3"]
    assert "buffered" in f.kinds() and f.hp(dummy) == 70
    assert not f.actions.active(hero.id)


def test_a_late_press_starts_the_chain_again_and_a_stale_buffer_expires():
    f = _combo_field()
    f.player("attack=slash", buffer_time=0.05)
    f.foe("Dummy", 25)
    f.tap("attack")
    f.run(0.4)  # the window has closed and the action ended
    f.tap("attack")
    assert [e.kind for e in f.log] == ["used", "used"]
    f.tap(
        "attack"
    )  # during slash1's active frames with a tiny buffer: dropped before the window opens
    f.run(0.5)
    assert f.kinds().count("combo") == 0


def test_a_dodge_interrupts_dashes_along_the_stick_and_is_invincible():
    roll = AbilityDefinition(
        "roll", timeline_id="roll", interrupts_actions=True, cooldown_seconds=0.5
    )
    slash = AbilityDefinition("slash", timeline_id="slash1")
    timelines = [
        _tl("slash1", _hit("cut", 0.2), length=0.5),
        _tl(
            "roll",
            ActionCue(
                "dash",
                0.0,
                "movement",
                {"x": 1, "y": 0, "relative": "aim", "speed": 300, "duration": 0.2},
            ),
            ActionCue("iframes", 0.0, "iframe", {"duration": 0.25}),
            length=0.25,
        ),
    ]
    claw = AttackDefinition("claw", damage=ValueFormula.constant(30))
    f = Field([roll, slash], timelines, [claw, AttackDefinition("cut")])
    hero = f.player("attack=slash; dodge=roll")
    imp = f.foe("Imp", 200, 200)
    imp.add_component(
        _set(Hitbox2DComponent(), team="foe", width=400, height=400, active=True, hit_tag="claw")
    )
    f.hits.grant_invincibility(hero.id, 0.05)
    f.tap("attack")
    f.input["move_down"] = 1.0  # roll downward although the hero faces right
    f.tap("dodge")
    assert f.actions.source(hero.id) == "roll"
    f.run(0.2)
    del f.input["move_down"]
    y = hero.get(Transform).y
    assert 50 < y < 75 and abs(hero.get(Transform).x) < 1  # ~300 * 0.2, straight down
    assert f.hp(hero) == 100  # the claw box covers the hero the whole roll
    assert hero.get(CharacterController2DComponent).speed_override == 0.0 or f.actions.active(
        hero.id
    )
    f.tap("dodge")
    assert f.log[-1].reason == "cooldown"
    f.run(0.6)
    assert f.hp(hero) == 70  # once the i-frames end the claw lands


def test_costs_cooldowns_and_regeneration():
    cost = [AbilityCost("mp", ValueFormula([FormulaTerm("source_stat", "power", 2.0)]))]
    fire = AbilityDefinition("fire", timeline_id="cast", costs=cost, cooldown_seconds=0.3)
    f = Field([fire], [_tl("cast", length=0.02)])
    hero = f.player("skill_1=fire", resources="hp=100; mp=25", stats="power=5")
    f.tap("skill_1")
    assert (
        f.log[-1].kind == "used"
        and f.log[-1].data["spent"] == {"mp": 10.0}
        and f.hp(hero, "mp") == 15
    )
    f.tap("skill_1")
    assert f.log[-1].reason == "cooldown"
    f.run(0.3)
    f.tap("skill_1")
    assert f.log[-1].kind == "used" and f.hp(hero, "mp") == 5
    f.run(0.3)
    f.tap("skill_1")
    assert f.log[-1].reason == "cost:mp" and f.hp(hero, "mp") == 5
    hero.get(CombatantComponent).reset_state()
    hero.get(CombatantComponent).regen = "mp=10"
    f.combat.state(hero).resources.set_current("mp", 0)
    f.run(1.0)
    assert f.hp(hero, "mp") == pytest.approx(10, abs=0.2)
    f.run(0.1)
    f.tap("skill_1")
    assert f.log[-1].kind == "used"


def test_cancel_windows_let_another_ability_cut_in_and_rooted_actions_hold_still():
    heavy = AbilityDefinition("heavy", timeline_id="heavy")
    jab = AbilityDefinition("jab", timeline_id="jab", move_while_acting=1.0)
    timelines = [
        _tl("heavy", ActionCue("cw", 0.3, "cancel_window", {"duration": 0.2}), length=0.8),
        _tl("jab", length=0.5),
    ]
    f = Field([heavy, jab], timelines)
    hero = f.player("attack=heavy; skill_1=jab", buffer_time=0.0)
    f.input["move_right"] = 1.0
    f.tap("attack")
    f.run(0.1)
    assert abs(hero.get(Transform).x) < 1e-6  # heavy roots the hero
    f.tap("skill_1")
    assert f.log[-1].reason == "busy"
    f.run(0.2)
    f.tap("skill_1")  # inside the cancel window
    assert f.actions.source(hero.id) == "jab"
    x = hero.get(Transform).x
    f.run(0.2)
    assert hero.get(Transform).x > x + 10  # jab lets the hero keep walking


def test_lock_on_picks_switches_and_drops_targets_and_aims_shots():
    bolt = AbilityDefinition("bolt", timeline_id="shoot")
    shoot = _tl(
        "shoot",
        ActionCue("loose", 0.0, "projectile", {"projectile_id": "arrow", "aim": True}),
        length=0.1,
    )
    f = Field(
        [bolt],
        [shoot],
        [AttackDefinition("pierce", damage=ValueFormula.constant(20))],
        [ProjectileDefinition("arrow", attack_id="pierce", speed=400)],
    )
    hero = f.player("attack=bolt", lock_mode="manual")
    near = f.foe("Near", -60, 0)  # behind the hero, who faces right
    far = f.foe("Far", 0, -150)
    f.tap("lock_on")
    assert hero.get(ActionCombatComponent).lock_target_id == near.id
    f.tap("attack")
    f.run(0.4)
    assert f.hp(near) == 80 and hero.get(CharacterController2DComponent).facing == "left"
    f.tap("lock_switch")
    assert hero.get(ActionCombatComponent).lock_target_id == far.id
    f.tap("attack")
    f.run(0.5)
    assert f.hp(far) == 80
    f.combat.state(far).resources.set_current("hp", 0)
    far.get(CombatantComponent).state.dead = True
    f.run(DT)
    assert hero.get(ActionCombatComponent).lock_target_id == "" and f.log[-1].kind == "lock_lost"
    f.tap("lock_on")
    f.tap("lock_on")
    assert hero.get(ActionCombatComponent).lock_target_id == "" and "released" in [
        e.reason for e in f.log
    ]


def test_nearest_mode_aims_every_use_at_the_closest_foe():
    bolt = AbilityDefinition("bolt", timeline_id="shoot")
    shoot = _tl(
        "shoot",
        ActionCue("loose", 0.0, "projectile", {"projectile_id": "arrow", "aim": True}),
        length=0.1,
    )
    f = Field(
        [bolt],
        [shoot],
        [AttackDefinition("pierce", damage=ValueFormula.constant(20))],
        [ProjectileDefinition("arrow", attack_id="pierce", speed=400)],
    )
    f.player("attack=bolt", lock_mode="nearest")
    a = f.foe("A", 0, 90)
    b = f.foe("B", 150, 0)
    f.tap("attack")
    f.run(0.5)
    assert (f.hp(a), f.hp(b)) == (80, 100)


def test_attacks_apply_real_time_states_that_tick_modify_stats_and_can_kill():
    poison = StateDefinition(
        "poison",
        2.0,
        periodic=[
            PeriodicEffect(
                0.5, Effect("poison_tick", [EffectOperation("resource_delta", "hp", -5)])
            )
        ],
    )
    rage = StateDefinition(
        "rage", 5.0, modifiers=[StatModifier("rage_attack", "attack", "multiply", 2.0)]
    )
    sting = AttackDefinition(
        "sting",
        damage=ValueFormula([FormulaTerm("source_stat", "attack")]),
        apply_states=[{"state": "poison"}, {"state": "nope", "chance": 1.0}],
    )
    stab = AbilityDefinition("stab", timeline_id="stab")
    f = Field([stab], [_tl("stab", _hit("sting"), length=0.1)], [sting], states=[poison, rage])
    hero = f.player("attack=stab", stats="attack=4")
    rat = f.foe("Rat", 25, hp=30)
    f.tap("attack")
    assert f.hp(rat) == 26 and [e.kind for e in f.combat_log][:2] == ["damage", "state_applied"]
    assert "state_unknown" in [e.kind for e in f.combat_log]
    f.run(1.0)
    assert f.hp(rat) == 16
    f.combat.apply_state(hero, "rage")
    f.run(0.2)
    f.tap("attack")  # rage doubles the attack stat the formula reads; the poison refreshes
    assert f.hp(rat) <= 16 - 8
    f.run(2.5)
    assert "death" in [e.kind for e in f.combat_log] and f.scene.get_entity(rat.id) is None


def test_new_ability_fields_round_trip_and_old_records_still_load():
    ability = AbilityDefinition(
        "roll",
        timeline_id="roll",
        cooldown_seconds=0.6,
        move_while_acting=0.25,
        interrupts_actions=True,
    )
    data = ability.to_data()
    assert AbilityDefinition.from_data(data) == ability
    plain = AbilityDefinition("plain").to_data()
    assert (
        "timeline_id" not in plain and AbilityDefinition.from_data(plain).cooldown_seconds == 0.0
    )
    attack = AttackDefinition(
        "sting", apply_states=[{"state": "poison", "chance": 0.5, "duration": 3}]
    )
    assert AttackDefinition.from_data(attack.to_data()) == attack


def test_input_drives_an_ability_in_the_game_session(runtime):
    game = runtime.game
    library = game.project.gameplay_library
    library.add_attack(AttackDefinition("test_cut", damage=ValueFormula.constant(12)))
    library.add_timeline(_tl("test_slash", _hit("test_cut", 0.0, 0.1), length=0.2))
    library.add_ability(AbilityDefinition("test_slash", timeline_id="test_slash"))
    game.set_player_position(0.0, 0.0)
    player = game.player
    controller = player.try_get(CharacterController2DComponent) or player.add_component(
        CharacterController2DComponent()
    )
    controller.facing = "right"
    player.add_component(PlayerInput2DComponent())
    player.add_component(_set(ActionCombatComponent(), bindings="attack=test_slash"))
    player.add_component(
        _set(
            Hitbox2DComponent(), team="hero", width=40, height=20, offset_x=20, follow_facing=True
        )
    )
    player.add_component(_set(CombatantComponent(), team="hero"))
    target = game.scene.add_entity(Entity("TestTarget"))
    target.add_component(Transform(24.0, 0.0))
    target.add_component(_set(Hurtbox2DComponent(), team="foe"))
    target.add_component(_set(CombatantComponent(), team="foe", resources="hp=50"))
    used = []
    game.action_combat.listeners.append(used.append)
    game.set_field_input({"attack": 1.0})
    game.field_update(1 / 60)
    game.set_field_input({"attack": 0.0})
    for _ in range(20):
        game.field_update(1 / 60)
    assert [e.kind for e in used] == ["used"]
    assert game.combat.state(target).resources.current("hp") == 38


def test_action_combat_entity_input_does_not_activate_other_players_skills():
    field = Field([AbilityDefinition("cast", timeline_id="cast")], [_tl("cast", length=0.5)])
    players = [field.player("skill_1=cast", x=i * 100) for i in range(4)]
    mapping = {p.id: InputSnapshot({"skill_1": 1 if i == 2 else 0}) for i, p in enumerate(players)}
    field.system = ActionCombatSystem(
        AbilityRegistry([AbilityDefinition("cast", timeline_id="cast")]),
        field.timelines,
        actions=field.actions,
        combat=field.combat,
        entity_snapshot_provider=lambda e: mapping.get(e.id),
    )
    field.system.update(field.scene, DT)
    assert set(field.actions.running) == {players[2].id}
