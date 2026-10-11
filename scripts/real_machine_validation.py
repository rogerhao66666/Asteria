"""Real-machine validation (D14 #4): run on a macOS machine with a display.

    python scripts/real_machine_validation.py OUTPUT_DIR [--only CHECK ...]

Every check opens real windows / devices (no dummy SDL drivers, no
offscreen Qt) and records one of PASS, FAIL, BLOCKED (required device or
permission missing) or NOT EXECUTED (needs a human; a procedure is printed
in the report instead). Nothing is marked PASS without a measurement.
Results: OUTPUT_DIR/results.json plus screenshots.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PROJECT = REPO / "reference_projects" / "complex_reference_rpg"
PROJECT_FILE = PROJECT / "project.asteria.json"
for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
    os.environ.pop(key, None)


def result(check, status, evidence, **details):
    return {"check": check, "status": status, "evidence": evidence, **details}


# -- checks (each runs in its own interpreter) --------------------------------


def check_gpu_window(out):
    import pygame

    from asteria.platform.moderngl_backend import ModernglRuntimeBackend
    from asteria.runtime.draw import TextureDraw
    from asteria.runtime.profiler import RuntimeProfiler

    backend = ModernglRuntimeBackend()
    backend.open("Asteria GPU window validation", 640, 360)
    renderer = backend.ctx.info["GL_RENDERER"]
    texture = backend.load_texture("hero", str(PROJECT / "playable_assets" / "battle" / "hero_01.png"))
    profiler = RuntimeProfiler(target_fps=60)
    sprites = 400
    for frame in range(240):
        backend.tick(60)
        profiler.begin_frame()
        backend.begin_frame()
        for i in range(sprites):
            x = (i * 37 + frame * 3) % 600
            y = (i * 53) % 320
            backend.draw_texture(texture, TextureDraw("hero", (64 * (frame // 8 % 4 + 1), 0, 64, 64), x, y, 32, 32))
        with profiler.section("present"):
            backend.end_frame()
        profiler.end_frame()
    raw = backend.ctx.screen.read(components=3)
    width, height = backend.screen_size
    image = pygame.image.frombuffer(raw, (width, height), "RGB")
    pygame.image.save(pygame.transform.flip(image, False, True), str(out / "gpu_window.png"))
    distinct = len(set(raw[i : i + 3] for i in range(0, len(raw), 3 * 97)))
    backend.close()
    report = profiler.report()
    software = "software" in renderer.lower()
    ok = distinct > 5 and not software and report["pacing"]["measured_fps"] > 30
    return result(
        "gpu_window",
        "PASS" if ok else "FAIL",
        f"ModernGL window on '{renderer}': {sprites} sprites/frame for 240 frames, "
        f"{report['pacing']['measured_fps']} fps, read-back framebuffer has {distinct} sampled colours",
        renderer=renderer,
        pacing=report["pacing"],
        frame=report["frame"],
        screenshot="gpu_window.png",
    )


def check_input(out):
    import pygame

    from asteria.platform.pygame_input import PygameInputSource
    from asteria.runtime.input_map import InputActionMap, InputActionTracker

    pygame.init()
    pygame.display.set_mode((320, 180))
    driver = pygame.display.get_driver()
    source = PygameInputSource(pygame)
    tracker = InputActionTracker(InputActionMap.default())
    seen = {}
    for key, action in ((pygame.K_RIGHT, "move_right"), (pygame.K_RETURN, "confirm"), (pygame.K_ESCAPE, "cancel")):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))
        source.handle_events(pygame.event.get())
        tracker.update(source.raw_state())
        seen[action] = tracker.just_pressed(action)
        pygame.event.post(pygame.event.Event(pygame.KEYUP, key=key))
        source.handle_events(pygame.event.get())
        tracker.update(source.raw_state())
    pads = pygame.joystick.get_count()
    pygame.quit()
    keyboard = result(
        "input_keyboard_event_queue",
        "PASS" if all(seen.values()) else "FAIL",
        f"Key events posted to the real {driver} window's SDL event queue reached the input map: {seen}",
        note="Synthetic events through the OS window queue; a physical key press is a separate manual item.",
    )
    physical = result(
        "input_keyboard_physical", "NOT EXECUTED", "Needs a person pressing keys in the game window (procedure M1)."
    )
    controller = result(
        "input_controller",
        "BLOCKED" if pads == 0 else "NOT EXECUTED",
        "No game controller connected (pygame.joystick.get_count() == 0); procedure M2."
        if pads == 0
        else f"{pads} controller(s) connected; run procedure M2 with a person.",
    )
    return [keyboard, physical, controller]


def check_audio(out):
    import pygame

    pygame.mixer.init()
    init = pygame.mixer.get_init()
    sound = pygame.mixer.Sound(str(PROJECT / "playable_assets" / "audio" / "hit.wav"))
    length = sound.get_length()
    start = time.perf_counter()
    channel = sound.play()
    busy_at_start = channel is not None and channel.get_busy()
    while channel.get_busy() and time.perf_counter() - start < length + 2.0:
        time.sleep(0.005)
    elapsed = time.perf_counter() - start
    pygame.mixer.music.load(str(PROJECT / "playable_assets" / "audio" / "battle_theme.ogg"))
    pygame.mixer.music.play()
    time.sleep(0.5)
    music_busy = pygame.mixer.music.get_busy()
    pygame.mixer.music.stop()
    pygame.mixer.quit()
    ok = busy_at_start and abs(elapsed - length) < 0.25 and music_busy
    return [
        result(
            "audio_playback_device",
            "PASS" if ok else "FAIL",
            f"CoreAudio device opened {init}; hit.wav ({length:.3f}s) kept its channel busy for {elapsed:.3f}s; "
            f"battle_theme.ogg streaming={music_busy}",
            note="Device-level playback only; audible confirmation is manual item M3.",
        ),
        result("audio_playback_audible", "NOT EXECUTED", "Needs a listener (procedure M3)."),
        result(
            "audio_latency",
            "NOT EXECUTED",
            "Output latency needs an acoustic or loopback measurement (procedure M4); "
            "the configured mixer buffer is not reported by pygame and is not presented as latency.",
        ),
    ]


def _runtime(battle_presentation="canonical"):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.battle_presentation_adapters import create_battle_presentation_adapter
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), PROJECT)
    runtime.manifest["battle"]["presentation"] = {"adapter": battle_presentation}
    runtime._battle_presentation = create_battle_presentation_adapter(runtime)
    return runtime


def check_battle_frame_pacing(out):
    import pygame

    from asteria.runtime.profiler import RuntimeProfiler

    runtime = _runtime()
    runtime.open()
    driver = pygame.display.get_driver()
    profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
    runtime._ui_mode = "field"
    runtime.game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    adapter = runtime._battle_presentation
    tyrant = None
    frame_changes, last_frame, shots, uses = 0, None, [], 0
    start = time.perf_counter()
    frames = 0
    while time.perf_counter() - start < 10.0 and runtime.running:
        dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
        events = pygame.event.get()
        if not adapter.busy() and runtime.game.mode == "battle" and not runtime._victory and frames % 20 == 0:
            key = (pygame.K_2, pygame.K_1, pygame.K_1)[uses % 3]
            events.append(pygame.event.Event(pygame.KEYDOWN, key=key))
            uses += 1
        profiler.begin_frame()
        runtime._frame(events, dt)
        with profiler.section("present"):
            pygame.display.flip()
        runtime._sample_counters()
        profiler.end_frame()
        frames += 1
        if adapter.screen is not None and adapter.visuals_enabled:
            tyrant = adapter.screen.animation.combatant("astral_tyrant:1")
            if tyrant.frame_index != last_frame:
                frame_changes += 1
                last_frame = tyrant.frame_index
        if adapter.particle_count() and len(shots) < 2 and frames > 30:
            name = f"battle_window_{len(shots)}.png"
            pygame.image.save(runtime.screen, str(out / name))
            shots.append(name)
    elapsed = time.perf_counter() - start
    runtime.close()
    report = profiler.report()
    pacing = report["pacing"]
    smooth_ok = adapter.visuals_enabled and frame_changes / elapsed >= 3.0
    pacing_ok = (
        pacing["measured_fps"] >= 55
        and pacing["interval_p99_ms"] <= 25.0
        and pacing["frames_over_budget"] <= max(1, int(0.01 * frames))
    )
    (out / "battle_profile.json").write_text(json.dumps(report, indent=2))
    return [
        result(
            "animation_smoothness",
            "PASS" if smooth_ok else "FAIL",
            f"Canonical battle screen in a real {driver} window: combatant sprites drawn, boss animation "
            f"advanced {frame_changes} frames in {elapsed:.1f}s ({frame_changes / elapsed:.1f}/s); "
            f"{uses} skills used through the key-event queue; VFX particles peaked at "
            f"{report['counters'].get('particles', {}).get('max', 0):g}",
            screenshots=shots,
            note="Perceived smoothness by a person is manual item M5.",
        ),
        result(
            "frame_pacing",
            "PASS" if pacing_ok else "FAIL",
            f"{frames} frames: {pacing['measured_fps']} fps (target 60), jitter {pacing['interval_jitter_ms']} ms, "
            f"p99 interval {pacing['interval_p99_ms']} ms, {pacing['frames_over_budget']} frames over 1.5x budget",
            pacing=pacing,
            frame=report["frame"],
            sections={k: v["mean_ms"] for k, v in report["sections"].items()},
            unsupported=report["unsupported"],
        ),
    ]


def check_field_camera(out):
    """CAM-02: the boss event's camera focus in a real window (zoom, map coverage, boss framing)."""
    import pygame

    from asteria.core import Transform

    runtime = _runtime()
    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    boss = next(e for e in runtime.game.scene.entities() if e.name == "Astral Tyrant").get(Transform)

    def run(seconds):
        start = time.perf_counter()
        while time.perf_counter() - start < seconds:
            dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
            runtime._frame(pygame.event.get(), dt)
            pygame.display.flip()

    run(0.5)
    before = runtime._field_screen_xy(boss.x, boss.y)
    pygame.image.save(runtime.screen, str(out / "field_camera_home.png"))
    runtime.game.events.start("boss_interaction_event", replace=True)
    run(1.5)  # focus blend is 0.8 s; the boss line is on screen meanwhile
    after = runtime._field_screen_xy(boss.x, boss.y)
    zoom = runtime.field_camera.zoom
    bx, by, bw, bh = runtime.field_camera.background_rect()
    covered = bx <= 0 and by <= 0 and bx + bw >= runtime.width - 1e-6 and by + bh >= runtime.height - 1e-6
    pygame.image.save(runtime.screen, str(out / "field_camera_boss_focus.png"))
    runtime.close()
    centre = (runtime.width / 2, runtime.height / 2)
    closer = abs(after[0] - centre[0]) < abs(before[0] - centre[0])
    ok = abs(zoom - 1.6) < 1e-6 and covered and closer
    return result(
        "field_camera_boss_focus",
        "PASS" if ok else "FAIL",
        f"Boss event camera in a real {driver} window: zoom {zoom:.2f} (authored 1.6), map image covers the "
        f"screen={covered}, boss moved from x={before[0]:.0f} to x={after[0]:.0f} (screen centre {centre[0]:.0f})",
        screenshots=["field_camera_home.png", "field_camera_boss_focus.png"],
        note="Whether the move feels right to a player is part of manual item M5.",
    )


def check_editor_playtest(out):
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = PROJECT_FILE
    window.show()
    app.processEvents()
    platform_name = app.platformName()
    started = window.play_project()
    process = window.runtime_process
    alive_after = None
    deadline = time.perf_counter() + 4.0
    while time.perf_counter() < deadline:
        app.processEvents()
        time.sleep(0.05)
    alive_after = process is not None and process.running
    stopped = window.stop_play()
    exited = process is not None and not process.running
    window.document.mark_saved()
    window.close()
    ok = started and alive_after and stopped and exited
    return result(
        "editor_to_runtime_playtest",
        "PASS" if ok else "FAIL",
        f"Qt platform '{platform_name}': Run Project started the runtime process={started}, "
        f"still running after 4 s={alive_after}, Stop Play returned={stopped}, process exited={exited}",
    )


def check_editor_tools(out):
    """CB10 editors in a real Cocoa editor window: each tool is driven, measured and screenshotted (nothing saved)."""
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = PROJECT_FILE
    window.resize(1600, 1000)
    window.show()
    checks, shots = {}, []

    def settle(seconds=0.3):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.02)

    def shot(name):
        settle()
        window.grab().save(str(out / name))
        shots.append(name)

    window.refresh_all()
    window.workspace.set_mode(WorkspaceMode.UI)
    window.ui_workspace.setCurrentWidget(window.animation_editor)
    window.animation_editor.refresh(sheet="battle.combatant.hero_01")
    checks["animation_editor"] = window.animation_editor.sheet == "battle.combatant.hero_01"
    shot("editor_animation.png")
    checks["action_timeline"] = window._open_action_timeline("fire_arc")
    shot("editor_action_timeline.png")
    window.ui_workspace.setCurrentWidget(window.vfx_editor)
    checks["vfx_tool"] = window.vfx_editor.select_vfx("battle.fx.flame")
    window.vfx_editor.scrub.setValue(450)
    checks["vfx_preview"] = window.vfx_editor._render() is not None and not window.vfx_editor.stage.pixmap.isNull()
    shot("editor_vfx.png")
    window.workspace.set_mode(WorkspaceMode.RPG)
    window.rpg_workspace.setCurrentWidget(window.enemy_ai_editor)
    ai = window.enemy_ai_editor
    ai.select_ai("astral_tyrant_ai")
    ai.select_rule("nova")
    ai.set_preview_resource("vitality", 1800)
    preview = ai.set_preview_resource("rage", 40)
    checks["enemy_ai_preview"] = preview is not None and preview.chances == (("nova", 1.0),)
    shot("editor_enemy_ai.png")
    window.rpg_workspace.setCurrentWidget(window.rpg_authoring)
    family = window.rpg_authoring.child
    family.category.setCurrentIndex(family.category.findData("enemies"))
    family.select_ids(family._ids[:3])
    checks["multi_select_batch_fields"] = len(family.selected_ids) == 3 and "stats.power" in family.batch_fields()
    shot("editor_records_multiselect.png")
    db = window.document.project.rpg_database
    encounter = db.encounters["boss_room"]
    removed = db.enemies.pop("mender_wisp")  # in-memory only: show a real problem, then restore
    window.problems_widget.refresh()
    window.problems_dock.raise_()
    problem = next(
        (p for p in window.problems_widget.problems if p.target[:3] == ("record", "rpg", "encounters")), None
    )
    checks["problems_panel"] = problem is not None and window.navigate_to_problem(problem)
    shot("editor_problems.png")
    db.enemies["mender_wisp"] = removed
    window.problems_widget.refresh()
    checks["problems_clear_again"] = window.problems_widget.problems == [] and encounter is db.encounters["boss_room"]
    window.workspace.set_mode(WorkspaceMode.CODE)
    code = window.code_workspace
    code.editor.setPlainText('scene = project.scene_named("Map")\nscene.')
    code.editor.moveCursor(code.editor.textCursor().MoveOperation.End)
    checks["script_completion"] = "entities" in code.show_completions()
    shot("editor_script.png")
    started = window.play_project()
    snapshot = None
    deadline = time.perf_counter() + 20.0
    while snapshot is None and time.perf_counter() < deadline:
        settle(0.5)
        snapshot = window.debugger_widget.refresh()
    window.debugger_widget.set_args("give_item", item_id="ether_leaf", quantity=1)
    given = window.debugger_widget.execute_current()
    checks["debugger_live_game"] = bool(started and snapshot and snapshot.get("mode") and given)
    window.debugger_widget.parentWidget().raise_()
    shot("editor_debugger.png")
    window.stop_play()
    window.document.mark_saved()
    window.close()
    failed = sorted(k for k, ok in checks.items() if not ok)
    return result(
        "editor_tools_gui",
        "PASS" if not failed else "FAIL",
        f"Qt platform '{app.platformName()}': "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items()),
        screenshots=shots,
        note="Screenshots are reviewed by the engineer; hands-on use by a person is not part of this check.",
    )


def check_editor_d17(out):
    """D17 editor surfaces in a real Cocoa editor: export, state machine, composition, trees, input map, profiler."""
    import tempfile

    from PySide6.QtWidgets import QApplication, QGraphicsPixmapItem

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    original = PROJECT_FILE.read_bytes()
    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = PROJECT_FILE
    window.document.mark_saved()
    window.resize(1600, 1000)
    window.show()
    checks, shots = {}, []

    def settle(seconds=0.3):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.02)

    def shot(name):
        settle()
        window.grab().save(str(out / name))
        shots.append(name)

    window.refresh_all()
    # Export Game first, while the document is clean (export saves a dirty project).
    with tempfile.TemporaryDirectory() as tmp:
        exported = window.export_game(Path(tmp) / "dist", name="RM Export", pyz=True, app=True)
        checks["export_game"] = exported["pyz"].is_file() and (exported["app"] / "Contents" / "Info.plist").is_file()
    sheet = "battle.combatant.hero_01"
    window.workspace.set_mode(WorkspaceMode.UI)
    machine = window.state_machine_editor
    window.ui_workspace.setCurrentWidget(machine)
    machine.refresh(select=sheet)
    machine._try(lambda: machine.api.create(sheet), "Created")
    checks["animation_states"] = bool(machine.add_state("attack", "attack")) and set(machine.graph.nodes) >= {
        "idle",
        "attack",
    }
    shot("editor_animation_states.png")
    composition = window.composition_editor
    window.ui_workspace.setCurrentWidget(composition)
    composition.refresh(select=sheet)
    composition.socket_id.setText("hand")
    composition.socket_x.setValue(10)
    composition.socket_y.setValue(-30)
    composition.add_socket_from_form()
    composition.attachment_id.setText("charm")
    composition.item_sheet.setCurrentText("battle.fx.heal")
    composition.attach_socket.setCurrentText("hand")
    composition.attach_scale.setValue(0.4)
    composition.item_frame.setValue(5)
    composition.attach_from_form()
    pixmaps = [i for i in composition.preview.scene().items() if isinstance(i, QGraphicsPixmapItem)]
    checks["character_composition"] = composition.attachments.count() == 1 and len(pixmaps) == 2
    shot("editor_character_composition.png")
    inputs = window.input_map_editor
    window.ui_workspace.setCurrentWidget(inputs)
    inputs.refresh(select="interact")
    inputs.device.setCurrentText("key")
    inputs.code.setText("f")
    checks["input_map"] = bool(inputs.add_binding_from_form()) and any(
        b.code == "f" for b in window.document.project.input_map.bindings("interact")
    )
    shot("editor_input_map.png")
    window.workspace.set_mode(WorkspaceMode.RPG)
    trees = window.behavior_tree_editor
    window.rpg_workspace.setCurrentWidget(trees)
    checks["behavior_trees"] = bool(
        trees.create_tree("rm_sentry", "selector") and trees.add_child("sequence") and trees.select_node((1,))
    )
    shot("editor_behavior_trees.png")
    # Profiler dock reads the running game (Play), then Stop.
    window.document.mark_saved()  # the edits above are in memory only; Play uses the file on disk
    started = window.play_project()
    report = None
    deadline = time.perf_counter() + 20.0
    while (report is None or report.get("frames", 0) < 30) and time.perf_counter() < deadline:
        settle(0.5)
        report = window.profiler_widget.refresh()
    checks["profiler_dock"] = bool(started and report and report.get("frames", 0) >= 30)
    window.profiler_widget.parentWidget().raise_()
    shot("editor_profiler.png")
    window.stop_play()
    window.document.mark_saved()
    window.close()
    checks["project_file_untouched"] = PROJECT_FILE.read_bytes() == original
    if not checks["project_file_untouched"]:
        PROJECT_FILE.write_bytes(original)
    failed = sorted(k for k, ok in checks.items() if not ok)
    return result(
        "editor_d17_gui",
        "PASS" if not failed else "FAIL",
        f"Qt platform '{app.platformName()}': "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items()),
        screenshots=shots,
        note="Nothing saved to the project. Hands-on use by a person is manual item M7.",
    )


def check_runtime_exit_and_recovery(out):
    import signal

    cmd = [sys.executable, "-m", "asteria.runtime.preview", str(PROJECT_FILE), "--frames", "90"]
    t0 = time.perf_counter()
    finished = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    clean = finished.returncode == 0
    clean_time = time.perf_counter() - t0
    # Crash recovery: kill a running game, then load the player save it had written.
    save_dir = PROJECT / "saves"
    save_path = save_dir / "playtest_autosave.asteria-save.json"
    backup = save_path.read_bytes() if save_path.exists() else None
    try:
        driver = (
            "import sys,time,pygame;sys.path.insert(0,{src!r});"
            "from asteria.editor import EditorDocument;from asteria.project import Project;"
            "from asteria.runtime.playable_test_runtime import PlayableTestRuntime;from pathlib import Path;"
            "p=Project.load_json(Path({proj!r}),EditorDocument().component_registry);"
            "rt=PlayableTestRuntime(p,p.game_start.instantiate(p),Path({root!r}));rt.open();rt._ui_mode='field';"
            "rt.game.set_player_position(7.0,3.0);rt.save_playtest();print('SAVED',flush=True);"
            "[ (rt._frame(pygame.event.get(),0.016),pygame.display.flip(),time.sleep(0.016)) for _ in range(100000)]"
        ).format(src=str(REPO / "src"), proj=str(PROJECT_FILE), root=str(PROJECT))
        child = subprocess.Popen([sys.executable, "-c", driver], stdout=subprocess.PIPE, text=True)
        line = ""
        while line != "SAVED":
            raw = child.stdout.readline()
            if not raw:
                break
            line = raw.strip()
        time.sleep(1.0)
        child.send_signal(signal.SIGKILL)
        child.wait(timeout=10)
        killed = child.returncode != 0
        from asteria.editor import EditorDocument
        from asteria.project import Project
        from asteria.runtime.game_save import GameRuntimeSave

        project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
        restored = GameRuntimeSave.load_json(save_path, project)
        recovered = line == "SAVED" and killed and tuple(restored.player_position) == (7.0, 3.0)
    finally:
        if backup is None:
            save_path.unlink(missing_ok=True)
        else:
            save_path.write_bytes(backup)
    return [
        result(
            "runtime_exit",
            "PASS" if clean else "FAIL",
            f"Real-window runtime ran 90 frames and exited with code {finished.returncode} in {clean_time:.1f}s",
            stderr=finished.stderr[-500:],
        ),
        result(
            "runtime_recovery",
            "PASS" if recovered else "FAIL",
            f"Runtime saved ({line}), was killed with SIGKILL (exit {child.returncode}); the save reloaded "
            f"with player position {tuple(restored.player_position)}",
        ),
    ]


# -- D17 features in real windows ----------------------------------------------------------------


def _pump(runtime, seconds, *, before=None, after=None):
    """Run real frames (ticked at 60 fps, flipped to the window) for ``seconds``; returns the frame count."""
    import pygame

    start, frames = time.perf_counter(), 0
    while time.perf_counter() - start < seconds and runtime.running:
        dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
        if before is not None:
            before(frames)
        runtime._frame(pygame.event.get(), dt)
        pygame.display.flip()
        if after is not None:
            after(frames)
        frames += 1
    return frames


def _key(key, up=False):
    import pygame

    pygame.event.post(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=key))


def check_cutscene(out):
    """EVT-03 / EVT-04: a skippable cutscene (move, camera, VFX, fade in parallel) through real key events."""
    import pygame

    from asteria.core import Transform
    from asteria.editor.event_flow_authoring import track
    from asteria.events import EventInstruction, EventProgram

    runtime = _runtime()
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    runtime._ui_mode = "field"
    game.set_player_position(0.0, 0.0)

    def world(command, wait=0.0, **args):
        return ("WORLD", {"command": command, "args": args, **({"wait": wait} if wait else {})})

    tracks = [
        track("hero", ("MOVE", {"entity": "player", "x": 20, "y": 0, "duration": 1.5})),
        track("camera", world("CAMERA_FOCUS", entity="Astral Tyrant", zoom=1.4, blend=0.3)),
        track("effects", world("PLAY_VFX", wait=0.3, asset_id="battle.fx.flame", entity="Astral Tyrant")),
    ]
    program = EventProgram(
        (
            EventInstruction("SEQUENCE", {"tracks": tracks, "cutscene": True, "skippable": True, "wait": "all"}),
            EventInstruction("WORLD", {"command": "CAMERA_RELEASE", "args": {"blend": 0}}),
            EventInstruction("SET_SWITCH", {"name": "rm_cutscene_done", "value": True}),
        )
    )
    game.project.event_programs.register("rm_cutscene", program)
    game.events.start("rm_cutscene")
    _key(pygame.K_RIGHT)  # held through the cutscene: must not move the player
    vfx_seen = []
    _pump(runtime, 0.6, after=lambda _f: vfx_seen.append(len(runtime.field_effects.vfx)))
    mid_x = game.player.get(Transform).x
    zoom = runtime.field_camera.zoom
    letterbox = tuple(runtime.screen.get_at((runtime.width // 2, 3))[:3])
    vfx = max(vfx_seen, default=0)
    pygame.image.save(runtime.screen, str(out / "cutscene_mid.png"))
    _key(pygame.K_RIGHT, up=True)
    _key(pygame.K_ESCAPE)  # skip
    _pump(runtime, 0.4)
    end_x = game.player.get(Transform).x
    done = game.save.event_context.get_switch("rm_cutscene_done")
    active = game.cutscene_active
    pygame.image.save(runtime.screen, str(out / "cutscene_skipped.png"))
    errors = list(game.event_errors)
    runtime.close()
    ok = 4.0 < mid_x < 14.0 and zoom > 1.0 and letterbox == (0, 0, 0) and vfx > 0
    ok = ok and end_x == 20.0 and done and not active and not errors
    return result(
        "cutscene_real_window",
        "PASS" if ok else "FAIL",
        f"Real {driver} window: after 0.6 s the tween had moved the player to x={mid_x:.1f} of 20 with the arrow "
        f"key held (input locked), camera zoom {zoom:.2f}, letterbox pixel {letterbox}, "
        f"{vfx} VFX at peak (parallel track); "
        f"Esc (real key event) skipped to x={end_x:.1f}, switch set={done}, cutscene active={active}, "
        f"errors={len(errors)}",
        screenshots=["cutscene_mid.png", "cutscene_skipped.png"],
        note="Whether the cutscene reads well to a player is part of manual item M5.",
    )


def check_battle_features(out):
    """CAM-02 boss intro and CMP-01/02 layered characters in the canonical battle screen."""
    import pygame

    from asteria.editor import EditorDocument
    from asteria.editor.character_composition_authoring import CharacterCompositionAuthoring

    runtime = _runtime()
    document = EditorDocument()
    document.set_project(runtime.game.project, file_path=PROJECT_FILE)
    api = CharacterCompositionAuthoring(document)
    heroes = [s for s in api.sheets() if s.startswith("battle.combatant.hero")]
    for sheet in heroes:
        api.add_socket(sheet, "hand", 10, -30)
        api.set_socket_key(sheet, "hand", 4, 18, -22, rotation=40)
        api.attach(sheet, "charm", "battle.fx.heal", "hand", scale=0.3, frame=5)
        api.add_layer(sheet, "battle.fx.heal", component_id="aura", z=-1)
    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    runtime.game.start_encounter("boss_room")
    adapter = runtime._battle_presentation
    adapter.begin()
    runtime._advance_to_hero_turn()
    zooms, busy = [], []
    shots = []

    def sample(frame):
        view = getattr(adapter, "_camera_view", None)
        zooms.append(view[2] if view else 1.0)
        busy.append(adapter.busy())
        if frame == 40:
            pygame.image.save(runtime.screen, str(out / "battle_boss_intro.png"))
            shots.append("battle_boss_intro.png")

    _pump(runtime, 3.0, after=sample)
    pygame.image.save(runtime.screen, str(out / "battle_layered_characters.png"))
    shots.append("battle_layered_characters.png")
    from asteria.runtime.camera import Camera2D

    layout = adapter.screen.composer.layout
    frame = adapter.screen.animation.build_frame(Camera2D(width=layout.virtual_width, height=layout.virtual_height))
    parts = sum(1 for d in frame.combatant_draws if d.texture_asset_id == "battle.fx.heal")
    composed = len(adapter.screen.animation.compositions)
    runtime.close()
    peak = max(zooms) if zooms else 1.0
    settled = zooms[-1] if zooms else 1.0
    intro_ok = peak >= 1.3 and abs(settled - 1.0) < 1e-3 and busy[0] and not busy[-1]
    layered_ok = composed > 0 and parts >= 2 * composed and not adapter.composition_errors
    return [
        result(
            "battle_boss_intro_camera",
            "PASS" if intro_ok else "FAIL",
            f"Real {driver} window, boss encounter: camera zoom peaked at {peak:.2f} (authored 1.35) and settled at "
            f"{settled:.2f}; commands blocked during the intro={busy[0] if busy else None}, free afterwards="
            f"{not busy[-1] if busy else None}",
            screenshots=shots[:1],
            note="How the intro feels is part of manual item M5.",
        ),
        result(
            "battle_layered_characters",
            "PASS" if layered_ok else "FAIL",
            f"{composed} heroes carry an authored socket attachment + back layer; {parts} part draws in the frame "
            f"(expected >= {2 * composed}); drawn in a real {driver} window",
            screenshots=shots[1:],
        ),
    ]


def check_game_menus(out):
    """ENG-21 save slots, ENG-15 rebinding and UI-01 status screen, driven by real key events."""
    import pygame

    from asteria.core import Transform

    saves = PROJECT / "saves"
    touched = [saves / "slot1.asteria-save.json", saves / "settings.json"]
    backups = {path: path.read_bytes() if path.exists() else None for path in touched}
    runtime = _runtime()
    try:
        runtime.open()
        driver = pygame.display.get_driver()
        runtime._ui_mode = "field"
        _pump(runtime, 0.2)
        # status screen from the field (I)
        _key(pygame.K_i)
        _pump(runtime, 0.3)
        status_open = runtime._ui_mode == "status"
        pygame.image.save(runtime.screen, str(out / "menu_status.png"))
        _key(pygame.K_ESCAPE)
        _pump(runtime, 0.2)
        # save into slot 1 (overwrite asks twice), move, then load it back
        runtime.game.set_player_position(11.0, 4.0)
        runtime.open_slots("save", back="field")
        for _ in range(2):
            _key(pygame.K_RETURN)
            _pump(runtime, 0.2)
        saved = (saves / "slot1.asteria-save.json").exists()
        pygame.image.save(runtime.screen, str(out / "menu_save_slots.png"))
        _key(pygame.K_ESCAPE)
        _pump(runtime, 0.1)
        runtime.game.set_player_position(-20.0, 0.0)
        runtime.open_slots("load", back="field")
        _key(pygame.K_DOWN)  # autosave -> slot 1
        _key(pygame.K_RETURN)
        _pump(runtime, 0.3)
        loaded = tuple(runtime.game.player.get(Transform).x for _ in (0,))[0]
        # rebind "move_right" to D through the Controls screen, then walk with it
        from asteria.runtime.input_rebinding import ControlsMenu

        runtime.controls_menu = ControlsMenu(runtime.project.input_map, runtime.settings.input_overrides)
        runtime._ui_mode = "controls"
        rows = [action for action, _ in runtime.controls_menu.rows()]
        target = rows.index("move_right")
        for _ in range(target):
            _key(pygame.K_DOWN)
        _key(pygame.K_RETURN)
        _pump(runtime, 0.2)
        _key(pygame.K_d)
        _pump(runtime, 0.2)
        pygame.image.save(runtime.screen, str(out / "menu_controls.png"))
        rebound = (
            [b.code for b in runtime.input.input_map.bindings("move_right")]
            if hasattr(runtime.input, "input_map")
            else []
        )
        runtime._ui_mode = "field"
        runtime.game.set_player_position(0.0, 0.0)
        _key(pygame.K_d)
        _pump(runtime, 0.6)
        _key(pygame.K_d, up=True)
        _pump(runtime, 0.1)
        walked = runtime.game.player.get(Transform).x
        runtime.close()
    finally:
        for path, data in backups.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
    return [
        result(
            "status_menu_real_window",
            "PASS" if status_open else "FAIL",
            f"I key (real event) opened the status screen={status_open} in a {driver} window",
            screenshots=["menu_status.png"],
        ),
        result(
            "save_slots_real_window",
            "PASS" if saved and abs(loaded - 11.0) < 1e-6 else "FAIL",
            f"Save to slot 1 through the slot screen (overwrite confirmed with a second Enter) wrote the file="
            f"{saved}; loading slot 1 restored player x={loaded:.1f} (saved 11.0)",
            screenshots=["menu_save_slots.png"],
        ),
        result(
            "controls_rebinding_real_window",
            "PASS" if walked > 5.0 else "FAIL",
            f"move_right rebound to D on the Controls screen (bindings now {rebound or 'n/a'}); holding D moved the "
            f"player to x={walked:.1f} in 0.6 s",
            screenshots=["menu_controls.png"],
            note="Physical key presses by a person remain manual item M1; gamepad rebinding needs a controller (M2).",
        ),
    ]


def check_follow_camera(out):
    """CAM-02: the field follow camera (manifest field.camera.follow) tracks the walking player."""
    import pygame

    runtime = _runtime()
    runtime.manifest["field"].setdefault("camera", {})["follow"] = {"zoom": 1.8, "smoothing": 8.0}
    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    runtime.game.set_player_position(-60.0, 0.0)
    _pump(runtime, 0.6)
    start = runtime.field_camera.view
    pygame.image.save(runtime.screen, str(out / "follow_camera_start.png"))
    _key(pygame.K_RIGHT)
    _pump(runtime, 1.5)
    _key(pygame.K_RIGHT, up=True)
    _pump(runtime, 0.6)
    end = runtime.field_camera.view
    pygame.image.save(runtime.screen, str(out / "follow_camera_end.png"))
    from asteria.core import Transform

    player_x = runtime.game.player.get(Transform).x
    runtime.close()
    moved = end[0] - start[0]
    ok = abs(end[2] - 1.8) < 1e-6 and player_x > -60.0 + 20 and moved > 10.0
    return result(
        "field_follow_camera",
        "PASS" if ok else "FAIL",
        f"Real {driver} window: follow zoom {end[2]:.2f}; the player walked from x=-60 to x={player_x:.1f} and the "
        f"camera centre moved {moved:.1f} world units with it",
        screenshots=["follow_camera_start.png", "follow_camera_end.png"],
    )


def check_packaged_app(out):
    """AST-06: the exported macOS .app starts the game in a real window, outside the repository."""
    import tempfile

    from asteria.project_tools import package_game

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        built = package_game(PROJECT_FILE, tmp / "dist", name="Asteria RM", app=True)
        env = dict(os.environ, HOME=str(tmp / "home"), ASTERIA_PYTHON=sys.executable)
        for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER"):
            env.pop(key, None)
        exe = built["app"] / "Contents" / "MacOS" / "Asteria_RM"
        t0 = time.perf_counter()
        proc = subprocess.run(
            [str(exe), "--frames", "120"], cwd=tmp, env=env, capture_output=True, text=True, timeout=180
        )
        elapsed = time.perf_counter() - t0
        size = built["pyz"].stat().st_size
    ok = proc.returncode == 0
    return result(
        "packaged_app_real_window",
        "PASS" if ok else "FAIL",
        f"Asteria RM.app ({size / 1e6:.1f} MB .pyz inside) launched from a temporary folder outside the repo, ran "
        f"120 frames in a real window and exited {proc.returncode} in {elapsed:.1f}s",
        stderr=proc.stderr[-800:],
        note="Double-clicking the .app in Finder (Gatekeeper, unsigned app) is manual item M6.",
    )


MV_PLAY_SCRIPT = """
import json, sys, time
from pathlib import Path
import pygame
from asteria.core import Transform
from asteria.platform.pygame_backend import PygameRuntimeBackend
from asteria.project_tools import load_project
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.tilemap_field import TileMapField, run_tilemap_field

root, out = Path(sys.argv[1]), Path(sys.argv[2])
project = load_project(root / "project.asteria.json")
field = TileMapField(GameSessionRuntime(project, project.game_start.instantiate(project)), root)
backend = PygameRuntimeBackend(project.input_map)
backend.open("Imported MV project", 816, 624)
start_scene = field.session.scene.id
log = {"driver": pygame.display.get_driver(), "start": list(field.session.save.player_position)}
state = {"phase": "walk", "shots": []}

def shot(name):
    pygame.image.save(backend.screen, str(out / name))
    state["shots"].append(name)

def key(k, up=False):
    pygame.event.post(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=k))

def on_frame(frame):
    s, session = state, field.session
    if frame == 2:
        shot("mv_import_start.png")
        key(pygame.K_UP)
    if s["phase"] == "walk" and frame == 200:  # walked up until the NPC blocks the way
        key(pygame.K_UP, up=True); key(pygame.K_e); s["phase"] = "talk"; s["talk_frame"] = frame
    elif s["phase"] == "talk" and frame == s["talk_frame"] + 3:
        key(pygame.K_e, up=True)
    elif s["phase"] == "talk" and frame == s["talk_frame"] + 8:
        log["dialogue"] = field.dialogue
        shot("mv_import_dialogue.png")
        key(pygame.K_e)
    elif s["phase"] == "talk" and frame == s["talk_frame"] + 12:
        key(pygame.K_e, up=True); key(pygame.K_UP); s["phase"] = "door"
    elif s["phase"] == "door" and session.scene.id != start_scene:
        key(pygame.K_UP, up=True); s["phase"] = "arrived"; s["arrived"] = frame
    elif s["phase"] == "arrived" and frame == s["arrived"] + 20:
        shot("mv_import_after_transfer.png")

frames = run_tilemap_field(field, backend, 816, 624, max_frames=900, on_frame=on_frame)
t = field.session.player.get(Transform)
log.update(frames=frames, transferred=field.session.scene.id != start_scene, scene=field.session.scene.name,
           cell=[int(t.x // 48), int(t.y // 48)], errors=[str(e) for e in field.session.event_errors],
           shots=state["shots"], mv_modules=sorted(m for m in sys.modules if "rpg_maker" in m))
backend.close()
print("MV_PLAY:" + json.dumps(log, ensure_ascii=False))
"""


def check_mv_import(out):
    """W-18: an imported RPG Maker MV project (local reference) plays in a real window as a native project."""
    import tempfile

    from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root

    root = resolve_rpg_maker_mv_root(REPO)
    layouts = (
        []
        if root is None
        else [
            l for l in discover_mv_projects(root) if l.relative_path.endswith("parallax_Resource_Pack/sample_project")
        ]
    )
    if not layouts:
        return result(
            "mv_import_real_window", "BLOCKED", "The local RPG Maker MV reference (parallax sample) is absent."
        )
    from asteria.assets.rpg_maker_mv_project import import_mv_project

    with tempfile.TemporaryDirectory() as tmp:
        project_path, imported = import_mv_project(layouts[0].root, Path(tmp) / "imported", map_ids=(1, 2))
        proc = subprocess.run(
            [sys.executable, "-c", MV_PLAY_SCRIPT, str(project_path.parent), str(Path(out).resolve())],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=tmp,
        )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("MV_PLAY:")), None)
    if line is None:
        return result(
            "mv_import_real_window", "FAIL", f"play process exited {proc.returncode}", stderr=proc.stderr[-1500:]
        )
    log = json.loads(line[len("MV_PLAY:") :])
    ok = (
        log["transferred"]
        and log["cell"] == [8, 23]
        and log.get("dialogue")
        and not log["errors"]
        and log["mv_modules"] == []
    )
    return result(
        "mv_import_real_window",
        "PASS" if ok else "FAIL",
        f"Parallax sample (maps 1-2) imported, saved, reloaded in a fresh process and played in a real "
        f"{log['driver']} window by real key events: NPC said {log.get('dialogue')!r}; the door transferred "
        f"to '{log['scene']}' cell {log['cell']} (expected [8, 23]); event errors {len(log['errors'])}; "
        f"MV modules loaded while playing {log['mv_modules']}",
        screenshots=log["shots"],
        note="Visual review of the tiles and characters is part of manual item M9.",
    )


CHECKS = {
    "gpu_window": check_gpu_window,
    "input": check_input,
    "audio": check_audio,
    "battle": check_battle_frame_pacing,
    "field_camera": check_field_camera,
    "editor": check_editor_playtest,
    "editor_tools": check_editor_tools,
    "editor_d17": check_editor_d17,
    "runtime": check_runtime_exit_and_recovery,
    "cutscene": check_cutscene,
    "battle_features": check_battle_features,
    "menus": check_game_menus,
    "follow_camera": check_follow_camera,
    "packaged_app": check_packaged_app,
    "mv_import": check_mv_import,
}


def _run_child(name, out):
    proc = subprocess.run(
        [sys.executable, __file__, str(out), "--child", name], capture_output=True, text=True, timeout=600, cwd=REPO
    )
    marker = "RESULT_JSON:"
    for line in proc.stdout.splitlines():
        if line.startswith(marker):
            return json.loads(line[len(marker) :])
    return [result(name, "FAIL", f"check crashed (exit {proc.returncode})", stderr=proc.stderr[-1500:])]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--child")
    args = parser.parse_args(argv)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(REPO / "src"))
    if args.child:
        value = CHECKS[args.child](out)
        print("RESULT_JSON:" + json.dumps(value if isinstance(value, list) else [value]))
        return 0
    results = []
    for name in args.only or CHECKS:
        results.extend(_run_child(name, out))
    meta = {
        "machine": platform.platform(),
        "python": platform.python_version(),
        "time": time.strftime("%Y-%m-%d %H:%M:%S %z"),
    }
    results_path = out / "results.json"
    if args.only and results_path.exists():  # keep evidence of checks that were not re-run
        rerun = {r["check"] for r in results}
        previous = json.loads(results_path.read_text()).get("results", [])
        results = [r for r in previous if r["check"] not in rerun] + results
    results_path.write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    for item in results:
        print(f"{item['status']:<13} {item['check']}: {item['evidence']}")
    return 0 if all(r["status"] != "FAIL" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
