"""Build the ARPG demo (D22 A10): a loot-driven action RPG made only of project data.

* a town (a merchant who buys monster parts and sells potions, a smith who brews potions,
  three class trainers), a top-down field (slimes, eyes that shoot, an elite pack, a boss) and a
  side-view dungeon (platforms, one-way ledges, a ladder, ranged drones, a boss);
* three classes - Warrior, Ranger, Mage - each with its own skill tree, plus a shared attribute
  tree; skill points on every level-up; a trainer changes your class at any time;
* loot: rarities with random affixes, a three-piece set, uniques, gold and crafting parts;
* potions are inventory items an ability spends (``item:potion``).

Everything is ordinary project data: the engine has no idea this is "an action RPG". The same
systems build a soulslike, a twin-stick shooter, a platformer brawler or anything else.

Run: ``python reference_projects/arpg_multiplayer_demo/build_project.py`` (writes this folder;
idempotent).
Play: ``python -m asteria.runtime.preview
reference_projects/arpg_multiplayer_demo/project.asteria.json``.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

import arpg_builds as builds  # noqa: E402
import arpg_loot as loot  # noqa: E402
import art  # noqa: E402
import lucifer_art as la  # noqa: E402
import maps  # noqa: E402

from asteria.core import Entity, Scene, Transform  # noqa: E402
from asteria.events import (  # noqa: E402
    EventBinding,
    EventInstruction,
    EventProgram,
    EventTriggerKind,
    SceneEventBindings,
)
from asteria.gameplay import Effect, EffectOperation  # noqa: E402
from asteria.gameplay.abilities import AbilityCost, AbilityDefinition  # noqa: E402
from asteria.gameplay.action_timeline import ActionCue, ActionTimeline  # noqa: E402
from asteria.gameplay.attacks import AttackDefinition  # noqa: E402
from asteria.gameplay.formulas import FormulaTerm, ValueFormula  # noqa: E402
from asteria.gameplay.modifiers import StatModifier  # noqa: E402
from asteria.gameplay.projectiles import ProjectileDefinition  # noqa: E402
from asteria.gameplay.states import PeriodicEffect, StateDefinition  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.rpg import (  # noqa: E402
    ActorDefinition,
    ActorProgressionState,
    ClassDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    Inventory,
    ItemDefinition,
    ProgressionAllocationRuntime,
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeRequirement,
    ProgressionNodeReward,
    ProgressionRuntime,
    RpgRuntimeState,
)
from asteria.rpg.ability_loadout import AbilityLoadoutRules  # noqa: E402
from asteria.rpg.behavior_tree import BehaviorNode, BehaviorTree  # noqa: E402
from asteria.rpg.composition import (  # noqa: E402
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionSelection,
)
from asteria.rpg.economy import ShopDefinition, ShopEntry  # noqa: E402
from asteria.runtime.action_combat import ActionCombatComponent  # noqa: E402
from asteria.runtime.action_play import CombatSceneComponent  # noqa: E402
from asteria.runtime.actor_link import (  # noqa: E402
    ActorLinkComponent,
    ClassAppearanceComponent,
)
from asteria.runtime.character_control import (  # noqa: E402
    AIController2DComponent,
    CharacterController2DComponent,
    Hitbox2DComponent,
    Hurtbox2DComponent,
    PlayerInput2DComponent,
)
from asteria.runtime.collision import Collider2DComponent  # noqa: E402
from asteria.runtime.combat import CombatantComponent  # noqa: E402
from asteria.runtime.components2d import (  # noqa: E402
    Animator2DComponent,
    Camera2DComponent,
    Interaction2DComponent,
    ParallaxBackground2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)
from asteria.runtime.game_start import GameStartDefinition  # noqa: E402
from asteria.runtime.loot import LooterComponent  # noqa: E402

HERO = "hero"
CLASSES = ("warrior", "ranger", "mage")


def _set(component, **fields):
    for k, v in fields.items():
        current = getattr(component, k, None)
        if isinstance(current, float) and isinstance(v, int) and not isinstance(v, bool):
            v = float(v)  # schema fields are typed: 40 -> 40.0
        setattr(component, k, v)
    return component


def scaled(stat, coefficient, *, defense=0.5, extra=None):
    """Damage: ``coefficient`` x the user's ``stat`` (plus ``extra`` terms) minus ``defense`` x
    the target's defense, at least 1."""
    terms = [FormulaTerm("source_stat", stat, coefficient)]
    terms += [FormulaTerm("source_stat", s, c) for s, c in (extra or {}).items()]
    terms.append(FormulaTerm("target_stat", "defense", -defense))
    return ValueFormula(terms, minimum=1)


def hit(attack, at, length=0.1, **shape):
    return ActionCue(
        f"{attack}_{at}", at, "hitbox", {"duration": length, "hit_tag": attack, **shape}
    )


def move(name, at, speed, duration, *, relative="aim", x=1, y=0):
    payload = {"x": x, "y": y, "relative": relative, "speed": speed, "duration": duration}
    return ActionCue(name, at, "movement", payload)


def shoot(name, at, projectile, **extra):
    return ActionCue(name, at, "projectile", {"projectile_id": projectile, "aim": True, **extra})


def end(timeline_id, at):
    return ActionCue(f"{timeline_id}_end", at, "gameplay_event", {"name": "end"})


def anim(at, clip="attack"):
    return ActionCue(f"anim_{clip}_{at}", at, "animation", {"clip": clip})


# -- combat content -------------------------------------------------------------------------------
def combat_content(project, looks, icons):
    library = project.gameplay_library
    states = (
        StateDefinition(
            "healing",
            3.0,
            periodic=(
                PeriodicEffect(
                    0.5, Effect("healing.tick", (EffectOperation("resource_delta", "hp", 14),))
                ),
            ),
            contributed_tags=("status.healing",),
            display_name="Healing",
            icon_id=icons["state_healing"],
        ),
        StateDefinition(
            "war_cry",
            8.0,
            modifiers=(
                StatModifier("war_cry.power", "power", "multiply", 1.35),
                StatModifier("war_cry.defense", "defense", "add", 6),
            ),
            contributed_tags=("status.war_cry",),
            display_name="War Cry",
            icon_id=icons["state_war_cry"],
        ),
        StateDefinition(
            "burning",
            3.0,
            periodic=(
                PeriodicEffect(
                    0.5, Effect("burning.tick", (EffectOperation("resource_delta", "hp", -3),))
                ),
            ),
            contributed_tags=("status.burning",),
            display_name="Burning",
            icon_id=icons["state_burning"],
        ),
        StateDefinition(
            "bleeding",
            4.0,
            periodic=(
                PeriodicEffect(
                    1.0, Effect("bleeding.tick", (EffectOperation("resource_delta", "hp", -4),))
                ),
            ),
            contributed_tags=("status.bleeding",),
            display_name="Bleeding",
            icon_id=icons["state_bleeding"],
        ),
        StateDefinition(
            "chilled",
            3.0,
            modifiers=(StatModifier("chilled.power", "power", "multiply", 0.6),),
            contributed_tags=("status.chilled",),
            display_name="Chilled",
            icon_id=icons["state_chilled"],
        ),
    )
    for state in states:
        library.add_state(state)

    attacks = (
        # the hero
        AttackDefinition("punch", damage=scaled("power", 0.6), knockback=60, hitstun=0.1),
        AttackDefinition(
            "w_cut",
            damage=scaled("power", 1.0),
            knockback=80,
            hitstun=0.18,
            poise_damage=12,
            hitstop=0.04,
            critical_chance_stat="dexterity",
        ),
        AttackDefinition(
            "w_finisher",
            damage=scaled("power", 1.8),
            knockback=230,
            knockdown=True,
            poise_damage=35,
            hitstop=0.08,
            critical_chance_stat="dexterity",
            apply_states=[{"state": "bleeding", "chance": 0.5}],
        ),
        AttackDefinition(
            "w_whirl",
            damage=scaled("power", 1.2),
            knockback=160,
            hitstun=0.2,
            poise_damage=18,
            hitstop=0.03,
        ),
        AttackDefinition(
            "w_leap",
            damage=scaled("power", 2.2),
            knockback=260,
            knockdown=True,
            poise_damage=50,
            hitstop=0.1,
            hitstop_scope="global",
            armor_break=1,
        ),
        AttackDefinition(
            "r_arrow",
            damage=scaled("dexterity", 0.9, extra={"power": 0.3}),
            knockback=50,
            hitstun=0.1,
            critical_chance_stat="dexterity",
            critical_multiplier=2.0,
        ),
        AttackDefinition(
            "r_pierce",
            damage=scaled("dexterity", 1.6, extra={"power": 0.4}),
            knockback=120,
            poise_damage=20,
            critical_chance_stat="dexterity",
            critical_multiplier=2.0,
        ),
        AttackDefinition(
            "m_fire",
            damage=scaled("magic", 1.1, defense=0.2, extra={"fire_dmg": 1.0}),
            tags=["Element.Fire"],
            apply_states=[{"state": "burning", "chance": 0.35}],
        ),
        AttackDefinition(
            "m_frost",
            damage=scaled("magic", 0.9, defense=0.2, extra={"cold_dmg": 1.0}),
            tags=["Element.Ice"],
            knockback=200,
            hitstun=0.4,
            apply_states=[{"state": "chilled"}],
        ),
        AttackDefinition(
            "m_meteor",
            damage=scaled("magic", 2.6, defense=0.2, extra={"fire_dmg": 1.0}),
            tags=["Element.Fire"],
            knockback=240,
            knockdown=True,
            poise_damage=60,
            hitstop=0.08,
            apply_states=[{"state": "burning"}],
        ),
        # monsters
        AttackDefinition("slime_bite", damage=scaled("power", 1.0), knockback=70, hitstun=0.12),
        AttackDefinition("eye_beam", damage=scaled("power", 1.0), knockback=40, hitstun=0.08),
        AttackDefinition(
            "skull_slash", damage=scaled("power", 1.1), knockback=110, hitstun=0.2, hitstop=0.04
        ),
        AttackDefinition(
            "cyclops_smash",
            damage=scaled("power", 1.6),
            knockback=260,
            knockdown=True,
            hitstop=0.1,
            hitstop_scope="global",
            armor_break=1,
        ),
        AttackDefinition("cyclops_rock", damage=scaled("power", 0.9), knockback=80),
        AttackDefinition("walker_bump", damage=scaled("power", 1.0), knockback=120, hitstun=0.1),
        AttackDefinition("drone_bolt", damage=scaled("power", 1.0), knockback=40),
        AttackDefinition(
            "golem_slam",
            damage=scaled("power", 1.5),
            knockback=240,
            knockback_lift=160,
            knockdown=True,
            hitstop=0.1,
            hitstop_scope="global",
            armor_break=1,
        ),
    )
    for attack in attacks:
        library.add_attack(attack)

    projectiles = (
        ProjectileDefinition(
            "arrow", attack_id="r_arrow", speed=320, lifetime=0.8, sprite=looks["arrow"]
        ),
        ProjectileDefinition(
            "piercing_arrow",
            attack_id="r_pierce",
            speed=420,
            lifetime=0.9,
            pierce=-1,
            width=10,
            height=10,
            sprite=looks["arrow"],
        ),
        ProjectileDefinition(
            "fire_bolt",
            attack_id="m_fire",
            speed=240,
            lifetime=1.2,
            homing_turn=260,
            homing_range=120,
            sprite=looks["fireball"],
        ),
        ProjectileDefinition(
            "meteor",
            attack_id="m_meteor",
            speed=150,
            lifetime=1.4,
            width=26,
            height=26,
            pierce=-1,
            sprite=looks["fireball_big"],
        ),
        ProjectileDefinition(
            "eye_bolt", attack_id="eye_beam", speed=150, lifetime=1.6, sprite=looks["orb"]
        ),
        ProjectileDefinition(
            "rock", attack_id="cyclops_rock", speed=170, lifetime=1.5, sprite=looks["rock"]
        ),
        ProjectileDefinition(
            "drone_bolt", attack_id="drone_bolt", speed=170, lifetime=1.8, sprite=looks["orb"]
        ),
    )
    for projectile in projectiles:
        library.add_projectile(projectile)

    timelines = (
        ActionTimeline("punch", [anim(0.0), hit("punch", 0.05), end("punch", 0.28)]),
        # warrior: a three-hit combo, whirlwind, a leaping strike, a war cry
        ActionTimeline(
            "w_slash1",
            [
                anim(0.0),
                hit("w_cut", 0.06, width=26, height=20, offset_x=14),
                ActionCue("c1", 0.12, "combo_window", {"duration": 0.25, "next": "w_slash2"}),
                end("w_slash1", 0.3),
            ],
        ),
        ActionTimeline(
            "w_slash2",
            [
                anim(0.0),
                hit("w_cut", 0.06, width=26, height=20, offset_x=14),
                ActionCue("c2", 0.12, "combo_window", {"duration": 0.25, "next": "w_slash3"}),
                end("w_slash2", 0.3),
            ],
        ),
        ActionTimeline(
            "w_slash3",
            [
                anim(0.0),
                move("lunge", 0.0, 170, 0.1, relative="facing"),
                hit("w_finisher", 0.1, 0.12, width=32, height=24, offset_x=16),
                end("w_slash3", 0.45),
            ],
        ),
        ActionTimeline(
            "w_whirl",
            [
                ActionCue("armor", 0.0, "armor", {"duration": 0.55}),
                anim(0.0),
                hit("w_whirl", 0.05, 0.12, width=56, height=56, offset_x=0, offset_y=0),
                hit("w_whirl", 0.25, 0.12, width=56, height=56, offset_x=0, offset_y=0),
                end("w_whirl", 0.55),
            ],
        ),
        ActionTimeline(
            "w_leap",
            [
                ActionCue("iframes", 0.0, "iframe", {"duration": 0.3}),
                anim(0.0),
                move("leap", 0.0, 260, 0.25),
                hit("w_leap", 0.25, 0.12, width=48, height=40, offset_x=8),
                end("w_leap", 0.6),
            ],
        ),
        ActionTimeline(
            "w_shout",
            [
                anim(0.0),
                ActionCue(
                    "cry", 0.1, "gameplay_event", {"name": "war_cry", "apply_state": "war_cry"}
                ),
                end("w_shout", 0.4),
            ],
        ),
        # ranger: arrows (more with Multishot), a volley, a piercing shot, a tumble
        ActionTimeline(
            "r_shot",
            [
                anim(0.0),
                shoot("loose", 0.08, "arrow", count_stat="multishot", spread=24),
                end("r_shot", 0.3),
            ],
        ),
        ActionTimeline(
            "r_volley",
            [anim(0.0), shoot("volley", 0.1, "arrow", count=7, spread=70), end("r_volley", 0.45)],
        ),
        ActionTimeline(
            "r_pierce",
            [
                anim(0.0),
                ActionCue("steady", 0.0, "armor", {"duration": 0.3}),
                shoot("pierce", 0.25, "piercing_arrow"),
                end("r_pierce", 0.5),
            ],
        ),
        ActionTimeline(
            "r_tumble",
            [
                ActionCue("iframes", 0.0, "iframe", {"duration": 0.3}),
                move("tumble", 0.0, 230, 0.2, x=-1),
                shoot("parting", 0.22, "arrow", count=3, spread=30),
                end("r_tumble", 0.4),
            ],
        ),
        # mage: a homing fire bolt, a frost nova, a meteor, a blink
        ActionTimeline(
            "m_bolt", [anim(0.0), shoot("cast", 0.1, "fire_bolt", offset_x=6), end("m_bolt", 0.3)]
        ),
        ActionTimeline(
            "m_nova",
            [
                anim(0.0),
                hit("m_frost", 0.08, 0.15, width=80, height=80, offset_x=0, offset_y=0),
                end("m_nova", 0.45),
            ],
        ),
        ActionTimeline(
            "m_meteor",
            [
                ActionCue("focus", 0.0, "armor", {"duration": 0.4}),
                anim(0.0),
                shoot("meteor", 0.35, "meteor"),
                end("m_meteor", 0.6),
            ],
        ),
        ActionTimeline(
            "m_blink",
            [
                ActionCue("iframes", 0.0, "iframe", {"duration": 0.2}),
                move("blink", 0.0, 600, 0.12),
                end("m_blink", 0.2),
            ],
        ),
        # everyone
        ActionTimeline(
            "roll",
            [
                move("dash", 0.0, 230, 0.22),
                ActionCue("iframes", 0.0, "iframe", {"duration": 0.3}),
                end("roll", 0.3),
            ],
        ),
        ActionTimeline(
            "potion",
            [
                ActionCue(
                    "drink", 0.05, "gameplay_event", {"name": "potion", "apply_state": "healing"}
                ),
                end("potion", 0.25),
            ],
        ),
        # monsters
        ActionTimeline("slime_bite", [hit("slime_bite", 0.25, 0.12), end("slime_bite", 0.6)]),
        ActionTimeline("eye_shot", [shoot("beam", 0.3, "eye_bolt"), end("eye_shot", 0.6)]),
        ActionTimeline(
            "skull_slash",
            [
                move("step", 0.0, 90, 0.15, relative="facing"),
                hit("skull_slash", 0.2, 0.12, width=24, height=20, offset_x=12),
                end("skull_slash", 0.6),
            ],
        ),
        ActionTimeline(
            "cyclops_smash",
            [
                ActionCue("armor", 0.0, "armor", {"duration": 1.0}),
                hit("cyclops_smash", 0.55, 0.15, width=64, height=56, offset_x=10),
                end("cyclops_smash", 1.0),
            ],
        ),
        ActionTimeline(
            "cyclops_throw",
            [shoot("throw", 0.35, "rock", count=3, spread=40), end("cyclops_throw", 0.8)],
        ),
        ActionTimeline(
            "walker_bump",
            [
                move("charge", 0.0, 120, 0.25, relative="facing"),
                hit("walker_bump", 0.1, 0.15),
                end("walker_bump", 0.6),
            ],
        ),
        ActionTimeline("drone_shot", [shoot("zap", 0.3, "drone_bolt"), end("drone_shot", 0.7)]),
        ActionTimeline(
            "golem_slam",
            [
                ActionCue("armor", 0.0, "armor", {"duration": 1.0}),
                move("hop", 0.0, 110, 0.3, relative="facing"),
                hit("golem_slam", 0.45, 0.15, width=70, height=40, offset_x=8),
                end("golem_slam", 1.0),
            ],
        ),
        ActionTimeline(
            "golem_volley",
            [shoot("spray", 0.3, "drone_bolt", count=5, spread=60), end("golem_volley", 0.8)],
        ),
    )
    for timeline in timelines:
        library.add_timeline(timeline)

    mp = lambda n: [AbilityCost("mp", n)]  # noqa: E731
    abilities = (
        AbilityDefinition("punch", timeline_id="punch"),
        AbilityDefinition("w_slash", timeline_id="w_slash1"),
        AbilityDefinition("w_whirl", timeline_id="w_whirl", cooldown_seconds=1.2, costs=mp(6)),
        AbilityDefinition("w_leap", timeline_id="w_leap", cooldown_seconds=3.0, costs=mp(10)),
        AbilityDefinition("w_shout", timeline_id="w_shout", cooldown_seconds=12.0, costs=mp(12)),
        AbilityDefinition("r_shot", timeline_id="r_shot"),
        AbilityDefinition("r_volley", timeline_id="r_volley", cooldown_seconds=2.0, costs=mp(8)),
        AbilityDefinition("r_pierce", timeline_id="r_pierce", cooldown_seconds=1.5, costs=mp(6)),
        AbilityDefinition(
            "r_tumble",
            timeline_id="r_tumble",
            cooldown_seconds=2.5,
            costs=mp(5),
            interrupts_actions=True,
        ),
        AbilityDefinition("m_bolt", timeline_id="m_bolt", cooldown_seconds=0.35, costs=mp(1)),
        AbilityDefinition("m_nova", timeline_id="m_nova", cooldown_seconds=2.5, costs=mp(12)),
        AbilityDefinition("m_meteor", timeline_id="m_meteor", cooldown_seconds=4.0, costs=mp(20)),
        AbilityDefinition(
            "m_blink",
            timeline_id="m_blink",
            cooldown_seconds=1.5,
            costs=mp(6),
            interrupts_actions=True,
        ),
        AbilityDefinition(
            "roll", timeline_id="roll", cooldown_seconds=0.6, interrupts_actions=True
        ),
        AbilityDefinition(
            "potion",
            timeline_id="potion",
            cooldown_seconds=4.0,
            costs=[AbilityCost("item:potion", 1)],
        ),
        AbilityDefinition("slime_bite", timeline_id="slime_bite", cooldown_seconds=1.0),
        AbilityDefinition("eye_shot", timeline_id="eye_shot", cooldown_seconds=1.8),
        AbilityDefinition("skull_slash", timeline_id="skull_slash", cooldown_seconds=1.2),
        AbilityDefinition("cyclops_smash", timeline_id="cyclops_smash", cooldown_seconds=3.0),
        AbilityDefinition("cyclops_throw", timeline_id="cyclops_throw", cooldown_seconds=2.5),
        AbilityDefinition("walker_bump", timeline_id="walker_bump", cooldown_seconds=1.4),
        AbilityDefinition("drone_shot", timeline_id="drone_shot", cooldown_seconds=1.6),
        AbilityDefinition("golem_slam", timeline_id="golem_slam", cooldown_seconds=3.0),
        AbilityDefinition("golem_volley", timeline_id="golem_volley", cooldown_seconds=3.5),
    )
    for ability in abilities:
        data = ability.to_data()
        if ability.ability_id in LABELS:  # a name and a picture for the action bar
            data["display_name"] = LABELS[ability.ability_id]
            if ability.ability_id in icons:
                data["icon_id"] = icons[ability.ability_id]
        library.add_ability(AbilityDefinition.from_data(data))
    LABELS.update(builds.register(library, looks))  # the skills of the three builds per class
    builds.add_effects(library, looks)  # spell and strike pictures on every skill
    builds.assign_animations(library)  # the three attack strips and the jump, by skill


LABELS = {
    "punch": "Punch",
    "w_slash": "Slash",
    "w_whirl": "Whirl",
    "w_leap": "Leap",
    "w_shout": "War Cry",
    "r_shot": "Shoot",
    "r_volley": "Volley",
    "r_pierce": "Pierce",
    "r_tumble": "Tumble",
    "m_bolt": "Firebolt",
    "m_nova": "Nova",
    "m_meteor": "Meteor",
    "m_blink": "Blink",
    "roll": "Roll",
    "potion": "Potion",
}


# -- classes, skill trees, the hero ---------------------------------------------------------------
def node(node_id, name, *, ranks=1, cost=1, stats=None, resources=None, abilities=(), needs=()):
    reward = ProgressionNodeReward(
        stat_bonuses=stats or {}, resource_bonuses=resources or {}, granted_abilities=abilities
    )
    return ProgressionNodeDefinition(
        node_id,
        name,
        max_rank=ranks,
        rank_costs={"ap": cost},
        rewards=reward,
        prerequisites=[ProgressionNodeRequirement(n) for n in needs],
    )


def classes_and_trees(db):
    db.add_class(ClassDefinition("adventurer", "Adventurer", granted_abilities=("punch",)))
    db.add_class(
        ClassDefinition(
            "warrior",
            "Warrior",
            stat_bonuses={"power": 8, "defense": 6},
            resource_bonuses={"hp": 80, "mp": 10},
            granted_tags=("class.warrior",),
            granted_abilities=("w_slash",),
        )
    )
    db.add_class(
        ClassDefinition(
            "ranger",
            "Ranger",
            stat_bonuses={"dexterity": 10, "power": 3, "defense": 2},
            resource_bonuses={"hp": 40, "mp": 20},
            granted_tags=("class.ranger",),
            granted_abilities=("r_shot",),
        )
    )
    db.add_class(
        ClassDefinition(
            "mage",
            "Mage",
            stat_bonuses={"magic": 12, "defense": 1},
            resource_bonuses={"hp": 20, "mp": 70},
            granted_tags=("class.mage",),
            granted_abilities=("m_bolt",),
        )
    )
    db.add_ability_loadout_rules(  # skill slots: more of them as the hero levels up
        AbilityLoadoutRules(
            "skill_slots",
            2,
            capacity_by_level={3: 3, 5: 4, 8: 5, 12: 6},
            limited_sources=("allocation", "learned"),
        )
    )
    builds.add_trees(db, LABELS)  # three builds per class, each a column of skills
    attributes = [
        (node("a_str", "Strength", ranks=10, stats={"power": 2}), (-240, 0)),
        (node("a_dex", "Dexterity", ranks=10, stats={"dexterity": 2}), (-80, 0)),
        (node("a_int", "Intellect", ranks=10, stats={"magic": 2}), (80, 0)),
        (node("a_vit", "Vitality", ranks=10, resources={"hp": 12}), (240, 0)),
        (node("a_spi", "Spirit", ranks=10, resources={"mp": 8}), (0, 100)),
    ]
    db.add_progression_graph(
        ProgressionGraphDefinition(
            "attributes",
            "Attributes",
            nodes=[n for n, _ in attributes],
            tags=("shared",),
            editor_view="graph",
            node_positions={n.node_id: p for n, p in attributes},
        )
    )
    db.add_actor(
        ActorDefinition(
            HERO,
            "Wanderer",
            class_id="adventurer",
            base_stats={
                "power": 10,
                "magic": 10,
                "defense": 4,
                "dexterity": 6,
                "multishot": 0,
                **dict.fromkeys(builds.BUILD_STATS, 0),
            },
            base_resources={
                "hp": {"minimum": 0, "maximum": 120, "current": 120},
                "mp": {"minimum": 0, "maximum": 40, "current": 40},
            },
            abilities=("roll", "potion"),
        )
    )


# -- loot -----------------------------------------------------------------------------------------
def loot_content(db, icons):
    loot.register(db, icons)  # gear, sets, rarities, affixes, drop tables
    for item_id, name in (
        ("potion", "Healing Potion"),
        ("slime_gel", "Slime Gel"),
        ("bone_shard", "Bone Shard"),
        ("eye_lens", "Eye Lens"),
        ("gear_scrap", "Gear Scrap"),
    ):
        db.add_item(ItemDefinition(item_id, name, stack_limit=99, icon_id=icons.get(item_id, "")))
    db.add_shop(
        ShopDefinition(
            "merchant",
            "Mira's Goods",
            entries=(
                ShopEntry("potion", buy_prices={"gold": 25}, sell_prices={"gold": 8}),
                ShopEntry("slime_gel", sell_prices={"gold": 4}),
                ShopEntry("bone_shard", sell_prices={"gold": 7}),
                ShopEntry("eye_lens", sell_prices={"gold": 9}),
                ShopEntry("gear_scrap", sell_prices={"gold": 10}),
            ),
        )
    )
    for recipe_id, name, inputs in (
        ("brew_gel", "Potion from Slime Gel", ("slime_gel", "slime_gel", "slime_gel")),
        ("brew_lens", "Potion from Eye Lenses", ("eye_lens", "eye_lens")),
        ("brew_scrap", "Potion from Gear Scrap", ("gear_scrap", "gear_scrap")),
    ):
        db.add_composition_recipe(
            CompositionRecipeDefinition(
                recipe_id,
                name,
                selections=[
                    CompositionSelection(f"{recipe_id}.{i}", (x,)) for i, x in enumerate(inputs)
                ],
                outputs=[CompositionOutput("potion", 1)],
                station="smith",
            )
        )


# -- enemies' minds -------------------------------------------------------------------------------
def n(kind, *children, **params):
    return BehaviorNode(kind, params, tuple(children))


def behaviour(db):
    trees = (
        BehaviorTree(
            "melee_grunt",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=18),
                    n("use_ability", ability="slime_bite", wait=True),
                ),
                n("sequence", n("player_within", radius=110), n("chase", arrive=12)),
                n("wander", radius=28),
            ),
        ),
        BehaviorTree(
            "shooter",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=140),
                    n("keep_distance", min=60, max=100),
                    n("use_ability", ability="eye_shot"),
                ),
                n("wander", radius=20),
            ),
        ),
        BehaviorTree(
            "elite",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=22),
                    n("use_ability", ability="skull_slash", wait=True),
                ),
                n("sequence", n("player_within", radius=140), n("chase", arrive=16)),
                n("wander", radius=24),
            ),
        ),
        BehaviorTree(
            "cyclops",
            n(
                "selector",
                n(
                    "sequence",
                    n("hp_below", fraction=0.5),
                    n("player_within", radius=40),
                    n("ability_ready", ability="cyclops_smash"),
                    n("use_ability", ability="cyclops_smash", wait=True),
                ),
                n(
                    "sequence",
                    n("player_within", radius=30),
                    n("use_ability", ability="cyclops_smash", wait=True),
                ),
                n(
                    "sequence",
                    n("player_within", radius=150),
                    n("ability_ready", ability="cyclops_throw"),
                    n("use_ability", ability="cyclops_throw", wait=True),
                ),
                n("sequence", n("player_within", radius=170), n("chase", arrive=24)),
            ),
        ),
        BehaviorTree(
            "walker",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=24),
                    n("use_ability", ability="walker_bump", wait=True),
                ),
                n("sequence", n("player_within", radius=90), n("chase", arrive=14)),
                n("side_patrol"),
            ),
        ),
        BehaviorTree(
            "drone",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=150),
                    n("face_player"),
                    n("use_ability", ability="drone_shot"),
                ),
                n("side_patrol"),
            ),
        ),
        BehaviorTree(
            "golem",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=40),
                    n("ability_ready", ability="golem_slam"),
                    n("use_ability", ability="golem_slam", wait=True),
                ),
                n(
                    "sequence",
                    n("hp_below", fraction=0.6),
                    n("ability_ready", ability="golem_volley"),
                    n("use_ability", ability="golem_volley", wait=True),
                ),
                n("sequence", n("player_within", radius=200), n("chase", arrive=30)),
            ),
        ),
    )
    for tree in trees:
        db.add_behavior_tree(tree)


# -- scenes ---------------------------------------------------------------------------------------
class SceneBuilder:
    def __init__(self, project, key, name):
        self.project, self.key = project, key
        self.scene = Scene(name, scene_id=art.asset_id("scene", key))
        self.programs = SceneEventBindings()
        project.add_scene(self.scene)

    def entity(self, name, x, y):
        entity = Entity(name, entity_id=art.asset_id("entity", self.key, name))
        entity.add_component(Transform(x, y))
        return self.scene.add_entity(entity)

    def look(self, entity, sheet, clips):
        entity.add_component(_set(SpriteRenderer2D(), sprite_sheet_asset_id=sheet))
        entity.add_component(_set(Animator2DComponent(), clip_set_id=clips))

    def setup(self, tilemap, *, view, zoom=3.0, background=""):
        holder = self.entity("Map", -40, -8)
        holder.add_component(_set(TileMap2DComponent(), tilemap_asset_id=tilemap))
        camera = self.entity("Camera", -40, 24)  # holders sit apart outside the map
        camera.add_component(_set(Camera2DComponent(), width=320, height=180, zoom=zoom))
        settings = self.entity("Combat Scene", -40, 56)
        settings.add_component(
            _set(
                CombatSceneComponent(),
                combat_mode="action",
                view=view,
                on_player_death="respawn",
                respawn_delay=2.5,
                camera_look_ahead=36.0 if view == "topdown" else 48.0,
                background_color=background,  # behind the map (the cave's darkness)
            )
        )

    def program(self, entity, program_id, instructions, *, trigger="action", radius=20.0):
        self.project.event_programs.register(
            program_id, EventProgram((*instructions, EventInstruction("END")), name=program_id)
        )
        self.programs.add(
            EventBinding(
                f"{program_id}.binding", entity.id, program_id, trigger=EventTriggerKind.ACTION
            )
        )
        entity.add_component(
            _set(
                Interaction2DComponent(),
                event_binding_id=f"{program_id}.binding",
                event_program_id=program_id,
                range=radius,
                require_facing=trigger == "action",
                trigger=trigger,
            )
        )

    def finish(self):
        self.project.scene_event_bindings[self.scene.id] = self.programs


def say(speaker, text):
    return EventInstruction("DIALOGUE", {"speaker": speaker, "text": text})


def world(command, **args):
    return EventInstruction("WORLD", {"command": command, "args": args})


def door(builder, name, x, y, scene_id, to, facing):
    entity = builder.entity(name, x, y)
    builder.program(
        entity,
        f"door.{builder.key}.{name.lower().replace(' ', '_')}",
        [world("TRANSFER", scene_id=scene_id, x=to[0], y=to[1], facing=facing)],
        trigger="touch",
        radius=14.0,
    )
    return entity


def npc(builder, name, xy, look, *, solid=True):
    entity = builder.entity(name, *xy)
    builder.look(entity, *look)
    if solid:
        entity.add_component(_set(Collider2DComponent(), width=12, height=12))
    return entity


def enemy(
    builder,
    name,
    xy,
    look,
    tree,
    *,
    view,
    hp,
    power,
    defense=2,
    speed=34.0,
    size=(6, 6),
    hit=(18, 14, 10),
    team="foe",
    gravity=None,
    **combatant,
):
    entity = builder.entity(name, *xy)
    builder.look(entity, *look)
    controller = _set(
        CharacterController2DComponent(),
        mode=view,
        speed=speed,
        half_width=float(size[0]),
        half_height=float(size[1]),
        facing="left",
    )
    if gravity is not None:
        controller.gravity = gravity
    entity.add_component(controller)
    entity.add_component(_set(AIController2DComponent(), driver="behavior_tree", tree_id=tree))
    entity.add_component(
        _set(Hurtbox2DComponent(), team=team, width=size[0] * 2 + 2, height=size[1] * 2 + 2)
    )
    entity.add_component(
        _set(
            Hitbox2DComponent(),
            team=team,
            width=hit[0],
            height=hit[1],
            offset_x=hit[2],
            follow_facing=True,
        )
    )
    entity.add_component(
        _set(
            CombatantComponent(),
            team=team,
            resources=f"hp={hp}",
            stats=f"power={power}, defense={defense}",
            **combatant,
        )
    )
    return entity


def player(builder, xy, look, looks):
    hero = builder.entity("Player", *xy)
    builder.look(hero, *look)
    hero.add_component(
        _set(
            CharacterController2DComponent(),
            speed=72.0,
            half_width=5.0,
            half_height=7.0,
            facing="down",
            coyote_time=0.1,
            jump_buffer=0.12,
            jump_cut=0.45,
            jump_speed=230.0,
            climb_speed=60.0,
        )
    )
    hero.add_component(PlayerInput2DComponent())
    hero.add_component(_set(ActorLinkComponent(), actor_id=HERO))
    # each class has its own look (the engine swaps it when the class changes)
    hero.add_component(
        _set(
            ClassAppearanceComponent(),
            looks="; ".join(
                f"{class_id}={looks[f'trainer_{class_id}'][0]}|{looks[f'trainer_{class_id}'][1]}"
                for class_id in CLASSES
            ),
        )
    )
    hero.add_component(
        _set(
            CombatantComponent(),
            team="hero",
            regen="mp=4",
            hitstun_rule="unless_poise",
            poise=25,
            poise_recovery=12,
        )
    )
    hero.add_component(_set(Hurtbox2DComponent(), team="hero", width=10, height=14))
    hero.add_component(
        _set(
            Hitbox2DComponent(), team="hero", width=22, height=16, offset_x=12, follow_facing=True
        )
    )
    hero.add_component(
        _set(
            ActionCombatComponent(),
            bindings=(
                "attack=w_slash|r_shot|m_bolt|punch; dodge=roll; potion=potion; "
                "skill_1=slot:1; skill_2=slot:2; skill_3=slot:3; skill_4=slot:4; "
                "skill_5=slot:5; skill_6=slot:6"
            ),
            require_known=True,
            lock_mode="nearest",
            lock_range=120.0,
        )
    )
    hero.add_component(_set(LooterComponent(), auto_pickup="currency", pickup_radius=22.0))
    return hero


def build_scenes(project, looks, tilemaps, layouts, backdrops):
    town_l, field_l, dungeon_l = layouts["town"], layouts["field"], layouts["dungeon"]
    town = SceneBuilder(project, "town", "Hollowbrook")
    field = SceneBuilder(project, "field", "Greenvale Fields")
    dungeon = SceneBuilder(project, "dungeon", "Rustdeep Mine")

    # -- town --------------------------------------------------------------------------------
    town.setup(tilemaps["town"], view="topdown")
    hero = player(town, town_l["start"], looks["hero"], looks)
    merchant = npc(town, "Mira the Merchant", town_l["merchant"], looks["merchant"])
    town.program(
        merchant,
        "npc.merchant",
        [
            say("Mira", "Monster parts, potions - I trade in both. Gold for your trophies!"),
            world("OPEN_SHOP", shop_id="merchant"),
        ],
    )
    smith = npc(town, "Brann the Smith", town_l["smith"], looks["smith"])
    town.program(
        smith,
        "npc.smith",
        [
            say("Brann", "Bring me gel, lenses or scrap and I'll brew you a potion."),
            world("OPEN_CRAFTING", station="smith"),
        ],
    )
    for (class_id, title, line), xy in zip(
        (
            ("warrior", "Warrior", "Steel and nerve. Stand your ground and cleave through them."),
            ("ranger", "Ranger", "Keep your distance; let your arrows speak."),
            ("mage", "Mage", "Fire, frost and a quick step - power has a price in mana."),
        ),
        town_l["trainers"],
        strict=True,
    ):
        trainer = npc(town, f"{title} Trainer", xy, looks[f"trainer_{class_id}"])
        town.program(
            trainer,
            f"npc.trainer.{class_id}",
            [
                say(f"{title} Trainer", line),
                world("SET_CLASSES", class_ids=class_id),
                world("SHOW_POPUP", text=f"You are now a {title}!", kind="item"),
                say(
                    f"{title} Trainer",
                    "Press C to open your skill tree. Every level brings two skill points.",
                ),
            ],
        )
    elder = npc(town, "Elder Oswin", town_l["elder"], looks["elder"])
    town.program(
        elder,
        "npc.elder",
        [
            say("Elder Oswin", "Slimes and worse roam the fields east of here."),
            say(
                "Elder Oswin", "A one-eyed brute rules the clearing; past the gate lies the mine."
            ),
            say("Elder Oswin", "Choose a calling from our trainers, and take these potions."),
            world("GIVE_ITEM", item_id="potion", quantity=2),
        ],
    )
    for index, xy in enumerate(town_l["villagers"]):
        villager = npc(town, f"Villager {index + 1}", xy, looks["villager"])
        town.program(
            villager,
            f"npc.villager.{index + 1}",
            [
                say(
                    "Villager",
                    ("Lovely day.", "The smith brews a fine potion.", "Sell your loot to Mira!")[
                        index % 3
                    ],
                )
            ],
        )
    door(town, "Road East", *town_l["to_field"], field.scene.id, field_l["from_town"], "right")
    town.finish()

    # -- field -------------------------------------------------------------------------------
    field.setup(tilemaps["field"], view="topdown")
    door(field, "Road West", *field_l["to_town"], town.scene.id, town_l["from_field"], "left")
    door(
        field,
        "Mine Gate",
        *field_l["to_dungeon"],
        dungeon.scene.id,
        dungeon_l["from_field"],
        "right",
    )
    common = dict(view="topdown", loot_level=2, currency_drop="gold=1-5")
    for i, xy in enumerate(field_l["slimes"]):
        enemy(
            field,
            f"Slime {i + 1}",
            xy,
            looks["slime"],
            "melee_grunt",
            hp=40,
            power=7,
            experience=60,
            drop_table_id="slime",
            **common,
        )
    for i, xy in enumerate(field_l["eyes"]):
        enemy(
            field,
            f"Watcher {i + 1}",
            xy,
            looks["eye"],
            "shooter",
            hp=32,
            power=8,
            experience=80,
            drop_table_id="eye",
            **common,
        )
    elite = dict(view="topdown", loot_level=5, loot_luck=1.0, currency_drop="gold=8-16")
    enemy(
        field,
        "Bone Champion",
        field_l["elite"],
        looks["skull_elite"],
        "elite",
        hp=220,
        power=14,
        defense=6,
        speed=40.0,
        poise=40,
        poise_recovery=20,
        armor=0,
        stagger_result="knocked_down",
        experience=500,
        defeat_switch="defeated.bone_champion",
        drop_table_id="elite",
        **elite,
    )
    for i, xy in enumerate(field_l["skulls"]):
        enemy(
            field,
            f"Skeleton {i + 1}",
            xy,
            looks["skull"],
            "elite",
            hp=70,
            power=10,
            defense=3,
            experience=120,
            drop_table_id="skull",
            **common,
        )
    enemy(
        field,
        "Gorgoth the Cyclops",
        field_l["boss"],
        looks["cyclops"],
        "cyclops",
        hp=900,
        power=18,
        defense=8,
        speed=30.0,
        size=(14, 14),
        hit=(40, 32, 18),
        poise=120,
        poise_recovery=30,
        stagger_result="knocked_down",
        knockback_resistance=0.6,
        experience=2500,
        defeat_switch="defeated.gorgoth",
        drop_table_id="cyclops",
        loot_level=9,
        loot_luck=2.0,
        currency_drop="gold=80-140",
        view="topdown",
    )
    field.finish()

    # -- dungeon (side view) -----------------------------------------------------------------
    dungeon.setup(tilemaps["dungeon"], view="side", background="#1c2230")
    # two scrolling cave silhouettes behind the tiles (the far one moves less than the near one)
    for name, texture, factor, scale, lift in (
        ("Far Hills", backdrops[0], 0.12, 3.0, 40.0),
        ("Near Hills", backdrops[1], 0.3, 3.0, 0.0),
    ):
        back = dungeon.entity(name, -40, 88 if lift else 120)
        back.add_component(
            _set(
                ParallaxBackground2DComponent(),
                texture_asset_id=texture,
                factor_x=factor,
                scale=scale,
                anchor="bottom",
                offset_y=-lift,
            )
        )
    door(
        dungeon,
        "Mine Exit",
        *dungeon_l["to_field"],
        field.scene.id,
        field_l["from_dungeon"],
        "left",
    )
    for i, (x, y, w, h) in enumerate(dungeon_l["platforms"]):
        ledge = dungeon.entity(f"Ledge {i + 1}", x, y)
        ledge.add_component(_set(Collider2DComponent(), width=w, height=h, one_way=True))
    for i, (x, y, w, h) in enumerate(dungeon_l["ladders"]):
        ladder = dungeon.entity(f"Ladder {i + 1}", x, y)
        ladder.add_component(_set(Collider2DComponent(), width=w, height=h, ladder=True))
    side = dict(view="side", loot_level=6, currency_drop="gold=3-9")
    for i, xy in enumerate(dungeon_l["walkers"]):
        enemy(
            dungeon,
            f"Crawler {i + 1}",
            xy,
            looks["walker"],
            "walker",
            hp=70,
            power=12,
            defense=4,
            speed=40.0,
            size=(8, 8),
            hit=(20, 16, 8),
            experience=150,
            drop_table_id="walker",
            **side,
        )
    for i, xy in enumerate(dungeon_l["bats"]):
        enemy(
            dungeon,
            f"Cave Bat {i + 1}",
            xy,
            looks["bat"],
            "drone",
            hp=40,
            power=10,
            speed=46.0,
            size=(8, 6),
            gravity=0.0,
            experience=120,
            drop_table_id="drone",
            **side,
        )
    for i, xy in enumerate([*dungeon_l["drills"], dungeon_l["drill_high"]]):
        enemy(
            dungeon,
            f"Drill Drone {i + 1}",
            xy,
            looks["drill"],
            "drone",
            hp=60,
            power=12,
            defense=5,
            speed=30.0,
            size=(8, 10),
            experience=160,
            drop_table_id="drone",
            **side,
        )
    enemy(
        dungeon,
        "Rust Golem",
        dungeon_l["boss"],
        looks["golem"],
        "golem",
        hp=1400,
        power=22,
        defense=10,
        speed=36.0,
        size=(20, 22),
        hit=(48, 40, 20),
        poise=160,
        poise_recovery=40,
        stagger_result="knocked_down",
        knockback_resistance=0.8,
        experience=4000,
        defeat_switch="defeated.rust_golem",
        drop_table_id="golem",
        loot_level=12,
        loot_luck=2.5,
        currency_drop="gold=150-260",
        view="side",
    )
    dungeon.finish()
    return town.scene, hero


# -- the new game ---------------------------------------------------------------------------------
def new_game(project, scene, hero):
    db = project.rpg_database
    loadout = EquipmentLoadout(
        tuple(EquipmentSlotDefinition(slot, capacity=1) for slot in loot.SLOTS)
    )
    inventory = Inventory()
    inventory.add("potion", 3)
    rpg = RpgRuntimeState(
        inventory=inventory,
        progression=ProgressionRuntime(db.progression_tracks.values()),
        loadouts={HERO: loadout},
        party_actor_ids=(HERO,),
        party_active_actor_ids=(HERO,),
        party_placements={HERO: "slot_1"},
        currencies={"gold": 40},
        progression_allocations={
            HERO: ProgressionAllocationRuntime(db.progression_graphs.values(), balances={"ap": 2})
        },
        actor_progression={
            HERO: ActorProgressionState(
                1, 0.0, unlocked_class_ids=("adventurer",), active_class_ids=("adventurer",)
            )
        },
    )
    hero_t = hero.get(Transform)
    project.game_start = GameStartDefinition(
        scene.id,
        hero.id,
        "down",
        (hero_t.x, hero_t.y),
        rpg.to_data(),
        None,
    )


PROJECT_ID = "09fb43ca-4bdc-4732-a3da-bee2d08c67ee"  # shared by both ARPG demos


# -- art ------------------------------------------------------------------------------------------
def make_art(assets):
    looks = {
        "hero": la.character(assets, "hero", "warrior", "Wanderer"),
        "merchant": la.character(assets, "merchant", "sorceress", "Merchant"),
        "smith": la.character(assets, "smith", "warrior", "Smith"),
        "elder": la.character(assets, "elder", "necromancer", "Elder"),
        "villager": la.character(assets, "villager", "cultist", "Villager"),
        "trainer_warrior": la.character(assets, "trainer_warrior", "warrior", "Warrior"),
        "trainer_ranger": la.character(assets, "trainer_ranger", "cultist", "Ranger"),
        "trainer_mage": la.character(assets, "trainer_mage", "sorceress", "Mage"),
        "slime": la.character(assets, "slime", "goblin_berserker", "Goblin", height=22),
        "eye": la.character(assets, "eye", "necromancer", "Watcher", height=24),
        "skull": la.character(assets, "skull", "skeleton_grunt", "Skeleton", height=26),
        "skull_elite": la.character(
            assets, "skull_elite", "skeleton_hunter", "Bone Champion", height=30
        ),
        "cyclops": la.character(assets, "cyclops", "skeleton_king", "Skeleton King", height=64),
        "walker": la.character(assets, "walker", "goblin_rider", "Crawler", height=22),
        "bat": la.character(assets, "bat", "goblin_slinger", "Cave Imp", height=20),
        "drill": la.character(assets, "drill", "skeleton_ancient", "Ancient Drone", height=24),
        "golem": la.character(assets, "golem", "goblin_beast", "Beast Golem", height=40),
        **{f"fx_{k}": v for k, v in la.effect_sheets(assets).items()},
        "arrow": la.arrow(assets),
    }
    fx = {k: v for k, v in looks.items() if k.startswith("fx_")}
    looks.update(  # shots and bolts are the Lucifer effect pictures
        fireball=fx["fx_fire_ball"],
        fireball_big=fx["fx_fire_ball"],
        orb=fx["fx_bolt_ball"],
        rock=fx["fx_rocks"],
    )
    return looks


def dress_in_lucifer(project):
    """The Lucifer UI skin and pixel font for the HUD and the host menus, and Lucifer icons for
    every skill, state, item and piece of gear (the pictures written first are dropped)."""
    import lucifer_reskin

    from asteria.presentation.battle_ui_renderer import BattleUiTheme

    library = project.battle_presentation_library
    if "default" not in library.ids("ui_theme"):
        library.set("ui_theme", "default", BattleUiTheme())
    reskin = lucifer_reskin.Reskin(project, HERE)
    reskin.ui()
    reskin.icons()
    la.node_icons(reskin, project)  # skill-tree nodes without a skill
    la.gear_icons(reskin, project, loot.ICON_FILES)  # a picture for every piece of gear
    gothic = la.gothic_ui(project, HERE)  # the ornate dark panels of Foozle's RPG UI Set 1
    db = project.rpg_database
    for item_id, picture in (("gear_scrap", "bag"), ("slime_gel", "coins")):
        if item_id in db.items:
            db.items[item_id] = dataclasses.replace(db.items[item_id], icon_id=gothic[picture])
    shutil.rmtree(HERE / art.OUT / "icons", ignore_errors=True)


def main():
    target = HERE / art.OUT
    if target.exists():
        shutil.rmtree(target)
    project = Project("Asteria ARPG Multiplayer Demo", project_id=PROJECT_ID)
    assets = art.Assets(project)
    art.write_credits()
    looks = make_art(assets)
    overworld = la.overworld_atlas()
    dungeon_tiles = la.dungeon_atlas()
    overworld_id = assets.tileset(
        "overworld", overworld.surface(), 16, len(overworld.cells), "Overworld", overworld.solid
    )
    dungeon_id = assets.tileset(
        "mine", dungeon_tiles.surface(), 18, len(dungeon_tiles.cells), "Mine", dungeon_tiles.solid
    )
    layouts = {
        "town": maps.town(overworld),
        "field": maps.field(overworld),
        "dungeon": maps.dungeon(dungeon_tiles),
    }
    tilemaps = {}
    for key, tileset in (("town", overworld_id), ("field", overworld_id), ("dungeon", dungeon_id)):
        layout = layouts[key]
        tilemaps[key] = assets.tilemap(
            key, layout["grid"].data(tileset, layout["size"]), key.capitalize()
        )
    db = project.rpg_database
    icons = dict.fromkeys(  # the real pictures are set by dress_in_lucifer
        ("state_healing", "state_war_cry", "state_burning", "state_bleeding", "state_chilled"), ""
    )
    combat_content(project, looks, icons)
    classes_and_trees(db)
    loot_content(db, icons)
    behaviour(db)
    town, hero = build_scenes(project, looks, tilemaps, layouts, la.mine_backdrops(assets))
    new_game(project, town, hero)
    dress_in_lucifer(project)
    art.title_image(HERE, layouts["field"], overworld)
    project.validate()
    path = HERE / "project.asteria.json"
    project.save_json(path)
    manifest = {
        "schema": "asteria.playable_test_content",
        "version": 1,
        "title": "Asteria ARPG Multiplayer Demo",
        "subtitle": "Hollowbrook - an ARPG demo",
        "field": {
            "background": f"{art.OUT}/title.png",
            "player_sheet": f"{art.OUT}/hero.png",
            "player_frame_size": [16, 16],
            "world_to_screen_scale": 3.0,
            "player_start": [0, 0],
            "boss_world": [0, 0],
            "entity_sprites": {},
            "player_render_width": 48,
        },
        "battle": {"skills": {k: {"label": v} for k, v in LABELS.items()}},
    }
    (HERE / "playable_test_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    sys.path.insert(0, str(REPO / "scripts"))
    from center_cameras import center_file

    center_file(HERE)  # every scene's camera on the hero; the Player's place is the start
    print(
        f"wrote {path.relative_to(REPO)}: {len(project.scenes())} scenes, "
        f"{len(project.gameplay_library.abilities.ids())} abilities, {len(db.classes)} classes, "
        f"{len(db.progression_graphs)} skill trees, {len(db.equipment)} equipment, "
        f"{len(project.assets.records())} assets"
    )


if __name__ == "__main__":
    main()
