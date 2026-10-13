"""Transactional ownership for resources created while staging a runtime scene."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .project_load import ProjectLoadReport
from .runtime_scene import RuntimeMaterializationIssue, RuntimeSceneTarget
from .scene_binding import RuntimeBindingRegistry

Dispose = Callable[[], None]


@dataclass(slots=True)
class StagedRuntimeObject:
    value: Any
    dispose: Dispose | None = None
    _released: bool = False

    def release(self):
        if self._released:
            return
        self._released = True
        if self.dispose:
            self.dispose()


@dataclass(frozen=True, slots=True)
class ResourceMaterializationReport:
    objects: tuple[Any, ...]
    issues: tuple[RuntimeMaterializationIssue, ...]
    committed: bool = False
    cleanup_issues: tuple[RuntimeMaterializationIssue, ...] = ()

    @property
    def ok(self):
        return self.committed and not self.issues


def staged(value, dispose=None):
    return StagedRuntimeObject(value, dispose)


class ResourceAwareMaterializer:
    def __init__(self, binders: RuntimeBindingRegistry, target: RuntimeSceneTarget):
        self.binders = binders
        self.target = target

    def _cleanup(self, items):
        issues = []
        for item in reversed(items):
            try:
                item.release()
            except Exception as e:
                issues.append(RuntimeMaterializationIssue("", "runtime.cleanup.failed", str(e)))
        return tuple(issues)

    def materialize(self, project: ProjectLoadReport, runtime_context: Any = None):
        if not project.ok or not project.activated:
            return ResourceMaterializationReport(
                (),
                (
                    RuntimeMaterializationIssue(
                        "",
                        "runtime.project.not_activatable",
                        "project load report is not activatable",
                    ),
                ),
                False,
            )
        owned = []
        issues = []
        for resolved in project.resolved:
            try:
                out = self.binders.bind(resolved, runtime_context)
                owned.append(
                    out if isinstance(out, StagedRuntimeObject) else StagedRuntimeObject(out)
                )
            except Exception as e:
                issues.append(
                    RuntimeMaterializationIssue(
                        resolved.binding.object_id, "runtime.binding.failed", str(e)
                    )
                )
                return ResourceMaterializationReport(
                    (), tuple(issues), False, self._cleanup(owned)
                )
        values = tuple(x.value for x in owned)
        try:
            self.target.commit_objects(values)
        except Exception as e:
            issues.append(RuntimeMaterializationIssue("", "runtime.commit.failed", str(e)))
            try:
                self.target.remove_objects(values)
            except Exception:
                pass
            return ResourceMaterializationReport((), tuple(issues), False, self._cleanup(owned))
        # Ownership transfers to runtime target on successful commit. Do not dispose.
        return ResourceMaterializationReport(values, (), True, ())
