"""VFX-01: particle effects as authored data - a deterministic simulation used by field emitters, the PLAY_VFX
event command, battle action-timeline beats and the editor's live preview."""

import dataclasses

import pytest

from asteria.presentation.particles import (
    PRESETS,
    ParticleEffectDefinition,
    ParticleSystem,
    effect_definition,
    particle_effect_asset,
    preset,
)


def _run(system, seconds, dt=0.05):
    for _ in range(round(seconds / dt)):
        system.update(dt)


def test_every_setting_round_trips_and_bad_values_are_named():
    for name in PRESETS:
        definition = preset(name, f"fx.{name}")
        assert ParticleEffectDefinition.from_data(definition.to_data()) == definition
    with pytest.raises(ValueError, match="lifetime"):
        ParticleEffectDefinition("x", lifetime=(0, 1))
    with pytest.raises(ValueError, match="shape"):
        ParticleEffectDefinition("x", shape="star")
    with pytest.raises(ValueError, match="unknown particle effect fields"):
        ParticleEffectDefinition.from_data({"effect_id": "x", "colour": [1, 2, 3]})
    # any numbers the author wants: huge rates, negative gravity, wide spreads
    wild = ParticleEffectDefinition("x", rate=5000, gravity=(-300, -900), spread=720, max_particles=10000)
    assert wild.rate == 5000 and wild.gravity == (-300.0, -900.0)


def test_the_simulation_is_deterministic_and_follows_its_settings():
    fire = preset("fire", "fx.fire")
    a, b = ParticleSystem(fire, seed=3), ParticleSystem(fire, seed=3)
    _run(a, 1.0)
    _run(b, 1.0)
    assert a.views() == b.views() and a.count > 0
    assert 30 <= a.spawned <= 41  # 40 per second for one second
    rising = ParticleSystem(fire.replace(spread=0, gravity=(0, 0), shape="point"), seed=1)
    _run(rising, 0.3)
    assert all(v.y < 0 for v in rising.views())  # direction -90 = up
    capped = ParticleSystem(fire.replace(rate=1000, max_particles=25, lifetime=(5, 5)))
    _run(capped, 1.0)
    assert capped.count == 25
    fading = ParticleSystem(ParticleEffectDefinition("x", burst=1, rate=0, lifetime=(1, 1), size=(10, 0)))
    fading.update(0.0)
    fading.update(0.5)
    (half,) = fading.views()
    assert half.size == pytest.approx(5) and 0 < half.color[3] < 255  # halfway between birth and death


def test_one_shots_end_emitting_and_local_particles_follow_the_emitter():
    burst = preset("explosion", "fx.boom")
    system = ParticleSystem(burst)
    system.update(0.0)
    assert system.count == 80 and not system.finished
    _run(system, 1.0)
    assert system.finished  # 0.05 s of emission, every particle dead after its 0.8 s life
    looping = ParticleSystem(preset("fire", "fx.fire"), emit_for=0.5)
    _run(looping, 2.0)
    assert looping.finished  # a looping effect played once stops after emit_for
    local = ParticleSystem(preset("sparkle", "fx.s").replace(local=True, rate=50, speed=(0, 0)))
    _run(local, 0.2)
    before = [(v.x, v.y) for v in local.views()]
    local.move_to(100, 40)
    after = [(v.x, v.y) for v in local.views()]
    assert after == [(x + 100, y + 40) for x, y in before]


def test_an_effect_is_a_project_asset_that_survives_save_and_load(tmp_path):
    from asteria.editor import EditorDocument
    from asteria.project import Project

    registry = EditorDocument().component_registry
    from asteria.core import Scene

    project = Project("Particles")
    project.add_scene(Scene("Map"))
    definition = preset("heal", "fx.heal").replace(color_end=(10, 20, 30, 0))
    project.assets.register(particle_effect_asset(definition))
    path = tmp_path / "p.asteria.json"
    project.save_json(path)
    loaded = Project.load_json(path, registry)
    assert effect_definition(loaded.assets, "fx.heal") == definition
    assert effect_definition(loaded.assets, "nothing") is None


def _field_emitter(runtime, effect, entity_name="Astral Tyrant", **fields):
    from asteria.runtime.environment2d import ParticleEmitter2DComponent

    runtime.project.assets.register(particle_effect_asset(effect), replace=True)
    entity = next(e for e in runtime.game.scene.entities() if e.name == entity_name)
    component = entity.try_get(ParticleEmitter2DComponent) or entity.add_component(ParticleEmitter2DComponent())
    component.effect_id = effect.effect_id
    for key, value in fields.items():
        setattr(component, key, value)
    return entity, component


def test_a_field_entity_emits_its_particles_and_they_are_drawn(runtime):
    runtime._ui_mode = "field"
    entity, component = _field_emitter(runtime, preset("fire", "fx.torch"), offset_y=-20.0)
    for _ in range(20):
        runtime._frame([], 0.05)
    emitter = runtime.field_effects.emitters[entity.id]
    assert emitter.system.count > 10 and runtime.particles_drawn == emitter.system.count
    from asteria.core import world_position

    x, y = world_position(entity)
    assert (emitter.system.x, emitter.system.y) == (x, y - 20.0)  # follows the entity, with its offset
    component.playing = False
    for _ in range(30):
        runtime._frame([], 0.05)
    assert emitter.system.count == 0  # stopped: the live particles finished, none new
    component.enabled = False
    runtime._frame([], 0.05)
    assert entity.id not in runtime.field_effects.emitters


def test_play_vfx_plays_a_particle_effect_once_at_an_entity(runtime):
    from asteria.events import EventInstruction, EventProgram

    runtime._ui_mode = "field"
    runtime.project.assets.register(particle_effect_asset(preset("heal", "fx.heal")))
    program = EventProgram(
        (EventInstruction("WORLD", {"command": "PLAY_VFX", "args": {"asset_id": "fx.heal", "entity": "player"}}),)
    )
    runtime.game.project.event_programs.register("heal_fx", program)
    runtime.game.events.start("heal_fx")
    runtime._frame([], 0.05)
    runtime._frame([], 0.05)
    (one_shot,) = runtime.field_effects.particles
    assert one_shot.entity_id == runtime.game.player.id and one_shot.system.count > 0
    for _ in range(60):
        runtime._frame([], 0.05)
    assert runtime.field_effects.particles == []  # over and removed


def test_a_battle_timeline_beat_can_cue_a_particle_effect(resource_root, monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from test_canonical_battle_presentation import _settle, _use
    from test_playable_battle_loop import _boss_runtime

    from asteria.runtime.battle_presentation_adapters import CanonicalBattleAdapter

    runtime = _boss_runtime(resource_root)
    try:
        project = runtime.game.project
        project.assets.register(particle_effect_asset(preset("explosion", "fx.burst")))
        library = project.battle_presentation_library
        sequence = library.require("motion_sequences", "fire_arc")
        beats = tuple(dataclasses.replace(b, cue="fx.burst") if b.channel == "vfx" else b for b in sequence.beats)
        library.set("motion_sequences", "fire_arc", dataclasses.replace(sequence, beats=beats))
        runtime._battle_presentation = adapter = CanonicalBattleAdapter(runtime)
        runtime.game.start_encounter("boss_room")
        adapter.begin()
        runtime._advance_to_hero_turn()
        runtime._present_battle(0.016)
        _settle(runtime)
        drawn, spread = [], [0.0]
        draw = runtime.particle_drawer.draw

        def record(surface, systems, *args, **kwargs):
            for system in systems:  # the burst must grow from one cue to the next frame, not restart
                spread[0] = max([spread[0], *(abs(v.x - system.x) + abs(v.y - system.y) for v in system.views())])
            drawn.append(draw(surface, systems, *args, **kwargs))
            return drawn[-1]

        runtime.particle_drawer.draw = record
        _use(runtime, "fire_arc")
        runtime._present_battle(0.0)
        for _ in range(60):
            runtime._present_battle(0.02)
        assert adapter._cue_particles and max(drawn) >= 40  # the burst was drawn on the target
        assert spread[0] > 15  # and its particles flew apart over the frames
    finally:
        runtime.close()


def test_the_editor_creates_edits_previews_and_undoes_particle_effects():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene
    from asteria.editor import EditorDocument
    from asteria.editor.inspector import build_inspector_fields, inspector_choices
    from asteria.editor.particle_effect_widget import ParticleEffectWidget
    from asteria.project import Project
    from asteria.runtime.environment2d import ParticleEmitter2DComponent

    QApplication.instance() or QApplication([])
    project = Project("P")
    scene = project.add_scene(Scene("Map"))
    document = EditorDocument(project)
    widget = ParticleEffectWidget(document)
    assert widget.new_effect("fx.campfire", "fire") == "fx.campfire"
    assert widget.selected_id == "fx.campfire" and widget.preview.system is not None
    widget.inputs["rate"].setValue(120.0)
    widget.inputs["gravity"].parts[1].setValue(-50.0)
    widget.inputs["blend"].setCurrentText("alpha")
    for _ in range(5):
        widget.preview._tick()
    assert widget.preview.system.definition.rate == 120.0  # the preview shows the unapplied form
    assert widget.apply() is True
    applied = effect_definition(project.assets, "fx.campfire")
    assert (applied.rate, applied.gravity, applied.blend) == (120.0, (0.0, -50.0), "alpha")
    document.undo()
    assert effect_definition(project.assets, "fx.campfire").rate == 40.0
    document.redo()
    widget.refresh()
    assert widget.duplicate_effect("fx.campfire_2") == "fx.campfire_2"
    entity = scene.add_entity(Entity("Torch"))
    emitter = entity.add_component(ParticleEmitter2DComponent())
    field = next(f for f in build_inspector_fields(emitter) if f.name == "effect_id")
    assert [v for _, v in inspector_choices(document, emitter, field)] == ["", "fx.campfire", "fx.campfire_2"]
    emitter.effect_id = "fx.campfire_2"
    assert "Map / Torch" in widget.api.usages("fx.campfire_2")
    widget.refresh(select="fx.campfire_2")
    assert widget.delete_effect(confirm=False) is False  # used: asks first, refused here
    assert widget.delete_effect(confirm=True) is True
    assert effect_definition(project.assets, "fx.campfire_2") is None
    document.undo()
    assert effect_definition(project.assets, "fx.campfire_2") is not None


def test_problems_warn_about_an_emitter_without_its_effect():
    from asteria.core import Entity, Scene
    from asteria.editor import EditorDocument
    from asteria.editor.problems import collect_problems
    from asteria.project import Project
    from asteria.runtime.environment2d import ParticleEmitter2DComponent

    project = Project("P")
    scene = project.add_scene(Scene("Map"))
    torch = scene.add_entity(Entity("Torch"))
    torch.add_component(ParticleEmitter2DComponent()).effect_id = "fx.gone"
    problems = [p for p in collect_problems(EditorDocument(project)) if p.area == "Particle Effects"]
    assert problems and "fx.gone" in problems[0].message
