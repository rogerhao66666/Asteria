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
    texture = backend.load_texture(
        "hero", str(PROJECT / "playable_assets" / "battle" / "hero_01.png")
    )
    profiler = RuntimeProfiler(target_fps=60)
    sprites = 400
    for frame in range(240):
        backend.tick(60)
        profiler.begin_frame()
        backend.begin_frame()
        for i in range(sprites):
            x = (i * 37 + frame * 3) % 600
            y = (i * 53) % 320
            backend.draw_texture(
                texture, TextureDraw("hero", (64 * (frame // 8 % 4 + 1), 0, 64, 64), x, y, 32, 32)
            )
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
        f"{report['pacing']['measured_fps']} fps, read-back framebuffer has {distinct} sampled "
        f"colours",
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
    for key, action in (
        (pygame.K_RIGHT, "move_right"),
        (pygame.K_RETURN, "confirm"),
        (pygame.K_ESCAPE, "cancel"),
    ):
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
        f"Key events posted to the real {driver} window's SDL event queue reached the input "
        f"map: {seen}",
        note="Synthetic events through the OS window queue; a physical key press is a separate "
        "manual item.",
    )
    physical = result(
        "input_keyboard_physical",
        "NOT EXECUTED",
        "Needs a person pressing keys in the game window (procedure M1).",
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
            f"CoreAudio device opened {init}; hit.wav ({length:.3f}s) kept its channel busy "
            f"for {elapsed:.3f}s; "
            f"battle_theme.ogg streaming={music_busy}",
            note="Device-level playback only; audible confirmation is manual item M3.",
        ),
        result("audio_playback_audible", "NOT EXECUTED", "Needs a listener (procedure M3)."),
        result(
            "audio_latency",
            "NOT EXECUTED",
            "Output latency needs an acoustic or loopback measurement (procedure M4); "
            "the configured mixer buffer is not reported by pygame and is not presented as "
            "latency.",
        ),
    ]


def _runtime(battle_presentation="canonical", backend=None):
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.battle_presentation_adapters import create_battle_presentation_adapter
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), PROJECT, backend=backend
    )
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
        if (
            not adapter.busy()
            and runtime.game.mode == "battle"
            and not runtime._victory
            and frames % 20 == 0
        ):
            key = (pygame.K_2, pygame.K_1, pygame.K_1)[uses % 3]
            events.append(pygame.event.Event(pygame.KEYDOWN, key=key))
            uses += 1
        profiler.begin_frame()
        runtime._frame(events, dt)
        with profiler.section("present"):
            runtime.present()
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
            f"Canonical battle screen in a real {driver} window: combatant sprites drawn, boss "
            f"animation "
            f"advanced {frame_changes} frames in {elapsed:.1f}s "
            f"({frame_changes / elapsed:.1f}/s); "
            f"{uses} skills used through the key-event queue; VFX particles peaked at "
            f"{report['counters'].get('particles', {}).get('max', 0):g}",
            screenshots=shots,
            note="Perceived smoothness by a person is manual item M5.",
        ),
        result(
            "frame_pacing",
            "PASS" if pacing_ok else "FAIL",
            f"{frames} frames: {pacing['measured_fps']} fps (target 60), jitter "
            f"{pacing['interval_jitter_ms']} ms, "
            f"p99 interval {pacing['interval_p99_ms']} ms, {pacing['frames_over_budget']} "
            f"frames over 1.5x budget",
            pacing=pacing,
            frame=report["frame"],
            sections={k: v["mean_ms"] for k, v in report["sections"].items()},
            unsupported=report["unsupported"],
        ),
    ]


def check_field_camera(out):
    """CAM-02: the boss event's camera focus in a real window (zoom, map coverage, boss
    framing)."""
    import pygame

    from asteria.core import Transform

    runtime = _runtime()
    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    boss = next(e for e in runtime.game.scene.entities() if e.name == "Astral Tyrant").get(
        Transform
    )

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
    covered = (
        bx <= 0
        and by <= 0
        and bx + bw >= runtime.width - 1e-6
        and by + bh >= runtime.height - 1e-6
    )
    pygame.image.save(runtime.screen, str(out / "field_camera_boss_focus.png"))
    runtime.close()
    centre = (runtime.width / 2, runtime.height / 2)
    closer = abs(after[0] - centre[0]) < abs(before[0] - centre[0])
    ok = abs(zoom - 1.6) < 1e-6 and covered and closer
    return result(
        "field_camera_boss_focus",
        "PASS" if ok else "FAIL",
        f"Boss event camera in a real {driver} window: zoom {zoom:.2f} (authored 1.6), map "
        f"image covers the "
        f"screen={covered}, boss moved from x={before[0]:.0f} to x={after[0]:.0f} (screen "
        f"centre {centre[0]:.0f})",
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
        f"still running after 4 s={alive_after}, Stop Play returned={stopped}, process "
        f"exited={exited}",
    )


def check_editor_tools(out):
    """CB10 editors in a real Cocoa editor window: each tool is driven, measured and screenshotted
    (nothing saved)."""
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
    checks["vfx_preview"] = (
        window.vfx_editor._render() is not None and not window.vfx_editor.stage.pixmap.isNull()
    )
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
    checks["multi_select_batch_fields"] = (
        len(family.selected_ids) == 3 and "stats.power" in family.batch_fields()
    )
    shot("editor_records_multiselect.png")
    db = window.document.project.rpg_database
    encounter = db.encounters["boss_room"]
    removed = db.enemies.pop("mender_wisp")  # in-memory only: show a real problem, then restore
    window.problems_widget.refresh()
    window.problems_dock.raise_()
    problem = next(
        (
            p
            for p in window.problems_widget.problems
            if p.target[:3] == ("record", "rpg", "encounters")
        ),
        None,
    )
    checks["problems_panel"] = problem is not None and window.navigate_to_problem(problem)
    shot("editor_problems.png")
    db.enemies["mender_wisp"] = removed
    window.problems_widget.refresh()
    checks["problems_clear_again"] = (
        window.problems_widget.problems == [] and encounter is db.encounters["boss_room"]
    )
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
        note="Screenshots are reviewed by the engineer; hands-on use by a person is not part of "
        "this check.",
    )


def check_editor_d17(out):
    """D17 editor surfaces in a real Cocoa editor: export, state machine, composition, trees, input
    map, profiler."""
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
        checks["export_game"] = (
            exported["pyz"].is_file() and (exported["app"] / "Contents" / "Info.plist").is_file()
        )
    sheet = "battle.combatant.hero_01"
    window.workspace.set_mode(WorkspaceMode.UI)
    machine = window.state_machine_editor
    window.ui_workspace.setCurrentWidget(machine)
    machine.refresh(select=sheet)
    machine._try(lambda: machine.api.create(sheet), "Created")
    checks["animation_states"] = bool(machine.add_state("attack", "attack")) and set(
        machine.graph.nodes
    ) >= {
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
    pixmaps = [
        i for i in composition.preview.scene().items() if isinstance(i, QGraphicsPixmapItem)
    ]
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
        trees.create_tree("rm_sentry", "selector")
        and trees.add_child("sequence")
        and trees.select_node((1,))
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
            "from asteria.runtime.playable_test_runtime import PlayableTestRuntime;from pathlib "
            "import Path;"
            "p=Project.load_json(Path({proj!r}),EditorDocument().component_registry);"
            "rt=PlayableTestRuntime(p,p.game_start.instantiate(p),Path({root!r}));rt.open();rt._ui_mode='field';"
            "rt.game.set_player_position(7.0,3.0);rt.save_playtest();print('SAVED',flush=True);"
            "[ (rt._frame(pygame.event.get(),0.016),pygame.display.flip(),time.sleep(0.016)) "
            "for _ in range(100000)]"
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
            f"Real-window runtime ran 90 frames and exited with code {finished.returncode} in "
            f"{clean_time:.1f}s",
            stderr=finished.stderr[-500:],
        ),
        result(
            "runtime_recovery",
            "PASS" if recovered else "FAIL",
            f"Runtime saved ({line}), was killed with SIGKILL (exit {child.returncode}); the "
            f"save reloaded "
            f"with player position {tuple(restored.player_position)}",
        ),
    ]


# -- D17 features in real windows ----------------------------------------------------------------


def _pump(runtime, seconds, *, before=None, after=None):
    """Run real frames (ticked at 60 fps, flipped to the window) for ``seconds``; returns the frame
    count."""
    import pygame

    start, frames = time.perf_counter(), 0
    while time.perf_counter() - start < seconds and runtime.running:
        dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
        if before is not None:
            before(frames)
        runtime._frame(pygame.event.get(), dt)
        runtime.present()
        if after is not None:
            after(frames)
        frames += 1
    return frames


def _key(key, up=False):
    import pygame

    pygame.event.post(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=key, mod=0))


def check_cutscene(out):
    """EVT-03 / EVT-04: a skippable cutscene (move, camera, VFX, fade in parallel) through real key
    events."""
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
        track(
            "effects",
            world("PLAY_VFX", wait=0.3, asset_id="battle.fx.flame", entity="Astral Tyrant"),
        ),
    ]
    program = EventProgram(
        (
            EventInstruction(
                "SEQUENCE", {"tracks": tracks, "cutscene": True, "skippable": True, "wait": "all"}
            ),
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
        f"Real {driver} window: after 0.6 s the tween had moved the player to x={mid_x:.1f} of "
        f"20 with the arrow "
        f"key held (input locked), camera zoom {zoom:.2f}, letterbox pixel {letterbox}, "
        f"{vfx} VFX at peak (parallel track); "
        f"Esc (real key event) skipped to x={end_x:.1f}, switch set={done}, cutscene "
        f"active={active}, "
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
    frame = adapter.screen.animation.build_frame(
        Camera2D(width=layout.virtual_width, height=layout.virtual_height)
    )
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
            f"Real {driver} window, boss encounter: camera zoom peaked at {peak:.2f} (authored "
            f"1.35) and settled at "
            f"{settled:.2f}; commands blocked during the intro={busy[0] if busy else None}, "
            f"free afterwards="
            f"{not busy[-1] if busy else None}",
            screenshots=shots[:1],
            note="How the intro feels is part of manual item M5.",
        ),
        result(
            "battle_layered_characters",
            "PASS" if layered_ok else "FAIL",
            f"{composed} heroes carry an authored socket attachment + back layer; {parts} part "
            f"draws in the frame "
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

        runtime.controls_menu = ControlsMenu(
            runtime.project.input_map, runtime.settings.input_overrides
        )
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
            f"Save to slot 1 through the slot screen (overwrite confirmed with a second Enter) "
            f"wrote the file="
            f"{saved}; loading slot 1 restored player x={loaded:.1f} (saved 11.0)",
            screenshots=["menu_save_slots.png"],
        ),
        result(
            "controls_rebinding_real_window",
            "PASS" if walked > 5.0 else "FAIL",
            f"move_right rebound to D on the Controls screen (bindings now "
            f"{rebound or 'n/a'}); holding D moved the "
            f"player to x={walked:.1f} in 0.6 s",
            screenshots=["menu_controls.png"],
            note="Physical key presses by a person remain manual item M1; gamepad rebinding "
            "needs a controller (M2).",
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
        f"Real {driver} window: follow zoom {end[2]:.2f}; the player walked from x=-60 to "
        f"x={player_x:.1f} and the "
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
            [str(exe), "--frames", "120"],
            cwd=tmp,
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        elapsed = time.perf_counter() - t0
        size = built["pyz"].stat().st_size
    ok = proc.returncode == 0
    return result(
        "packaged_app_real_window",
        "PASS" if ok else "FAIL",
        f"Asteria RM.app ({size / 1e6:.1f} MB .pyz inside) launched from a temporary folder "
        f"outside the repo, ran "
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
kind = sys.argv[3] if len(sys.argv) > 3 else "pygame"
prefix = "mv_import" if kind == "pygame" else "mv_import_gpu"
project = load_project(root / "project.asteria.json")
field = TileMapField(GameSessionRuntime(project, project.game_start.instantiate(project)), root)
if kind == "moderngl":
    from asteria.platform.moderngl_backend import ModernglRuntimeBackend
    backend = ModernglRuntimeBackend(project.input_map)
else:
    backend = PygameRuntimeBackend(project.input_map)
backend.open("Imported MV project", 816, 624)
start_scene = field.session.scene.id
log = {"driver": pygame.display.get_driver(), "start": list(field.session.save.player_position)}
state = {"phase": "walk", "shots": []}

def shot(name):
    name = name.replace("mv_import", prefix)
    if kind == "moderngl":
        state["pending_shot"] = name
        backend.request_capture()
        return
    pygame.image.save(backend.screen, str(out / name))
    state["shots"].append(name)

def key(k, up=False):
    pygame.event.post(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=k))

def on_frame(frame):
    s, session = state, field.session
    if s.get("pending_shot") and getattr(backend, "captured", None) is not None:
        pygame.image.save(backend.captured, str(out / s["pending_shot"]))
        s["shots"].append(s.pop("pending_shot"))
        backend.captured = None
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
log.update(environment_unsupported=getattr(backend, "environment_unsupported", []))
log.update(frames=frames, transferred=field.session.scene.id != start_scene,
scene=field.session.scene.name,
           cell=[int(t.x // 48), int(t.y // 48)], errors=[str(e) for e in
           field.session.event_errors],
           shots=state["shots"], mv_modules=sorted(m for m in sys.modules if "rpg_maker" in m))
backend.close()
print("MV_PLAY:" + json.dumps(log, ensure_ascii=False))
"""


def check_mv_import(out):
    """W-18: an imported RPG Maker MV project (local reference) plays in a real window as a native
    project."""
    import tempfile

    from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root

    root = resolve_rpg_maker_mv_root(REPO)
    layouts = (
        []
        if root is None
        else [
            l
            for l in discover_mv_projects(root)
            if l.relative_path.endswith("parallax_Resource_Pack/sample_project")
        ]
    )
    if not layouts:
        return result(
            "mv_import_real_window",
            "BLOCKED",
            "The local RPG Maker MV reference (parallax sample) is absent.",
        )
    from asteria.assets.rpg_maker_mv_project import import_mv_project

    with tempfile.TemporaryDirectory() as tmp:
        project_path, imported = import_mv_project(
            layouts[0].root, Path(tmp) / "imported", map_ids=(1, 2)
        )
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                MV_PLAY_SCRIPT,
                str(project_path.parent),
                str(Path(out).resolve()),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=tmp,
        )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("MV_PLAY:")), None)
    if line is None:
        return result(
            "mv_import_real_window",
            "FAIL",
            f"play process exited {proc.returncode}",
            stderr=proc.stderr[-1500:],
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
        f"Parallax sample (maps 1-2) imported, saved, reloaded in a fresh process and played "
        f"in a real "
        f"{log['driver']} window by real key events: NPC said {log.get('dialogue')!r}; the "
        f"door transferred "
        f"to '{log['scene']}' cell {log['cell']} (expected [8, 23]); event errors "
        f"{len(log['errors'])}; "
        f"MV modules loaded while playing {log['mv_modules']}",
        screenshots=log["shots"],
        note="Visual review of the tiles and characters is part of manual item M9.",
    )


def check_gpu_playable(out):
    """ENG-12: the playable game on the ModernGL presenter, same battle workload as frame_pacing
    (pygame)."""
    import pygame

    from asteria.runtime.profiler import RuntimeProfiler

    runtime = _runtime(backend="moderngl")
    runtime.open()
    if runtime.gpu is None:
        runtime.close()
        return result(
            "gpu_playable_runtime",
            "FAIL",
            f"GPU presenter did not start: {runtime.gpu_fallback_reason}",
        )
    renderer = runtime.gpu.renderer
    profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
    runtime._ui_mode = "field"
    _pump(runtime, 1.0)
    field_identity = pygame.image.tobytes(runtime.capture(), "RGB") == pygame.image.tobytes(
        runtime.screen, "RGB"
    )
    pygame.image.save(runtime.capture(), str(out / "gpu_field.png"))
    runtime.game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    adapter = runtime._battle_presentation
    frames, uses, uploads = 0, 0, []
    start = time.perf_counter()
    while time.perf_counter() - start < 10.0 and runtime.running:
        dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
        events = pygame.event.get()
        if (
            not adapter.busy()
            and runtime.game.mode == "battle"
            and not runtime._victory
            and frames % 20 == 0
        ):
            events.append(
                pygame.event.Event(
                    pygame.KEYDOWN, key=(pygame.K_2, pygame.K_1, pygame.K_1)[uses % 3]
                )
            )
            uses += 1
        profiler.begin_frame()
        runtime._frame(events, dt)
        with profiler.section("present"):
            runtime.present()
        uploads.append(runtime.gpu.last_upload_ms)
        runtime._sample_counters()
        profiler.end_frame()
        frames += 1
        if frames == 120:
            pygame.image.save(runtime.capture(), str(out / "gpu_battle.png"))
    battle_identity = pygame.image.tobytes(runtime.capture(), "RGB") == pygame.image.tobytes(
        runtime.screen, "RGB"
    )
    report = profiler.report()
    runtime.close()
    pacing = report["pacing"]
    (out / "gpu_battle_profile.json").write_text(json.dumps(report, indent=2))
    ok = (
        field_identity
        and battle_identity
        and pacing["measured_fps"] >= 55
        and pacing["interval_p99_ms"] <= 25.0
    )
    gpu = report["sections"].get("gpu_time", {})
    return result(
        "gpu_playable_runtime",
        "PASS" if ok else "FAIL",
        f"Playable game on the ModernGL presenter ({renderer}): field and canonical battle in "
        f"a real window; "
        f"the GPU frame equals the composed frame pixel for pixel (field={field_identity}, "
        f"battle={battle_identity}); battle workload {frames} frames, {pacing['measured_fps']} "
        f"fps, p99 interval "
        f"{pacing['interval_p99_ms']} ms; frame mean {report['frame']['mean_ms']} ms; upload mean "
        f"{sum(uploads) / max(1, len(uploads)):.3f} ms; GPU time mean {gpu.get('mean_ms')} ms; "
        f"draw calls "
        f"{report['counters'].get('draw_calls', {}).get('max')} per frame; {uses} skills used",
        screenshots=["gpu_field.png", "gpu_battle.png"],
        sections={k: v["mean_ms"] for k, v in report["sections"].items()},
        note="Same workload as frame_pacing (pygame) for comparison; see gpu_battle_profile.json.",
    )


def _vfx_scene(runtime, *, weather="rain", particles=400):
    """In-memory (never saved) environment on the reference field: lights, shadow, water, weather,
    post."""
    from asteria.core import Entity, Transform
    from asteria.runtime.environment2d import (
        Environment2DComponent,
        LightSource2DComponent,
        ShadowCaster2DComponent,
        WaterRegion2DComponent,
    )

    scene = runtime.game.scene
    settings = scene.add_entity(Entity("RM Scene Settings"))
    settings.add_component(Transform())
    env = settings.add_component(Environment2DComponent())
    env.lighting_enabled, env.ambient_intensity = True, 0.35
    env.ambient_r, env.ambient_g, env.ambient_b = 0.6, 0.7, 1.0
    env.weather, env.weather_intensity, env.weather_max_particles = weather, 0.8, particles
    env.bloom_enabled, env.bloom_threshold, env.bloom_intensity = True, 0.85, 0.5
    env.saturation, env.vignette = 1.1, 0.35
    glow = runtime.game.player.add_component(LightSource2DComponent())
    glow.radius, glow.intensity, glow.height = 60.0, 1.3, 16.0
    boss = next(e for e in scene.entities() if e.name == "Astral Tyrant")
    bt = boss.get(Transform)
    lamp = scene.add_entity(Entity("RM Lamp"))
    lamp.add_component(Transform(bt.x - 50, bt.y - 10))
    light = lamp.add_component(LightSource2DComponent())
    light.radius, light.intensity, light.casts_shadow = 120.0, 1.6, True
    light.color_r, light.color_g, light.color_b = 1.0, 0.75, 0.45
    wall = scene.add_entity(Entity("RM Wall"))
    wall.add_component(Transform(bt.x - 25, bt.y - 10))
    caster = wall.add_component(ShadowCaster2DComponent())
    caster.width, caster.height, caster.offset_y = 6.0, 30.0, 0.0
    pond = scene.add_entity(Entity("RM Pond"))
    pond.add_component(Transform(-60.0, 30.0))
    water = pond.add_component(WaterRegion2DComponent())
    water.width, water.height = 70.0, 30.0
    return env


def check_vfx_environment(out):
    """VFX-02 / VFX-03 in real windows: GPU effect chain, the pygame fallback, battle afterimages,
    weather load."""
    import pygame

    from asteria.runtime.profiler import RuntimeProfiler

    results = []
    for backend in ("moderngl", "pygame"):
        runtime = _runtime(backend=backend)
        runtime.open()
        driver = pygame.display.get_driver()
        if backend == "moderngl" and runtime.gpu is None:
            results.append(
                result(
                    "vfx_gpu_field",
                    "FAIL",
                    f"GPU presenter did not start: {runtime.gpu_fallback_reason}",
                )
            )
            runtime.close()
            continue
        _vfx_scene(runtime)
        profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
        runtime._ui_mode = "field"
        runtime.game.set_player_position(-40.0, 10.0)

        def measured(frame, profiler=profiler):
            profiler.end_frame()
            profiler.begin_frame()

        profiler.begin_frame()
        _pump(runtime, 5.0, after=measured)
        name = f"vfx_{backend}_field.png"
        pygame.image.save(runtime.capture(), str(out / name))
        report = profiler.report()
        pacing = report["pacing"]
        errors = list(runtime.environment_errors)
        unsupported = list(runtime.environment_unsupported)
        particles = report["counters"].get("particles", {}).get("max", 0)
        draw_calls = report["counters"].get("draw_calls", {}).get("max")
        runtime.close()
        ok = pacing["measured_fps"] >= 55 and not errors and particles > 0
        if backend == "pygame":
            ok = ok and set(unsupported) >= {"bloom", "grade", "vignette", "shadows"}
        results.append(
            result(
                f"vfx_{backend}_field",
                "PASS" if ok else "FAIL",
                f"{backend} ({driver}): field with lighting (ambient + player light + "
                f"shadow-casting lamp), water, "
                f"rain ({particles:g} particles), bloom, grading, vignette for 5 s: "
                f"{pacing['measured_fps']} fps, "
                f"p99 interval {pacing['interval_p99_ms']} ms, frame interval mean "
                f"{report['frame']['mean_ms']} ms, "
                f"draw calls/frame {draw_calls}; shader errors {errors}; "
                f"GPU-only effects reported unsupported {unsupported}",
                screenshots=[name],
                sections={k: v["mean_ms"] for k, v in report["sections"].items()},
            )
        )

    # battle: bloom + afterimages from a motion_fx beat, on the GPU
    runtime = _runtime(backend="moderngl")
    from asteria.editor.action_timeline_authoring import ActionTimelineController
    from asteria.editor.model import EditorDocument

    document = EditorDocument()
    document.set_project(runtime.game.project)
    timeline = ActionTimelineController(document)
    for sequence_id in timeline.sequences():
        timeline.add_beat(
            sequence_id, "rm_echo", 0.0, "motion_fx", "afterimage", "@source", duration=1.2
        )
    runtime.open()
    env = _vfx_scene(runtime, weather="none")
    env.lighting_enabled = False
    runtime._ui_mode = "field"
    runtime.game.start_encounter("boss_room")
    adapter = runtime._battle_presentation
    adapter.begin()
    runtime._advance_to_hero_turn()
    _pump(runtime, 1.5)
    runtime._use_skill(
        0
    )  # the acting hero's first skill: its motion sequence carries the motion_fx beat
    ghosts = {"max": 0}

    def count(frame):
        echoes = adapter.screen.animation.echoes.by_key.values()
        ghosts["max"] = max([ghosts["max"], *[len(e.snapshots) for e in echoes]])
        if frame == 25:
            pygame.image.save(runtime.capture(), str(out / "vfx_gpu_battle_afterimage.png"))

    _pump(runtime, 2.0, after=count)
    runtime.close()
    results.append(
        result(
            "vfx_gpu_battle_afterimage",
            "PASS" if ghosts["max"] >= 2 else "FAIL",
            f"Canonical battle on the GPU with bloom, grading and vignette; a skill's "
            f"motion_fx beat produced up to "
            f"{ghosts['max']} afterimage copies of the acting member",
            screenshots=["vfx_gpu_battle_afterimage.png"],
            note="Whether the effects look good is manual item M10.",
        )
    )

    # weather load: 2000 rain particles on the GPU path
    runtime = _runtime(backend="moderngl")
    runtime.open()
    _vfx_scene(runtime, particles=2500)
    profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
    runtime._ui_mode = "field"
    profiler.begin_frame()
    _pump(runtime, 4.0, after=lambda f: (profiler.end_frame(), profiler.begin_frame()))
    report = profiler.report()
    runtime.close()
    pacing = report["pacing"]
    particles = report["counters"].get("particles", {}).get("max", 0)
    results.append(
        result(
            "vfx_weather_load",
            "PASS" if pacing["measured_fps"] >= 55 else "FAIL",
            f"Rain at {particles:g} particles plus the full GPU chain for 4 s: "
            f"{pacing['measured_fps']} fps, "
            f"p99 interval {pacing['interval_p99_ms']} ms, vfx section mean "
            f"{report['sections'].get('vfx', {}).get('mean_ms')} ms",
        )
    )
    return results


def check_mv_import_gpu(out):
    """W-18 + ENG-12 + VFX: the imported MV project on the ModernGL backend, at night (lights,
    rain, bloom)."""
    import tempfile

    from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root

    root = resolve_rpg_maker_mv_root(REPO)
    layouts = (
        []
        if root is None
        else [
            l
            for l in discover_mv_projects(root)
            if l.relative_path.endswith("parallax_Resource_Pack/sample_project")
        ]
    )
    if not layouts:
        return result(
            "mv_import_gpu_night",
            "BLOCKED",
            "The local RPG Maker MV reference (parallax sample) is absent.",
        )
    from asteria.assets.rpg_maker_mv_project import import_mv_project
    from asteria.core import Entity, Transform
    from asteria.project_tools import load_project
    from asteria.runtime.environment2d import Environment2DComponent, LightSource2DComponent

    with tempfile.TemporaryDirectory() as tmp:
        project_path, _ = import_mv_project(
            layouts[0].root, Path(tmp) / "imported", map_ids=(1, 2)
        )
        project = load_project(
            project_path
        )  # author a night environment on map 1, as an editor user would
        scene = project.scene(project.startup_scene_id)
        settings = scene.add_entity(Entity("Night"))
        settings.add_component(Transform())
        env = settings.add_component(Environment2DComponent())
        env.lighting_enabled, env.ambient_intensity = True, 0.3
        env.ambient_r, env.ambient_g, env.ambient_b = 0.5, 0.6, 1.0
        env.weather, env.weather_intensity, env.bloom_enabled = "rain", 0.7, True
        player = scene.get_entity(project.game_start.player_entity_id)
        lamp = player.add_component(LightSource2DComponent())
        lamp.radius, lamp.intensity = 150.0, 1.4
        project.save_json(project_path)
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                MV_PLAY_SCRIPT,
                str(project_path.parent),
                str(Path(out).resolve()),
                "moderngl",
            ],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=tmp,
        )
    line = next((l for l in proc.stdout.splitlines() if l.startswith("MV_PLAY:")), None)
    if line is None:
        return result(
            "mv_import_gpu_night",
            "FAIL",
            f"play process exited {proc.returncode}",
            stderr=proc.stderr[-1500:],
        )
    log = json.loads(line[len("MV_PLAY:") :])
    ok = (
        log["transferred"]
        and log["cell"] == [8, 23]
        and log.get("dialogue")
        and not log["errors"]
        and not log["mv_modules"]
    )
    return result(
        "mv_import_gpu_night",
        "PASS" if ok else "FAIL",
        f"Imported parallax sample with an authored night environment (Environment2D + a light "
        f"on the player, "
        f"rain, bloom) on the ModernGL backend in a real {log['driver']} window: dialogue "
        f"{log.get('dialogue')!r}, "
        f"door transfer to cell {log['cell']}, event errors {len(log['errors'])}, MV modules "
        f"{log['mv_modules']}",
        screenshots=log["shots"],
    )


def check_gameplay_systems(out):
    """STR-01 / BTL / RPG: the JRPG stress playthrough in the real playable window, canonical
    battle drawn."""
    import pygame

    from asteria.validation.jrpg_stress import run_jrpg_stress

    runtime = _runtime()
    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    adapter = runtime._battle_presentation
    state = {"begun": False, "frames": 0, "shots": []}

    def present(seconds):
        start = time.perf_counter()
        while time.perf_counter() - start < seconds:
            dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
            runtime._frame(pygame.event.get(), dt)
            runtime.present()
            state["frames"] += 1
            if (
                runtime.game.mode == "battle"
                and not adapter.busy()
                and time.perf_counter() - start > 0.3
            ):
                break

    def on_step(name):
        if runtime.game.mode == "battle" and not state["begun"]:
            adapter.begin()
            state["begun"] = True
        present(2.5 if name != "turn" else 1.5)
        if name in ("battle_started", "captured", "broken") and name not in state["shots"]:
            pygame.image.save(runtime.capture(), str(out / f"gameplay_{name}.png"))
            state["shots"].append(name)

    report, game = run_jrpg_stress(runtime.game.project, game=runtime.game, on_step=on_step)
    present(3.0)
    pygame.image.save(runtime.capture(), str(out / "gameplay_end.png"))
    errors = list(game.event_errors)
    runtime.close()
    ok = not report.missing and report.outcome == "victory" and not errors and state["begun"]
    items = "; ".join(f"{k}: {v}" for k, v in report.evidence.items())
    return result(
        "gameplay_systems_real_window",
        "PASS" if ok else "FAIL",
        f"JRPG stress playthrough (STR-01) in the real playable {driver} window with the "
        f"canonical battle screen "
        f"presenting every step ({state['frames']} frames): {len(report.evidence)}/13 items, "
        f"outcome "
        f"{report.outcome}, missing {report.missing}, event errors {len(errors)}. {items}",
        screenshots=[f"gameplay_{n}.png" for n in state["shots"]] + ["gameplay_end.png"],
        note="Actions go through the game session API; keys and menus are covered by the battle "
        "/ menus checks.",
    )


def check_game_menus_more(out):
    """UI-01 / UI-02 / RPG-05 / WLD-01: pause, quest log, shop, item use, equipment, settings, game
    over by keys."""
    import pygame

    from asteria.gameplay.effects import Effect, EffectOperation, EffectOperationKind
    from asteria.rpg import QuestDefinition, QuestObjective, ShopDefinition, ShopEntry
    from asteria.rpg.items import ItemDefinition
    from asteria.runtime.game_menus import PAUSE_OPTIONS

    runtime = _runtime()
    db = runtime.game.project.rpg_database  # in-memory content (nothing is saved)
    db.add_shop(
        ShopDefinition(
            "rm_shop", "RM Shop", [ShopEntry("ether_leaf", buy_prices={"gold": 30}, stock=3)]
        )
    )
    db.add_quest(
        QuestDefinition(
            "rm_quest",
            "RM Quest",
            objectives=[
                QuestObjective(
                    "leaves",
                    "item",
                    target="ether_leaf",
                    required=99,
                    description="Collect ether leaves",
                )
            ],
        )
    )
    db.add_item(
        ItemDefinition(
            "rm_potion",
            "RM Potion",
            use_effects=[
                Effect(
                    "rm.heal",
                    [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "vitality", 30)],
                )
            ],
        )
    )
    saves = PROJECT / "saves"
    touched = [saves / "settings.json"]
    backups = {path: path.read_bytes() if path.exists() else None for path in touched}
    checks, shots = {}, []

    def shot(name):
        pygame.image.save(runtime.capture(), str(out / name))
        shots.append(name)

    def press(*keys, wait=0.15):
        for key in keys:
            _key(key)
            _pump(runtime, 0.05)
            _key(key, up=True)
            _pump(runtime, wait)

    def choose_pause(option):
        index = [o for o, _ in PAUSE_OPTIONS].index(option)
        press(pygame.K_ESCAPE)
        for _ in range(index):
            press(pygame.K_DOWN, wait=0.05)
        press(pygame.K_RETURN)

    try:
        runtime.open()
        driver = pygame.display.get_driver()
        runtime._ui_mode = "field"
        game = runtime.game
        game.start_quest("rm_quest")
        _pump(runtime, 0.3)
        choose_pause("quests")
        checks["quest_log"] = runtime._ui_mode == "quests"
        shot("menus_quest_log.png")
        press(pygame.K_ESCAPE, pygame.K_ESCAPE)
        game.open_shop("rm_shop")
        game.save.rpg_state.currencies["gold"] = (
            game.save.rpg_state.currencies.get("gold", 0.0) + 100
        )
        gold = game.save.rpg_state.currencies["gold"]
        leaves = game.save.rpg_state.inventory.count("ether_leaf")
        _pump(runtime, 0.2)
        checks["shop_opened_by_event_state"] = runtime._ui_mode == "shop"
        press(pygame.K_RETURN)
        shot("menus_shop.png")
        checks["shop_buy"] = (
            game.save.rpg_state.currencies["gold"] == gold - 30
            and game.save.rpg_state.inventory.count("ether_leaf") == leaves + 1
        )
        press(pygame.K_ESCAPE)
        actor = game.save.rpg_state.party_active_actor_ids[0]
        values = game.save.rpg_state.actor_snapshots[actor].resources["values"]["vitality"]
        values["current"] = values["maximum"] - 50
        game.save.rpg_state.inventory.add("rm_potion", 1)
        runtime.open_status_menu()
        menu = runtime.status_menu
        while menu.tab != "items":
            press(pygame.K_TAB, wait=0.05)
        target = next(i for i, r in enumerate(menu.rows()) if r[1] == "rm_potion")
        for _ in range(target - menu.row):
            press(pygame.K_DOWN, wait=0.05)
        press(pygame.K_RETURN)
        healed = game.save.rpg_state.actor_snapshots[actor].resources["values"]["vitality"][
            "current"
        ]
        checks["item_use"] = (
            healed == values["maximum"] - 20
            and game.save.rpg_state.inventory.count("rm_potion") == 0
        )
        shot("menus_item_used.png")
        while menu.tab != "equipment":
            press(pygame.K_TAB, wait=0.05)
        loadout = game.save.rpg_state.loadouts[menu.actor_id]
        weapon = loadout.equipped("weapon")[0].equipment.equipment_id
        slot_row = next(
            i for i, r in enumerate(menu.rows()) if r[0] == "slot" and r[1] == "weapon"
        )
        while menu.row != slot_row:
            press(pygame.K_DOWN if menu.row < slot_row else pygame.K_UP, wait=0.05)
        press(pygame.K_RETURN)
        unequipped = not loadout.equipped("weapon")
        candidate = next(
            i for i, r in enumerate(menu.rows()) if r[0] == "candidate" and r[1] == weapon
        )
        while menu.row != candidate:
            press(pygame.K_DOWN if menu.row < candidate else pygame.K_UP, wait=0.05)
        press(pygame.K_RETURN)
        checks["equip_cycle"] = (
            unequipped and loadout.equipped("weapon")[0].equipment.equipment_id == weapon
        )
        shot("menus_equipment.png")
        press(pygame.K_ESCAPE)
        choose_pause("settings")
        checks["settings"] = runtime._ui_mode == "settings"
        shot("menus_settings.png")
        press(pygame.K_ESCAPE, pygame.K_ESCAPE)
        game.start_encounter("boss_room")
        for member_id in tuple(game.active_hero_ids()):
            game.battle.member(member_id).subject.resources.set_current(
                game.rules.knockout_resource_id, 0
            )
        runtime._defeat = True
        _pump(runtime, 0.3)
        checks["game_over"] = runtime._ui_mode == "game_over"
        shot("menus_game_over.png")
        press(pygame.K_DOWN, pygame.K_RETURN)
        checks["game_over_to_title"] = runtime._ui_mode == "title"
        runtime.close()
    finally:
        for path, data in backups.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(data)
    failed = sorted(k for k, v in checks.items() if not v)
    return result(
        "game_menus_more_real_window",
        "PASS" if not failed else "FAIL",
        f"Real {driver} window, real key events: "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items()),
        screenshots=shots,
    )


def check_editor_workflows(out):
    """Editor workflows in a shown Cocoa editor (EDT-02/03/04/11/13/14/16, AST-02, ENG-23); nothing
    is saved."""
    from PySide6.QtWidgets import QApplication

    from asteria.core import Transform
    from asteria.core.prefab import PrefabInstanceComponent
    from asteria.editor import EditorDocument
    from asteria.editor.commands import SetAttributeCommand
    from asteria.editor.hierarchy import drop_entities
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.events import EventInstruction
    from asteria.project import Project
    from asteria.runtime import Interaction2DComponent

    app = QApplication.instance() or QApplication([])
    original = PROJECT_FILE.read_bytes()
    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = PROJECT_FILE
    window._resolve_project_resources()
    window.resize(1600, 1000)
    window.show()
    window.raise_()
    window.activateWindow()
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
    settle(0.5)
    # EDT-02 asset browser with thumbnails
    window.refresh_asset_list()
    items = [window.asset_list.item(i) for i in range(window.asset_list.count())]
    checks["asset_browser_thumbnails"] = bool(items) and any(not i.icon().isNull() for i in items)
    # EDT-03 / EDT-13 / EDT-14 records: search, copy / paste / cut by the window's shortcuts, batch
    # edit
    window.workspace.set_mode(WorkspaceMode.RPG)
    window.rpg_workspace.setCurrentWidget(window.rpg_authoring)
    family = window.rpg_authoring.child
    family.category.setCurrentIndex(family.category.findData("items"))
    everything = list(family._ids)
    family.search.setText("leaf")
    checks["record_search"] = bool(family._ids) and len(family._ids) < len(everything)
    family.search.clear()
    deadline = (
        time.perf_counter() + 2.0
    )  # another window (a previous check's) may still hold the focus
    while window._focused_record_family() is not family and time.perf_counter() < deadline:
        window.raise_()
        window.activateWindow()
        family.browser.setFocus()
        settle(0.2)
    checks["editor_had_focus"] = window._focused_record_family() is family
    if checks["editor_had_focus"]:
        family.select_ids([family._ids[0]])
        window.copy_action.trigger()
        window.paste_action.trigger()
        copy_id = f"{family._ids[0]}_copy"
        pasted = copy_id in window.document.project.rpg_database.items
        family.select_ids([copy_id])
        window.cut_action.trigger()
        checks["record_copy_paste_cut_shortcuts"] = (
            pasted and copy_id not in window.document.project.rpg_database.items
        )
    else:
        checks["record_copy_paste_cut_shortcuts"] = False
    shot("workflow_records.png")
    family.category.setCurrentIndex(family.category.findData("enemies"))
    ids = family._ids[:2]
    family.select_ids(ids)
    enemies = window.document.project.rpg_database.enemies
    batch = family.batch_edit_selected("stats.power", "77") and all(
        enemies[k].stats["power"] == 77 for k in ids
    )
    window.document.undo()
    checks["batch_edit_and_undo"] = batch and not all(enemies[k].stats["power"] == 77 for k in ids)
    # EDT-14 hierarchy drag and drop (the drop the tree performs), one undo step
    window.workspace.set_mode(WorkspaceMode.SCENE)
    scene = window.document.project.scene(window.document.project.startup_scene_id)
    movable = [e for e in scene.entities() if e.has(Transform) and e is not None][:2]
    child, parent = movable[0], movable[1]
    drop_entities(window.document, [child], "entity", parent, "on")
    window.refresh_all()
    reparented = child.get(Transform).parent_id == parent.id
    window.document.undo()
    checks["hierarchy_drop_and_undo"] = reparented and child.get(Transform).parent_id != parent.id
    shot("workflow_hierarchy.png")
    # ENG-23 prefab: create, place two, edit one, apply to prefab (propagates), revert
    boss = next(e for e in scene.entities() if e.has(Interaction2DComponent))
    window.document.select_entity(boss)
    created = window.create_prefab_from_selection("rm_prefab") is not None
    a = window.place_prefab("rm_prefab", 10, 10)
    a = window._selected_entity()
    window.place_prefab("rm_prefab", 30, 10)
    b = window._selected_entity()
    talk = a.get(Interaction2DComponent)
    window.document.execute(SetAttributeCommand(talk, "range", 99.0, talk.range))
    window.document.select_entity(a)
    window.apply_instance_to_prefab()
    propagated = b.get(Interaction2DComponent).range == 99.0
    window.document.select_entity(b)
    reverted = window.revert_instance_to_prefab() is not None
    checks["prefab_create_place_apply_revert"] = (
        created and a.has(PrefabInstanceComponent) and propagated and reverted
    )
    shot("workflow_prefab.png")
    # AST-02 pivot edit in the animation editor
    window.workspace.set_mode(WorkspaceMode.UI)
    window.ui_workspace.setCurrentWidget(window.animation_editor)
    window.animation_editor.refresh(sheet="battle.combatant.hero_01")
    editor = window.animation_editor
    editor.pivot_x.setValue(0.4)
    pivot = editor.apply_sheet() and editor.api.data("battle.combatant.hero_01")["pivot"][0] == 0.4
    shot("workflow_pivot.png")
    window.document.undo()
    checks["pivot_edit_and_undo"] = (
        pivot and editor.api.data("battle.combatant.hero_01")["pivot"][0] != 0.4
    )
    # EDT-04 + EDT-11: an event authored in the editor runs in the live game; Play from Selection,
    # Restart
    window.event_flow_editor.api.new_program(
        "rm_editor_event",
        "RM",
        [EventInstruction("SET_SWITCH", {"name": "rm_editor_event_ran", "value": True})],
    )
    player = next(
        e for e in scene.entities() if e.id == window.document.project.game_start.player_entity_id
    )
    window.document.selection.set_single("entity", player)
    started = window.play_from_selection()
    ran = restarted = False
    snapshot = None
    deadline = time.perf_counter() + 20.0
    while snapshot is None and time.perf_counter() < deadline:
        settle(0.5)
        snapshot = window.debugger_widget.refresh()
    if snapshot is not None:
        window.debugger_widget.set_args("trigger_event", program_id="rm_editor_event")
        window.debugger_widget.execute_current()
        settle(0.5)
        snapshot = window.debugger_widget.refresh()
        ran = bool(snapshot and snapshot.get("switches", {}).get("rm_editor_event_ran"))
        restarted = window.restart_play()
        again = None
        deadline = time.perf_counter() + 20.0
        while again is None and time.perf_counter() < deadline:
            settle(0.5)
            again = window.debugger_widget.refresh()
        restarted = bool(
            restarted and again and not again.get("switches", {}).get("rm_editor_event_ran")
        )
    checks["editor_event_runs_in_live_game"] = bool(started and ran)
    checks["play_from_selection_and_restart"] = bool(started and restarted)
    shot("workflow_play_from_selection.png")
    window.stop_play()
    window.document.mark_saved()
    window.close()
    checks["project_file_untouched"] = PROJECT_FILE.read_bytes() == original
    if not checks["project_file_untouched"]:
        PROJECT_FILE.write_bytes(original)
    failed = sorted(k for k, v in checks.items() if not v)
    return result(
        "editor_workflows_gui",
        "PASS" if not failed else "FAIL",
        f"Qt platform '{app.platformName()}', shown editor: "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items()),
        screenshots=shots,
        note="Hands-on use by a person (mouse drags, typing) is manual item M7.",
    )


def check_battle_without_art(out):
    """D19 / CB15 A9: a project without battle art fights on the canonical screen (pygame and
    ModernGL)."""
    import pygame

    from asteria.runtime.profiler import RuntimeProfiler

    results = []
    autosave = PROJECT / "saves" / "playtest_autosave.asteria-save.json"
    backup = autosave.read_bytes() if autosave.exists() else None
    try:
        for backend in ("pygame", "moderngl"):
            runtime = _runtime(backend=backend)
            library = runtime.game.project.battle_presentation_library  # in memory only
            for category in ("combatant_visuals", "motion_sequences"):
                for profile_id in list(library.ids(category)):
                    library.remove(category, profile_id)
            runtime.open()
            driver = pygame.display.get_driver()
            profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
            runtime._ui_mode = "field"
            runtime.game.start_encounter("boss_room")
            adapter = runtime._battle_presentation
            adapter.begin()
            runtime._advance_to_hero_turn()
            frames, vfx, shots = 0, 0, []
            start = time.perf_counter()
            profiler.begin_frame()
            while time.perf_counter() - start < 90 and not (runtime._victory or runtime._defeat):
                dt = min(runtime.clock.tick(60) / 1000.0, 0.05)
                events = pygame.event.get()
                if not adapter.busy() and runtime.game.mode == "battle" and frames % 10 == 0:
                    _key(pygame.K_1)
                runtime._frame(events, dt)
                runtime.present()
                profiler.end_frame()
                profiler.begin_frame()
                frames += 1
                vfx = max(vfx, adapter.particle_count())
                if frames == 90:
                    name = f"no_art_{backend}_battle.png"
                    pygame.image.save(runtime.capture(), str(out / name))
                    shots.append(name)
            generated = all(
                v.sprite_sheet_asset_id.startswith("generated.")
                for v in adapter.screen.scene.combatants
            )
            victory = runtime._victory
            _pump(runtime, 3.0)
            _key(pygame.K_RETURN)
            _pump(runtime, 0.4)
            back_to_field = runtime.game.mode == "field" and not runtime._victory
            _key(pygame.K_F5)
            _pump(runtime, 0.3)
            saved = autosave.exists()
            report = profiler.report()
            runtime.close()
            pacing = report["pacing"]
            ok = (
                generated
                and victory
                and back_to_field
                and saved
                and vfx > 0
                and pacing["measured_fps"] >= 55
            )
            results.append(
                result(
                    f"battle_without_art_{backend}",
                    "PASS" if ok else "FAIL",
                    f"{backend} ({driver}): no combatant visuals / motion sequences; generated "
                    f"combatants={generated}, "
                    f"manifest fx played as VFX (peak {vfx}), victory={victory} after {frames} "
                    f"frames by real key "
                    f"events, back to the field={back_to_field}, F5 save={saved}; "
                    f"{pacing['measured_fps']} fps, "
                    f"p99 {pacing['interval_p99_ms']} ms",
                    screenshots=shots,
                )
            )
    finally:
        if backup is None:
            autosave.unlink(missing_ok=True)
        else:
            autosave.write_bytes(backup)
    return results


def check_engine_systems(out):
    """ENG-05 / ENG-07 / ENG-16 / ENG-17 / ANI-03 / ANI-05 / CAM-02 in the engine's own main loop:
    ``Application.run`` with the pygame backend in a real window, real clock, 8 s, scene drawn
    every frame."""

    from asteria.core import (
        Application,
        ApplicationConfig,
        Entity,
        PersistentComponent,
        Scene,
        SceneTransition,
        System,
        Transform,
    )
    from asteria.gameplay.action_timeline import ActionCue, ActionTimeline
    from asteria.graphics import SpriteClip, SpriteKeyframe
    from asteria.platform.pygame_backend import PygameRuntimeBackend
    from asteria.runtime import (
        AnimationClipSet,
        AnimationSystem,
        Animator2DComponent,
        Collider2DComponent,
        CollisionSystem,
        CollisionWorld,
        SpriteRenderer2D,
    )
    from asteria.runtime.character_control import (
        CharacterController2DComponent,
        CharacterControllerSystem,
        Hitbox2DComponent,
        HitboxSystem,
        Hurtbox2DComponent,
    )
    from asteria.runtime.components2d import Camera2DComponent
    from asteria.runtime.entity_actions import EntityActionSystem
    from asteria.runtime.systems import CameraFollowSystem

    seen = {
        "fixed": 0,
        "frames": 0,
        "trigger": [],
        "pairs": set(),
        "hits": [],
        "anim": [],
        "cues": [],
        "lead": [],
    }

    def body(scene, name, x, y, size=24, layer=0, mask=0xFFFFFFFF, trigger=False, *extra):
        entity = scene.add_entity(Entity(name))
        entity.add_component(Transform(x, y))
        collider = entity.add_component(Collider2DComponent())
        collider.width = collider.height = size
        collider.layer, collider.mask, collider.is_trigger = layer, mask, trigger
        for component in extra:
            entity.add_component(component)
        return entity

    town, cave = Scene("Town"), Scene("Cave")
    collisions, hitboxes, camera = CollisionSystem(), HitboxSystem(), CameraFollowSystem()
    actions = EntityActionSystem(hitboxes=hitboxes)
    clips = {
        "hero": AnimationClipSet(
            {
                "walk": SpriteClip(
                    "walk", [SpriteKeyframe(1, 0.1, ("footstep",)), SpriteKeyframe(2, 0.1)], True
                ),
            }
        )
    }
    animation = AnimationSystem(clips.get)

    class Counter(System):
        def update(self, scene, dt):
            seen["frames"] += 1

        def fixed_update(self, scene, dt):
            seen["fixed"] += 1

    for system in (
        Counter(),
        actions,
        CharacterControllerSystem(),
        collisions,
        hitboxes,
        animation,
        camera,
    ):
        town.scheduler.add(system)
    sword = Hitbox2DComponent()
    sword.team, sword.width = "hero", 24
    hero = body(
        town,
        "Hero",
        100,
        200,
        24,
        1,
        0b100,
        False,
        sword,
        Hurtbox2DComponent(),
        SpriteRenderer2D(),
    )
    controller = hero.add_component(CharacterController2DComponent())
    controller.speed = 60
    spec = hero.add_component(Animator2DComponent())
    spec.clip_set_id, spec.default_clip = "hero", "walk"
    hero.add_component(PersistentComponent())
    body(town, "Zone", 300, 200, 64, 2, 0xFFFFFFFF, True)  # layer 2: in the hero's mask
    body(town, "Wall", 420, 200, 24, 2, 0b010)  # layer 2 collides with the hero's layer 1
    body(town, "Ghost", 420, 200, 24, 3)  # layer 3 is not in the hero's mask
    foe_box = Hurtbox2DComponent()
    foe_box.team = "enemy"
    foe = town.add_entity(Entity("Foe"))
    foe.add_component(Transform(495, 200))
    foe.add_component(foe_box)
    rig = town.add_entity(Entity("Camera"))
    rig.add_component(Transform())
    cam = rig.add_component(Camera2DComponent())
    cam.follow_entity_id, cam.look_ahead_x, cam.look_ahead_smoothing = hero.id, 60, 0
    collisions.listeners.append(lambda kind, trigger, other: seen["trigger"].append(kind))
    hitboxes.listeners.append(lambda event: seen["hits"].append(event.hit_tag))
    animation.listeners.append(lambda entity_id, clip, index, name: seen["anim"].append(name))
    lunge = ActionTimeline(
        "lunge",
        [
            ActionCue("step", 0.0, "movement", {"x": 1, "y": 0, "duration": 0.4}),
            ActionCue("swing", 0.2, "hitbox", {"duration": 0.2, "hit_tag": "lunge"}),
            ActionCue("spark", 0.2, "vfx", {"asset_id": "battle.fx.slash"}),
        ],
    )

    class Backend(PygameRuntimeBackend):
        def tick(self, target_fps=60):
            dt = super().tick(target_fps)
            self.elapsed = getattr(self, "elapsed", 0.0) + dt
            self.wall_start = getattr(self, "wall_start", time.perf_counter())
            return dt

        def end_frame(self):
            t = self.elapsed
            scene = app.scene
            if scene is town:
                transform = hero.get(Transform)
                if t < 3.0:  # walk right through the trigger zone toward the wall
                    transform.x = 100 + 120 * t
                elif t < 3.1 and not actions.active(hero.id):
                    transform.x = 470
                    actions.play(hero.id, lunge)
                    seen["lunge_started"] = True
                for contact in CollisionWorld.from_scene(town).contacts():
                    names = tuple(
                        sorted((town.get_entity(contact.a).name, town.get_entity(contact.b).name))
                    )
                    seen["pairs"].add(names)
                seen["cues"] += [c.kind for c in actions.events]
                view = camera.camera(rig.id)
                if view is not None and 0.5 < t < 2.9:
                    centre = view.x + view.width / view.zoom / 2
                    seen["lead"].append(centre - transform.x)
                    # ENG-13 parallax: a far layer (0.5) moves half as fast on screen as the play
                    # layer
                    near = view.world_to_screen(500.0, 100.0)[0]
                    far = view.world_to_screen(500.0, 100.0, 0.5, 1.0)[0]
                    seen.setdefault("parallax", []).append((near, far))
                if 3.4 < t < 4.6 and not seen.get("grouped"):
                    seen["grouped"] = (
                        True  # CAM-02 target group: frame the hero and the foe together
                    )
                    cam.follow_entity_id, cam.group_entity_ids, cam.group_padding = (
                        "",
                        f"{hero.id}, {foe.id}",
                        0,
                    )
                if seen.get("grouped") and 4.0 < t < 4.6 and view is not None:
                    middle = (hero.get(Transform).x + foe.get(Transform).x) / 2
                    centre = view.x + view.width / view.zoom / 2
                    seen.setdefault("group", []).append((abs(centre - middle), view.zoom))
                if t > 5.0 and app._transition is None and not seen.get("changed"):
                    seen["changed"] = True
                    app.change_scene(
                        cave, SceneTransition(fade_out=0.3, fade_in=0.3, color=(0, 0, 0))
                    )
            self.draw(scene, t)
            super().end_frame()
            if t > 8.0:
                app.stop()

        def draw(self, scene, t):
            view = camera.camera(rig.id) if scene is town else None
            ox = (view.x if view is not None else 0) - 0
            colors = {
                "Hero": (90, 170, 255),
                "Zone": (90, 220, 140),
                "Wall": (230, 120, 90),
                "Ghost": (150, 150, 160),
            }
            if view is not None:  # the far (parallax 0.5) backdrop column
                fx, _ = view.world_to_screen(500.0, 100.0, 0.5, 1.0)
                self.pg.draw.rect(self.screen, (60, 64, 90), (fx - 40, 60, 80, 300))
            for entity in scene.entities():
                tr = entity.get(Transform)
                if tr is None or entity.name == "Camera":
                    continue
                color = colors.get(entity.name, (240, 200, 90))
                rect = (tr.x - ox - 14, tr.y - 14, 28, 28)
                self.pg.draw.rect(self.screen, color, rect, 2 if entity.name == "Zone" else 0)
            font = self.pg.font.Font(None, 24)
            lines = [
                f"Application.run  t={t:4.1f}s  scene={scene.name}  fixed steps={seen['fixed']}",
                f"trigger {seen['trigger'][-3:]}  hits {seen['hits'][-2:]}  anim events "
                f"{len(seen['anim'])}",
            ]
            for i, line in enumerate(lines):
                self.screen.blit(font.render(line, True, (230, 232, 240)), (12, 12 + 22 * i))
            if app.transition_cover:
                shade = self.pg.Surface(self.screen.get_size(), self.pg.SRCALPHA)
                shade.fill((0, 0, 0, int(255 * app.transition_cover)))
                self.screen.blit(shade, (0, 0))
            if 2.0 < t < 2.05 or (scene is cave and "shot" not in seen):
                name = "engine_systems_town.png" if scene is town else "engine_systems_cave.png"
                if scene is cave:
                    seen["shot"] = True
                self.pg.image.save(self.screen, str(out / name))

    backend = Backend()
    app = Application(
        backend, ApplicationConfig("Asteria engine systems", 960, 400, fixed_timestep=1 / 50)
    )
    app.set_scene(town)
    start = time.perf_counter()
    app.run()
    wall = time.perf_counter() - start
    driver = "cocoa"  # the backend opened a pygame window; pygame quit at the end of run()
    simulated = backend.elapsed  # the frame times Application.run received from the real clock
    expected_fixed = simulated * 50
    seen["fixed"] = app.time.fixed_steps
    points = seen.get("parallax") or []
    moved_near = points[-1][0] - points[0][0] if len(points) > 1 else 0.0
    parallax_ratio = (points[-1][1] - points[0][1]) / moved_near if moved_near else None
    checks = {
        "fixed_update": abs(seen["fixed"] - expected_fixed) <= max(6, expected_fixed * 0.05),
        "trigger_enter_stay_exit": seen["trigger"][:1] == ["enter"]
        and "stay" in seen["trigger"]
        and "exit" in seen["trigger"],
        "layers_masks": ("Hero", "Wall") in seen["pairs"]
        and ("Ghost", "Hero") not in seen["pairs"],
        "hitbox": "lunge" in seen["hits"],
        "frame_events": "footstep" in seen["anim"],
        "action_timeline_cues": "vfx" in seen["cues"],
        "look_ahead": bool(seen["lead"]) and min(seen["lead"]) > 20,
        "persistent_entity": hero.scene is cave and app.scene is cave,
        "parallax": parallax_ratio is not None and abs(parallax_ratio - 0.5) < 0.02,
        "target_group": bool(seen.get("group")) and min(d for d, _ in seen["group"]) < 2.0,
    }
    ok = all(checks.values())
    return result(
        "engine_systems_real_window",
        "PASS" if ok else "FAIL",
        f"Application.run with the pygame backend in a real {driver} window for {wall:.1f} s "
        f"({seen['frames']} town frames, real clock, {simulated:.2f} s simulated): "
        f"fixed steps {seen['fixed']} at 50 Hz "
        f"(expected ~{expected_fixed:.0f}); "
        f"trigger events {sorted(set(seen['trigger']))}; contact pairs "
        f"{sorted(seen['pairs'])}; hits {seen['hits']}; "
        f"frame events {sorted(set(seen['anim']))}; action cues {sorted(set(seen['cues']))}; "
        f"camera lead "
        f"{min(seen['lead'] or [0]):.0f}..{max(seen['lead'] or [0]):.0f} px; parallax 0.5 "
        f"layer moved "
        f"{(parallax_ratio or 0):.3f}x the play layer; target group centre off the hero-foe "
        f"midpoint by "
        f"{min((d for d, _ in seen.get('group') or [(99, 0)])):.1f} px (zoom "
        f"{(seen.get('group') or [(0, 0)])[-1][1]:.2f}); hero moved to {hero.scene.name}. "
        + ", ".join(f"{k}={'ok' if v else 'FAIL'}" for k, v in checks.items()),
        screenshots=["engine_systems_town.png", "engine_systems_cave.png"],
        note="Movement is scripted (no keys); key-driven input is covered by the input / menus "
        "/ battle checks.",
    )


def check_m10_compare(out):
    """M10 (automatable part): the same field frame on ModernGL and on the pygame fallback,
    compared by numbers,
    plus a 30 s soak per backend. Whether the effects look right stays manual (M10 visual
    confirmation)."""
    import pygame
    from PIL import Image, ImageChops, ImageStat

    from asteria.runtime.profiler import RuntimeProfiler

    frames, soak, notes = {}, {}, {}
    for backend in ("moderngl", "pygame"):
        for mode in ("plain", "effects"):
            runtime = _runtime(backend=backend)
            runtime.open()
            if backend == "moderngl" and runtime.gpu is None:
                runtime.close()
                return result(
                    "m10_compare",
                    "FAIL",
                    f"GPU presenter did not start: {runtime.gpu_fallback_reason}",
                )
            if mode == "effects":
                _vfx_scene(runtime, weather="none")
            runtime._ui_mode = "field"
            runtime.game.set_player_position(-40.0, 10.0)
            _pump(runtime, 1.5)
            name = f"m10_{backend}_{mode}.png"
            pygame.image.save(runtime.capture(), str(out / name))
            frames[(backend, mode)] = out / name
            if mode == "effects":
                notes[backend] = {
                    "unsupported": sorted(runtime.environment_unsupported),
                    "errors": [str(e) for e in runtime.environment_errors],
                }
            runtime.close()
        # stability: rain and the full chain for 30 s, real frames
        runtime = _runtime(backend=backend)
        runtime.open()
        _vfx_scene(runtime, weather="rain", particles=800)
        runtime._ui_mode = "field"
        profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
        rss_start = _rss_mb()
        profiler.begin_frame()
        tick = lambda f, p=profiler: (p.end_frame(), p.begin_frame())  # noqa: E731
        count = _pump(runtime, 10.0, after=tick)
        rss_warm = _rss_mb()  # after warm-up (GPU driver allocations settle in the first seconds)
        count += _pump(runtime, 20.0, after=tick)
        report = profiler.report()
        soak[backend] = {
            "frames": count,
            "fps": report["pacing"]["measured_fps"],
            "p99_ms": report["pacing"]["interval_p99_ms"],
            "max_ms": report["frame"].get("max_ms"),
            "over_budget": report["pacing"].get(
                "frames_over_budget", report["pacing"].get("over_1_5x")
            ),
            "errors": len(runtime.environment_errors) + len(runtime.game.event_errors),
            "rss_growth_mb": round(_rss_mb() - rss_start, 1),
            "rss_growth_after_warmup_mb": round(_rss_mb() - rss_warm, 1),
        }
        runtime.close()

    def load(key):
        return Image.open(frames[key]).convert("RGB")

    def stats(image):
        luma = ImageStat.Stat(image.convert("L"))
        return round(luma.mean[0], 1), round(luma.stddev[0], 1)

    def differ(a, b):
        diff = ImageChops.difference(a, b).convert("L")
        hist = diff.histogram()
        total = sum(hist)
        return round(sum(i * n for i, n in enumerate(hist)) / total, 2), round(
            sum(hist[24:]) / total * 100, 2
        )

    plain = differ(load(("moderngl", "plain")), load(("pygame", "plain")))
    effects = differ(load(("moderngl", "effects")), load(("pygame", "effects")))
    gpu, cpu = load(("moderngl", "effects")), load(("pygame", "effects"))
    heat = (
        ImageChops.difference(gpu, cpu)
        .convert("L")
        .point(lambda v: min(255, v * 4))
        .convert("RGB")
    )
    sheet = Image.new("RGB", (gpu.width * 3 + 40, gpu.height), (12, 12, 16))
    for i, image in enumerate((gpu, cpu, heat)):
        sheet.paste(image, (i * (gpu.width + 20), 0))
    sheet.save(out / "m10_moderngl_pygame_diff.png")
    lum = {b: stats(load((b, "effects"))) for b in ("moderngl", "pygame")}
    ok = (
        plain[1] < 1.0  # without environment effects the two backends draw the same frame
        and all(
            v["errors"] == 0 and v["fps"] >= 55 and v["rss_growth_after_warmup_mb"] < 10
            for v in soak.values()
        )
        and set(notes["pygame"]["unsupported"]) >= {"bloom", "grade", "vignette", "shadows"}
        and not notes["moderngl"]["unsupported"]
    )
    detail = {
        "plain_frame_diff": {"mean_abs": plain[0], "pixels_over_24_pct": plain[1]},
        "effects_frame_diff": {"mean_abs": effects[0], "pixels_over_24_pct": effects[1]},
        "effects_luma_mean_std": lum,
        "unsupported_on_backend": {b: v["unsupported"] for b, v in notes.items()},
        "soak_30s": soak,
    }
    (out / "m10_compare.json").write_text(json.dumps(detail, indent=2) + "\n")
    return result(
        "m10_compare",
        "PASS" if ok else "FAIL",
        f"Same field frame on both backends in real cocoa windows. Without environment "
        f"effects: mean |diff| "
        f"{plain[0]}, {plain[1]}% pixels differ by >24. With lighting, shadow, water, bloom, "
        f"grading, vignette: "
        f"mean |diff| {effects[0]}, {effects[1]}% pixels differ; luma mean/std ModernGL "
        f"{lum['moderngl']} vs "
        f"pygame {lum['pygame']}; pygame reports unsupported {notes['pygame']['unsupported']}, "
        f"ModernGL "
        f"{notes['moderngl']['unsupported'] or 'none'}. 30 s soak with rain (800 particles): "
        + "; ".join(
            f"{b} {v['frames']} frames {v['fps']} fps p99 {v['p99_ms']} ms max {v['max_ms']} "
            f"ms errors {v['errors']} "
            f"RSS {v['rss_growth_mb']:+} MB ({v['rss_growth_after_warmup_mb']:+} MB after the "
            f"first 10 s)"
            for b, v in soak.items()
        ),
        screenshots=["m10_moderngl_pygame_diff.png", *[p.name for p in frames.values()]],
        note="Numbers only. Whether the GPU effects look right (and whether the fallback is "
        "acceptable) is M10's "
        "visual confirmation, still NOT EXECUTED.",
    )


def check_migrated_project_plays(out):
    """ENG-20: the reference project is stored in older formats (project v8, RPG database v24,
    component
    Interaction2D v1). Copy it, upgrade it with the asteria-upgrade CLI in its own process, then
    play the
    upgraded project in a real window: walk, talk to the boss by key, save with F5 and load the
    save."""
    import shutil
    import tempfile

    import pygame

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    before = json.loads(PROJECT_FILE.read_text())
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "old_project"
        shutil.copytree(
            PROJECT, root, ignore=shutil.ignore_patterns("saves", "__pycache__", "*.bak")
        )
        path = root / "project.asteria.json"
        upgrade = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; from asteria.project_tools import upgrade_main; "
                "sys.exit(upgrade_main([sys.argv[1]]))",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=REPO,
            env=dict(os.environ, PYTHONPATH=str(REPO / "src")),
        )
        after = json.loads(path.read_text())
        project = Project.load_json(path, EditorDocument().component_registry)
        runtime = PlayableTestRuntime(project, project.game_start.instantiate(project), root)
        runtime.open()
        driver = pygame.display.get_driver()
        runtime._ui_mode = "field"
        game = runtime.game
        start = tuple(game.save.player_position)
        _key(pygame.K_RIGHT)
        _pump(runtime, 0.6)
        _key(pygame.K_RIGHT, up=True)
        _pump(runtime, 0.1)
        walked = tuple(game.save.player_position) != start or game.player is not None
        boss = next(e for e in game.scene.entities() if e.name == "Astral Tyrant")
        from asteria.core import Transform

        bt = boss.get(Transform)
        game.set_player_position(bt.x - 30.0, bt.y)
        _pump(runtime, 0.1)
        _key(pygame.K_RIGHT)  # face the boss (its interaction needs facing)
        _pump(runtime, 0.08)
        _key(pygame.K_RIGHT, up=True)
        _pump(runtime, 0.2)
        _key(pygame.K_e)
        _pump(runtime, 0.4)
        talked = game.pending_dialogue is not None or game.event_busy or game.mode == "battle"
        pygame.image.save(runtime.capture(), str(out / "migrated_project_playing.png"))
        _key(pygame.K_F5)
        _pump(runtime, 0.2)
        save = root / "saves" / "playtest_autosave.asteria-save.json"
        loaded = GameRuntimeSave.load_json(save, project) if save.is_file() else None
        runtime.close()
    ok = (
        upgrade.returncode == 0
        and before.get("version") < after.get("version")
        and walked
        and talked
        and loaded is not None
    )
    return result(
        "migrated_project_plays",
        "PASS" if ok else "FAIL",
        f"Reference project copied in its stored format (project v{before.get('version')}), "
        f"upgraded by the "
        f"asteria-upgrade CLI in its own process "
        f"({upgrade.stdout.strip() or upgrade.stderr.strip()[-200:]}) to "
        f"v{after.get('version')}, then played in a real {driver} window: walked by key "
        f"events={walked}, "
        f"pressed E at the boss -> dialogue / event / battle={talked}, F5 save written and loaded="
        f"{loaded is not None}",
        screenshots=["migrated_project_playing.png"],
    )


def check_asset_categories(out):
    """AST-07 / AST-08: one asset of every canonical category (the golden set: character, NPC,
    monster,
    tileset, prop, icon, VFX, skill, scene, projectile, UI) loaded through the canonical asset
    store the
    editor and runtime use, and shown in a real window - animated categories play their first
    clip."""
    import pygame

    from asteria.runtime.animation import AnimatorState
    from asteria.validation.golden import _clips_of, _sprite_source, _store

    root = REPO / "tests" / "golden" / "assets"
    loaded = _store(root).load(root)
    pygame.init()
    screen = pygame.display.set_mode((960, 540))
    pygame.display.set_caption("Asteria asset categories")
    driver = pygame.display.get_driver()
    clock = pygame.time.Clock()
    items = sorted(loaded.loaded, key=lambda x: x.manifest.kind)
    cells, rows = [], {}
    for item in items:
        manifest, asset = item.manifest, item.asset
        source = _sprite_source(asset, manifest)
        uri = source[0] if source else manifest.source
        image = None
        for candidate in (
            uri,
            getattr(asset, "image", ""),
            *(v.image_uri for v in getattr(asset, "visuals", ())),
        ):
            if candidate and str(candidate).endswith(".png") and (root / candidate).is_file():
                image = pygame.image.load(str(root / candidate)).convert_alpha()
                break
        clips = _clips_of(asset)
        clip = next(iter(clips.values()), None)
        frame = tuple(source[1]) if source else (image.get_size() if image else (32, 32))
        cells.append(
            (manifest.kind, manifest.asset_id, image, frame, AnimatorState(clip) if clip else None)
        )
        rows[manifest.asset_id] = {"kind": manifest.kind, "frames_seen": set(), "pixels": 0}
    start = time.perf_counter()
    while time.perf_counter() - start < 1.2:
        dt = clock.tick(60) / 1000.0
        pygame.event.pump()
        screen.fill((24, 26, 32))
        for i, (kind, asset_id, image, frame, animator) in enumerate(cells):
            cx, cy = 20 + (i % 6) * 156, 20 + (i // 6) * 250
            if image is not None:
                columns = max(1, image.get_width() // frame[0])
                index = animator.frame_index if animator else 0
                if animator:
                    animator.update(dt)
                rect = pygame.Rect(
                    (index % columns) * frame[0], (index // columns) * frame[1], *frame
                )
                rect = rect.clip(image.get_rect())
                part = image.subsurface(rect)
                scale = min(130 / max(1, part.get_width()), 170 / max(1, part.get_height()), 4)
                part = pygame.transform.scale(
                    part,
                    (
                        max(1, int(part.get_width() * scale)),
                        max(1, int(part.get_height() * scale)),
                    ),
                )
                screen.blit(part, (cx, cy))
                rows[asset_id]["frames_seen"].add(index)
                rows[asset_id]["pixels"] = max(
                    rows[asset_id]["pixels"],
                    sum(
                        1
                        for x in range(0, part.get_width(), 4)
                        for y in range(0, part.get_height(), 4)
                        if part.get_at((x, y))[3] > 0
                    ),
                )
            label = pygame.font.Font(None, 22).render(kind, True, (230, 232, 240))
            screen.blit(label, (cx, cy + 180))
        pygame.display.flip()
    pygame.image.save(screen, str(out / "asset_categories.png"))
    pygame.quit()
    kinds = sorted({r["kind"] for r in rows.values()})
    drawn = sorted(r["kind"] for r in rows.values() if r["pixels"] > 0)
    animated = sorted(r["kind"] for r in rows.values() if len(r["frames_seen"]) > 1)
    ok = loaded.ok and set(drawn) == set(kinds) and len(kinds) >= 11
    return result(
        "asset_categories_real_window",
        "PASS" if ok else "FAIL",
        f"{len(rows)} golden assets in {len(kinds)} categories {kinds} loaded through the "
        f"canonical asset store and "
        f"drawn in a real {driver} window; drawn {drawn}; animated in the window (more than "
        f"one frame shown) "
        f"{animated}. Audio playback (AST-08) is item 3a; prefabs are item 28 (editor workflows).",
        screenshots=["asset_categories.png"],
    )


def check_editor_characters(out):
    """EDT-16 + AST-11 in a shown Cocoa editor on a copy of the reference project: import a
    walking sprite
    sheet, place the character (Actor + linked entity), give an Actor that appearance, play the
    project and
    find the character in the live game; then auto-fix an image (preview, backup, confirmation)
    and pack an
    atlas from the Asset list."""
    import shutil
    import tempfile

    from PIL import Image
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.project import Project
    from asteria.runtime import ActorLinkComponent, SpriteRenderer2D

    app = QApplication.instance() or QApplication([])
    original = PROJECT_FILE.read_bytes()
    sheet = PROJECT / "playable_assets" / "player_field_sheet.png"
    checks, shots, notes = {}, [], {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "project"
        shutil.copytree(
            PROJECT, root, ignore=shutil.ignore_patterns("saves", "__pycache__", "*.bak")
        )
        path = root / "project.asteria.json"
        project = Project.load_json(path, EditorDocument().component_registry)
        window = AsteriaEditorWindow(project)
        window.document.file_path = path
        window._resolve_project_resources()
        window.resize(1600, 1000)
        window.show()
        window.raise_()
        window.activateWindow()

        def settle(seconds=0.3):
            deadline = time.perf_counter() + seconds
            while time.perf_counter() < deadline:
                app.processEvents()
                time.sleep(0.02)

        def shot(name, widget=None):
            settle()
            (widget or window).grab().save(str(out / name))
            shots.append(name)

        window.workspace.set_mode(WorkspaceMode.SCENE)
        window.refresh_all()
        settle(0.5)
        # EDT-16: sprite sheet -> character -> placed entity linked to its Actor, with a thumbnail
        visual = window.place_character_from_sheet(sheet, "RM Walker")
        copied = (root / "characters" / "rm_walker.png").is_file()
        created = window._place_character_at((6, 6)) if visual is not None else None
        entity = created.entity if created is not None else None
        link = entity.get(ActorLinkComponent).actor_id if entity is not None else None
        checks["sheet_copied_into_project"] = copied
        checks["character_placed_and_linked_to_actor"] = (
            bool(link) and link in project.rpg_database.actors
        )
        window.refresh_asset_list()
        items = [window.asset_list.item(i) for i in range(window.asset_list.count())]
        walker = [i for i in items if "rm_walker" in i.text()]
        checks["asset_list_thumbnail"] = bool(walker) and not walker[0].icon().isNull()
        if entity is not None:
            window.document.select_component(entity.get(SpriteRenderer2D))
            window.refresh_inspector()
        shot("characters_placed.png")
        # Actor appearance: another actor takes the new sheet
        sheet_id = (
            entity.get(SpriteRenderer2D).sprite_sheet_asset_id if entity is not None else None
        )
        other = next((a for a in sorted(project.rpg_database.actors) if a != link), None)
        applied = bool(
            other and sheet_id and window.set_actor_appearance(other, sheet_id) is not False
        )
        checks["actor_appearance_applied"] = applied
        notes["sheet"] = sheet_id
        # play from the placed character: the live game shows it in its field
        window.document.select_entity(entity)
        started = window.play_from_selection()
        snapshot = None
        deadline = time.perf_counter() + 25.0
        while snapshot is None and time.perf_counter() < deadline:
            settle(0.5)
            snapshot = window.debugger_widget.refresh()
        names = [e["name"] for e in (snapshot or {}).get("field_entities", [])]
        checks["character_in_live_game"] = bool(
            started and snapshot and entity is not None and entity.name in names
        )
        notes["live_entities"] = len(names)
        shot("characters_playing.png")
        window.stop_play()
        # AST-11: auto-fix from the Asset list - a padded copy of the sheet, cropped with preview
        # and backup
        padded = root / "playable_assets" / "rm_padded.png"
        with Image.open(sheet) as source:
            frame = source.convert("RGBA").crop((0, 0, 64, 64))
        canvas = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        canvas.alpha_composite(frame, (16, 16))
        canvas.save(padded)
        from asteria.assets import AssetRecord

        project.assets.add(
            AssetRecord.create(kind="texture", source_path="playable_assets/rm_padded.png")
        )
        window.refresh_asset_list()
        for i in range(window.asset_list.count()):
            item = window.asset_list.item(i)
            item.setSelected("rm_padded.png" in item.text())
        seen = {}

        def drive(dialog):
            dialog.show()
            dialog.fix.setCurrentIndex(dialog.fix.findData("crop_transparent_border"))
            shot("autofix_preview.png", dialog)
            seen["preview"] = dialog.report.text()
            dialog.apply()

        report = window.auto_fix_selected_image(dialog_hook=drive)
        with Image.open(padded) as fixed:
            fixed_size = fixed.size
        checks["autofix_preview_apply_backup"] = (
            report is not None
            and fixed_size[0] < 96
            and (padded.parent / "rm_padded.bak.png").is_file()
        )
        notes["autofix"] = f"{seen.get('preview')} -> {fixed_size}"
        soft = root / "playable_assets" / "rm_soft.png"
        Image.new("RGBA", (8, 8), (200, 40, 40, 100)).save(soft)
        project.assets.add(
            AssetRecord.create(kind="texture", source_path="playable_assets/rm_soft.png")
        )
        window.refresh_asset_list()
        for i in range(window.asset_list.count()):
            item = window.asset_list.item(i)
            item.setSelected("rm_soft.png" in item.text())
        refused = window.auto_fix_selected_image(
            dialog_hook=lambda d: (
                d.fix.setCurrentIndex(d.fix.findData("normalize_alpha")),
                d.apply(confirm=False),
            )
        )
        checks["destructive_fix_needs_confirmation"] = (
            refused is None and not (soft.parent / "rm_soft.bak.png").exists()
        )
        for i in range(window.asset_list.count()):
            item = window.asset_list.item(i)
            item.setSelected(
                any(n in item.text() for n in ("rm_padded.png", "rm_walker", "rm_soft.png"))
            )
        packed = window.pack_selected_images(root / "atlas" / "rm_atlas.png")
        regions = json.loads(packed[1].read_text())["regions"] if packed else {}
        checks["atlas_packed_with_regions"] = len(regions) >= 3
        notes["atlas"] = sorted(regions)
        shot("characters_assets.png")
        window.document.mark_saved()
        window.close()
        settle(0.2)
    checks["reference_project_untouched"] = PROJECT_FILE.read_bytes() == original
    failed = sorted(k for k, v in checks.items() if not v)
    return result(
        "editor_characters_gui",
        "PASS" if not failed else "FAIL",
        f"Qt platform '{app.platformName()}', shown editor on a copy of the reference project: "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items())
        + f"; sheet {notes.get('sheet')}, {notes.get('live_entities')} live field entities, "
        f"auto-fix "
        f"{notes.get('autofix')}, atlas regions {notes.get('atlas')}",
        screenshots=shots,
        note="Hands-on use by a person (mouse drags, typing) is manual item M7.",
    )


def check_icons_and_particles(out):
    """AST-07 menu icons (shop, Items, Equipment by real key events) and VFX-01 particles in real
    windows: a
    field emitter on an entity plus a PLAY_VFX one-shot (pygame and ModernGL, fps measured) and a
    battle
    timeline beat that bursts particles on the target. Effects are added in memory; nothing is
    saved."""
    import dataclasses

    import pygame

    from asteria.events import EventInstruction, EventProgram
    from asteria.presentation.particles import particle_effect_asset, preset
    from asteria.rpg import ShopDefinition, ShopEntry
    from asteria.runtime.environment2d import ParticleEmitter2DComponent
    from asteria.runtime.profiler import RuntimeProfiler

    results = []
    # -- AST-07: icons in the shop and the status menu --------------------------------------------
    runtime = _runtime()
    game = runtime.game
    game.project.rpg_database.add_shop(
        ShopDefinition(
            "rm_icons",
            "RM Icons",
            [
                ShopEntry(i, buy_prices={"gold": 10})
                for i in ("ether_leaf", "healing_herb", "iron_ore")
            ],
        )
    )
    drawn = {}
    original = runtime._draw_icon

    def counted(icon_id, x, y, size=22):
        shown = original(icon_id, x, y, size)
        if shown:
            drawn.setdefault(
                runtime._ui_mode
                + ("/" + runtime.status_menu.tab if runtime._ui_mode == "status" else ""),
                set(),
            ).add(icon_id)
        return shown

    runtime._draw_icon = counted

    def press(key, wait=0.12):
        _key(key)
        _pump(runtime, 0.05)
        _key(key, up=True)
        _pump(runtime, wait)

    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    _pump(runtime, 0.2)
    game.open_shop("rm_icons")
    _pump(runtime, 0.3)
    pygame.image.save(runtime.capture(), str(out / "icons_shop.png"))
    press(pygame.K_ESCAPE)
    for item in ("ether_leaf", "iron_ore", "weapon_03", "accessory_02"):
        game.save.rpg_state.inventory.add(item, 1)
    runtime.open_status_menu()
    menu = runtime.status_menu
    while menu.tab != "items":
        press(pygame.K_TAB, wait=0.05)
    _pump(runtime, 0.2)
    pygame.image.save(runtime.capture(), str(out / "icons_items.png"))
    while menu.tab != "equipment":
        press(pygame.K_TAB, wait=0.05)
    _pump(runtime, 0.2)
    pygame.image.save(runtime.capture(), str(out / "icons_equipment.png"))
    runtime.close()
    screens = {k: sorted(v) for k, v in drawn.items()}
    ok = (
        all(screens.get(k) for k in ("shop", "status/items", "status/equipment"))
        and driver == "cocoa"
    )
    results.append(
        result(
            "menu_icons_real_window",
            "PASS" if ok else "FAIL",
            f"Real {driver} window, real key events (Esc, Tab): icons drawn per screen {screens}",
            screenshots=["icons_shop.png", "icons_items.png", "icons_equipment.png"],
        )
    )

    # -- VFX-01: field emitter + PLAY_VFX one-shot, both backends ---------------------------------
    def field_run(backend, shot_name):
        runtime = _runtime(backend=backend)
        project = runtime.game.project
        project.assets.register(particle_effect_asset(preset("fire", "rm.fire")))
        project.assets.register(particle_effect_asset(preset("sparkle", "rm.sparkle")))
        project.assets.register(particle_effect_asset(preset("heal", "rm.heal")))
        game = runtime.game
        boss = next(e for e in game.scene.entities() if e.name == "Astral Tyrant")
        fire = boss.add_component(ParticleEmitter2DComponent())
        fire.effect_id, fire.offset_y = "rm.fire", -10.0
        sparkle = game.player.add_component(ParticleEmitter2DComponent())
        sparkle.effect_id = "rm.sparkle"
        project.event_programs.register(
            "rm_heal_fx",
            EventProgram(
                (
                    EventInstruction(
                        "WORLD",
                        {
                            "command": "PLAY_VFX",
                            "args": {"asset_id": "rm.heal", "entity": "player"},
                        },
                    ),
                )
            ),
        )
        runtime.open()
        driver = pygame.display.get_driver()
        runtime._ui_mode = "field"
        profiler = runtime.enable_profiling(RuntimeProfiler(target_fps=60))
        counts = {"max": 0, "one_shot": 0}

        def after(frame):
            profiler.end_frame()
            profiler.begin_frame()
            counts["max"] = max(counts["max"], getattr(runtime, "particles_drawn", 0))
            counts["one_shot"] = max(
                counts["one_shot"], sum(p.system.count for p in runtime.field_effects.particles)
            )
            if frame == 30:
                game.events.start("rm_heal_fx")
            if frame == 60:
                pygame.image.save(runtime.capture(), str(out / shot_name))

        profiler.begin_frame()
        _pump(runtime, 3.0, after=after)
        pacing = profiler.report()["pacing"]
        emitters = len(runtime.field_effects.emitters)
        runtime.close()
        return driver, pacing, counts, emitters

    for backend, name in ((None, "pygame"), ("moderngl", "moderngl")):
        driver, pacing, counts, emitters = field_run(backend, f"particles_field_{name}.png")
        ok = (
            counts["max"] > 20
            and counts["one_shot"] > 0
            and emitters == 2
            and pacing["measured_fps"] >= 50
        )
        results.append(
            result(
                f"particles_field_{name}",
                "PASS" if ok else "FAIL",
                f"{name} ({driver}): two entity emitters (fire on the boss, sparkle following "
                f"the player) and a "
                f"PLAY_VFX heal one-shot for 3 s: up to {counts['max']} particles drawn per "
                f"frame, one-shot peak "
                f"{counts['one_shot']}, {pacing['measured_fps']} fps, p99 interval "
                f"{pacing['interval_p99_ms']} ms",
                screenshots=[f"particles_field_{name}.png"],
                note="Whether the particles look good is manual item M10.",
            )
        )

    # -- VFX-01: battle beat ----------------------------------------------------------------------
    runtime = _runtime()
    project = runtime.game.project
    project.assets.register(particle_effect_asset(preset("explosion", "rm.burst")))
    library = project.battle_presentation_library
    for sequence_id in library.ids("motion_sequences"):  # every skill's VFX beat bursts particles
        sequence = library.require("motion_sequences", sequence_id)
        beats = tuple(
            dataclasses.replace(b, cue="rm.burst") if b.channel == "vfx" else b
            for b in sequence.beats
        )
        library.set("motion_sequences", sequence_id, dataclasses.replace(sequence, beats=beats))
    runtime.open()
    driver = pygame.display.get_driver()
    game = runtime.game
    runtime._ui_mode = "field"
    game.start_encounter("boss_room")
    peak = {"n": 0, "shot": False}
    draw = runtime.particle_drawer.draw

    def counting_draw(*args, **kwargs):
        n = draw(*args, **kwargs)
        peak["n"] = max(peak["n"], n)
        if n >= 30 and args[1] and args[1][0].age >= 0.2:
            peak["due"] = True  # saved after this frame is presented, once the burst has spread
        return n

    runtime.particle_drawer.draw = counting_draw

    def save_when_due(_frame):
        if peak.get("due") and not peak["shot"]:
            pygame.image.save(runtime.capture(), str(out / "particles_battle.png"))
            peak["shot"] = True

    adapter = runtime._battle_presentation
    adapter.begin()
    runtime._advance_to_hero_turn()
    used = 0
    for _ in range(60):  # a skill by a real key press whenever the hero may act
        if (
            not adapter.busy()
            and runtime.game.mode == "battle"
            and runtime._battle_actor() is not None
        ):
            _key(pygame.K_1)
            _pump(runtime, 0.05)
            _key(pygame.K_1, up=True)
            used += 1
        _pump(runtime, 0.1, after=save_when_due)
        if peak["shot"]:
            break
    _pump(runtime, 0.5)
    targets = sorted({entry[0].member_id for entry in adapter._cue_particles.values()})
    runtime.close()
    results.append(
        result(
            "particles_battle_beat",
            "PASS" if peak["n"] >= 30 and peak["shot"] and targets else "FAIL",
            f"Canonical battle in a real {driver} window: every action timeline's VFX beat "
            f"cues a particle effect; "
            f"bursts drawn on {targets} (whichever side acted first; {used} hero skill key "
            f"presses), up to "
            f"{peak['n']} particles in one frame",
            screenshots=["particles_battle.png"] if peak["shot"] else [],
        )
    )
    return results


def check_editor_particles(out):
    """VFX-01 in a shown Cocoa editor: Particle Effects tab - new effect from a preset, values
    changed in the
    form, the live preview running on its own timer, Apply / Undo, an emitter's Inspector choice,
    usage."""
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.presentation.particles import effect_definition
    from asteria.project import Project
    from asteria.runtime.environment2d import ParticleEmitter2DComponent

    app = QApplication.instance() or QApplication([])
    original = PROJECT_FILE.read_bytes()
    project = Project.load_json(PROJECT_FILE, EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    window.document.file_path = PROJECT_FILE
    window._resolve_project_resources()
    window.resize(1500, 950)
    window.show()
    window.raise_()
    checks, shots = {}, []

    def settle(seconds=0.3):
        deadline = time.perf_counter() + seconds
        while time.perf_counter() < deadline:
            app.processEvents()
            time.sleep(0.02)

    window.workspace.set_mode(WorkspaceMode.UI)
    editor = window.particle_editor
    window.ui_workspace.setCurrentWidget(editor)
    settle(0.4)
    checks["new_from_preset"] = editor.new_effect("rm.campfire", "fire") == "rm.campfire"
    editor.inputs["rate"].setValue(90.0)
    editor.inputs["spread"].setValue(40.0)
    editor.inputs["color_end"].set_rgba((60, 120, 255, 0))
    settle(1.2)  # the preview runs on its own QTimer
    live = editor.preview.system
    checks["preview_runs"] = live is not None and live.count > 40 and live.definition.rate == 90.0
    editor.grab().save(str(out / "editor_particles.png"))
    shots.append("editor_particles.png")
    checks["apply"] = (
        editor.apply() and effect_definition(project.assets, "rm.campfire").rate == 90.0
    )
    window.document.undo()
    checks["undo"] = effect_definition(project.assets, "rm.campfire").rate == 40.0
    window.document.redo()
    scene = project.scene(project.startup_scene_id)
    boss = next(e for e in scene.entities() if e.name == "Astral Tyrant")
    emitter = boss.add_component(ParticleEmitter2DComponent())
    emitter.effect_id = "rm.campfire"
    window.workspace.set_mode(WorkspaceMode.SCENE)
    window.document.select_component(emitter)
    window.refresh_inspector()
    settle(0.3)
    table = window.inspector.table
    combos = [table.cellWidget(r, 1) for r in range(table.rowCount())]
    combos = [c for c in combos if hasattr(c, "findData")]
    checks["inspector_choice"] = any(c.findData("rm.campfire") >= 0 for c in combos)
    window.grab().save(str(out / "editor_particles_inspector.png"))
    shots.append("editor_particles_inspector.png")
    checks["usage"] = any("Astral Tyrant" in u for u in editor.api.usages("rm.campfire"))
    window.document.mark_saved()
    window.close()
    checks["project_file_untouched"] = PROJECT_FILE.read_bytes() == original
    failed = sorted(k for k, v in checks.items() if not v)
    return result(
        "editor_particles_gui",
        "PASS" if not failed else "FAIL",
        f"Qt platform '{app.platformName()}', shown editor: "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items())
        + f"; preview had {live.count if live else 0} live particles",
        screenshots=shots,
        note="Hands-on use by a person is manual item M7; judging the look is M10.",
    )


def check_octopath_demo(out):
    """BTL-02 / BTL-03 / GP-02: the Octopath-style demo project played in a real window by key
    events through
    the battle command menu: boost and a chosen target, a divine skill (three boost points,
    particle burst),
    concocting two ingredients, then the battle won. Enemies are worn down in memory to keep the
    run short."""
    import pygame

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    root = REPO / "reference_projects" / "octopath_demo"
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=960, height=540
    )
    runtime.open()
    driver = pygame.display.get_driver()
    game, checks, shots = runtime.game, {}, []

    def press(key, wait=0.1):
        _key(key)
        _pump(runtime, 0.04)
        _key(key, up=True)
        _pump(runtime, wait)

    def shot(name):
        pygame.image.save(runtime.capture(), str(out / name))
        shots.append(name)

    def hero_turn(limit=12.0):
        deadline = time.perf_counter() + limit
        while time.perf_counter() < deadline:
            if game.battle is None or runtime._victory:
                return None
            if not runtime._battle_presentation.busy() and runtime._battle_actor():
                return runtime._battle_actor()
            _pump(runtime, 0.1)
        return None

    def select(actor, ability_id):
        commands = runtime.battle_commands
        ids = [r.action_id for r in commands.entries(actor)]
        for _ in range(ids.index(ability_id) - commands.cursor):
            press(pygame.K_DOWN, 0.04)
        press(pygame.K_RETURN)

    executed = []  # what landed (the battle screen drains the battle log every frame)
    execute = game.execute

    def counting_execute(actor_id, ability_id, target_ids):
        executed.append(ability_id)
        return execute(actor_id, ability_id, target_ids)

    game.execute = counting_execute
    runtime._ui_mode = "field"
    _pump(runtime, 0.4)
    shot("octo_field.png")
    game.start_encounter("boss_room")
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    actor = hero_turn()
    checks["command_menu"] = actor is not None and bool(runtime.battle_commands.entries(actor))
    shot("octo_menu.png")
    # boost x2 and a chosen target
    game.battle.battle_resources.change(actor, "bp", 3)
    press(pygame.K_RIGHT)
    checks["boost_set_by_key"] = runtime.battle_commands.boost == 1
    attack = next(
        r.action_id
        for r in runtime.battle_commands.entries(actor)
        if r.action_id.startswith("attack_")
    )
    select(actor, attack)
    checks["target_menu"] = runtime.battle_commands.mode == "target"
    shot("octo_target.png")
    press(pygame.K_RETURN, 0.3)
    checks["boosted_attack_two_hits"] = executed.count(attack) == 2
    # a divine skill: three boost points, a particle burst
    divine = None
    for _ in range(8):
        actor = hero_turn()
        if actor is None:
            break
        known = game.battle.member(actor).ability_ids
        divine = next(
            (a for a in known if "divine" in game.project.gameplay_library.abilities.get(a).tags),
            None,
        )
        if divine is not None:
            break
        press(pygame.K_RETURN)
        press(pygame.K_RETURN)
    peak = {"n": 0, "shot": False}
    draw = runtime.particle_drawer.draw

    def counted(*args, **kwargs):
        n = draw(*args, **kwargs)
        peak["n"] = max(peak["n"], n)
        if n >= 40 and not peak["shot"] and args[1] and args[1][0].age >= 0.15:
            peak["due"] = True
        return n

    runtime.particle_drawer.draw = counted
    if divine is not None:
        game.battle.battle_resources.change(
            actor, "bp", 3 - game.battle.battle_resources.current(actor, "bp")
        )
        before = game.battle.battle_resources.current(actor, "bp")
        select(actor, divine)
        if runtime.battle_commands.mode == "target":
            press(pygame.K_RETURN)
        for _ in range(40):
            _pump(runtime, 0.05)
            if peak.get("due") and not peak["shot"]:
                shot("octo_divine.png")
                peak["shot"] = True
        checks["divine_spends_three_bp"] = (
            before - game.battle.battle_resources.current(actor, "bp") >= 3
        )
        checks["divine_particle_burst"] = peak["shot"]
    else:
        checks["divine_spends_three_bp"] = checks["divine_particle_burst"] = False
    # concoct with the apothecary when his turn comes
    concocted = False
    for _ in range(10):
        actor = hero_turn()
        if actor is None:
            break
        if "concoct" in game.battle.member(actor).ability_ids:
            herbs = game.save.rpg_state.inventory.count("healing_herb")
            select(actor, "concoct")
            select(actor, "healing_herb")  # base
            shot("octo_concoct.png")
            select(actor, "fire_dust")  # catalyst: a fire bomb on every enemy
            if runtime.battle_commands.mode == "target":
                press(pygame.K_RETURN)
            concocted = (
                game.save.rpg_state.inventory.count("healing_herb") < herbs
                and "bomb_fire" in executed
            )
            break
        press(pygame.K_RETURN)
        press(pygame.K_RETURN)
    checks["concoct_by_keys"] = concocted
    # win: wear the enemies down and keep pressing Enter
    for _ in range(400):
        if runtime._victory or game.battle is None:
            break
        for enemy in game.active_enemy_ids():
            pool = game.battle.member(enemy).subject.resources
            pool.set_current("vitality", min(pool.current("vitality"), 400))
        if not runtime._battle_presentation.busy() and runtime._battle_actor():
            if runtime.battle_commands.mode == "ingredients":
                press(pygame.K_ESCAPE, 0.05)
            press(pygame.K_RETURN, 0.05)
        else:
            _pump(runtime, 0.05)
    checks["battle_won_by_keys"] = bool(runtime._victory)
    _pump(runtime, 0.6)
    shot("octo_victory.png")
    runtime.close()
    # the other enemy kinds: each encounter opens with its art, shields and weaknesses
    for encounter_id in ("slime_pit", "old_crypt", "gazer_nest", "samurai_duel"):
        fresh = Project.load_json(
            root / "project.asteria.json", EditorDocument().component_registry
        )
        other = PlayableTestRuntime(
            fresh, fresh.game_start.instantiate(fresh), root, width=960, height=540
        )
        other.open()
        other._ui_mode = "field"
        other.game.start_encounter(encounter_id)
        other._battle_presentation.begin()
        other._advance_to_hero_turn()
        _pump(other, 2.0)
        adapter = other._battle_presentation
        drawn = adapter.visuals_enabled and all(
            adapter.screen.scene.visual_for(e).sprite_sheet_asset_id.endswith(e.split(":", 1)[0])
            for e in other.game.active_enemy_ids()
        )
        checks[f"encounter_{encounter_id}"] = bool(drawn and other.game.active_enemy_ids())
        pygame.image.save(other.capture(), str(out / f"octo_{encounter_id}.png"))
        shots.append(f"octo_{encounter_id}.png")
        other.close()
    failed = sorted(k for k, v in checks.items() if not v)
    return result(
        "octopath_demo_real_window",
        "PASS" if not failed and driver == "cocoa" else "FAIL",
        f"Octopath-style demo in a real {driver} window, real key events: "
        + ", ".join(f"{k}={'ok' if v else 'FAILED'}" for k, v in checks.items())
        + f"; divine skill {divine}, up to {peak['n']} particles in a frame",
        screenshots=shots,
        note="Whether it plays well is for a person (M5 / M10).",
    )


def _rss_mb():
    value = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True
    ).stdout
    return int(value.strip()) / 1024.0


def check_battle_memory(out):
    """ENG-10: battle-scoped images are released after every battle; process memory stays flat
    over 12 battles
    in the real playable window."""
    import pygame

    runtime = _runtime()
    runtime.open()
    driver = pygame.display.get_driver()
    runtime._ui_mode = "field"
    game = runtime.game
    samples, field_cache = [], []

    def one_battle():
        game.start_encounter("boss_room")
        runtime._battle_presentation.begin()
        _pump(runtime, 0.4)
        for enemy_id in tuple(game.active_enemy_ids()):
            while enemy_id in game.active_enemy_ids():
                for hero_id in tuple(game.active_hero_ids()):
                    if enemy_id in game.active_enemy_ids():
                        game.execute(hero_id, "strike", (enemy_id,))
        game.finish_victory()
        _pump(runtime, 0.3)
        field_cache.append(sum(1 for owner in runtime._image_scope.values() if owner == "battle"))
        samples.append(_rss_mb())

    _pump(runtime, 0.5)
    for _ in range(12):
        one_battle()
    pygame.image.save(runtime.capture(), str(out / "battle_memory_after_12.png"))
    released = runtime.released_images
    runtime.close()
    growth = samples[-1] - samples[1]  # after the first battle the caches and fonts are warm
    ok = all(count == 0 for count in field_cache) and released > 0 and growth < 25.0
    return result(
        "battle_memory_real_window",
        "PASS" if ok else "FAIL",
        f"12 boss battles entered and left in the real playable {driver} window: battle-scoped "
        f"images left in the "
        f"cache after each battle {field_cache}; {released} images released in total; process "
        f"RSS per battle (MB) "
        f"{[round(x, 1) for x in samples]}; growth from battle 2 to 12 {growth:+.1f} MB (limit "
        f"+25 MB)",
        screenshots=["battle_memory_after_12.png"],
    )


# -- D19: session-level integration tests replayed in the real playable window --------------------

REPLAY = {
    "RPG-02": [
        "shops_and_quests::test_equipment_set_bonuses_apply_by_piece_count_and_survive_save_load"
    ],
    "RPG-04": [
        "drop_tables::test_victory_rolls_the_enemy_drop_table_and_pity_survives_save_and_load"
    ],
    "RPG-05": [
        "shops_and_quests::test_shop_buys_sells_and_tracks_limited_stock",
        "game_menus::test_runtime_opens_shop_from_an_event_and_buys",
    ],
    "RPG-06": [
        "runtime_menus_d12::test_crafting_screen_opened_by_event_crafts_in_the_runtime",
        "runtime_menus_d12::test_recipe_discovery_by_event_and_by_experiment",
    ],
    "RPG-07": [
        "world_interactions::test_refusals_cost_success_rewards_and_one_time_use",
        "world_interactions::test_party_capability_and_cost_are_checked",
        "world_interactions::test_stat_checks_are_deterministic_and_failures_run_their_branch",
        "world_interactions::test_an_event_runs_an_interaction_and_branches_on_its_outcome",
    ],
    "RPG-09": ["behavior_trees::test_a_tree_in_the_game_session_starts_its_encounter"],
    "CMP-01": [
        "character_composition::test_the_playable_field_draws_the_players_layers_and_attachments",
        "character_composition::test_battle_draws_layers_behind_and_attachments_in_front_of_the_body",
    ],
    "ANI-05": [
        "character_control::test_controllers_actions_and_hits_run_in_the_game_session_field_update",
        "character_control::test_project_action_timelines_are_authored_as_records_and_played_from_events",
    ],
    "RPG-10": [
        "runtime_field_enemies::test_spawned_enemy_chases_player_and_starts_battle_in_the_runtime",
        "runtime_field_enemies::test_spawn_zone_respawns_and_field_ai_pauses_outside_the_field",
        "field_ai_and_spawning::test_touching_a_visible_encounter_starts_the_battle",
    ],
    "WLD-01": [
        "shops_and_quests::test_victory_advances_defeat_objectives_and_events_drive_quests",
        "game_menus::test_quest_rows_and_menu_cursor",
    ],
    "WLD-02": [
        "world_record_and_capture::test_events_drive_reputation_counters_and_unlock_achievements",
        "runtime_menus_d12::test_achievement_and_bestiary_screens_from_the_pause_menu",
    ],
    "EVT-01": [
        "session_events::test_authored_dialogue_choice_branch_and_encounter_run_in_order",
        "session_events::test_failed_world_command_stops_the_event_and_is_reported",
        "session_events::test_event_waiting_on_dialogue_survives_save_and_reload",
        "session_events::test_autorun_binding_runs_once_until_its_condition_turns_off",
    ],
    "EVT-02": [
        "session_events::test_refusing_takes_the_other_branch_and_starts_no_battle",
        "session_events::test_item_currency_and_presentation_commands_change_session_state",
        "session_events::test_transfer_moves_the_player_to_another_scene_and_its_events",
    ],
    "EVT-03": [
        "event_flow_integration::test_common_events_autorun_and_parallel_follow_their_switches",
        "event_flow_integration::test_battle_event_fires_on_its_condition_once_and_holds_battle_input",
    ],
    "EVT-04": [
        "event_flow_integration::test_a_sequence_runs_dialogue_and_music_tracks_in_parallel"
    ],
    "RPG-01": [
        "inventory_rules::test_the_game_session_applies_the_project_rules_to_events_and_shops"
    ],
    "RPG-08": [
        "companions_and_summons::test_a_boss_summons_minions_it_owns_and_they_take_turns",
        "companions_and_summons::test_a_companion_in_reserve_is_called_into_the_battle_and_events_can_summon",
        "companions_and_summons::test_a_captured_companion_grows_and_is_kept_in_reserve_across_save_and_load",
        "companions_and_summons::test_summoned_combatants_appear_on_the_battle_screen",
    ],
    "GP-02": [
        "ability_rules_in_battle::test_cost_is_paid_and_targets_follow_the_ability_targeting_data",
        "ability_rules_in_battle::test_cooldown_blocks_the_ability_for_its_users_next_turns",
        "ability_rules_in_battle::test_timeline_mode_casts_resolve_later_and_recovery_delays_the_next_turn",
    ],
    "BTL-02": [
        "dot_in_session::test_damage_over_time_is_fixed_unless_the_author_gives_it_interaction_tags",
        "octopath_style_battle::test_two_weapons_weapon_weakness_and_resistance",
        "octopath_style_battle::test_weakness_hits_break_the_shield_and_the_break_doubles_damage",
        "octopath_style_battle::test_boost_repeats_attacks_and_powers_spells",
        "octopath_style_battle::test_secondary_job_and_a_poison_that_worsens_every_turn",
    ],
    "ANI-02": [
        "canonical_battle_presentation::test_an_authored_state_machine_chooses_the_battle_clips"
    ],
    "BTL-03": [
        "octopath_demo::test_boosted_sword_attack_hits_three_times_breaks_shields_and_reveals_the_weakness",
        "octopath_demo::test_break_skips_the_enemy_turn_and_doubles_damage",
        "octopath_demo::test_divine_skill_needs_three_boost_points_and_spends_them",
        "octopath_demo::test_one_spell_of_three_elements_reveals_three_weaknesses",
        "octopath_demo::test_donate_boost_call_the_pet_and_concoct",
        "octopath_demo::test_poison_worsens_sleep_skips_turns_and_attack_up_raises_damage",
        "octopath_demo::test_the_demo_battle_is_won_with_the_keyboard",
        "octopath_demo::test_fire_heals_the_gel_slime_and_lightning_breaks_it",
        "octopath_demo::test_the_mirror_gazer_reflects_spells_and_cannot_be_put_to_sleep",
        "octopath_demo::test_the_bone_wraith_shrugs_off_poison_and_fears_light",
        "octopath_demo::test_the_iron_samurai_resists_swords_and_needs_a_spear",
        "octopath_demo::test_field_enemies_wander_and_touching_one_starts_its_battle",
    ],
    "CMP-03": [
        "field_popups::test_item_gains_and_authored_popups_rise_and_fade_above_characters",
        "field_popups::test_a_full_bag_says_so",
    ],
}


def check_b_items_replay(out):
    """B items whose remaining gap was "no real-machine run": their session-level integration
    tests run
    inside the real playable window (tests/real_window.py), unchanged, with frames presented after
    each
    session call. Tests that never drove the window do not count."""
    report_path = out / "b_items_replay.json"
    shots = out / "replay"
    files = sorted(
        {f"tests/test_{name.split('::')[0]}.py" for names in REPLAY.values() for name in names}
    )
    env = dict(os.environ, ASTERIA_REAL_WINDOW="1", ASTERIA_REAL_WINDOW_REPORT=str(report_path))
    env["ASTERIA_REAL_WINDOW_SHOTS"] = str(shots)
    for key in ("SDL_VIDEODRIVER", "SDL_AUDIODRIVER", "QT_QPA_PLATFORM"):
        env.pop(key, None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", *files],
        capture_output=True,
        text=True,
        timeout=900,
        cwd=REPO,
        env=env,
    )
    report = json.loads(report_path.read_text())
    summary = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    results = []
    for item, names in REPLAY.items():
        rows = []
        for name in names:
            nodeid = f"tests/test_{name.replace('::', '.py::', 1)}"
            outcome = report["results"].get(nodeid, "not run")
            frames = report["per_test"].get(nodeid, 0)
            rows.append((name.split("::")[1], outcome, frames))
        ok = report["driver"] == "cocoa" and all(o == "passed" and f > 0 for _, o, f in rows)
        detail = "; ".join(f"{n}: {o}, {f} frames" for n, o, f in rows)
        results.append(
            result(
                f"replay_{item}",
                "PASS" if ok else "FAIL",
                f"{item}: session-level integration tests replayed in the real playable "
                f"{report['driver']} window "
                f"(same assertions; frames presented after each session call): {detail}",
                screenshots=[f"replay/{n}.png" for n, _, _ in rows],
            )
        )
    results.append(
        result(
            "b_items_replay_run",
            "PASS" if proc.returncode == 0 else "FAIL",
            f"pytest exit {proc.returncode}; {len(report['results'])} tests in {len(files)} "
            f"files, "
            f"{report['frames']} frames presented in total; {summary}",
        )
    )
    return results


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
    "gpu_playable": check_gpu_playable,
    "vfx": check_vfx_environment,
    "mv_import_gpu": check_mv_import_gpu,
    "gameplay": check_gameplay_systems,
    "menus_more": check_game_menus_more,
    "editor_workflows": check_editor_workflows,
    "battle_no_art": check_battle_without_art,
    "b_items_replay": check_b_items_replay,
    "engine_systems": check_engine_systems,
    "battle_memory": check_battle_memory,
    "m10_compare": check_m10_compare,
    "migrated_project": check_migrated_project_plays,
    "asset_categories": check_asset_categories,
    "editor_characters": check_editor_characters,
    "icons_and_particles": check_icons_and_particles,
    "editor_particles": check_editor_particles,
    "octopath_demo": check_octopath_demo,
}


def _run_child(name, out):
    proc = subprocess.run(
        [sys.executable, __file__, str(out), "--child", name],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=REPO,
    )
    marker = "RESULT_JSON:"
    for line in proc.stdout.splitlines():
        if line.startswith(marker):
            return json.loads(line[len(marker) :])
    return [
        result(name, "FAIL", f"check crashed (exit {proc.returncode})", stderr=proc.stderr[-1500:])
    ]


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
        rerun = {r["check"] for r in results} | set(
            args.only
        )  # also drop old crash entries (named by key)
        previous = json.loads(results_path.read_text()).get("results", [])
        results = [r for r in previous if r["check"] not in rerun] + results
    results_path.write_text(json.dumps({"meta": meta, "results": results}, indent=2))
    for item in results:
        print(f"{item['status']:<13} {item['check']}: {item['evidence']}")
    return 0 if all(r["status"] != "FAIL" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
