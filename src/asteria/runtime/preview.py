from __future__ import annotations

import argparse
from pathlib import Path

from asteria.core import ComponentRegistry, Transform
from asteria.gameplay import GameplayAttributesComponent
from asteria.project import Project
from asteria.runtime.components2d import (
    Animator2DComponent,
    Camera2DComponent,
    Interaction2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)


def build_preview_registry():
    registry = ComponentRegistry()
    registry.register(Transform)
    registry.register(SpriteRenderer2D)
    registry.register(Camera2DComponent)
    registry.register(Interaction2DComponent)
    registry.register(Animator2DComponent)
    registry.register(TileMap2DComponent)
    registry.register(GameplayAttributesComponent)
    return registry


def run_preview(
    project_path, scene_id=None, *, backend=None, width=960, height=540, target_fps=60
):
    registry = build_preview_registry()
    project = Project.load_json(project_path, registry)
    scene = project.scene(scene_id or project.startup_scene_id)
    if scene is None:
        raise ValueError("Preview scene does not exist")

    if backend is None:
        from asteria.platform.pygame_backend import PygameRuntimeBackend

        backend = PygameRuntimeBackend()

    backend.open(f"Asteria Preview — {scene.name}", width, height)
    try:
        root = Path(project_path).resolve().parent
        reference_sidecar = root / "reference_data/tilemap.json"
        if (
            reference_sidecar.exists()
            and hasattr(backend, "load_texture")
            and hasattr(backend, "draw_texture")
        ):
            from asteria.runtime.reference_runtime import (
                ReferenceRuntime,
                run_reference_runtime,
            )

            runtime = ReferenceRuntime.load(project, scene, root)
            run_reference_runtime(runtime, backend, width, height, target_fps)
        else:
            while not backend.should_close():
                if hasattr(backend, "tick"):
                    backend.tick(target_fps)
                backend.begin_frame()
                if hasattr(backend, "draw_grid"):
                    backend.draw_grid(32, width / 2, height / 2)
                for index, entity in enumerate(scene.entities()):
                    transform = entity.try_get(Transform)
                    if transform is None:
                        continue
                    x = width / 2 + transform.x
                    y = height / 2 + transform.y
                    if hasattr(backend, "draw_marker"):
                        backend.draw_marker(x, y, 8, index == 0)
                backend.end_frame()
    finally:
        backend.close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run an Asteria scene preview")
    parser.add_argument("project")
    parser.add_argument("--scene")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    args = parser.parse_args(argv)
    return run_preview(args.project, args.scene, width=args.width, height=args.height)


if __name__ == "__main__":
    raise SystemExit(main())
