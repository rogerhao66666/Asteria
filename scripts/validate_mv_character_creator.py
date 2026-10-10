#!/usr/bin/env python3
"""Bounded real Cocoa/pygame validation for MV-backed character creation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv import RPGMakerMVImporter
from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog
from asteria.assets.rpg_maker_mv_map import discover_mv_maps
from asteria.assets.rpg_maker_mv_project import RPGMakerMVProjectImporter
from asteria.assets.rpg_maker_mv_weapon import weapon_visual_for_type
from asteria.editor.character_generator_widget import CharacterGeneratorWidget
from asteria.editor.character_generator_workspace import CharacterGeneratorWorkspace
from asteria.project import Project
from asteria.runtime.preview import build_preview_registry


def _core_part(catalog, category, number, gender="Male"):
    return next(
        part
        for part in catalog.parts
        if part.source_root.parent.name == "rpg_maker_mv"
        and part.source_category == category
        and part.part_number == number
        and part.gender == gender
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
        (2, widget.damaged_canvas, "editor-damaged.png"),
        (3, widget.side_view_canvas, "editor-side-view.png"),
    )
    for index, canvas, name in captures:
        widget.preview_tabs.setCurrentIndex(index)
        app.processEvents()
        if not canvas.grab().save(str(output / name), "PNG"):
            raise RuntimeError(f"failed to capture {name}")

    def choose(category, part_id):
        widget.category_combo.setCurrentText(category)
        item = next(
            item
            for item in (widget.part_grid.item(i) for i in range(widget.part_grid.count()))
            if item.data(0x0100) == part_id
        )
        widget.part_grid.setCurrentItem(item)
        app.processEvents()

    before_hair = workspace.preview_representation("side_view").tobytes()
    selected_hair = workspace.recipe.parts["hair_front"]
    another_hair = next(
        part
        for part in workspace.choices("hair_front", gender="Male")
        if part.id != selected_hair and part.side_view is not None
    )
    choose("hair_front", another_hair.id)
    hair_changed = before_hair != workspace.preview_representation("side_view").tobytes()

    for family, capture in (("Female", "editor-female-side-view.png"), ("Kid", "editor-kid-side-view.png")):
        widget.gender_combo.setCurrentText(family)
        for category in ("face_shape", "eyes", "eyebrows", "nose", "mouth", "hair_back", "outfit", "hair_front"):
            candidate = next(
                (
                    part
                    for part in workspace.choices(category, gender=family)
                    if part.source_root.parent.name == "rpg_maker_mv"
                    and part.walking is not None
                    and part.side_view is not None
                ),
                None,
            )
            if candidate is not None:
                choose(category, candidate.id)
        workspace.recipe.id = f"validated-{family.lower()}"
        workspace.generate(output / "generated")
        widget.preview_tabs.setCurrentIndex(3)
        app.processEvents()
        if not widget.side_view_canvas.grab().save(str(output / capture), "PNG"):
            raise RuntimeError(f"failed to capture {capture}")
    platform = app.platformName()
    widget.close()
    app.processEvents()
    return platform, hair_changed


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
        surface.blit(
            _pygame_image(pygame, large_frame),
            (large_standing[0] - large_size[0] // 2, large_standing[1] - large_size[1]),
        )
        pygame.draw.line(surface, (235, 183, 76), (0, standard_standing[1]), (640, standard_standing[1]), 2)
        pygame.display.flip()
    pygame.image.save(surface, output / "runtime-map.png")
    pygame.quit()
    return {
        "frames_rendered": max_frames,
        "standard_character": {
            "frame_size": [48, 48],
            "standing_y": standard_standing[1],
            "rect_bottom": standard_standing[1],
        },
        "large_character": {
            "frame_size": list(large_size),
            "standing_y": large_standing[1],
            "rect_bottom": large_standing[1],
        },
    }


def _render_battle_weapons(output, bundle, reference_root, show_windows):
    import pygame

    system_data = json.loads((reference_root / "NewData" / "data" / "System.json").read_text(encoding="utf-8"))
    pygame.init()
    surface = pygame.display.set_mode((640, 300), flags=0 if show_windows else pygame.HIDDEN)
    pygame.display.set_caption("Asteria MV Weapon Animation Validation")
    actor = pygame.image.load(str(bundle.side_view_path)).convert_alpha()
    weapon_pixels = []
    for frame in range(3):
        pygame.event.pump()
        surface.fill((37, 43, 61))
        for x, weapon_type, motion_index in ((120, "Sword", 7), (410, "Bow", 8)):
            visual = weapon_visual_for_type(weapon_type, system_data)
            assert visual.frames and visual.sheet_name
            source = ((motion_index % 3 * 3 + frame) * 64, motion_index // 3 * 64, 64, 64)
            character_frame = actor.subsurface(source)
            surface.blit(pygame.transform.scale(character_frame, (128, 128)), (x - 64, 115))
            sheet = pygame.image.load(
                str(reference_root / "NewData" / "img" / "system" / f"{visual.sheet_name}.png")
            ).convert_alpha()
            weapon_frame = sheet.subsurface(visual.frames[frame])
            weapon_pixels.append(pygame.image.tobytes(weapon_frame, "RGBA"))
            surface.blit(pygame.transform.scale(weapon_frame, (192, 128)), (x - 128, 115))
        pygame.display.flip()
        if show_windows:
            pygame.time.delay(80)
    pygame.image.save(surface, output / "runtime-battle-weapons.png")
    pygame.quit()
    return {"weapon_frames_rendered": 6, "weapon_swapped_visual": weapon_pixels[0] != weapon_pixels[1]}


def run_validation(output_dir: str | Path, *, max_frames: int = 3, show_windows: bool = False):
    if max_frames <= 0:
        raise ValueError("max_frames must be positive")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
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
    editor_platform, hair_changed = _capture_editor(workspace, output, show_windows)

    layout = discover_mv_projects(reference_root)[0]
    map_entry = discover_mv_maps(layout)[0]
    imported = RPGMakerMVProjectImporter.import_project(layout, map_ids=(map_entry.map_id,))
    scene = imported.project.scenes()[0]
    command = workspace.create_character_command(bundle, imported.project, scene, (2, 4), display_name="Validated Hero")
    created = command.execute()
    project_path = output / "generated-project.asteria.json"
    imported.project.save_json(project_path)
    reopened_project = Project.load_json(project_path, build_preview_registry())
    reopened_workspace = CharacterGeneratorWorkspace.create_mv(generator_catalog)
    reopened_workspace.load_bundle(bundle.metadata_path)
    project_reloaded = (
        created.actor_id in reopened_project.rpg_database.actors
        and reopened_project.scene(scene.id).get_entity(created.entity_id) is not None
        and reopened_project.assets.resolve(bundle.canonical_assets[0].asset_id) is not None
        and reopened_workspace.recipe.parts["hair_front"] == selections["hair_front"].id
    )
    mv_map = next(entity.rpg_maker_mv_map for entity in scene.entities() if hasattr(entity, "rpg_maker_mv_map"))
    runtime = _render_runtime(output, mv_map, bundle, reference_root, max_frames, show_windows)
    battle_visual = _render_battle_weapons(output, bundle, reference_root, show_windows)
    result = {
        "schema": "asteria.mv-character-validation.v1",
        "editor_platform": editor_platform,
        "families_checked": ["Male", "Female", "Kid"],
        "hair_variation_changed_side_view": hair_changed,
        "map_id": map_entry.map_id,
        "actor_registered": imported.project.rpg_database.actors.get(created.actor_id) is created.actor,
        "project_reloaded": project_reloaded,
        "bundle_part_ids": list(bundle.source_part_ids),
        **runtime,
        **battle_visual,
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
