from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json, os, subprocess, sys, tempfile

class RuntimeLaunchError(RuntimeError):
    pass

@dataclass(slots=True)
class RuntimeProcess:
    process:object
    snapshot_path:Path

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
                self.process.wait()
        try:
            self.snapshot_path.unlink()
        except FileNotFoundError:
            pass

def launch_play_session(session,*,popen_factory=subprocess.Popen,python_executable=None):
    if not session.active:
        raise RuntimeLaunchError("Play session is not active")
    fd,path=tempfile.mkstemp(prefix="asteria-play-",suffix=".asteria.json")
    snapshot_path=Path(path)
    try:
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(session.runtime_project.to_data(),f,indent=2,sort_keys=True)
            f.write("\n")
        executable=python_executable or sys.executable
        process=popen_factory([
            executable,"-m","asteria.runtime.preview",str(snapshot_path),
            "--scene",session.source_scene_id
        ])
        return RuntimeProcess(process,snapshot_path)
    except Exception as exc:
        try:snapshot_path.unlink()
        except FileNotFoundError:pass
        raise RuntimeLaunchError(str(exc)) from exc
