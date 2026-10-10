"""Transactional runtime scene materialization from a valid ProjectLoadReport."""

from dataclasses import dataclass
from typing import Any, Protocol

from .project_load import ProjectLoadReport
from .scene_binding import RuntimeBindingRegistry


class RuntimeSceneTarget(Protocol):
    def commit_objects(self, objects: tuple[Any, ...]) -> None: ...
    def remove_objects(self, objects: tuple[Any, ...]) -> None: ...


@dataclass(frozen=True, slots=True)
class RuntimeMaterializationIssue:
    object_id: str
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class RuntimeMaterializationReport:
    objects: tuple[Any, ...]
    issues: tuple[RuntimeMaterializationIssue, ...]
    committed: bool = False

    @property
    def ok(self):
        return not self.issues and self.committed


class RuntimeSceneMaterializer:
    def __init__(self, binders: RuntimeBindingRegistry, target: RuntimeSceneTarget):
        self.binders = binders
        self.target = target

    def materialize(self, project: ProjectLoadReport, runtime_context: Any = None):
        if not project.ok or not project.activated:
            return RuntimeMaterializationReport(
                (),
                (
                    RuntimeMaterializationIssue(
                        "", "runtime.project.not_activatable", "project load report is not activatable"
                    ),
                ),
                False,
            )
        staged = []
        issues = []
        for resolved in project.resolved:
            try:
                staged.append(self.binders.bind(resolved, runtime_context))
            except Exception as e:
                issues.append(RuntimeMaterializationIssue(resolved.binding.object_id, "runtime.binding.failed", str(e)))
                break
        if issues:
            # Staged values have never been exposed to target; optional disposable objects are cleaned
            # by target only after commit, so there is nothing scene-visible to rollback here.
            return RuntimeMaterializationReport((), tuple(issues), False)
        batch = tuple(staged)
        try:
            self.target.commit_objects(batch)
        except Exception as e:
            # Target contract requires commit to be atomic; defensive rollback hook handles targets
            # that allocated externally before raising.
            try:
                self.target.remove_objects(batch)
            except Exception:
                pass
            return RuntimeMaterializationReport(
                (), (RuntimeMaterializationIssue("", "runtime.commit.failed", str(e)),), False
            )
        return RuntimeMaterializationReport(batch, (), True)


class RecordingRuntimeScene:
    def __init__(self, fail_commit=False):
        self.objects = []
        self.fail_commit = fail_commit

    def commit_objects(self, objects):
        if self.fail_commit:
            raise RuntimeError("commit rejected")
        self.objects.extend(objects)

    def remove_objects(self, objects):
        ids = {id(x) for x in objects}
        self.objects[:] = [x for x in self.objects if id(x) not in ids]
