#!/usr/bin/env python3
"""Bounded real Cocoa/pygame validation for MV-backed character creation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from asteria.assets.character_generator import CharacterRecipe
from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv import RPGMakerMVImporter
from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog
from asteria.assets.rpg_maker_mv_map import discover_mv_maps
from asteria.assets.rpg_maker_mv_project import RPGMakerMVProjectImporter
from asteria.editor.character_generator_widget import CharacterGeneratorWidget
from asteria.editor.character_generator_workspace import CharacterGeneratorWorkspace


def _core_part(catalog, category, number, gender="Male"):
    return next(
        part for part in catalog.parts
        if part.source_root.parent.name == "rpg_maker_mv"
        and part.source_category == category and part.part_number == number and part.gender == gender
    )


def _capture_editor(workspace, output: Path, show_windows: bool):
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    widget = CharacterGeneratorWidget(workspace)
    widget.resize(1500, 820)
    if show_windows:
        widget.show()
    app.processEvents()
    captures = (
        (0, widget.walking_canvas, "editor-walking.png"),
        (1, widget.face_canvas, "editor-face.png"),
        (2, widget.side_view_canvas, "editor-side-view.png"),
    )
    for index, canvas, name in captures:
        widget.preview_tabs.setCurrentIndex(index)
        app.processEvents()
        if not canvas.grab().save(str(output / name), "PNG"):
            raise RuntimeError(f"failed to capture {name}")
    platform = app.platformName()
    widget.close(); app.processEvents()
    return platform


def _pygame_image(pygame, image: Image.Image):
    rgba = image.convert("RGBA")
    return pygame.image.frombytes(rgba.tobytes(), rgba.size, "RGBA")


def _render_runtime(output, mv_map, bundle, reference_root, max_frames, show_windows):
    import pygame

    pygame.init()
    flags = 0 if show_windows else pygame.HIDDEN
    surface = pygame.display.set_mode((640, 360), flags=flags)
    pygame.display.set_caption("Asteria MV Character Creator Validation")
    generated = Image.open(bundle.walking_path).convert("RGBA")
    importer = RPGMakerMVImporter()
    large_path = reference_root / "NewData" / "img" / "characters" / "$BigMonster1.png"
    large_info = importer.inspect(large_path)
    large_sheet = Image.open(large_path).convert("RGBA")
    large_boxes = importer.walk_clip_boxes(large_info, character_index=0, direction="down")
    standard_standing = (2 * 48 + 24, 4 * 48 + 48)
    large_standing = (6 * 48 + 24, 4 * 48 + 48)
    large_size = large_info.frame_size
    assert large_size is not None

    for frame in range(max_frames):
        pygame.event.pump()
        surface.fill((19, 22, 28))
        visible_columns, visible_rows = 13, 7
        for row in range(visible_rows):
            for column in range(visible_columns):
                index = row * mv_map.width + column
                occupied = index < len(mv_map.layers[0]) and any(layer[index] for layer in mv_map.layers[:4])
                color = (47, 58, 66) if occupied else (31, 36, 43)
                pygame.draw.rect(surface, color, (column * 48, row * 48, 48, 48))
                pygame.draw.rect(surface, (64, 72, 82), (column * 48, row * 48, 48, 48), 1)
        standard_frame = generated.crop(((frame % 3) * 48, 0, (frame % 3 + 1) * 48, 48))
        large_frame = large_sheet.crop(large_boxes[frame % 3])
        surface.blit(_pygame_image(pygame, standard_frame), (standard_standing[0] - 24, standard_standing[1] - 48))
        surface.blit(_pygame_image(pygame, large_frame), (large_standing[0] - large_size[0] // 2, large_standing[1] - large_size[1]))
        pygame.draw.line(surface, (235, 183, 76), (0, standard_standing[1]), (640, standard_standing[1]), 2)
        pygame.display.flip()
    pygame.image.save(surface, output / "runtime-map.png")
    pygame.quit()
    return {
        "frames_rendered": max_frames,
        "standard_character": {
            "frame_size": [48, 48], "standing_y": standard_standing[1], "rect_bottom": standard_standing[1],
        },
        "large_character": {
            "frame_size": list(large_size), "standing_y": large_standing[1], "rect_bottom": large_standing[1],
        },
    }


def run_validation(output_dir: str | Path, *, max_frames: int = 3, show_windows: bool = False):
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")
    output = Path(output_dir).resolve(); output.mkdir(parents=True, exist_ok=True)
    repo = Path(__file__).resolve().parents[1]
    reference_root = resolve_rpg_maker_mv_root(repo)
    if reference_root is None:
        raise RuntimeError("local RPG Maker MV reference is unavailable")

    generator_catalog = RPGMakerMVGeneratorCatalog.discover(reference_root)
    selections = {
        "body": _core_part(generator_catalog, "Body", 1),
        "face_shape": _core_part(generator_catalog, "Face", 1),
        "eyes": _core_part(generator_catalog, "Eyes", 1),
        "eyebrows": _core_part(generator_catalog, "Eyebrows", 1),
        "nose": _core_part(generator_catalog, "Nose", 1),
        "mouth": _core_part(generator_catalog, "Mouth", 1),
        "hair_back": _core_part(generator_catalog, "RearHair", 1),
        "outfit": _core_part(generator_catalog, "Clothing", 1),
        "hair_front": _core_part(generator_catalog, "FrontHair", 1),
    }
    workspace = CharacterGeneratorWorkspace.create_mv(generator_catalog, "validated-hero")
    for category, part in selections.items():
        workspace.select(category, part.id)
    bundle = workspace.generate(output / "generated")
    editor_platform = _capture_editor(workspace, output, show_windows)

    layout = discover_mv_projects(reference_root)[0]
    map_entry = discover_mv_maps(layout)[0]
    imported = RPGMakerMVProjectImporter.import_project(layout, map_ids=(map_entry.map_id,))
    scene = imported.project.scenes()[0]
    command = workspace.create_character_command(bundle, imported.project, scene, (2, 4), display_name="Validated Hero")
    created = command.execute()
    mv_map = next(entity.rpg_maker_mv_map for entity in scene.entities() if hasattr(entity, "rpg_maker_mv_map"))
    runtime = _render_runtime(output, mv_map, bundle, reference_root, max_frames, show_windows)
    result = {
        "schema": "asteria.mv-character-validation.v1",
        "editor_platform": editor_platform,
        "map_id": map_entry.map_id,
        "actor_registered": imported.project.rpg_database.actors.get(created.actor_id) is created.actor,
        "bundle_part_ids": list(bundle.source_part_ids),
        **runtime,
    }
    (output / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("/private/tmp/asteria-mv-character-creator"))
    parser.add_argument("--max-frames", type=int, default=3)
    parser.add_argument("--show-windows", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(run_validation(args.output, max_frames=args.max_frames, show_windows=args.show_windows), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
