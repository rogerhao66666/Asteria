"""Real-window gallery of a project's battle art: every clip of every combatant and every effect,
drawn by the engine's own battle drawer on the battle backdrop at the size the battle uses.

    python scripts/battle_art_gallery_live_check.py OUTPUT_DIR [PROJECT_DIR]

PROJECT_DIR defaults to the Full Verification demo. One picture per combatant (a row per clip,
every keyframe left to right, the figure standing on the ground line as in a fight) and one per
group of effects (each played frame by frame on a stand-in target, placed by the effect's own
``vfx`` placement). ``results.json`` lists the pictures and any clip or frame the drawer could
not show. Nothing is written into the project.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
WIDTH, HEIGHT = 1280, 720
VIRTUAL_W = 480  # the battle layout width: sprites are drawn at WIDTH / VIRTUAL_W


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    out = Path(argv[0])
    project_dir = Path(
        argv[1] if len(argv) > 1 else REPO / "reference_projects" / "full_verification_demo"
    )
    out.mkdir(parents=True, exist_ok=True)
    for name in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
        os.environ.pop(name, None)
    import pygame
    from PIL import Image

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.battle_presentation_adapters import PygameTextureDrawer
    from asteria.runtime.battle_visuals import (
        BattleVisualResolver,
        vfx_content_center,
        vfx_placement,
        vfx_rect,
    )

    project = Project.load_json(
        project_dir / "project.asteria.json", EditorDocument().component_registry
    )
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Battle art gallery")
    driver = pygame.display.get_driver()
    images = {}

    def load_image(uri):
        if uri not in images:
            images[uri] = pygame.image.load(str(project_dir / uri)).convert_alpha()
        return images[uri]

    resolver = BattleVisualResolver(project, lambda uri: Image.open(project_dir / uri).size)
    k = WIDTH / VIRTUAL_W
    host = type("Host", (), {})()
    host.pg, host.screen, host.load_image = pygame, screen, load_image
    drawer = PygameTextureDrawer(host, resolver, k)
    backdrop_path = project_dir / "playable_assets" / "battle_background.png"
    backdrop = (
        pygame.transform.scale(
            load_image("playable_assets/battle_background.png"), (WIDTH, HEIGHT)
        )
        if backdrop_path.is_file()
        else None
    )
    font = pygame.font.Font(None, 22)
    problems, shots = [], []

    def clear(title):
        if backdrop is not None:
            screen.blit(backdrop, (0, 0))
        else:
            screen.fill((40, 60, 50))
        screen.blit(font.render(title, True, (250, 250, 250)), (8, 6))

    def show(name):
        for _ in range(2):  # the window shows the frame before it is saved
            pygame.event.pump()
            pygame.display.flip()
        pygame.image.save(screen, str(out / f"{name}.png"))
        shots.append(name)

    library = project.battle_presentation_library
    # -- combatants: a row per clip, every keyframe left to right ------------------------------
    for profile_id in sorted(library.ids("combatant_visuals")):
        profile = library.require("combatant_visuals", profile_id)
        asset_id = profile.assets.battlefield_asset_id
        try:
            sheet = resolver.sprite_sheet(asset_id)
            clips = resolver.clip_set(asset_id).clips
        except Exception as exc:  # noqa: BLE001 - reported, the gallery goes on
            problems.append(f"{profile_id}: {exc}")
            continue
        scale = float(profile.transform.scale_x)
        frame = sheet.frames[0]
        w, h = frame.width * scale, frame.height * scale  # layout units
        names = sorted(clips)
        row_h = min(h + 6, (HEIGHT / k - 20) / max(1, len(names)))
        clear(f"{profile_id}  ({asset_id}, scale {scale:g})")
        for r, clip_name in enumerate(names):
            keys = clips[clip_name].keyframes
            ground = 20 + (r + 1) * row_h
            screen.blit(
                font.render(clip_name, True, (250, 250, 210)),
                (8, round((ground - row_h / 2) * k) - 8),
            )
            step = min(w + 2, (VIRTUAL_W - 50) / max(1, len(keys)))
            for i, key in enumerate(keys):
                f = sheet.frames[key.frame_index]
                x = 48 + i * step
                fit = min(1.0, (row_h - 2) / h)  # tall sheets shrink to fit their row
                drawer.blit_region(
                    asset_id,
                    (f.x, f.y, f.width, f.height),
                    x,
                    ground - h * fit,
                    w * fit,
                    h * fit,
                )
        show(f"combatant_{profile_id}")

    # -- effects: each played frame by frame on a stand-in target -------------------------------
    effects = sorted(
        a.asset_id
        for a in project.assets.snapshot()
        if a.kind == "sprite_sheet" and "vfx" in a.tags
    )
    target = "hero_01" if "hero_01" in library.ids("combatant_visuals") else None
    per_page = 4
    for page in range(0, len(effects), per_page):
        clear(
            "effects " + ", ".join(e.rsplit(".", 1)[-1] for e in effects[page : page + per_page])
        )
        for r, asset_id in enumerate(effects[page : page + per_page]):
            meta = resolver.sheet_meta(asset_id)
            sheet = resolver.sprite_sheet(asset_id)
            keys = resolver.clip_set(asset_id).clips.get("play")
            if keys is None:
                problems.append(f"{asset_id}: no play clip")
                continue
            placement = vfx_placement(meta)
            ground = 70 + r * 60
            screen.blit(
                font.render(asset_id.rsplit(".", 1)[-1], True, (250, 250, 210)),
                (8, round((ground - 30) * k)),
            )
            if target is not None:  # the target the effect lands on
                t_profile = library.require("combatant_visuals", target)
                t_sheet = resolver.sprite_sheet(t_profile.assets.battlefield_asset_id)
                t_scale = float(t_profile.transform.scale_x)
                t_frame = t_sheet.frames[0]
                t_w, t_h = t_frame.width * t_scale, t_frame.height * t_scale
            else:
                t_w = t_h = 40
            body = t_h * 0.8
            boxes = []
            image = load_image(resolver.source_uri(asset_id))
            for f in sheet.frames:
                rect = image.subsurface((f.x, f.y, f.width, f.height)).get_bounding_rect()
                boxes.append((rect.left, rect.top, rect.right, rect.bottom) if rect.w else None)
            frame0 = sheet.frames[0]
            content = vfx_content_center([b for b in boxes if b], frame0.width, frame0.height)
            columns = keys.keyframes[:16]
            step = (VIRTUAL_W - 60) / max(1, len(columns))
            for i, key in enumerate(columns):
                ax = 60 + i * step + step / 2
                if target is not None:
                    tf = t_sheet.frames[0]
                    drawer.blit_region(
                        t_profile.assets.battlefield_asset_id,
                        (tf.x, tf.y, tf.width, tf.height),
                        ax - t_w / 2,
                        ground - t_h,
                        t_w,
                        t_h,
                        opacity=0.5,
                    )
                f = sheet.frames[key.frame_index]
                cx, cy, ew, eh = vfx_rect(placement, ax, ground, body, f.width, f.height, content)
                drawer.blit_region(
                    asset_id,
                    (f.x, f.y, f.width, f.height),
                    cx - ew / 2,
                    cy - eh / 2,
                    ew,
                    eh,
                    opacity=float(placement.get("opacity", 1.0)),
                    blend=placement.get("blend", "normal"),
                )
        show(f"effects_{page // per_page + 1:02d}")

    pygame.quit()
    report = {
        "driver": driver,
        "status": "PASS" if driver == "cocoa" and not problems else "FAIL",
        "pictures": shots,
        "problems": problems,
    }
    (out / "results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("driver", "status", "problems")}, indent=2))
    print(len(shots), "pictures in", out)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
