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
    debug_port: int | None = None
    debug_token: str | None = None
    log_path: Path | None = None
    _log_file: object = None

    def read_log(self):
        """Everything the game wrote to stdout/stderr so far (empty when not captured)."""
        if self.log_path is None or not self.log_path.exists():
            return ""
        return self.log_path.read_text(encoding="utf-8", errors="replace")

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
        if self._log_file is not None:
            self._log_file.close()
            self._log_file = None
        for path in (self.snapshot_path, self.save_snapshot_path):
            if path is None:
                continue
            try:
                path.unlink()
            except FileNotFoundError:
                pass


def _free_port():
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def launch_play_session(
    session,
    *,
    popen_factory=subprocess.Popen,
    python_executable=None,
    debug=False,
    spawn=None,
    capture_log=False,
):
    """Start the runtime for ``session``.

    ``debug`` opens the loopback debug channel (port + random token are kept
    on the returned RuntimeProcess); ``spawn`` = (x, y) starts the player at a
    chosen point; ``capture_log`` writes the game's stdout/stderr to a log
    file the editor can show.
    """
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
        debug_port = debug_token = None
        if debug:
            import secrets

            debug_port, debug_token = _free_port(), secrets.token_hex(16)
            args += ["--debug-port", str(debug_port), "--debug-token", debug_token]
        if spawn is not None:
            args += ["--spawn", str(float(spawn[0])), str(float(spawn[1]))]
        log_path = log_file = None
        if capture_log:
            fd3, path3 = tempfile.mkstemp(prefix="asteria-play-", suffix=".log")
            os.close(fd3)
            log_path = Path(path3)
            log_file = open(log_path, "w", encoding="utf-8")  # noqa: SIM115 - closed by RuntimeProcess.stop
            process = popen_factory(args, stdout=log_file, stderr=subprocess.STDOUT)
        else:
            process = popen_factory(args)
        return RuntimeProcess(
            process, snapshot_path, save_snapshot_path, debug_port, debug_token, log_path, log_file
        )
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
