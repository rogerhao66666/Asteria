"""ARPG stress scene (ASTERIA_SPEC §35 ARPG stress test; D22 A2): many enemies, many projectiles, measured.

``run_arpg_stress(repo, enemies=300, projectiles=500, frames=300, kernel="numpy")`` loads the reference project in a
headless ``PlayableTestRuntime``, fills the field with chasing enemies (controller, collider, hurtbox, combatant) and a
few walls, keeps ``projectiles`` shots in flight, swings a melee hitbox every half second, and profiles every
``GameSession.field_update`` section (ai, collision, combat, projectiles...). Engine work only — drawing comes with the
ARPG presentation. Numbers belong to this machine; compare runs on the same machine only.
"""

from __future__ import annotations

import hashlib
import os
import random
from math import cos, pi, sin
from pathlib import Path

DT = 1.0 / 60.0


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def _populate(game, enemies, rng):
    from asteria.core import Entity, Transform
    from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
    from asteria.gameplay.attacks import AttackDefinition
    from asteria.gameplay.formulas import ValueFormula
    from asteria.gameplay.projectiles import ProjectileDefinition
    from asteria.runtime import Collider2DComponent, FieldAIComponent
    from asteria.runtime.character_control import (
        AIController2DComponent,
        CharacterController2DComponent,
        Hitbox2DComponent,
        Hurtbox2DComponent,
    )
    from asteria.runtime.combat import CombatantComponent

    library = game.project.gameplay_library
    library.attacks.setdefault(
        "stress_bolt", AttackDefinition("stress_bolt", damage=ValueFormula.constant(1), knockback=40)
    )
    library.attacks.setdefault(
        "stress_slash", AttackDefinition("stress_slash", damage=ValueFormula.constant(2), knockback=120, hitstun=0.1)
    )
    library.projectiles.setdefault(
        "stress_bolt",
        ProjectileDefinition("stress_bolt", attack_id="stress_bolt", speed=220, lifetime=2.5, pierce=-1, wall_mask=1),
    )
    library.timelines.setdefault(
        "stress_slash",
        ActionTimeline(
            "stress_slash", [ActionCue("hit", 0.0, "hitbox", {"duration": 0.15, "hit_tag": "stress_slash"})]
        ),
    )
    player = game.player
    px, py = player.get(Transform).x, player.get(Transform).y
    for component in (
        _set(Hurtbox2DComponent(), team="hero"),
        _set(Hitbox2DComponent(), team="hero", width=48.0, height=32.0, offset_x=20.0, follow_facing=True),
        _set(CombatantComponent(), team="hero", resources="hp=1000000"),
    ):
        if not player.has(type(component)):
            player.add_component(component)
    if not player.has(CharacterController2DComponent):
        player.add_component(CharacterController2DComponent())
    scene = game.scene
    for k in range(8):  # a few walls (layer 0) for movement and shots
        angle = k * pi / 4
        wall = scene.add_entity(Entity(f"Stress Wall {k}"))
        wall.add_component(Transform(px + cos(angle) * 420, py + sin(angle) * 420))
        wall.add_component(_set(Collider2DComponent(), width=60.0, height=60.0))
    for k in range(enemies):
        angle, reach = rng.uniform(0, 2 * pi), rng.uniform(80, 400)
        enemy = scene.add_entity(Entity(f"Stress Enemy {k}"))
        enemy.add_component(Transform(px + cos(angle) * reach, py + sin(angle) * reach))
        enemy.add_component(_set(CharacterController2DComponent(), speed=40.0, half_width=5.0, half_height=5.0))
        enemy.add_component(_set(AIController2DComponent(), driver="field_ai"))
        enemy.add_component(_set(FieldAIComponent(), behaviour="chase", detect_radius=2000.0, lose_radius=4000.0))
        enemy.add_component(_set(Collider2DComponent(), width=10.0, height=10.0, layer=1))
        enemy.add_component(_set(Hurtbox2DComponent(), team="foe", width=14.0, height=14.0))
        enemy.add_component(
            _set(CombatantComponent(), team="foe", resources="hp=1000000", knockback_resistance=0.5, death="keep")
        )
    return px, py


def run_arpg_stress(repo, *, enemies=300, projectiles=500, frames=300, kernel=None, seed=1, target_fps=60):
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from asteria import kernels
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from asteria.runtime.profiler import RuntimeProfiler

    previous = kernels.active().NAME
    kernels.use(kernel or "auto")
    root = Path(repo) / "reference_projects" / "complex_reference_rpg"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), root)
    runtime.open()
    try:
        runtime._ui_mode = "field"
        game = runtime.game
        rng = random.Random(seed)
        px, py = _populate(game, enemies, rng)
        shots = game.projectiles  # systems for this scene (kernel set chosen now)
        hits = landed = 0
        game.combat.listeners.append(lambda event: None)
        profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=target_fps))
        for index in range(frames):
            missing = projectiles - len(shots)
            for _ in range(max(0, missing)):
                angle = rng.uniform(0, 2 * pi)
                sx, sy = px + rng.uniform(-60, 60), py + rng.uniform(-60, 60)
                shots.fire("stress_bolt", sx, sy, (cos(angle), sin(angle)), owner_id=game.player.id, team="hero")
            if index % 30 == 0:
                game.play_action(game.player.id, "stress_slash")
            profiler.begin_frame()
            game.field_update(DT)
            profiler.end_frame()
            hits += len(game.hits.events) + len(shots.hit_events)
            landed += sum(1 for event in game.combat.events if event.kind == "damage")
            profiler.count("entity_count", len(game.scene.entities()))
            profiler.count("projectiles", len(shots))
        report = profiler.report()
        profiler.close()
        from asteria.core import Transform

        state = sorted(
            (e.name, t.x, t.y) for e, t in game.scene.query(Transform) if e.name.startswith("Stress Enemy")
        ) + sorted((v.x, v.y, v.vx, v.vy) for v in shots.views())
        report["arpg"] = {
            "kernel": kernels.active().NAME,
            "enemies": enemies,
            "projectiles_target": projectiles,
            "frames": frames,
            "hits": hits,
            "damage_events": landed,
            "state_digest": hashlib.sha256(repr(state).encode()).hexdigest(),  # every enemy and shot, exactly
        }
        return report
    finally:
        runtime.close()
        kernels.use(previous)


__all__ = ["run_arpg_stress"]
