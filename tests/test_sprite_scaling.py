"""A sprite sheet chooses how its frames are resized: ``pixel`` (nearest neighbour, the default)
keeps pixel art sharp; ``smooth`` blends the pixels of painted or rendered pictures. The choice is
the sheet's metadata, read by the battle drawer, the field view and the editor."""

import json
from pathlib import Path
from types import SimpleNamespace

import pygame
import pytest
from PIL import Image

from asteria.editor import EditorDocument
from asteria.editor.animation_authoring import (
    AnimationAuthoringController,
    AnimationAuthoringError,
)
from asteria.graphics import SpriteFrame, SpriteSheet
from asteria.project import Project
from asteria.reference_data import load_sprite_sheet
from asteria.runtime.battle_presentation_adapters import PygameTextureDrawer
from asteria.runtime.tile_scene_view import TileSceneView

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"
SHEET = "battle.combatant.hero_01"


def _picture():
    """A 12x10 figure with soft edges: nearest and bilinear resizing differ."""
    image = pygame.Surface((12, 10), pygame.SRCALPHA)
    for y in range(10):
        for x in range(12):
            if 2 <= x < 10 and 1 <= y < 9:
                image.set_at((x, y), (20 * x, 25 * y, 120, 255 if x % 2 else 90))
    return image


def test_sheet_data_and_validation_carry_the_choice(tmp_path):
    sheet = SpriteSheet(SimpleNamespace(expected_kind="texture"), [SpriteFrame(0, 0, 4, 4)])
    assert sheet.scaling == "pixel" and not sheet.smooth
    sheet.scaling = "smooth"
    sheet.validate()
    assert sheet.smooth
    sheet.scaling = "blurry"
    with pytest.raises(ValueError):
        sheet.validate()
    path = tmp_path / "sheet.json"
    texture = "11111111-2222-4333-8444-555555555555"  # asset ids are UUIDs
    data = {"texture_asset_id": texture, "frames": [{"x": 0, "y": 0, "width": 4, "height": 4}]}
    path.write_text(json.dumps(data))
    assert load_sprite_sheet(path).scaling == "pixel"
    path.write_text(json.dumps({**data, "scaling": "smooth"}))
    assert load_sprite_sheet(path).smooth


def test_the_battle_drawer_blends_only_the_sheets_that_ask(monkeypatch):
    pictures = {"pixel": _picture(), "smooth": _picture()}
    metas = {"pixel": {}, "smooth": {"scaling": "smooth"}}
    resolver = SimpleNamespace(generated_image=pictures.get, sheet_meta=metas.__getitem__)
    screens = {}
    for asset_id in ("pixel", "smooth"):
        host = SimpleNamespace(pg=pygame, screen=pygame.Surface((80, 60), pygame.SRCALPHA))
        drawer = PygameTextureDrawer(host, resolver, 2.5)
        drawer.blit_region(asset_id, (0, 0, 12, 10), 4, 4, 12, 10)
        drawer.blit_region(asset_id, (0, 0, 12, 10), 40, 4, 12, 10, rotation_deg=20.0)
        screens[asset_id] = host.screen
    for asset_id, resize in (
        ("pixel", pygame.transform.scale),
        ("smooth", pygame.transform.smoothscale),
    ):
        wanted = pygame.Surface((80, 60), pygame.SRCALPHA)
        image = resize(pictures[asset_id], (30, 25))
        wanted.blit(image, (10, 10))
        turned = pygame.transform.rotate(image, -20.0)
        wanted.blit(
            turned, (round(115 - turned.get_width() / 2), round(22.5 - turned.get_height() / 2))
        )
        assert pygame.image.tobytes(screens[asset_id], "RGBA") == pygame.image.tobytes(
            wanted, "RGBA"
        ), asset_id
    assert pygame.image.tobytes(screens["pixel"], "RGBA") != pygame.image.tobytes(
        screens["smooth"], "RGBA"
    )
    assert drawer.smooth("missing") is False  # a sheet without metadata: pixel art


def test_the_field_view_resizes_a_smooth_sheet_with_blended_pixels():
    picture = _picture()
    sheets = {
        "pixel": SpriteSheet(SimpleNamespace(asset_id="tex"), [SpriteFrame(0, 0, 12, 10)]),
        "smooth": SpriteSheet(
            SimpleNamespace(asset_id="tex"), [SpriteFrame(0, 0, 12, 10)], scaling="smooth"
        ),
    }
    view = SimpleNamespace(
        pg=pygame,
        _frames={},
        resources=SimpleNamespace(get=lambda sheet_id, kind: sheets[sheet_id]),
        _texture=lambda asset_id: picture,
    )
    pixel, _, _ = TileSceneView._sprite(view, "pixel", 0, 3.0)
    smooth, _, _ = TileSceneView._sprite(view, "smooth", 0, 3.0)
    assert pygame.image.tobytes(pixel, "RGBA") == pygame.image.tobytes(
        pygame.transform.scale(picture, (36, 30)), "RGBA"
    )
    assert pygame.image.tobytes(smooth, "RGBA") == pygame.image.tobytes(
        pygame.transform.smoothscale(picture, (36, 30)), "RGBA"
    )


def test_the_editor_sets_the_choice_and_the_runtime_resolver_reads_it():
    from asteria.runtime.battle_visuals import BattleVisualResolver

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    document = EditorDocument(project, file_path=ROOT / "project.asteria.json")
    api = AnimationAuthoringController(document)
    resolver = lambda: BattleVisualResolver(  # noqa: E731
        document.project, lambda uri: Image.open(ROOT / uri).size
    )
    assert api.data(SHEET)["scaling"] == "pixel" and not resolver().sprite_sheet(SHEET).smooth
    api.set_scaling(SHEET, "smooth")
    assert api.data(SHEET)["scaling"] == "smooth"
    assert resolver().sprite_sheet(SHEET).smooth
    assert dict(api.asset(SHEET).metadata)["scaling"] == "smooth"
    with pytest.raises(AnimationAuthoringError):
        api.set_scaling(SHEET, "blurry")
    document.undo()
    assert api.data(SHEET)["scaling"] == "pixel"
    api.set_scaling(SHEET, "pixel")
    assert "scaling" not in dict(api.asset(SHEET).metadata)  # the default is not written
