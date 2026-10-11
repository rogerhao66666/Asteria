"""VFX-02 / VFX-03: scene environment (lights, shadows, normal maps, fog, weather, bloom, grading, screen
shaders) on the GPU effect chain, the pygame fallback, and the scene data round trip."""

import pytest

pygame = pytest.importorskip("pygame")

from asteria.core import Entity, Scene, Transform  # noqa: E402
from asteria.runtime.environment2d import (  # noqa: E402
    Environment2DComponent,
    LightSource2DComponent,
    ShadowCaster2DComponent,
    resolve_environment,
)

W, H = 96, 64


def _scene(**env):
    scene = Scene("Lit")
    settings = scene.add_entity(Entity("Scene Settings"))
    settings.add_component(Transform())
    component = settings.add_component(Environment2DComponent())
    for key, value in env.items():
        setattr(component, key, value)
    return scene


def _light(scene, x, y, *, radius=40.0, intensity=1.0, shadow=False, height=20.0):
    entity = scene.add_entity(Entity("Lamp"))
    entity.add_component(Transform(x, y))
    light = entity.add_component(LightSource2DComponent())
    light.radius, light.intensity, light.casts_shadow, light.height = radius, intensity, shadow, height
    light.color_r = light.color_g = light.color_b = 1.0
    return entity


def _env(scene, **kw):
    return resolve_environment(scene, to_screen=lambda x, y: (x, y), scale=1.0, **kw)


@pytest.fixture
def gl():
    moderngl = pytest.importorskip("moderngl")
    try:
        ctx = moderngl.create_standalone_context()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no OpenGL: {exc}")
    yield ctx
    ctx.release()


def _render(gl, world, env, *, ui=None, normals=None):
    from asteria.platform.gpu_presenter import GpuPresenter

    fbo = gl.simple_framebuffer((W, H), components=4)
    presenter = GpuPresenter(gl, (W, H), target=fbo)
    presenter.present_layers(world, ui, pygame, environment=env, normals=normals, time=0.0)
    out = presenter.read(pygame)
    return out, presenter


def _world(color=(200, 200, 200)):
    surface = pygame.Surface((W, H), 0, 32)
    surface.fill(color)
    return surface


def _lum(surface, x, y):
    r, g, b, *_ = surface.get_at((x, y))
    return (r + g + b) / 3


def test_lights_brighten_their_radius_over_the_ambient(gl):
    scene = _scene(lighting_enabled=True, ambient_intensity=0.2)
    _light(scene, 48, 32)
    out, presenter = _render(gl, _world(), _env(scene))
    assert _lum(out, 48, 32) > 150 and _lum(out, 2, 2) < 60  # lit centre, ambient corner (200 * 0.2 = 40)
    assert presenter.last_draw_calls >= 4  # light map + scene + grade + UI composite


def test_shadow_casters_block_shadow_casting_lights(gl):
    scene = _scene(lighting_enabled=True, ambient_intensity=0.0)
    _light(scene, 30, 32, radius=60, shadow=True)
    wall = scene.add_entity(Entity("Wall"))
    wall.add_component(Transform(48, 32))
    caster = wall.add_component(ShadowCaster2DComponent())
    caster.width, caster.height, caster.offset_y = 4.0, 30.0, 0.0
    out, _ = _render(gl, _world(), _env(scene))
    assert _lum(out, 60, 32) < _lum(out, 12, 32) * 0.3  # behind the wall vs the same distance in front


def test_normal_maps_shade_toward_the_light(gl):
    scene = _scene(lighting_enabled=True, ambient_intensity=0.0)
    _light(scene, 48, 32, radius=80, height=6.0)
    normals = pygame.Surface((W, H), 0, 32)
    normals.fill((128, 128, 255))
    pygame.draw.rect(normals, (40, 128, 160), (16, 24, 16, 16))  # left patch faces left (away from the light)
    pygame.draw.rect(normals, (216, 128, 160), (64, 24, 16, 16))  # right patch... faces right (away too)
    pygame.draw.rect(normals, (216, 128, 160), (20, 44, 8, 8))  # faces right = toward the light, left side
    out, _ = _render(gl, _world(), _env(scene), normals=normals)
    toward, away = _lum(out, 24, 48), _lum(out, 24, 32)
    assert toward > away * 1.5


def test_bloom_spreads_light_from_bright_pixels(gl):
    world = _world((0, 0, 0))
    pygame.draw.rect(world, (255, 255, 255), (44, 28, 8, 8))
    dark, _ = _render(gl, world, _env(_scene(vignette=0.0001)))
    bloomed, _ = _render(gl, world, _env(_scene(bloom_enabled=True, bloom_threshold=0.5, bloom_intensity=1.5)))
    assert _lum(dark, 40, 32) == 0 and _lum(bloomed, 40, 32) > 10  # glow beside the bright square


def test_grading_vignette_and_ui_stays_untouched(gl):
    world = _world((220, 60, 40))
    ui = pygame.Surface((W, H), pygame.SRCALPHA, 32)
    ui.fill((0, 0, 0, 0))
    pygame.draw.rect(ui, (10, 200, 30, 255), (0, 0, 10, 10))  # an opaque UI widget
    out, _ = _render(gl, world, _env(_scene(saturation=0.0, vignette=0.9)), ui=ui)
    r, g, b, _ = out.get_at((48, 32))
    assert abs(r - g) <= 2 and abs(g - b) <= 2  # desaturated world
    assert _lum(out, 90, 60) < _lum(out, 48, 32)  # vignette darkens the corner
    assert tuple(out.get_at((4, 4)))[:3] == (10, 200, 30)  # UI composited after grading


def test_builtin_and_project_screen_shaders(gl, tmp_path):
    world = _world((200, 50, 50))
    gray, _ = _render(gl, world, _env(_scene(screen_shader="grayscale")))
    r, g, b, _ = gray.get_at((10, 10))
    assert abs(r - g) <= 2 and abs(g - b) <= 2
    source = "vec4 effect(vec2 uv) { return vec4(1.0 - scene(uv).rgb, 1.0); }"
    env = _env(_scene(screen_shader_asset_id="s"), read_shader=lambda asset_id: source)
    inverted, _ = _render(gl, world, env)
    assert tuple(inverted.get_at((10, 10)))[:3] == (55, 205, 205)
    broken = _env(_scene(screen_shader_asset_id="bad"), read_shader=lambda asset_id: "this is not glsl")
    out, presenter = _render(gl, world, broken)
    assert presenter.post.errors and tuple(out.get_at((10, 10)))[:3] == (200, 50, 50)  # reported, game goes on


def test_fog_mixes_toward_its_colour(gl):
    out, _ = _render(gl, _world((0, 0, 0)), _env(_scene(fog_density=0.8, fog_r=1.0, fog_g=1.0, fog_b=1.0)))
    assert _lum(out, 48, 32) > 80


def test_pygame_fallback_lights_and_fogs_and_reports_gpu_only_effects():
    from asteria.runtime.environment_fallback import PygameEnvironmentRenderer, unsupported

    scene = _scene(lighting_enabled=True, ambient_intensity=0.2, bloom_enabled=True, fog_density=0.0)
    _light(scene, 48, 32)
    env = _env(scene)
    world = _world()
    PygameEnvironmentRenderer(pygame).apply(world, env)
    assert _lum(world, 48, 32) > 120 and _lum(world, 2, 2) < 60
    assert unsupported(env) == ["bloom"]


def test_weather_is_deterministic_capped_and_follows_the_camera():
    from asteria.runtime.weather import WeatherSystem

    a, b = WeatherSystem(W, H, seed="s"), WeatherSystem(W, H, seed="s")
    for system in (a, b):
        for _ in range(30):
            system.update(1 / 60, "snow", 0.5, 200, camera=(0.0, 0.0))
    assert (a.x, a.y) == (b.x, b.y) and a.count == int(200 * 0.5 * 0.8)
    before = list(a.x)
    a.update(0.0, "snow", 0.5, 200, camera=(10.0, 0.0), scale=2.0)  # camera moved right 10 world units
    stayed = [(x, after) for x, after in zip(before, a.x, strict=True) if x - 20.0 >= -60]  # others respawn
    assert stayed and all(abs(after - (x - 20.0)) < 1e-6 for x, after in stayed)
    surface = _world((0, 0, 0))
    assert a.draw(pygame, surface) == a.count
    a.update(1 / 60, "none", 0.5, 200)
    assert a.count == 0


def test_environment_components_survive_project_save_and_reload(tmp_path):
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    project = Project("Env")
    scene = project.add_scene(_scene(lighting_enabled=True, weather="rain", bloom_enabled=True, saturation=0.4))
    _light(scene, 5, 6, shadow=True)
    project.save_json(tmp_path / "p.json")
    again = Project.load_json(tmp_path / "p.json", default_component_registry())
    env = _env(again.scenes()[0])
    assert env.lighting and env.weather == "rain" and env.post_effect("bloom") and env.post_effect("grade")
    assert env.lights[0][0].casts_shadow and (env.lights[0][0].x, env.lights[0][0].y) == (5.0, 6.0)


# --- VFX-03: water, afterimages, trails --------------------------------------------------------------------


def _water(scene, x, y, w, h, **kw):
    from asteria.runtime.environment2d import WaterRegion2DComponent

    entity = scene.add_entity(Entity("Pond"))
    entity.add_component(Transform(x, y))
    water = entity.add_component(WaterRegion2DComponent())
    water.width, water.height = w, h
    for key, value in kw.items():
        setattr(water, key, value)
    return water


def _stripes():
    world = _world((0, 0, 0))
    for x in range(0, W, 4):
        pygame.draw.line(world, (255, 255, 255), (x, 0), (x, H))
    return world


def test_water_ripples_and_tints_only_inside_its_region(gl):
    scene = _scene()
    _water(scene, 24, 32, 48, 64, amplitude=2.0, wavelength=8.0, tint_strength=0.5)
    world = _stripes()
    out, _ = _render(gl, world, _env(scene))
    inside = [tuple(out.get_at((x, y)))[:3] for x in range(0, 48) for y in range(0, H)]
    original_inside = [tuple(world.get_at((x, y)))[:3] for x in range(0, 48) for y in range(0, H)]
    assert inside != original_inside  # distorted and tinted
    assert all(out.get_at((x, y))[:3] == world.get_at((x, y))[:3] for x in range(52, W) for y in range(H))


def test_water_fallback_shifts_rows_and_tints():
    from asteria.runtime.environment_fallback import PygameEnvironmentRenderer

    scene = _scene()
    _water(scene, 24, 32, 48, 64, amplitude=2.0, wavelength=8.0, tint_strength=0.5)
    world = _stripes()
    before = pygame.image.tobytes(world, "RGB")
    renderer = PygameEnvironmentRenderer(pygame)
    renderer.time = 0.3
    renderer.apply(world, _env(scene))
    assert pygame.image.tobytes(world, "RGB") != before
    assert world.get_at((80, 10)) == _stripes().get_at((80, 10))  # outside untouched


def test_motion_echo_records_fades_and_expires():
    from asteria.presentation.motion_fx import EchoSettings, MotionEcho

    echo = MotionEcho(EchoSettings.of("afterimage"))
    echo.activate(0.0, 0.2)
    for i in range(10):
        echo.record(i * 0.03, f"pose{i}", moving=False)
    ghosts = echo.ghosts(0.27)
    assert 1 <= len(ghosts) <= 4 and ghosts[0][1] < ghosts[-1][1] <= 1.0  # older copies are fainter
    assert echo.ghosts(5.0) == [] and echo.idle  # expired
    trail = EchoSettings.of("trail", count=20)
    assert trail.count == 20 and trail.interval < EchoSettings.of("afterimage").interval


def test_motion_fx_beats_give_battle_afterimages(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_playable_battle_loop import _boss_runtime

    from asteria.editor.action_timeline_authoring import ActionTimelineController
    from asteria.editor.model import EditorDocument
    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter
    from asteria.runtime.camera import Camera2D

    runtime = _boss_runtime(resource_root)
    try:
        document = EditorDocument()
        document.set_project(runtime.game.project)
        timeline = ActionTimelineController(document)
        for sequence_id in timeline.sequences():
            timeline.add_beat(sequence_id, "echo", 0.0, "motion_fx", "afterimage", "@source", duration=1.0)
            assert not [p for p in timeline.problems(timeline.get(sequence_id)) if "motion_fx" in p]
        from asteria.editor.action_timeline_authoring import ActionTimelineError

        with pytest.raises(ActionTimelineError, match="motion_fx cue"):  # rejected when authored
            timeline.add_beat("default_action", "bad_echo", 0.0, "motion_fx", "sparkles", "@source")
        runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        adapter.begin()
        runtime._advance_to_hero_turn()
        runtime._present_battle(0.016)
        while adapter.busy():
            runtime._present_battle(0.02)
        runtime._use_skill(0)
        actor_draws = None
        layout = adapter.screen.composer.layout
        camera = Camera2D(width=layout.virtual_width, height=layout.virtual_height)
        for _ in range(80):
            runtime._present_battle(0.02)
            frame = adapter.screen.animation.build_frame(camera)
            for member in list(adapter.screen.animation.echoes.by_key):
                visual = adapter.screen.scene.visual_for(member)
                draws = [d for d in frame.combatant_draws if abs(d.depth - visual.anchor.depth) < 1e-3]
                if len(draws) >= 3:
                    actor_draws = draws
            if actor_draws:
                break
        assert actor_draws and len(actor_draws) >= 3  # body + at least two fading copies
        ghosts = sorted(actor_draws, key=lambda d: d.depth)[:-1]
        assert all(g.opacity < 1.0 for g in ghosts)
    finally:
        runtime.close()


def test_field_trail_and_environment_layers_on_the_pygame_path(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_playable_battle_loop import _boss_runtime

    from asteria.runtime.environment2d import MotionTrail2DComponent

    runtime = _boss_runtime(resource_root)
    try:
        runtime._ui_mode = "field"
        runtime.game.player.add_component(MotionTrail2DComponent()).kind = "afterimage"
        runtime._frame([], 0.016)
        runtime.present()
        plain = runtime.screen.copy()
        settings = runtime.game.scene.add_entity(Entity("Scene Settings"))
        settings.add_component(Transform())
        env = settings.add_component(Environment2DComponent())
        env.lighting_enabled, env.ambient_intensity, env.fog_density = True, 0.25, 0.0
        for _ in range(8):  # walk right: echoes build up behind the player
            x, y = runtime.game.player.get(Transform).x, runtime.game.player.get(Transform).y
            runtime.game.set_player_position(x + 3.0, y)
            runtime._frame([], 0.07)
            runtime.present()
        assert runtime._field_echoes.by_key[runtime.game.player.id].snapshots
        lit = runtime.screen
        # an opaque HUD text pixel ("Field Test", yellow): the UI layer is never lit
        hud = next(
            (x, y)
            for y in range(runtime.height - 84, runtime.height - 60)
            for x in range(34, 200)
            if plain.get_at((x, y))[0] > 230 and plain.get_at((x, y))[1] > 200
        )
        world = (runtime.width // 2, 140)
        assert lit.get_at(hud) == plain.get_at(hud)
        assert sum(lit.get_at(world)[:3]) < sum(plain.get_at(world)[:3]) * 0.6
        assert runtime.environment_unsupported == []
    finally:
        runtime.close()
