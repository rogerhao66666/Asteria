"""Runtime benchmark (CB13): profile a field scene full of AI enemies and a choreographed battle.

``run_benchmark(repo, field_frames, battle_frames, enemies, real_window)``
drives ``PlayableTestRuntime`` frame by frame with the runtime profiler and
returns one profiler report per phase. Headless runs (dummy SDL drivers)
measure engine work; real-window runs (``real_window=True``) also measure
presentation and frame pacing. Numbers are measurements of this machine —
compare runs on the same machine only.
"""

from __future__ import annotations

import os
from pathlib import Path


def _install_enemies(game, count):
    from asteria.core import Entity, Transform
    from asteria.core.prefab import prefab_from_entity
    from asteria.runtime import Collider2DComponent, FieldAIComponent, SpawnZoneComponent

    template = Entity("Benchmark Slime")
    template.add_component(Transform())
    ai = template.add_component(FieldAIComponent())
    ai.behaviour, ai.speed, ai.wander_radius = "wander", 30.0, 40.0
    collider = template.add_component(Collider2DComponent())
    collider.width = collider.height = 10.0
    game.project.prefabs.add(prefab_from_entity(template, "benchmark_slime"))
    zone = Entity("Benchmark Zone")
    transform = zone.add_component(Transform())
    transform.x, transform.y = -60.0, 20.0
    spec = zone.add_component(SpawnZoneComponent())
    spec.prefab_id, spec.max_alive, spec.radius, spec.respawn_seconds = (
        "benchmark_slime",
        count,
        50.0,
        0.5,
    )
    game.scene.add_entity(zone)


def run_benchmark(
    repo, *, field_frames=600, battle_frames=600, enemies=50, real_window=False, target_fps=60
):
    if not real_window:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from asteria.runtime.profiler import RuntimeProfiler

    root = Path(repo) / "reference_projects" / "complex_reference_rpg"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), root)
    runtime.open()
    pg = runtime.pg
    reports = {}
    try:
        runtime._battle_presentation = CanonicalBattleAdapter(runtime)

        def phase(name, frames, before_frame=None):
            # timings without heap tracing (tracemalloc slows every allocation many times)
            profiler = runtime.enable_profiling(
                RuntimeProfiler(target_fps=target_fps, track_python_heap=False)
            )
            for index in range(frames):
                dt = (
                    min(runtime.clock.tick(target_fps) / 1000.0, 0.05)
                    if real_window
                    else 1.0 / target_fps
                )
                events = pg.event.get()
                if before_frame is not None:
                    events = list(events) + list(before_frame(index))
                profiler.begin_frame()
                runtime._frame(events, dt)
                with profiler.section("present"):
                    pg.display.flip()
                runtime._sample_counters()
                profiler.end_frame()
            reports[name] = profiler.report()
            profiler.close()

        # Field: spawned enemies wander with collision while the player walks.
        runtime._ui_mode = "field"
        game = runtime.game
        _install_enemies(game, enemies)
        phase("field", field_frames)

        # Battle: a hero skill whenever the screen is idle; enemies answer through their AI.
        game.start_encounter("boss_room")
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()

        def battle_input(index):
            adapter = runtime._battle_presentation
            if runtime._victory or runtime._defeat or adapter.busy() or index % 10:
                return ()
            return (pg.event.Event(pg.KEYDOWN, key=(pg.K_2, pg.K_1)[index // 10 % 2]),)

        phase("battle", battle_frames, battle_input)
    finally:
        runtime.close()
    return reports
