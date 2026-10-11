"""CAM-02: look-ahead, bounds, target groups, authored shots (cutscene / boss) with eased transitions, shake."""

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.runtime.camera import (
    Camera2D,
    CameraDirector,
    CameraFollow2D,
    CameraShot,
    CameraTargetGroup,
    clamp_center_to_bounds,
)
from asteria.runtime.components2d import Camera2DComponent
from asteria.runtime.systems import CameraFollowSystem


def _center(camera):
    return camera.x + camera.width / camera.zoom / 2, camera.y + camera.height / camera.zoom / 2


def test_look_ahead_leads_the_direction_of_motion_and_holds_when_stopped():
    camera = Camera2D(width=320, height=180)
    follow = CameraFollow2D(camera, look_ahead_x=40, look_ahead_y=20, look_ahead_smoothing=0)
    follow.update(100, 100, 0.1, velocity=(50, 0))
    assert _center(camera) == (140, 100)
    follow.update(100, 100, 0.1, velocity=(-50, 10))
    assert _center(camera) == (60, 120)
    follow.update(100, 100, 0.1, velocity=(0, 0))
    assert _center(camera) == (60, 120)  # standing still keeps looking the same way
    smooth = CameraFollow2D(Camera2D(), look_ahead_x=40, look_ahead_smoothing=5)
    smooth.update(0, 0, 0.1, velocity=(10, 0))
    assert 0 < _center(smooth.camera)[0] - 0 < 40  # eases toward the lead


def test_bounds_keep_the_view_inside_and_centre_small_maps():
    assert clamp_center_to_bounds(0, 0, 100, 50, (0, 0, 400, 300)) == (50, 25)
    assert clamp_center_to_bounds(390, 290, 100, 50, (0, 0, 400, 300)) == (350, 275)
    assert clamp_center_to_bounds(10, 10, 500, 50, (0, 0, 400, 300)) == (200, 25)


def test_target_group_frames_everyone_with_padding_and_clamped_zoom():
    group = CameraTargetGroup(padding=10, min_zoom=0.25, max_zoom=2.0)
    cx, cy, zoom = group.frame([(0, 0), (200, 100)], 320, 180)
    assert (cx, cy) == (100, 50) and zoom == pytest.approx(min(320 / 220, 180 / 120))
    assert group.frame([(0, 0, 3), (100, 0, 1)], 320, 180)[0] == 25  # weights pull the centre
    assert group.frame([(0, 0)], 320, 180)[2] == 2.0  # one target: max zoom
    assert group.frame([(0, 0), (5000, 0)], 320, 180)[2] == 0.25
    with pytest.raises(ValueError):
        group.frame([], 320, 180)


def test_director_blends_to_a_shot_and_back_to_the_live_follow_view():
    director = CameraDirector()
    assert director.update(0.0, (0, 0, 1)) == (0, 0, 1)
    director.focus(CameraShot(100, 50, zoom=2.0), blend=1.0, ease="linear")
    assert director.update(0.5, (0, 0, 1)) == pytest.approx((50, 25, 1.5))
    assert director.update(0.5, (0, 0, 1)) == pytest.approx((100, 50, 2.0))
    assert director.active and not director.transitioning
    director.release(blend=1.0, ease="smooth")
    mid = director.update(0.5, (10, 0, 1))  # the follow view moved meanwhile; release targets it live
    assert mid == pytest.approx((55, 25, 1.5))  # smoothstep(0.5) == 0.5
    assert director.update(0.5, (20, 0, 1)) == (20, 0, 1) and not director.active
    target = {"x": 0.0}
    director.focus(CameraShot(follow=lambda: (target["x"], 7)), blend=0, ease="cut")
    target["x"] = 33
    assert director.update(0.1, (0, 0, 1)) == (33, 7, 1)  # follows a moving entity, keeps the base zoom
    with pytest.raises(ValueError, match="easing"):
        director.focus(CameraShot(), ease="bouncy")


def test_shake_is_deterministic_decays_and_is_reported_separately():
    a, b = CameraDirector(), CameraDirector()
    a.shake(4, 0.5)
    b.shake(4, 0.5)
    first = [a.update(0.05, (0, 0, 1)) for _ in range(5)]
    assert first == [b.update(0.05, (0, 0, 1)) for _ in range(5)]
    assert any(v != (0, 0, 1) for v in first) and a.shake_offset != (0.0, 0.0)
    for _ in range(10):
        a.update(0.05, (0, 0, 1))
    assert a.update(0.05, (0, 0, 1)) == (0, 0, 1) and a.shake_offset == (0.0, 0.0)


def _rig(scene, **fields):
    rig = scene.add_entity(Entity("Camera"))
    rig.add_component(Transform())
    spec = rig.add_component(Camera2DComponent())
    for key, value in fields.items():
        setattr(spec, key, value)
    return rig, spec


def test_follow_system_uses_component_bounds_groups_and_director_shots():
    scene = Scene("S")
    system = CameraFollowSystem()
    scene.scheduler.add(system)
    a = scene.add_entity(Entity("A"))
    a.add_component(Transform(0, 0))
    b = scene.add_entity(Entity("B"))
    b.add_component(Transform(400, 0))
    rig, spec = _rig(scene, group_entity_ids=f"{a.id}, {b.id}", group_padding=0, min_zoom=0.1, max_zoom=4)
    scene.update(0.016)
    view = system.camera(rig.id)
    assert _center(view) == pytest.approx((200, 0)) and view.zoom == pytest.approx(320 / 400)
    spec.group_entity_ids, spec.follow_entity_id = "", b.id
    spec.bounds_enabled, spec.bounds_max_x, spec.bounds_max_y = True, 500, 300
    scene.update(0.016)
    assert _center(system.camera(rig.id)) == pytest.approx((500 - 160, 90))  # clamped inside the bounds
    system.director(rig.id).focus(CameraShot(10, 20, zoom=2), blend=0)
    scene.update(0.016)
    assert _center(system.camera(rig.id)) == pytest.approx((10, 20)) and system.camera(rig.id).zoom == 2
    assert (rig.get(Transform).x, rig.get(Transform).y) != (system.camera(rig.id).x, system.camera(rig.id).y)


def test_version_1_camera_records_load_with_v2_defaults():
    from asteria.core import ComponentRegistry, deserialize_component, serialize_component

    registry = ComponentRegistry()
    registry.register(Camera2DComponent)
    old = {
        "type": "asteria.Camera2D",
        "version": 1,
        "fields": {
            "width": 320,
            "height": 180,
            "zoom": 2.0,
            "active": True,
            "follow_entity_id": "hero",
            "deadzone_x": 4.0,
            "deadzone_y": 2.0,
            "smoothing": 6.0,
        },
    }
    camera = deserialize_component(old, registry)
    assert camera.zoom == 2.0 and camera.look_ahead_x == 0.0 and camera.bounds is None and camera.group_ids == ()
    assert serialize_component(camera)["version"] == 2


def test_camera_world_commands_are_registered_for_events_and_the_event_editor():
    from asteria.runtime.world_command_handlers import (
        PRESENTATION_COMMANDS,
        STANDARD_WORLD_COMMANDS,
        WORLD_COMMAND_ARGUMENTS,
    )

    for name in ("CAMERA_FOCUS", "CAMERA_RELEASE", "CAMERA_SHAKE"):
        assert name in STANDARD_WORLD_COMMANDS and name in PRESENTATION_COMMANDS
    assert WORLD_COMMAND_ARGUMENTS["CAMERA_FOCUS"][:3] == ("entity", "x", "y")


def test_field_camera_is_identity_by_default_and_never_shows_past_the_map():
    from asteria.runtime.field_camera import FieldViewCamera

    camera = FieldViewCamera(960, 540, 3.0)
    camera.update(0.016)
    assert camera.world_to_screen(10, 20) == (960 / 2 + 30, 540 / 2 + 65 + 60)  # the old fixed mapping
    assert camera.background_rect() == pytest.approx((0, 0, 960, 540))
    camera.director.focus(CameraShot(150, 80, zoom=2), blend=0)  # far corner
    camera.update(0.016)
    x, y, w, h = camera.background_rect()
    assert x <= 0 and y <= 0 and x + w >= 960 - 1e-6 and y + h >= 540 - 1e-6
    camera.director.focus(CameraShot(0, 0, zoom=0.3), blend=0)
    assert camera.update(0.016)[2] == 1.0  # never zooms out past the map


def test_boss_event_focuses_the_camera_on_the_boss_then_cuts_back_for_the_battle(resource_root, monkeypatch):
    pygame = pytest.importorskip("pygame")
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    root = Path(__file__).parents[1] / "reference_projects/complex_reference_rpg"
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    save = GameRuntimeSave.load_json(root / "saves" / "boss_stress.asteria-save.json", project)
    runtime = PlayableTestRuntime(project, save, resource_root, width=960, height=540)
    runtime.open()
    try:
        runtime._ui_mode = "field"
        key = lambda k: pygame.event.Event(pygame.KEYDOWN, key=k)  # noqa: E731
        runtime._frame([key(pygame.K_e)], 0.016)
        assert runtime.game.pending_dialogue.line.speaker == "Astral Tyrant"
        for _ in range(70):  # the 0.8 s focus blend while the line is shown
            runtime._frame([], 0.016)
        boss = next(e for e in runtime.game.scene.entities() if e.name == "Astral Tyrant").get(Transform)
        bx, by = runtime._field_screen_xy(boss.x, boss.y)
        assert runtime.field_camera.zoom == pytest.approx(1.6)
        assert abs(bx - 480) < abs(480 + boss.x * 3 - 480)  # the boss moved toward the screen centre
        x, y, w, h = runtime.field_camera.background_rect()
        assert x <= 0 and y <= 0 and x + w >= 960 - 1e-6 and y + h >= 540 - 1e-6
        runtime._frame([key(pygame.K_RETURN)], 0.016)
        assert runtime.game.mode == "battle"
        runtime.game.battle = None
        runtime.game.mode = "field"  # back on the field after the fight
        runtime._ui_mode = "field"
        runtime._frame([], 0.016)
        runtime._frame([], 0.016)
        assert runtime.field_camera.view == pytest.approx(runtime.field_camera.home)
        assert not runtime.field_camera.director.active
    finally:
        runtime.close()


def _canonical_battle(resource_root, monkeypatch, encounter="boss_room", **presentation):
    pytest.importorskip("pygame")
    from test_playable_battle_loop import _boss_runtime

    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter

    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    runtime = _boss_runtime(resource_root)
    runtime.manifest["battle"].setdefault("presentation", {}).update(presentation)
    runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
    runtime.game.start_encounter(encounter)
    adapter.begin()
    return runtime, adapter


def test_boss_battles_open_with_a_boss_intro_camera(resource_root, monkeypatch):
    runtime, adapter = _canonical_battle(resource_root, monkeypatch)
    try:
        assert adapter.busy() and adapter.intro_boss_id.startswith("astral_tyrant")
        layout = adapter.screen.composer.layout
        zooms, centres = [], []
        for _ in range(40):  # 0.8 s: blending in and holding
            runtime._present_battle(0.02)
            zooms.append(adapter._camera_view[2])
            centres.append(adapter._camera_view[0])
        boss = adapter.screen.scene.visual_for(adapter.intro_boss_id)
        half_w = layout.virtual_width / (2 * 1.35)
        assert max(zooms) == pytest.approx(1.35)
        # moves onto the boss as far as the battlefield edge allows (never shows past the background)
        expected = min(max(boss.anchor.x, half_w), layout.virtual_width - half_w)
        assert centres[-1] == pytest.approx(expected, abs=1.0)
        for cx, zoom in zip(centres, zooms, strict=True):
            view_w = layout.virtual_width / zoom
            assert cx - view_w / 2 >= -1e-6 and cx + view_w / 2 <= layout.virtual_width + 1e-6
        assert not adapter.screen.action_menu.view.total_count  # no commands during the intro
        for _ in range(60):
            runtime._present_battle(0.02)
        assert adapter._camera_view == pytest.approx((layout.virtual_width / 2, layout.virtual_height / 2, 1.0))
        assert not adapter.busy()
    finally:
        runtime.close()


def test_boss_intro_can_be_switched_off(resource_root, monkeypatch):
    runtime, adapter = _canonical_battle(resource_root, monkeypatch, boss_intro=False)
    try:
        assert not adapter.busy() and adapter._intro_until == 0.0
    finally:
        runtime.close()


def test_field_follow_camera_follows_the_player_inside_the_map(runtime):
    from asteria.runtime.field_camera import FieldViewCamera

    camera = FieldViewCamera(960, 540, 3.0, follow={"zoom": 2.0, "smoothing": 0, "deadzone": (5, 5)})
    camera.update(0.016, (0.0, 0.0))
    start = camera.view
    camera.update(0.016, (3.0, 0.0))
    assert camera.view[0] == start[0]  # inside the dead zone
    camera.update(0.016, (40.0, 0.0))
    assert camera.view[0] == pytest.approx(35.0) and camera.view[2] == 2.0
    camera.update(0.016, (10_000.0, 0.0))
    x, y, w, h = camera.background_rect()
    assert x + w >= 960 - 1e-6 and x <= 0  # clamped: never past the map edge
    camera.director.focus(CameraShot(0, 0, zoom=2.5), blend=0)
    camera.update(0.016, (10_000.0, 0.0))
    assert camera.zoom == 2.5
    camera.director.release(blend=0)
    camera.update(0.016, (10_000.0, 0.0))
    assert camera.zoom == 2.0  # back to the follow view
    runtime.manifest["field"]["camera"] = {"follow": {"zoom": 1.5, "smoothing": 0}}
    runtime._field_camera = None
    runtime._ui_mode = "field"
    runtime.game.set_player_position(20.0, 0.0)
    runtime._frame([], 0.016)
    assert runtime.field_camera.zoom == 1.5 and runtime.field_camera.view[0] > 0
