"""ARPG playground (D22 A8): the reference project's field turned into an action scene, to play and verify the real-time
combat screen before the ARPG demo project exists.

``build_playground(runtime, view="topdown")`` adds, as ordinary project data: attacks, timelines and abilities (a
three-hit combo, a dodge, a homing fire bolt), a few enemies driven by behaviour trees (chasers, an archer, a boss with
an armored slam below half HP), drop tables with gold and equipment, and a ``CombatScene`` setting. ``view="side"`` adds
a block-out side-view course (platforms, a one-way ledge, a slope, a ladder). Nothing here is engine code.

    python scripts/arpg_playground.py [--side]
"""

from __future__ import annotations


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def _content(game):
    from asteria.gameplay.abilities import AbilityCost, AbilityDefinition
    from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
    from asteria.gameplay.attacks import AttackDefinition
    from asteria.gameplay.formulas import FormulaTerm, ValueFormula
    from asteria.gameplay.projectiles import ProjectileDefinition
    from asteria.rpg.behavior_tree import BehaviorNode, BehaviorTree
    from asteria.rpg.drop_tables import DropEntry, DropTable
    from asteria.rpg.items import EquipmentDefinition
    from asteria.rpg.loot import AffixDefinition, AffixModifier

    library, db = game.project.gameplay_library, game.project.rpg_database
    if "pg_cut" in library.attacks:
        return
    power = ValueFormula(
        [FormulaTerm("source_stat", "power", 0.6), FormulaTerm("target_stat", "defense", -0.3)], minimum=1
    )
    for attack in (
        AttackDefinition("pg_cut", damage=power, knockback=90, hitstun=0.15, poise_damage=10, hitstop=0.04),
        AttackDefinition(
            "pg_finisher",
            damage=ValueFormula([FormulaTerm("source_stat", "power", 1.2)], minimum=1),
            knockback=220,
            knockdown=True,
            poise_damage=30,
            hitstop=0.08,
        ),
        AttackDefinition(
            "pg_fire",
            damage=ValueFormula([FormulaTerm("source_stat", "magic", 0.8)], minimum=1),
            tags=["Element.Fire"],
            apply_states=[],
        ),
        AttackDefinition("pg_claw", damage=ValueFormula.constant(6), knockback=60, hitstun=0.1),
        AttackDefinition("pg_arrow", damage=ValueFormula.constant(5)),
        AttackDefinition(
            "pg_slam",
            damage=ValueFormula.constant(18),
            knockback=260,
            knockdown=True,
            hitstop=0.1,
            hitstop_scope="global",
            armor_break=1,
        ),
    ):
        library.add_attack(attack)
    library.add_projectile(
        ProjectileDefinition("pg_bolt", attack_id="pg_fire", speed=260, homing_turn=240, homing_range=140, lifetime=1.4)
    )
    library.add_projectile(ProjectileDefinition("pg_shaft", attack_id="pg_arrow", speed=200, lifetime=1.6))

    def hit(attack, at, length=0.1):
        return ActionCue(f"{attack}_{at}", at, "hitbox", {"duration": length, "hit_tag": attack})

    def end(timeline_id, at):
        return ActionCue(f"{timeline_id}_end", at, "gameplay_event", {"name": "end"})

    for timeline in (
        ActionTimeline(
            "pg_slash1",
            [
                hit("pg_cut", 0.06),
                ActionCue("c1", 0.12, "combo_window", {"duration": 0.25, "next": "pg_slash2"}),
                end("pg_slash1", 0.32),
            ],
        ),
        ActionTimeline(
            "pg_slash2",
            [
                hit("pg_cut", 0.06),
                ActionCue("c2", 0.12, "combo_window", {"duration": 0.25, "next": "pg_slash3"}),
                end("pg_slash2", 0.32),
            ],
        ),
        ActionTimeline(
            "pg_slash3",
            [
                ActionCue("lunge", 0.0, "movement", {"x": 1, "relative": "facing", "speed": 160, "duration": 0.1}),
                hit("pg_finisher", 0.1, 0.12),
                end("pg_slash3", 0.45),
            ],
        ),
        ActionTimeline(
            "pg_roll",
            [
                ActionCue("dash", 0.0, "movement", {"x": 1, "relative": "aim", "speed": 230, "duration": 0.22}),
                ActionCue("iframes", 0.0, "iframe", {"duration": 0.3}),
                end("pg_roll", 0.3),
            ],
        ),
        ActionTimeline(
            "pg_cast",
            [
                ActionCue("cast", 0.08, "projectile", {"projectile_id": "pg_bolt", "aim": True, "offset_x": 8}),
                end("pg_cast", 0.25),
            ],
        ),
        ActionTimeline("pg_bite", [hit("pg_claw", 0.15), end("pg_bite", 0.4)]),
        ActionTimeline(
            "pg_shoot",
            [ActionCue("loose", 0.1, "projectile", {"projectile_id": "pg_shaft", "aim": True}), end("pg_shoot", 0.4)],
        ),
        ActionTimeline(
            "pg_slam",
            [
                ActionCue("armor", 0.0, "armor", {"duration": 0.9}),
                ActionCue("lean", 0.0, "movement", {"x": 1, "relative": "aim", "speed": 90, "duration": 0.3}),
                hit("pg_slam", 0.45, 0.15),
                end("pg_slam", 0.9),
            ],
        ),
    ):
        library.add_timeline(timeline)
    for ability in (
        AbilityDefinition("pg_slash", timeline_id="pg_slash1"),
        AbilityDefinition("pg_roll", timeline_id="pg_roll", interrupts_actions=True, cooldown_seconds=0.6),
        AbilityDefinition("pg_bolt", timeline_id="pg_cast", cooldown_seconds=0.8, costs=[AbilityCost("mp", 4)]),
        AbilityDefinition("pg_bite", timeline_id="pg_bite", cooldown_seconds=1.0),
        AbilityDefinition("pg_shoot", timeline_id="pg_shoot", cooldown_seconds=1.4),
        AbilityDefinition("pg_slam", timeline_id="pg_slam", cooldown_seconds=2.5),
    ):
        library.add_ability(ability)

    def n(kind, *children, **params):
        return BehaviorNode(kind, params, tuple(children))

    for tree in (
        BehaviorTree(
            "pg_chaser",
            n(
                "selector",
                n("sequence", n("player_within", radius=18), n("use_ability", ability="pg_bite", wait=True)),
                n("sequence", n("player_within", radius=110), n("chase", arrive=12)),
                n("wander", radius=24),
            ),
        ),
        BehaviorTree(
            "pg_archer",
            n(
                "selector",
                n(
                    "sequence",
                    n("player_within", radius=130),
                    n("keep_distance", min=50, max=90),
                    n("use_ability", ability="pg_shoot"),
                ),
                n("wander", radius=16),
            ),
        ),
        BehaviorTree(
            "pg_boss",
            n(
                "selector",
                n(
                    "sequence",
                    n("hp_below", fraction=0.5),
                    n("player_within", radius=34),
                    n("ability_ready", ability="pg_slam"),
                    n("use_ability", ability="pg_slam", wait=True),
                ),
                n("sequence", n("player_within", radius=20), n("use_ability", ability="pg_bite", wait=True)),
                n("sequence", n("player_within", radius=150), n("chase", arrive=16)),
            ),
        ),
    ):
        db.add_behavior_tree(tree)
    sword_slot = next(iter(game.save.rpg_state.loadouts[game.save.rpg_state.party_actor_ids[0]]._slots))
    db.add_equipment(EquipmentDefinition("pg_blade", "Blade", slot=sword_slot, tags=["blade"]))
    db.add_affix(
        AffixDefinition(
            "pg_sharp",
            "Sharp",
            "prefix",
            [AffixModifier("power", "add", 3, 8, integer=True, per_level=1)],
            allowed_tags=["blade"],
        )
    )
    db.add_affix(
        AffixDefinition("pg_bear", "of the Bear", "suffix", [AffixModifier("defense", "add", 2, 6, integer=True)])
    )
    db.add_drop_table(DropTable("pg_grunt", entries=[DropEntry("pg_blade", weight=1)], nothing_weight=2, rolls=1))
    db.add_drop_table(DropTable("pg_boss", guaranteed=[DropEntry("pg_blade", minimum=2, maximum=2)]))


def _enemy(game, name, x, y, tree, *, hp, team="foe", **combatant):
    from asteria.core import Entity, Transform
    from asteria.runtime.character_control import (
        AIController2DComponent,
        CharacterController2DComponent,
        Hitbox2DComponent,
        Hurtbox2DComponent,
    )
    from asteria.runtime.combat import CombatantComponent

    view = game.combat_scene.view
    entity = game.scene.add_entity(Entity(name))
    entity.add_component(Transform(x, y))
    entity.add_component(
        _set(CharacterController2DComponent(), mode=view, speed=34.0, half_width=5.0, half_height=6.0, facing="left")
    )
    entity.add_component(_set(AIController2DComponent(), driver="behavior_tree", tree_id=tree))
    entity.add_component(_set(Hurtbox2DComponent(), team=team, width=12, height=14))
    entity.add_component(_set(Hitbox2DComponent(), team=team, width=18, height=14, offset_x=10, follow_facing=True))
    entity.add_component(_set(CombatantComponent(), team=team, resources=f"hp={hp}", stats="defense=4", **combatant))
    return entity


def _side_course(game):
    from asteria.core import Entity, Transform
    from asteria.runtime.collision import Collider2DComponent

    def solid(x, y, w, h, **fields):
        e = game.scene.add_entity(Entity("Course"))
        e.add_component(Transform(x, y))
        e.add_component(_set(Collider2DComponent(), width=w, height=h, **fields))

    solid(0, 40, 320, 10)  # ground, top y = 35
    solid(-60, 12, 50, 4, one_way=True)  # a ledge
    solid(70, 15, 60, 40, shape="slope_right")  # a ramp up to y -5
    solid(120, 0, 40, 10)  # a plateau
    solid(-120, 0, 10, 80, ladder=True)  # a ladder up to the left ledge
    solid(-120, -42, 50, 4, one_way=True)


def build_playground(runtime, view="topdown"):
    from asteria.core import Entity
    from asteria.runtime.action_combat import ActionCombatComponent
    from asteria.runtime.action_play import CombatSceneComponent

    game = runtime.game
    runtime._ui_mode = "field"
    settings = game.combat_scene
    if settings is None:
        holder = game.scene.add_entity(Entity("Combat Scene"))
        settings = holder.add_component(CombatSceneComponent())
    settings.combat_mode, settings.view = "action", view
    settings.draw_colliders = view == "side"
    settings.background_color = "#283048" if view == "side" else ""
    settings.player_life_resource = "vitality"  # this project's heroes live on vitality
    _content(game)
    from asteria.runtime.field_ai import VisibleEncounterComponent

    sprites = runtime.manifest["field"].get("entity_sprites", {})
    for entity in list(game.scene.entities()):  # the reference field's turn-based boss and encounters stay out
        if entity.has(VisibleEncounterComponent) or entity.name in sprites:
            entity.enabled = False
    game.prepare_action_player()
    spec = game.player.get(ActionCombatComponent)
    spec.bindings = "attack=pg_slash; dodge=pg_roll; skill_1=pg_bolt"
    spec.lock_mode, spec.lock_range = "nearest", 60.0  # keyboard play: swing at the nearest foe in reach
    from asteria.runtime.combat import CombatantComponent

    game.player.get(CombatantComponent).hitstun_rule = "never"  # small hits do not interrupt the hero
    if view == "side":
        _side_course(game)
        game.set_player_position(-20.0, 20.0)
        foes = [
            ("Slime", 60, 20, "pg_chaser", 30),
            ("Archer", 125, -14, "pg_archer", 24),
            ("Guard", -40, 20, "pg_chaser", 40),
        ]
    else:
        foes = [
            ("Slime A", -40, -20, "pg_chaser", 30),
            ("Slime B", -60, 25, "pg_chaser", 30),
            ("Archer", 80, -30, "pg_archer", 24),
        ]
    for name, x, y, tree, hp in foes:
        _enemy(
            game,
            name,
            x,
            y,
            tree,
            hp=hp,
            drop_table_id="pg_grunt",
            currency_drop="gold=2-6",
            experience=60,
            loot_level=3,
        )
    if view != "side":
        _enemy(
            game,
            "Warlord",
            90,
            30,
            "pg_boss",
            hp=160,
            poise=40,
            stagger_result="knocked_down",
            currency_drop="gold=40-60",
            experience=400,
            drop_table_id="pg_boss",
            loot_level=8,
            loot_luck=1.5,
        )
    return game


__all__ = ["build_playground"]
