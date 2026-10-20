"""Skeleton animation components persist and produce runtime texture draws."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from asteria.assets import AssetRef
from asteria.core import Entity, Scene, Transform, deserialize_scene, serialize_scene
from asteria.core.ids import new_id
from asteria.graphics import SpriteFrame, SpriteSheet
from asteria.graphics.skeleton import Bone, Key, Skeleton, SkeletonClip, Slot
from asteria.graphics.skeleton_data import skeleton_to_data
from asteria.runtime.component_registry import default_component_registry
from asteria.runtime.skeleton_component import (
    SkeletonAnimation2DComponent,
    SkeletonSceneRuntime,
)


@pytest.fixture(scope="module")
def app():
    widgets = pytest.importorskip("PySide6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


class Camera:
    zoom = 2.0

    @staticmethod
    def world_to_screen(x, y):
        return x + 100, y + 100


def make_component():
    clip = SkeletonClip(
        "walk",
        1,
        tracks={("root", "x"): (Key(0, 0), Key(1, 10))},
    )
    rig = Skeleton(
        "hero",
        (Bone("root", x=1, y=2, length=2),),
        (Slot("body", "root", "hero_sheet"),),
        {"walk": clip},
    )
    return SkeletonAnimation2DComponent(
        json.dumps(skeleton_to_data(rig)), clip_name="walk", speed=2
    )


def make_scene():
    scene = Scene("Skeleton")
    entity = Entity("Hero")
    entity.add_component(Transform(10, 20))
    entity.add_component(make_component())
    scene.add_entity(entity)
    return scene, entity


def test_skeleton_component_round_trips_in_scene_json():
    scene, _ = make_scene()
    encoded = serialize_scene(scene)
    restored = deserialize_scene(encoded, default_component_registry())
    component = restored.entities()[0].try_get(SkeletonAnimation2DComponent)

    assert component is not None
    assert component.clip_name == "walk"
    assert component.speed == 2
    assert json.loads(component.skeleton_json)["schema"] == "asteria.skeleton"


def test_skeleton_scene_runtime_advances_and_draws_through_texture_adapter():
    scene, _ = make_scene()
    runtime = SkeletonSceneRuntime()
    texture_id = new_id()
    sheet = SpriteSheet(AssetRef(texture_id), [SpriteFrame(0, 0, 2, 2)])

    runtime.update(scene, 0.25)
    draws = runtime.draw_commands(scene, Camera(), lambda _: sheet)

    assert len(draws) == 1
    assert draws[0].texture_asset_id == texture_id
    assert draws[0].source == (0, 0, 2, 2)
    assert draws[0].screen_x == 115
    assert draws[0].screen_y == 120


def test_tile_scene_view_draws_component_slot_into_game_surface():
    pygame = pytest.importorskip("pygame")

    from asteria.runtime.skeleton_component import SkeletonSceneRuntime
    from asteria.runtime.tile_scene_view import TileSceneView

    scene, _ = make_scene()
    texture_id = new_id()
    sheet = SpriteSheet(AssetRef(texture_id), [SpriteFrame(0, 0, 2, 2)])
    texture = pygame.Surface((2, 2), pygame.SRCALPHA)
    texture.fill((40, 240, 90, 255))
    view = TileSceneView.__new__(TileSceneView)
    view.pg = pygame
    view.session = SimpleNamespace(scene=scene, combat_scene=None)
    view.resources = SimpleNamespace(get=lambda _asset_id, _kind: sheet)
    view.width, view.height = 200, 160
    view.camera = Camera()
    view._animated = {}
    view._skeleton_runtime = SkeletonSceneRuntime()
    view._parallax = lambda screen: None
    view._layer = lambda screen, group, backdrop=None: None
    view._texture = lambda _asset_id: texture
    view._skeleton_runtime.update(scene, 0.25)
    screen = pygame.Surface((view.width, view.height), pygame.SRCALPHA)

    view.draw(screen)

    assert screen.get_at((116, 121)) == (40, 240, 90, 255)


def test_playable_test_runtime_draws_skeleton_component_without_tile_scene(tmp_path):
    pygame = pytest.importorskip("pygame")

    from asteria.assets import AssetRecord
    from asteria.graphics.skeleton import Bone, Skeleton, Slot
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = __import__("asteria.project", fromlist=["Project"]).Project("Field rig")
    texture = project.assets.add(
        AssetRecord.create(kind="texture", source_path="rig.png", name="Rig texture")
    )
    sheet_record = project.assets.add(
        AssetRecord.create(kind="sprite_sheet", source_path="rig_sheet.json", name="Rig")
    )
    texture_image = pygame.Surface((2, 2), pygame.SRCALPHA)
    texture_image.fill((230, 40, 180, 255))
    pygame.image.save(texture_image, str(tmp_path / texture.source_path))
    (tmp_path / sheet_record.source_path).write_text(
        json.dumps(
            {
                "texture_asset_id": texture.id,
                "frames": [{"x": 0, "y": 0, "width": 2, "height": 2}],
            }
        ),
        encoding="utf-8",
    )
    rig = Skeleton("field_hero", (Bone("root"),), (Slot("body", "root", sheet_record.id),))
    entity = Entity("Rigged")
    entity.add_component(Transform(10, 20))
    entity.add_component(SkeletonAnimation2DComponent(json.dumps(skeleton_to_data(rig))))
    scene = Scene("Field")
    scene.add_entity(entity)
    project.add_scene(scene)

    class FieldCamera(Camera):
        zoom = 1.0

    runtime = object.__new__(PlayableTestRuntime)
    runtime.project = project
    runtime.game = SimpleNamespace(scene=scene, project=project)
    runtime.resource_root = Path(tmp_path)
    runtime.manifest = {"field": {"world_to_screen_scale": 1.0}}
    runtime._field_camera = FieldCamera()
    runtime._skeleton_scene_runtime = SkeletonSceneRuntime()
    runtime._skeleton_sheet_cache = {}
    runtime.pg = pygame
    runtime.screen = pygame.Surface((200, 180), pygame.SRCALPHA)
    runtime.load_image = lambda _path: texture_image
    runtime._skeleton_scene_runtime.update(scene, 0.0)

    class RuntimeCamera:
        zoom = 1.0

        @staticmethod
        def world_to_screen(x, y):
            return runtime._field_screen_xy(x, y)

    draws = runtime._skeleton_scene_runtime.draw_entity(
        entity, RuntimeCamera(), runtime._skeleton_sheet
    )
    assert len(draws) == 1
    assert draws[0].screen_x == 109.5 and draws[0].screen_y == 119.0
    assert runtime._asset_source_path(draws[0].texture_asset_id, "texture") is not None
    assert runtime.tile_view is None

    runtime._draw_skeleton_entities()

    assert runtime.screen.get_at((110, 120)) == (230, 40, 180, 255)


def test_editor_scene_viewport_advances_attached_skeleton_preview(app, tmp_path):
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtTest import QTest

    from asteria.assets import AssetRecord
    from asteria.editor.model import EditorDocument
    from asteria.editor.viewport_widget import SceneViewportWidget
    from asteria.project import Project

    project = Project("Scene animation")
    scene = Scene("Field")
    project.add_scene(scene)
    entity = Entity("Hero")
    entity.add_component(Transform(0, 0))
    clip = SkeletonClip("walk", 1, tracks={("root", "x"): (Key(0, 0), Key(1, 10))})
    rig = Skeleton(
        "hero",
        (Bone("root", length=4),),
        (Slot("body", "root", "hero_sheet"),),
        {"walk": clip},
    )
    entity.add_component(
        SkeletonAnimation2DComponent(
            json.dumps(skeleton_to_data(rig)), clip_name="walk", playing=True
        )
    )
    scene.add_entity(entity)
    texture = QImage(2, 2, QImage.Format_ARGB32)
    texture.fill(QColor("cyan"))
    assert texture.save(str(tmp_path / "hero.png"))
    record = project.assets.add(
        AssetRecord.create(kind="texture", source_path="hero.png", name="Hero")
    )
    document = EditorDocument(project, file_path=tmp_path / "project.asteria")
    document.asset_views.set_sprite_sheet(
        "hero_sheet", SpriteSheet(AssetRef(record.id), [SpriteFrame(0, 0, 2, 2)])
    )
    widget = SceneViewportWidget(document)
    widget.resize(320, 240)
    widget.show()
    try:
        app.processEvents()
        assert widget._skeleton_timer.isActive()
        draws = widget.skeleton_runtime.draw_commands(
            scene, widget.camera, document.asset_views.sprite_sheet
        )
        assert len(draws) == 1
        QTest.qWait(90)
        assert widget.skeleton_runtime._times[entity.id] > 0
    finally:
        widget.close()
        app.processEvents()
