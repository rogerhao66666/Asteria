"""ASTERIA_SPEC §20 (D22 A4): enemy and boss AI — field AI on column storage, behaviour-tree nodes for real-time
combat (abilities, distance, strafing, side-view patrol, jumps, summons, states, HP phases), contact damage."""

import random
from array import array
from math import atan2, degrees, hypot

import pytest

from asteria import kernels
from asteria.core import Entity, Scene, Transform
from asteria.core.columns import column_spec
from asteria.core.prefab import PrefabLibrary, prefab_from_entity
from asteria.gameplay.abilities import AbilityDefinition, AbilityRegistry
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
from asteria.gameplay.attacks import AttackDefinition
from asteria.gameplay.formulas import ValueFormula
from asteria.gameplay.modifiers import StatModifier
from asteria.gameplay.projectiles import ProjectileDefinition
from asteria.gameplay.states import StateDefinition, StateRegistry
from asteria.kernels import _python
from asteria.rpg.behavior_tree import BehaviorNode, BehaviorTree
from asteria.runtime.action_combat import ActionCombatSystem
from asteria.runtime.behavior_tree import BehaviorTreeSystem
from asteria.runtime.character_control import (
    AIController2DComponent,
    CharacterController2DComponent,
    CharacterControllerSystem,
    Hitbox2DComponent,
    HitboxSystem,
    Hurtbox2DComponent,
)
from asteria.runtime.collision import Collider2DComponent, CollisionWorld
from asteria.runtime.combat import CombatantComponent, CombatSystem
from asteria.runtime.component_registry import default_component_registry
from asteria.runtime.entity_actions import EntityActionSystem
from asteria.runtime.field_ai import FieldAIComponent, FieldAISystem
from asteria.runtime.projectiles import ProjectileSystem

DT = 1 / 60
np_kernels = pytest.importorskip("asteria.kernels._numpy")


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def _n(kind, *children, **params):
    return BehaviorNode(kind, params, tuple(children))


def _tl(timeline_id, *cues, length):
    return ActionTimeline(
        timeline_id, [*cues, ActionCue(f"end_{timeline_id}", length, "gameplay_event", {"name": "end"})]
    )


class Arena:
    def __init__(self, trees=(), abilities=(), timelines=(), attacks=(), projectiles=(), states=(), prefabs=None):
        self.scene = Scene("Arena")
        registry = StateRegistry()
        for state in states:
            registry.register(state)
        self.hits = HitboxSystem()
        self.combat = CombatSystem(
            {a.attack_id: a for a in attacks}, hits=self.hits, rng=random.Random(3), states=registry
        )
        self.projectiles = ProjectileSystem(
            {p.projectile_id: p for p in projectiles}, hits=self.hits, combat=self.combat
        )
        self.actions = EntityActionSystem(
            hitboxes=self.hits, paused=self.combat.paused, armor=self.combat, projectiles=self.projectiles
        )
        self.combat.actions = self.actions
        self.action_combat = ActionCombatSystem(
            AbilityRegistry(abilities), {t.timeline_id: t for t in timelines}, actions=self.actions, combat=self.combat
        )
        self.controllers = CharacterControllerSystem(paused=self.combat.paused)
        self.prefabs = prefabs
        self.bt = BehaviorTreeSystem(
            {t.tree_id: t for t in trees},
            rng=random.Random(4),
            action_combat=self.action_combat,
            combat=self.combat,
            world=lambda: CollisionWorld.from_scene(self.scene),
            spawn=self._spawn,
        )
        for system in (
            self.bt,
            self.action_combat,
            self.actions,
            self.controllers,
            self.hits,
            self.projectiles,
            self.combat,
        ):
            self.scene.scheduler.add(system)
        self.log = []
        self.combat.listeners.append(self.log.append)

    def _spawn(self, prefab_id, x, y):
        from asteria.core.prefab import instantiate

        entity = instantiate(self.prefabs, prefab_id, default_component_registry())
        entity.get(Transform).x, entity.get(Transform).y = x, y
        return self.scene.add_entity(entity)

    def player(self, x=0.0, y=0.0, hp=100, **controller):
        hero = self.scene.add_entity(Entity("Hero"))
        hero.add_component(Transform(x, y))
        hero.add_component(_set(CharacterController2DComponent(), speed=0.0, **controller))
        hero.add_component(_set(Hurtbox2DComponent(), team="hero"))
        hero.add_component(_set(CombatantComponent(), team="hero", resources=f"hp={hp}"))
        self.bt.target_id = hero.id
        return hero

    def enemy(self, name, tree_id, x=0.0, y=0.0, hp=100, mode="topdown", **combatant):
        foe = self.scene.add_entity(Entity(name))
        foe.add_component(Transform(x, y))
        foe.add_component(_set(CharacterController2DComponent(), speed=60.0, mode=mode, facing="right"))
        foe.add_component(_set(AIController2DComponent(), driver="behavior_tree", tree_id=tree_id))
        foe.add_component(_set(Hurtbox2DComponent(), team="foe"))
        foe.add_component(_set(Hitbox2DComponent(), team="foe", width=30, height=20, offset_x=15, follow_facing=True))
        foe.add_component(_set(CombatantComponent(), team="foe", resources=f"hp={hp}", **combatant))
        return foe

    def solid(self, x, y, w, h, **fields):
        wall = self.scene.add_entity(Entity("Solid"))
        wall.add_component(Transform(x, y))
        wall.add_component(_set(Collider2DComponent(), width=w, height=h, **fields))
        return wall

    def run(self, seconds):
        for _ in range(max(1, round(seconds / DT))):
            self.scene.update(DT)

    def hp(self, entity):
        return self.combat.state(entity).resources.current("hp")


# -- field AI on columns ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("seed", range(4))
def test_field_ai_kernel_matches_the_reference(seed):
    rng = random.Random(seed)
    n = 90
    f = {
        name: array(tc, [0] * n) if tc != "d" else array("d", [0.0] * n)
        for name, tc in column_spec(FieldAIComponent).items()
    }
    t = {name: array("d", [rng.uniform(-200, 200) for _ in range(n)]) for name in ("x", "y")}
    c = {name: array("d", [rng.uniform(20, 90) for _ in range(n)]) for name in ("intent_x", "intent_y", "speed")}
    for s in range(n):
        f["mode_code"][s] = rng.randrange(6)
        f["home_x"][s], f["home_y"][s] = rng.uniform(-50, 50), rng.uniform(-50, 50)
        f["detect_radius"][s], f["lose_radius"][s], f["arrive_distance"][s] = (
            rng.uniform(40, 150),
            rng.uniform(150, 250),
            rng.choice((0.0, 2.0, 400.0)),
        )
    slots = sorted(rng.sample(range(n), 70))
    behaviour = [rng.randrange(5) for _ in slots]
    has = [rng.random() < 0.85 for _ in slots]
    tx = [rng.uniform(-200, 200) if h else float("nan") for h in has]
    ty = [rng.uniform(-200, 200) if h else float("nan") for h in has]
    copies = [
        ({k: array(v.typecode, v) for k, v in f.items()}, {k: array(v.typecode, v) for k, v in c.items()})
        for _ in range(2)
    ]
    rest_ref = _python.fieldai_step(copies[0][0], t, copies[0][1], slots, behaviour, tx, ty, has, DT)
    rest_np = np_kernels.fieldai_step(copies[1][0], t, copies[1][1], slots, behaviour, tx, ty, has, DT)
    assert rest_np == rest_ref and copies[0] == copies[1]


def test_field_ai_scenes_end_identically_with_every_kernel_set():
    results = []
    for name in kernels.available():
        previous = kernels.use(name)
        try:
            scene = Scene("S")
            player = scene.add_entity(Entity("P"))
            player.add_component(Transform(0, 0))
            system = FieldAISystem(rng=random.Random(9), default_target_id=player.id)
            scene.scheduler.add(system)
            scene.scheduler.add(CharacterControllerSystem())
            rng = random.Random(1)
            for k in range(60):
                e = scene.add_entity(Entity(f"E{k}"))
                e.add_component(Transform(rng.uniform(-150, 150), rng.uniform(-150, 150)))
                e.add_component(
                    _set(
                        FieldAIComponent(),
                        behaviour=("chase", "flee", "wander", "patrol", "idle")[k % 5],
                        patrol_path="0,0; 40,10",
                        detect_radius=120.0,
                    )
                )
                if k % 6:
                    e.add_component(_set(CharacterController2DComponent(), speed=50.0))
            for frame in range(120):
                player.get(Transform).x = 60 * (frame // 40)
                scene.update(DT)
            results.append(
                sorted(
                    (e.name, round(t.x, 9), round(t.y, 9), system.state(e.id).mode)
                    for e, t in scene.query(Transform)
                    if e.name != "P"
                )
            )
        finally:
            kernels.use(previous)
    assert all(r == results[0] for r in results)
    assert {mode for *_, mode in results[0]} >= {"chase", "wander", "patrol", "idle"}


# -- behaviour trees -------------------------------------------------------------------------------------------------
def _melee():
    slash = AbilityDefinition("slash", timeline_id="slash", cooldown_seconds=0.8)
    slam = AbilityDefinition("slam", timeline_id="slam", cooldown_seconds=1.5)
    timelines = [
        _tl("slash", ActionCue("hit", 0.1, "hitbox", {"duration": 0.1, "hit_tag": "slash"}), length=0.3),
        _tl(
            "slam",
            ActionCue("armor", 0.0, "armor", {"duration": 0.6}),
            ActionCue("hit", 0.3, "hitbox", {"duration": 0.1, "hit_tag": "slam"}),
            length=0.6,
        ),
    ]
    attacks = [
        AttackDefinition("slash", damage=ValueFormula.constant(5)),
        AttackDefinition("slam", damage=ValueFormula.constant(20)),
    ]
    return [slash, slam], timelines, attacks


def test_a_boss_switches_phase_by_hp_and_uses_its_abilities_in_reach():
    abilities, timelines, attacks = _melee()
    boss_tree = BehaviorTree(
        "boss",
        _n(
            "selector",
            _n(
                "sequence",
                _n("hp_below", fraction=0.5),
                _n("player_within", radius=25),
                _n("ability_ready", ability="slam"),
                _n("use_ability", ability="slam", wait=True),
            ),
            _n(
                "sequence",
                _n("hp_above", fraction=0.5),
                _n("player_within", radius=25),
                _n("use_ability", ability="slash", wait=True),
            ),
            _n("chase", arrive=20),
        ),
    )
    a = Arena([boss_tree], abilities, timelines, attacks)
    hero = a.player(100, 0)
    boss = a.enemy("Boss", "boss", 0, 0, hp=200)
    a.run(1.6)
    assert a.hp(hero) < 100 and a.hp(hero) % 5 == 0  # phase 1: slashes only
    a.combat.state(boss).resources.set_current("hp", 90)
    before = a.hp(hero)
    a.run(1.0)
    assert before - a.hp(hero) >= 20  # phase 2: the armored slam
    assert any(e.kind == "damage" and e.amount == 20 for e in a.log)


def test_a_ranged_enemy_keeps_its_distance_and_shoots_the_player():
    shoot = AbilityDefinition("shoot", timeline_id="shoot", cooldown_seconds=0.5)
    timeline = _tl("shoot", ActionCue("loose", 0.0, "projectile", {"projectile_id": "dart", "aim": True}), length=0.2)
    tree = BehaviorTree(
        "archer",
        _n(
            "selector",
            _n("sequence", _n("keep_distance", min=80, max=120), _n("use_ability", ability="shoot")),
            _n("wait", seconds=0.1),
        ),
    )
    a = Arena(
        [tree],
        [shoot],
        [timeline],
        [AttackDefinition("dart", damage=ValueFormula.constant(4))],
        [ProjectileDefinition("dart", attack_id="dart", speed=300)],
    )
    hero = a.player(0, 0)
    archer = a.enemy("Archer", "archer", 30, 40)
    a.run(2.5)
    d = hypot(archer.get(Transform).x, archer.get(Transform).y)
    assert 78 <= d <= 122 and a.hp(hero) <= 100 - 8


def test_strafing_circles_the_player():
    tree = BehaviorTree("dancer", _n("strafe", direction=1, seconds=10))
    a = Arena([tree])
    a.player(0, 0)
    dancer = a.enemy("Dancer", "dancer", 80, 0)
    start = atan2(0, 80)
    a.run(1.0)
    t = dancer.get(Transform)
    assert degrees(atan2(t.y, t.x) - start) < -20 and 70 < hypot(t.x, t.y) < 110  # direction 1: counter-clockwise on screen
    b = Arena([BehaviorTree("dancer", _n("strafe", direction=-1, seconds=10))])
    b.player(0, 0)
    other = b.enemy("Dancer", "dancer", 80, 0)
    b.run(1.0)
    assert degrees(atan2(other.get(Transform).y, other.get(Transform).x)) > 20


def test_side_patrol_turns_at_ledges_and_walls_and_jump_leaves_the_ground():
    tree = BehaviorTree("walker", _n("side_patrol"))
    a = Arena([tree])
    a.player(500, -500)
    a.solid(0, 20, 120, 8)  # floor from x -60 to 60; nothing beyond
    a.solid(40, 0, 6, 30)  # a wall on the right
    walker = a.enemy("Walker", "walker", 0, 7.9, mode="side")
    xs = []
    for _ in range(360):
        a.scene.update(DT)
        xs.append(walker.get(Transform).x)
    assert min(xs) > -60 and max(xs) < 40 - 3 and walker.get(Transform).y < 10  # never walked off or through
    assert sum(1 for p, q, r in zip(xs, xs[1:], xs[2:]) if (q - p) * (r - q) < 0) >= 2  # turned around
    jumper_tree = BehaviorTree("jumper", _n("jump"))
    b = Arena([jumper_tree])
    b.player(500, -500)
    b.solid(0, 20, 200, 8)
    jumper = b.enemy("Jumper", "jumper", 0, 7.9, mode="side")
    b.run(0.1)
    assert jumper.get(Transform).y < 5


def test_summon_states_and_contact_damage():
    minion = Entity("Minion")
    minion.add_component(Transform())
    minion.add_component(_set(CombatantComponent(), team="foe"))
    prefabs = PrefabLibrary()
    prefabs.add(prefab_from_entity(minion, "minion"))
    rage = StateDefinition("rage", 10.0, modifiers=[StatModifier("rage", "attack", "multiply", 2.0)])
    tree = BehaviorTree(
        "caller",
        _n(
            "sequence",
            _n("summon", prefab="minion", count=3, radius=20),
            _n("apply_state", state="rage"),
            _n("has_state", state="rage"),
            _n("wait", seconds=99),
        ),
    )
    a = Arena(
        [tree], states=[rage], prefabs=prefabs, attacks=[AttackDefinition("touch", damage=ValueFormula.constant(3))]
    )
    hero = a.player(0, 0)
    caller = a.enemy("Caller", "caller", 200, 0)
    blob = a.scene.add_entity(Entity("Blob"))
    blob.add_component(Transform(5, 0))
    blob.add_component(
        _set(Hitbox2DComponent(), team="foe", width=20, height=20, active=True, hit_tag="touch", rehit_interval=0.5)
    )
    a.run(1.05)
    assert len([e for e, _ in a.scene.query(Transform) if e.name == "Minion"]) == 3
    assert a.combat.state(caller).states.get("rage") is not None
    assert a.hp(hero) == 100 - 3 * 3  # touched at 0, 0.5 and 1.0 s


def test_new_nodes_are_authored_in_the_editor():
    from asteria.editor import EditorDocument
    from asteria.editor.behavior_tree_authoring import PARAMS, BehaviorTreeAuthoring
    from asteria.project import Project
    from asteria.rpg.behavior_tree import NODE_KINDS

    assert set(NODE_KINDS) <= set(PARAMS)  # every kind has a form
    document = EditorDocument()
    document.set_project(Project("P"))
    api = BehaviorTreeAuthoring(document)
    api.create("brute")
    api.add_child("brute", (), "chase")
    api.add_child("brute", (), "use_ability")
    last = (len(api.get("brute").root.children) - 1,)
    api.set_params("brute", last, ability="smash", wait=True)
    node = api.get("brute").node(last)
    assert (node.kind, node.params["ability"], node.params["wait"]) == ("use_ability", "smash", True)


def test_a_behavior_tree_enemy_attacks_in_the_game_session(runtime):
    game = runtime.game
    library = game.project.gameplay_library
    library.add_attack(AttackDefinition("test_bite", damage=ValueFormula.constant(7)))
    library.add_timeline(
        _tl("test_bite", ActionCue("hit", 0.0, "hitbox", {"duration": 0.1, "hit_tag": "test_bite"}), length=0.2)
    )
    library.add_ability(AbilityDefinition("test_bite", timeline_id="test_bite", cooldown_seconds=1.0))
    game.project.rpg_database.add_behavior_tree(
        BehaviorTree(
            "test_biter",
            _n(
                "selector",
                _n("sequence", _n("player_within", radius=25), _n("use_ability", ability="test_bite")),
                _n("chase", arrive=16),
            ),
        )
    )
    game.set_player_position(0.0, 0.0)
    game.player.add_component(_set(Hurtbox2DComponent(), team="hero"))
    game.player.add_component(_set(CombatantComponent(), team="hero"))
    biter = game.scene.add_entity(Entity("TestBiter"))
    biter.add_component(Transform(60.0, 0.0))
    biter.add_component(_set(CharacterController2DComponent(), speed=50.0))
    biter.add_component(_set(AIController2DComponent(), driver="behavior_tree", tree_id="test_biter"))
    biter.add_component(_set(Hitbox2DComponent(), team="foe", width=30, height=20, offset_x=12, follow_facing=True))
    biter.add_component(_set(CombatantComponent(), team="foe"))
    for _ in range(120):
        game.field_update(1 / 60)
    assert game.combat.state(game.player).resources.current("hp") <= 100 - 7
