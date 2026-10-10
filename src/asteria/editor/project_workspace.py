from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from asteria.core import Scene
from asteria.project import Project

from .model import EditorDocument
from .playmode import PlaySession, create_play_session
from .storage import load_document, save_document


class ProjectWorkspaceError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProjectWorkspaceState:
    project_name: str | None
    project_path: str | None
    dirty: bool
    can_run: bool
    running: bool
    scene_count: int
    startup_scene_id: str | None
    recent_projects: tuple[str, ...]


class RecentProjectStore:
    """Small editor preference store; never part of canonical game data."""

    def __init__(self, path=None, *, capacity=12):
        self.path = Path(path).expanduser().resolve() if path else None
        self.capacity = max(1, int(capacity))
        self._items = []

    def load(self):
        if self.path is None or not self.path.exists():
            return tuple(self._items)
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if raw.get("schema") != "asteria.editor.recent_projects":
                raise ValueError("unsupported recent-project store")
            self._items = [str(Path(x).expanduser().resolve()) for x in raw["projects"]]
            self._items = self._items[: self.capacity]
        except Exception as exc:
            raise ProjectWorkspaceError(str(exc)) from exc
        return tuple(self._items)

    def add(self, path):
        value = str(Path(path).expanduser().resolve())
        self._items = [value] + [x for x in self._items if x != value]
        self._items = self._items[: self.capacity]
        self.save()
        return tuple(self._items)

    def remove_missing(self):
        self._items = [x for x in self._items if Path(x).exists()]
        self.save()
        return tuple(self._items)

    def save(self):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "asteria.editor.recent_projects",
            "version": 1,
            "projects": self._items,
        }
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    @property
    def items(self):
        return tuple(self._items)


class ProjectWorkspaceController:
    """Headless-testable project lifecycle behind the Qt editor shell.

    This owns editor workflow only. Project data remains the canonical Project,
    and play mode always receives an isolated runtime snapshot.
    """

    def __init__(self, document=None, *, recent_store=None):
        self.document = document or EditorDocument()
        self.recent_store = recent_store or RecentProjectStore()
        self.play_session: PlaySession | None = None

    def new_project(self, name, path, *, startup_scene_name="Main"):
        if not str(name).strip():
            raise ProjectWorkspaceError("project name is required")
        target = Path(path).expanduser().resolve()
        project = Project(str(name).strip())
        scene = Scene(str(startup_scene_name).strip() or "Main")
        project.add_scene(scene)
        self.document.set_project(project, file_path=target)
        save_document(self.document, target)
        self.recent_store.add(target)
        return project

    def open_project(self, path):
        if self.play_session is not None and self.play_session.active:
            raise ProjectWorkspaceError("stop play mode before opening another project")
        try:
            project = load_document(self.document, path)
        except Exception as exc:
            raise ProjectWorkspaceError(str(exc)) from exc
        self.recent_store.add(self.document.file_path)
        return project

    def save(self):
        try:
            path = save_document(self.document)
        except Exception as exc:
            raise ProjectWorkspaceError(str(exc)) from exc
        self.recent_store.add(path)
        return path

    def save_as(self, path):
        try:
            target = save_document(self.document, path)
        except Exception as exc:
            raise ProjectWorkspaceError(str(exc)) from exc
        self.recent_store.add(target)
        return target

    def validate_project(self):
        if self.document.project is None:
            return ("No project is open",)
        try:
            self.document.project.validate()
        except Exception as exc:
            return (str(exc),)
        return ()

    def run(self):
        if self.play_session is not None and self.play_session.active:
            raise ProjectWorkspaceError("project is already running")
        errors = self.validate_project()
        if errors:
            raise ProjectWorkspaceError(errors[0])
        self.play_session = create_play_session(self.document)
        return self.play_session

    def stop(self):
        if self.play_session is not None:
            self.play_session.stop()
        self.play_session = None

    def state(self):
        p = self.document.project
        errors = self.validate_project()
        return ProjectWorkspaceState(
            p.name if p else None,
            str(self.document.file_path) if self.document.file_path else None,
            self.document.dirty,
            p is not None and not errors,
            self.play_session is not None and self.play_session.active,
            len(p.scenes()) if p else 0,
            p.startup_scene_id if p else None,
            self.recent_store.items,
        )
