"""The editor starts on a current starter project with the left panel on Project; Game Start
reads by name; scene cameras sit on the hero."""

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")


def test_the_starter_project_is_made_once_and_kept(tmp_path):
    from asteria.editor.shell import ensure_starter_project

    folder = tmp_path / "Basic RPG"
    path = ensure_starter_project(folder)
    assert path.is_file() and (folder / ".starter.json").is_file()
    marker = path.read_bytes()
    assert ensure_starter_project(folder) == path and path.read_bytes() == marker
    assert not (tmp_path / "Basic RPG (previous)").exists()


def test_an_old_untouched_starter_is_rebuilt_in_place(tmp_path):
    from asteria.editor.shell import ensure_starter_project

    folder = tmp_path / "Basic RPG"
    path = ensure_starter_project(folder)
    stamp = json.loads((folder / ".starter.json").read_text())
    stamp["fingerprint"] = "an-older-template"  # the template has changed since
    (folder / ".starter.json").write_text(json.dumps(stamp))
    (folder / "stray.txt").write_text("from the old copy")
    ensure_starter_project(folder)
    assert path.is_file() and not (folder / "stray.txt").exists()
    assert not (tmp_path / "Basic RPG (previous)").exists()  # nothing of the user's to keep


def test_an_edited_or_unknown_starter_is_moved_aside_not_lost(tmp_path):
    from asteria.editor.shell import ensure_starter_project

    folder = tmp_path / "Basic RPG"
    path = ensure_starter_project(folder)
    data = json.loads(path.read_text())
    data["name"] = "My game"  # the user edited it
    path.write_text(json.dumps(data))
    stamp = json.loads((folder / ".starter.json").read_text())
    stamp["fingerprint"] = "an-older-template"
    (folder / ".starter.json").write_text(json.dumps(stamp))
    ensure_starter_project(folder)
    kept = tmp_path / "Basic RPG (previous)" / "project.asteria.json"
    assert json.loads(kept.read_text())["name"] == "My game"
    assert json.loads(path.read_text())["name"] == "Basic RPG"
    # a starter made before the stamp existed is treated the same way
    (folder / ".starter.json").unlink()
    ensure_starter_project(folder)
    assert (tmp_path / "Basic RPG (previous 2)" / "project.asteria.json").is_file()


def test_the_left_panel_always_opens_on_project(tmp_path):
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / "layout.ini"), QSettings.IniFormat)
    first = AsteriaEditorWindow()
    try:
        first.resize(1280, 800)
        first.show()
        for _ in range(10):
            app.processEvents()
        assert first.current_left_tab() == "ProjectSceneDock"  # the default
        first.show_left_tab("LayersDock")
        for _ in range(5):
            app.processEvents()
        assert first.current_left_tab() == "LayersDock"
        first.layout_settings = settings
        first.save_layout()
    finally:
        first.close()
    second = AsteriaEditorWindow()
    try:
        second.restore_layout(settings)
        second.show()
        for _ in range(10):
            app.processEvents()
        assert second.current_left_tab() == "ProjectSceneDock"  # not remembered
    finally:
        second.close()


def test_the_starter_map_has_no_stray_rock_fragments(tmp_path):
    import json

    from asteria.editor.basic_rpg_map import ROCK_TILES
    from asteria.editor.project_templates import create_from_template

    folder = tmp_path / "Starter"
    create_from_template("basic_rpg", "Basic RPG", folder)
    data = json.loads((folder / "editable_map_assets" / "field_map.json").read_text())
    used = {t for layer in data["layers"] for c in layer["chunks"] for t in c["tiles"]}
    assert not used & ROCK_TILES


def test_a_scene_opens_with_room_around_the_game_camera():
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene, Transform
    from asteria.editor import EditorDocument
    from asteria.editor.viewport_widget import SceneViewportWidget
    from asteria.project import Project
    from asteria.runtime import Camera2DComponent

    QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Field"))
    entity = scene.add_entity(Entity("Camera"))
    entity.add_component(Transform(0, 0))
    spec = entity.add_component(Camera2DComponent())
    spec.width, spec.height = 480, 270
    viewport = SceneViewportWidget(EditorDocument(project))
    viewport.resize(1000, 600)
    assert viewport.frame_game_camera()
    tight = viewport.camera.zoom
    assert viewport.frame_initial()
    assert viewport.camera.zoom < tight * 0.7


def test_the_start_scene_is_picked_by_name_and_new_scenes_get_unique_names():
    from asteria.core import Scene
    from asteria.editor import EditorDocument
    from asteria.editor.game_start_authoring import GameStartAuthoringController
    from asteria.editor.scenes import build_add_scene_command
    from asteria.project import Project

    project = Project("Game")
    first = project.add_scene(Scene("Town"))
    document = EditorDocument(project)
    controller = GameStartAuthoringController(document)
    assert controller.references("scenes") == ((first.id, "Town"),)
    names = []
    for _ in range(3):
        command = build_add_scene_command(project, "Scene")
        command.redo()
        names.append(command.scene.name)
    assert names == ["Scene", "Scene 2", "Scene 3"]


def test_a_reference_dropdown_shows_names_and_keeps_ids(tmp_path):
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_systems_authoring import F
    from asteria.editor.game_systems_widget import RecordForm

    QApplication.instance() or QApplication([])
    field = F("scene_id", "Start Scene", "optional_ref", source="scenes", empty_label="(startup)")
    form = RecordForm((field,), lambda source: (("id-1", "Town"), ("id-2", "Woods")))
    form.set_data({"scene_id": "id-2"})
    combo = form.widgets["scene_id"]
    assert combo.currentText() == "Woods" and form.data()["scene_id"] == "id-2"
    combo.setCurrentIndex(0)
    assert combo.currentText() == "(startup)" and form.data()["scene_id"] == ""


def test_the_party_list_shows_names_and_the_position_toggle_says_what_it_does():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.game_start_authoring import GAME_START_FORM
    from asteria.editor.game_systems_widget import RecordForm

    QApplication.instance() or QApplication([])
    refs = {"actors": (("hero_01", "Aldric (hero_01)"), ("hero_02", "Mira (hero_02)"))}
    fields = [f for f in GAME_START_FORM if f.key in ("party_actor_ids", "position_x")]
    form = RecordForm(tuple(fields), lambda source: refs.get(source, ()))
    form.set_data({"party_actor_ids": ["hero_02"], "position_x": 5})
    party = form.widgets["party_actor_ids"]  # chips: the names, picked from the actors
    assert party.values == ["hero_02"]
    assert party._labels["hero_02"].label == "Mira (hero_02)"
    assert form.data()["party_actor_ids"] == ["hero_02"]
    assert form.widgets["position_x"].check.text() == "Set position"


def test_cameras_follow_the_player_and_the_players_place_is_the_start():
    from asteria.editor.scene_cameras import center

    def entity(eid, x, y, camera=False):
        components = [{"type": "asteria.Transform", "fields": {"x": x, "y": y}}]
        if camera:
            components.append({"type": "asteria.Camera2D", "fields": {"follow_entity_id": ""}})
        return {"id": eid, "components": components}

    data = {
        "game_start": {"scene_id": "a", "player_entity_id": "p", "player_position": [5.0, 6.0]},
        "scenes": [
            {"id": "a", "entities": [entity("p", 5.0, 6.0), entity("cam", -40.0, 24.0, True)]},
            {"id": "b", "entities": [entity("cam2", 0.0, 0.0, True)]},
        ],
        "event_programs": {
            "door": {
                "instructions": [
                    {"args": {"command": "TRANSFER", "args": {"scene_id": "b", "x": 70, "y": 80}}}
                ]
            }
        },
    }
    assert center(data) == 2
    cams = [s["entities"][-1] for s in data["scenes"]]
    assert [c["components"][1]["fields"]["follow_entity_id"] for c in cams] == ["p", "p"]
    assert [tuple(c["components"][0]["fields"].values()) for c in cams] == [
        (5.0, 6.0),
        (70.0, 80.0),
    ]
    assert data["game_start"]["player_position"] is None  # the Player's own place is the start
    assert center(data) == 0  # nothing left to do


def test_a_picture_field_follows_the_scene_camera_as_authored():
    from asteria.core import Entity, Scene, Transform
    from asteria.runtime.components2d import Camera2DComponent
    from asteria.runtime.field_camera import scene_camera_follow

    scene = Scene("Field")
    hero = scene.add_entity(Entity("Player"))
    hero.add_component(Transform(0, 0))
    assert scene_camera_follow(scene, 320.0) is None  # no camera: the fixed whole-map view
    camera = scene.add_entity(Entity("Camera")).add_component(Camera2DComponent())
    camera.follow_entity_id = hero.id
    assert scene_camera_follow(scene, 320.0)["zoom"] == 1.0  # as wide as the map: no zoom
    camera.width, camera.smoothing = 160, 4.0
    follow = scene_camera_follow(scene, 320.0)
    assert follow["zoom"] == 2.0 and follow["smoothing"] == 4.0  # half as wide: zoomed in


def test_every_party_demo_scene_has_a_camera_on_the_hero():
    root = Path(__file__).resolve().parents[1]
    for folder in (
        "reference_projects/octopath_demo",
        "reference_projects/complex_reference_rpg",
        "src/asteria/templates/party_rpg",
        "reference_projects/full_verification_demo",
        "reference_projects/diablo_demo",
    ):
        data = json.loads((root / folder / "project.asteria.json").read_text())
        player = data["game_start"]["player_entity_id"]
        for scene in data["scenes"]:
            cameras = [
                c["fields"]
                for e in scene["entities"]
                for c in e["components"]
                if c["type"] == "asteria.Camera2D"
            ]
            assert cameras and all(c["follow_entity_id"] == player for c in cameras), (
                folder,
                scene["name"],
            )
