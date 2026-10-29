"""A11 measurement (D22): the ARPG demo in a real window, frames uncapped, timed per part.

    ASTERIA_KERNELS=python|numpy python scripts/arpg_demo_measure.py OUT.json [--extra 0]
                                                                   [--frames 600]

The player stands in the middle of Greenvale Fields attacking; ``--extra N`` adds N more slimes
around them (a crowded screen). Reports the mean / p95 of the whole frame and of its parts:
simulation (``field_update``), drawing (tile view + HUD) and presenting.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from asteria.core import Transform  # noqa: E402
from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.runtime.playable_test_runtime import PlayableTestRuntime  # noqa: E402


def stats(values):
    ordered = sorted(values)
    return {
        "mean_ms": round(sum(ordered) / len(ordered) * 1000, 2),
        "p95_ms": round(ordered[int(len(ordered) * 0.95)] * 1000, 2),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--extra", type=int, default=0)
    parser.add_argument("--frames", type=int, default=600)
    args = parser.parse_args(argv)
    root = REPO / "reference_projects" / "arpg_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=1280, height=720
    )
    rt.open()
    rt._ui_mode = "field"
    game, pg = rt.game, rt.pg
    field = next(s for s in project.scenes() if s.name.startswith("Greenvale"))
    game.transfer_player(field.id, 36 * 16, 28 * 16, facing="right")
    game.set_classes("", ["ranger"])
    if args.extra:
        import math

        from asteria.core.serialization import deserialize_entity, serialize_entity
        from asteria.runtime.preview import build_preview_registry

        slime = next(e for e in game.scene.entities() if e.name.startswith("Slime"))
        data = serialize_entity(slime)
        registry = build_preview_registry()
        for i in range(args.extra):
            copy = dict(data, id=None, name=f"Crowd {i}")
            entity = deserialize_entity(copy, registry)
            angle, reach = i * 2.399, 40 + (i % 12) * 12
            t = entity.get(Transform)
            t.x = 36 * 16 + math.cos(angle) * reach
            t.y = 28 * 16 + math.sin(angle) * reach
            game.scene.add_entity(entity)
    parts = {"frame": [], "simulate": [], "draw": [], "present": []}
    original_update, original_draw = game.field_update, rt._draw_field
    timing = {}

    def timed_update(dt):
        start = time.perf_counter()
        result = original_update(dt)
        timing["simulate"] = time.perf_counter() - start
        return result

    def timed_draw(*a, **k):
        start = time.perf_counter()
        result = original_draw(*a, **k)
        timing["draw"] = time.perf_counter() - start
        return result

    game.field_update, rt._draw_field = timed_update, timed_draw
    shots = 0
    for i in range(args.frames):
        if i % 10 == 0:  # keep shooting (the arrows and hits are part of the load)
            for kind in (pg.KEYDOWN, pg.KEYUP):
                pg.event.post(pg.event.Event(kind, key=pg.K_j, mod=0, unicode="", scancode=0))
            shots += 1
        timing.clear()
        start = time.perf_counter()
        rt._frame(pg.event.get(), 1 / 60)
        mid = time.perf_counter()
        rt.present()
        end = time.perf_counter()
        if i < 30:
            continue  # warm-up
        parts["frame"].append(end - start)
        parts["present"].append(end - mid)
        parts["simulate"].append(timing.get("simulate", 0.0))
        parts["draw"].append(timing.get("draw", 0.0))
    from asteria.runtime.combat import CombatantComponent

    report = {
        "driver": pg.display.get_driver(),
        "kernels": os.environ.get("ASTERIA_KERNELS", "default"),
        "enemies": sum(1 for _ in game.scene.query(CombatantComponent)) - 1,
        "frames": len(parts["frame"]),
        **{name: stats(values) for name, values in parts.items()},
        "uncapped_fps": round(len(parts["frame"]) / sum(parts["frame"]), 1),
        "projectiles_seen": len(game.projectiles.views()),
    }
    rt.close()
    Path(args.output).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
