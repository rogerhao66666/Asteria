from __future__ import annotations

import argparse
from pathlib import Path

from asteria.core import ComponentRegistry, PersistentComponent, Transform
from asteria.core.prefab import PrefabInstanceComponent
from asteria.gameplay import GameplayAttributesComponent
from asteria.project import Project
from asteria.runtime.actor_link import ActorLinkComponent
from asteria.runtime.collision import Collider2DComponent
from asteria.runtime.components2d import (
    Animator2DComponent,
    Camera2DComponent,
    Interaction2DComponent,
    SpriteRenderer2D,
    TileMap2DComponent,
)
from asteria.runtime.field_ai import FieldAIComponent, SpawnZoneComponent, VisibleEncounterComponent
from asteria.runtime.game_save import GameRuntimeSave


def build_preview_registry():
    registry = ComponentRegistry()
    registry.register(Transform)
    registry.register(SpriteRenderer2D)
    registry.register(Camera2DComponent)
    registry.register(Interaction2DComponent)
    registry.register(Animator2DComponent)
    registry.register(TileMap2DComponent)
    registry.register(GameplayAttributesComponent)
    registry.register(ActorLinkComponent)
    registry.register(PersistentComponent)
    registry.register(PrefabInstanceComponent)
    registry.register(Collider2DComponent)
    from asteria.runtime.character_control import register_character_components

    register_character_components(registry)
    from asteria.runtime.npc_state import NpcIdentity2DComponent

    registry.register(NpcIdentity2DComponent)
    registry.register(FieldAIComponent)
    registry.register(SpawnZoneComponent)
    registry.register(VisibleEncounterComponent)
    return registry


BACKENDS = ("pygame", "moderngl")


def build_backend(kind, input_map=None):
    """Window backend by name: "pygame" (default, CPU) or "moderngl" (GPU sprite batching)."""
    if kind == "pygame":
        from asteria.platform.pygame_backend import PygameRuntimeBackend

        return PygameRuntimeBackend(input_map=input_map)
    if kind == "moderngl":
        from asteria.platform.moderngl_backend import ModernglRuntimeBackend

        return ModernglRuntimeBackend(input_map=input_map)
    raise ValueError(f"unknown backend {kind!r}; choose one of {', '.join(BACKENDS)}")


def run_preview(
    project_path,
    scene_id=None,
    *,
    resource_root=None,
    backend=None,
    width=None,
    height=None,
    target_fps=60,
    save_path=None,
    playtest_profile=None,
    backend_kind="pygame",
    max_frames=None,
    profile_path=None,
    battle_presentation=None,
    debug_port=None,
    debug_token=None,
    spawn=None,
):
    registry = build_preview_registry()
    project = Project.load_json(project_path, registry)
    root = (
        Path(resource_root).expanduser().resolve() if resource_root is not None else Path(project_path).resolve().parent
    )
    runtime_save = GameRuntimeSave.load_json(save_path, project) if save_path else None
    if runtime_save is None and playtest_profile:
        from asteria.editor.playtest_profiles import PlaytestProfileLibrary

        runtime_save = PlaytestProfileLibrary(root).instantiate(playtest_profile, project)
    if runtime_save is None:
        runtime_save = project.game_start.instantiate(project)
    effective_scene_id = runtime_save.scene_id if runtime_save is not None else (scene_id or project.startup_scene_id)
    scene = project.scene(effective_scene_id)
    if runtime_save is not None and runtime_save.player_entity_id and runtime_save.player_position is not None:
        player = scene.get_entity(runtime_save.player_entity_id) if scene is not None else None
        if player is not None:
            transform = player.try_get(Transform)
            if transform is not None:
                transform.x, transform.y = runtime_save.player_position
    if scene is None:
        raise ValueError("Preview scene does not exist")

    active_camera = next(
        (
            entity.try_get(Camera2DComponent)
            for entity in scene.entities()
            if entity.try_get(Camera2DComponent) is not None and entity.try_get(Camera2DComponent).active
        ),
        None,
    )
    width = int(width or (active_camera.width if active_camera is not None else 960))
    height = int(height or (active_camera.height if active_camera is not None else 540))

    if backend is None:
        backend = build_backend(backend_kind, project.input_map)

    backend.open(f"Asteria Preview — {scene.name}", width, height)
    try:
        playable_manifest = root / "playable_test_manifest.json"
        reference_sidecar = root / "reference_data/tilemap.json"
        if playable_manifest.exists():
            # Human-operable sample-game path. This remains manifest/content-driven;
            # Project + GameRuntimeSave own game rules/state.
            backend.close()
            from asteria.runtime.playable_test_runtime import run_playable_test_runtime

            return run_playable_test_runtime(
                project,
                root,
                runtime_save=runtime_save,
                save_path=save_path,
                width=width,
                height=height,
                target_fps=target_fps,
                max_frames=max_frames,
                profile_path=profile_path,
                battle_presentation=battle_presentation,
                debug_port=debug_port,
                debug_token=debug_token,
                spawn=spawn,
            )
        if reference_sidecar.exists() and hasattr(backend, "load_texture") and hasattr(backend, "draw_texture"):
            from asteria.runtime.reference_runtime import (
                ReferenceRuntime,
                run_reference_runtime,
            )

            runtime = ReferenceRuntime.load(project, scene, root)
            run_reference_runtime(runtime, backend, width, height, target_fps, max_frames=max_frames)
        else:
            frames = 0
            while not backend.should_close():
                frames += 1
                if max_frames is not None and frames > max_frames:
                    break
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
    parser.add_argument("--resource-root")
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--save")
    parser.add_argument("--playtest-profile")
    parser.add_argument("--backend", choices=BACKENDS, default="pygame")
    parser.add_argument("--frames", type=int, help="quit after this many frames (smoke tests)")
    parser.add_argument("--fps", type=int, default=60, help="target frame rate")
    parser.add_argument("--profile", help="write a runtime profile (JSON) to this path on exit")
    parser.add_argument(
        "--battle-presentation",
        choices=("legacy", "canonical"),
        help="battle screen to use (default: the project manifest's choice)",
    )
    parser.add_argument("--debug-port", type=int, help="open the editor debug channel on this loopback port")
    parser.add_argument("--debug-token", help="token the editor debugger must present")
    parser.add_argument("--spawn", type=float, nargs=2, metavar=("X", "Y"), help="start the player here")
    args = parser.parse_args(argv)
    return run_preview(
        args.project,
        args.scene,
        resource_root=args.resource_root,
        width=args.width,
        height=args.height,
        save_path=args.save,
        playtest_profile=args.playtest_profile,
        backend_kind=args.backend,
        max_frames=args.frames,
        target_fps=args.fps,
        profile_path=args.profile,
        battle_presentation=args.battle_presentation,
        debug_port=args.debug_port,
        debug_token=args.debug_token,
        spawn=args.spawn,
    )


if __name__ == "__main__":
    raise SystemExit(main())
