"""ASTERIA_SPEC §20 (D22 A2): projectiles — firing, facing, spread, walls, pierce, homing, gravity, lifetime, hits
resolved by the combat system; the same results with every kernel set."""

import random
from math import atan2, degrees

import pytest

from asteria import kernels
from asteria.core import Entity, Scene, Transform
from asteria.gameplay import GameplayLibrary
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.formulas import ValueFormula
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.runtime.character_control import (
    CharacterController2DComponent,
    CharacterControllerSystem,
    HitboxSystem,
    Hurtbox2DComponent,
)
from asteria.runtime.collision import Collider2DComponent, CollisionWorld
from asteria.runtime.combat import CombatantComponent, CombatSystem
from asteria.runtime.entity_actions import EntityActionSystem
from asteria.runtime.projectiles import ProjectileSystem

DT = 1 / 60
KERNEL_SETS = kernels.available()


@pytest.fixture(params=KERNEL_SETS)
def kernel(request):
    previous = kernels.active().NAME
    kernels.use(request.param)
    yield request.param
    kernels.use(previous)


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


class Range:
    def __init__(self, *projectiles, attacks=()):
        self.scene = Scene("Range")
        self.hits = HitboxSystem()
        attack_map = {a.attack_id: a for a in (AttackDefinition("shot", damage=ValueFormula.constant(10)), *attacks)}
        self.combat = CombatSystem(attack_map, hits=self.hits, rng=random.Random(1))
        self.projectiles = ProjectileSystem(
            {p.projectile_id: p for p in projectiles},
            hits=self.hits,
            combat=self.combat,
            world=lambda: CollisionWorld.from_scene(self.scene),
            paused=self.combat.paused,
        )
        self.actions = EntityActionSystem(hitboxes=self.hits, projectiles=self.projectiles, paused=self.combat.paused)
        self.combat.actions = self.actions
        for system in (self.actions, CharacterControllerSystem(paused=self.combat.paused), self.hits, self.projectiles):
            self.scene.scheduler.add(system)
        self.scene.scheduler.add(self.combat)
        self.log = []
        self.projectiles.listeners.append(self.log.append)

    def entity(self, name, x, y=0.0, *components):
        entity = self.scene.add_entity(Entity(name))
        entity.add_component(Transform(x, y))
        for component in components:
            entity.add_component(component)
        return entity

    def target(self, name, x, y=0.0, *, team="foe", hp=100, size=16.0, **combatant):
        return self.entity(
            name,
            x,
            y,
            _set(Hurtbox2DComponent(), team=team, width=size, height=size),
            _set(CombatantComponent(), team=team, resources=f"hp={hp}", **combatant),
            _set(CharacterController2DComponent(), knockback_decay=0.0),
        )

    def wall(self, x, y, w, h, **fields):
        return self.entity("Wall", x, y, _set(Collider2DComponent(), width=w, height=h, **fields))

    def run(self, seconds):
        for _ in range(round(seconds / DT)):
            self.scene.update(DT)

    def hp(self, entity):
        return self.combat.state(entity).resources.current("hp")

    def ended(self):
        return [(e.projectile_id, e.data["reason"]) for e in self.log if e.kind == "ended"]


def test_definitions_round_trip_and_live_in_the_gameplay_library():
    arrow = ProjectileDefinition(
        "arrow", attack_id="shot", speed=300, pierce=2, wall="bounce", homing_turn=90, gravity=50
    )
    assert ProjectileDefinition.from_data(arrow.to_data()) == arrow
    library = GameplayLibrary()
    library.add_projectile(arrow)
    assert GameplayLibrary.from_data(library.to_data()).projectiles["arrow"] == arrow
    with pytest.raises(ValueError):
        ProjectileDefinition("x", wall="explode")


def test_a_shot_hits_the_first_foe_only_once_and_pushes_away_from_the_shot(kernel):
    r = Range(
        ProjectileDefinition("bolt", attack_id="knock", speed=300),
        attacks=[AttackDefinition("knock", damage=ValueFormula.constant(10), knockback=100)],
    )
    friend = r.target("Friend", 30, team="hero")
    foe = r.target("Foe", 80)
    behind = r.target("Behind", 120)
    r.projectiles.fire("bolt", 0, 0, (1, 0), owner_id="hero_id", team="hero")
    r.run(0.6)
    assert (r.hp(friend), r.hp(foe), r.hp(behind)) == (100, 90, 100)
    assert foe.get(CharacterController2DComponent).push_x == pytest.approx(100)
    assert r.ended() == [("bolt", "target")] and len(r.projectiles) == 0


def test_pierce_counts_extra_targets(kernel):
    r = Range(
        ProjectileDefinition("lance", attack_id="shot", speed=400, pierce=1),
        ProjectileDefinition("ray", attack_id="shot", speed=400, pierce=-1, lifetime=0.5),
    )
    foes = [r.target(f"F{k}", 40 + 30 * k) for k in range(4)]
    r.projectiles.fire("lance", 0, 0, (1, 0), team="hero")
    r.run(0.5)
    assert [r.hp(f) for f in foes] == [90, 90, 100, 100]
    r.projectiles.fire("ray", 0, 0, (1, 0), team="hero")
    r.run(0.6)
    assert [r.hp(f) for f in foes] == [80, 80, 90, 90] and r.ended() == [("lance", "target"), ("ray", "lifetime")]


def test_walls_destroy_bounce_stop_or_let_shots_pass(kernel):
    shots = [
        ProjectileDefinition("rock", speed=200),
        ProjectileDefinition("ball", speed=200, wall="bounce", bounce_limit=1, lifetime=3),
        ProjectileDefinition("dart", speed=200, wall="stop", lifetime=1),
        ProjectileDefinition("ghost", speed=200, wall="pass", lifetime=0.5),
        ProjectileDefinition("filtered", speed=200, wall_mask=0b10, lifetime=0.5),
    ]
    r = Range(*shots)
    r.wall(60, 0, 10, 100)
    r.wall(-60, 0, 10, 100)
    r.wall(0, 40, 300, 4, one_way=True)  # one-way platforms never stop a shot
    uids = {s.projectile_id: r.projectiles.fire(s.projectile_id, 0, 0, (1, 0))[0] for s in shots}
    r.run(0.3)
    views = {v.uid: v for v in r.projectiles.views()}
    assert uids["rock"] not in views and ("rock", "wall") in r.ended()
    assert views[uids["ball"]].vx < 0 and views[uids["ghost"]].x > 60 and views[uids["filtered"]].x > 60
    dart = views[uids["dart"]]
    assert (dart.vx, dart.vy) == (0, 0) and 50 < dart.x < 56
    r.run(0.6)  # back across to the far wall
    assert uids["ball"] not in {v.uid for v in r.projectiles.views()}  # second wall: past its bounce limit
    assert ("ball", "wall") in r.ended() and ("ghost", "lifetime") in r.ended()


def test_homing_curves_into_a_target_in_range_and_ignores_far_ones(kernel):
    r = Range(ProjectileDefinition("orb", attack_id="shot", speed=150, homing_turn=360, homing_range=200, lifetime=3))
    near = r.target("Near", 0, 80)
    far = r.target("Far", 0, -400)
    r.projectiles.fire("orb", 0, 0, (1, 0), team="hero")
    r.run(1.5)
    assert r.hp(near) == 90 and r.hp(far) == 100


def test_gravity_makes_an_arc_for_lobbed_shots(kernel):
    r = Range(ProjectileDefinition("bomb", speed=200, gravity=400, lifetime=2))
    uid = r.projectiles.fire("bomb", 0, 0, (1, -1))[0]
    heights = []
    for _ in range(40):
        r.scene.update(DT)
        heights.append(next(v.y for v in r.projectiles.views() if v.uid == uid))
    top = min(heights)
    assert top < -20 and heights[-1] > top and heights.index(top) not in (0, len(heights) - 1)


def test_fire_from_turns_offset_and_angle_with_the_facing_and_fans_a_spread(kernel):
    r = Range(ProjectileDefinition("arrow", speed=100))
    archer = r.entity(
        "Archer", 50, 50, _set(CharacterController2DComponent(), facing="left"), _set(Hurtbox2DComponent(), team="hero")
    )
    uids = r.projectiles.fire_from(
        archer, {"projectile_id": "arrow", "offset_x": 10, "offset_y": -4, "angle": 0, "count": 3, "spread": 40}
    )
    views = sorted(r.projectiles.views(), key=lambda v: v.vy)
    assert [v.uid for v in r.projectiles.views()] == uids
    assert all((v.x, v.y) == (40, 46) for v in views)
    assert [round(degrees(atan2(v.vy, v.vx))) for v in views] == [-160, 180, 160]
    archer.get(CharacterController2DComponent).facing = "down"
    (uid,) = r.projectiles.fire_from(archer, {"projectile_id": "arrow", "offset_x": 10})
    view = next(v for v in r.projectiles.views() if v.uid == uid)
    assert (view.x, view.y, round(view.vx), round(view.vy)) == (50, 60, 0, 100)


def test_iframes_and_a_scene_wide_hitstop_hold_shots(kernel):
    r = Range(
        ProjectileDefinition("bolt", attack_id="stop", speed=300, pierce=-1),
        attacks=[AttackDefinition("stop", damage=ValueFormula.constant(10), hitstop=0.2, hitstop_scope="global")],
    )
    ghost = r.target("Ghost", 40)
    r.hits.grant_invincibility(ghost.id, 1.0)
    foe = r.target("Foe", 80)
    uid = r.projectiles.fire("bolt", 0, 0, (1, 0), team="hero")[0]
    r.run(0.35)
    assert r.hp(ghost) == 100 and r.hp(foe) == 90
    x = next(v.x for v in r.projectiles.views() if v.uid == uid)
    r.scene.update(DT)
    frozen = next(v.x for v in r.projectiles.views() if v.uid == uid)
    assert r.combat.paused("") and frozen == x


def test_an_action_timeline_cue_fires_and_both_kernel_sets_agree():
    outcomes = []
    for name in KERNEL_SETS:
        previous = kernels.use(name)
        try:
            r = Range(
                ProjectileDefinition("fan", attack_id="shot", speed=250, homing_turn=45, lifetime=1.2, gravity=30)
            )
            caster = r.entity(
                "Caster",
                0,
                0,
                _set(CharacterController2DComponent(), facing="right"),
                _set(Hurtbox2DComponent(), team="hero"),
            )
            foes = [r.target(f"F{k}", 120, -60 + 30 * k, size=10) for k in range(5)]
            cue = ActionCue("cast", 0.1, "projectile", {"projectile_id": "fan", "count": 5, "spread": 60})
            r.actions.play(caster.id, ActionTimeline("volley", [cue]))
            r.run(1.5)
            outcomes.append(([r.hp(f) for f in foes], r.ended(), [(e.kind, e.uid, e.x, e.y) for e in r.log]))
        finally:
            kernels.use(previous)
    assert sum(100 - hp for hp in outcomes[0][0]) >= 30  # at least three of the five shots land
    assert all(o == outcomes[0] for o in outcomes)


def test_projectiles_run_in_the_game_session_field_update(runtime):
    game = runtime.game
    library = game.project.gameplay_library
    library.add_attack(AttackDefinition("test_arrow_hit", damage=ValueFormula.constant(25)))
    library.add_projectile(ProjectileDefinition("test_arrow", attack_id="test_arrow_hit", speed=300))
    library.add_timeline(
        ActionTimeline(
            "test_shoot", [ActionCue("loose", 0.0, "projectile", {"projectile_id": "test_arrow", "offset_x": 12})]
        )
    )
    game.set_player_position(0.0, 0.0)
    game.player.add_component(_set(Hurtbox2DComponent(), team="hero"))
    game.player.add_component(_set(CombatantComponent(), team="hero"))
    controller = game.player.try_get(CharacterController2DComponent)
    if controller is None:
        game.player.add_component(_set(CharacterController2DComponent(), facing="right"))
    else:
        controller.facing = "right"
    target = game.scene.add_entity(Entity("TestTarget"))
    target.add_component(Transform(90.0, 0.0))
    target.add_component(_set(Hurtbox2DComponent(), team="foe"))
    target.add_component(_set(CombatantComponent(), team="foe", resources="hp=40"))
    game.play_action(game.player.id, "test_shoot")
    for _ in range(30):
        game.field_update(1 / 60)
    assert game.combat.state(target).resources.current("hp") == 15
    assert [e.kind for e in game.projectiles.events] == [] and len(game.projectiles) == 0
