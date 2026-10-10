from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


class RuntimeLaunchError(RuntimeError):
    pass


@dataclass(slots=True)
class RuntimeProcess:
    process: object
    snapshot_path: Path
    save_snapshot_path: Path | None = None

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        for path in (self.snapshot_path, self.save_snapshot_path):
            if path is None:
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def launch_play_session(session, *, popen_factory=subprocess.Popen, python_executable=None):
    if not session.active:
        raise RuntimeLaunchError("Play session is not active")
    fd, path = tempfile.mkstemp(prefix="asteria-play-", suffix=".asteria.json")
    snapshot_path = Path(path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(session.runtime_project.to_data(), f, indent=2, sort_keys=True)
            f.write("\n")
        save_snapshot_path = None
        if session.runtime_save is not None:
            fd2, path2 = tempfile.mkstemp(prefix="asteria-save-", suffix=".asteria-save.json")
            save_snapshot_path = Path(path2)
            with os.fdopen(fd2, "w", encoding="utf-8") as f:
                json.dump(session.runtime_save.to_data(), f, indent=2, sort_keys=True)
                f.write("\n")
        executable = python_executable or sys.executable
        args = [
            executable,
            "-m",
            "asteria.runtime.preview",
            str(snapshot_path),
            "--scene",
            session.source_scene_id,
        ]
        if session.resource_root is not None:
            args += ["--resource-root", str(session.resource_root)]
        if save_snapshot_path is not None:
            args += ["--save", str(save_snapshot_path)]
        if session.playtest_profile_id is not None:
            args += ["--playtest-profile", session.playtest_profile_id]
        process = popen_factory(args)
        return RuntimeProcess(process, snapshot_path, save_snapshot_path)
    except Exception as exc:
        try:
            snapshot_path.unlink()
        except FileNotFoundError:
            pass
        try:
            if "save_snapshot_path" in locals() and save_snapshot_path is not None:
                save_snapshot_path.unlink()
        except FileNotFoundError:
            pass
        raise RuntimeLaunchError(str(exc)) from exc
