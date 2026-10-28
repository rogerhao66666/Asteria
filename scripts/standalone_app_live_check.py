"""Real-window check of the standalone app (AST-06), run BY the app, not by a venv:

    dist/Asteria.app/Contents/MacOS/Asteria scripts/standalone_app_live_check.py OUT

A game window started by a program in the background (this script, a terminal) may open behind
other windows on macOS; then check the screenshots with the game started through ``open``.

Opens the editor on a copy of the Full Verification demo the app carries, playtests it (the
app starts itself as the game), exports a game that needs no Python and starts that game, all
in real windows and silent (ASTERIA_MUTE=1). Screenshots and ``results.json`` go to ``OUT``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ["ASTERIA_MUTE"] = "1"
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def pump(app, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def screenshot(path):
    """The whole screen (the game windows are other processes)."""
    done = subprocess.run(["/usr/sbin/screencapture", "-x", str(path)], check=False, timeout=30)
    return done.returncode == 0 and Path(path).is_file()


def main(out):
    from PySide6.QtWidgets import QApplication

    from asteria import frozen
    from asteria.editor.project_templates import TEMPLATES
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    out.mkdir(parents=True, exist_ok=True)
    results = {"frozen": frozen.is_frozen(), "executable": sys.executable}
    root = frozen.engine_root()
    results["engine"] = str(root)
    results["player"] = str(frozen.player_runtime())
    full = next(t for t in TEMPLATES if t.template_id == "full_verification")
    results["full_verification_template"] = full.available()
    app = QApplication.instance() or QApplication(sys.argv)
    project_dir = out / "full_verification"
    shutil.rmtree(project_dir, ignore_errors=True)
    shutil.copytree(root / "reference_projects" / "full_verification_demo", project_dir)
    path = project_dir / "project.asteria.json"
    window = AsteriaEditorWindow()
    window.set_project(Project.load_json(path, window.document.component_registry), path)
    window.resize(1400, 900)
    window.show()
    window.raise_()
    pump(app, 3)
    results["editor_screenshot"] = window.grab().save(str(out / "1_editor.png"))

    results["playtest_started"] = bool(window.play_project())
    process = window.runtime_process
    pump(app, 8)
    results["playtest_running_after_8s"] = process is not None and process.running
    results["playtest_screenshot"] = screenshot(out / "2_playtest.png")
    if process is not None:
        results["playtest_log_tail"] = process.read_log()[-400:]
        process.stop()
    pump(app, 1)

    export = out / "export"
    shutil.rmtree(export, ignore_errors=True)
    result = window.export_game(export, name="FV Quest", pyz=False, app=True)
    results["export_standalone"] = result["standalone"]
    results["export_app"] = str(result["app"])
    results["export_warnings"] = list(result["report"].warnings)
    program = frozen.player_executable(result["app"])
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "SDL_VIDEO"))}
    game = subprocess.Popen([str(program), "--frames", "420"], env=env)
    time.sleep(5)
    results["exported_game_screenshot"] = screenshot(out / "3_exported_game.png")
    results["exported_game_exit"] = game.wait(timeout=120)
    window.close()  # the export saved the project, so nothing asks to be saved
    pump(app, 1)
    (out / "results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    passed = (
        results["frozen"]
        and results["full_verification_template"]
        and results["playtest_running_after_8s"]
        and results["export_standalone"]
        and results["exported_game_exit"] == 0
    )
    print("PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "standalone_check")))
