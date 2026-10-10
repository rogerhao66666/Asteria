"""Materialize exactly the requests approved by whole-scene backend preflight."""

from dataclasses import dataclass
from typing import Any, Callable
from .backend_preflight import BackendPreflightReport, PreflightEntry
from .runtime_resources import StagedRuntimeObject
from .runtime_adapter_registry import RuntimeResource
from .runtime_scene import RuntimeSceneTarget, RuntimeMaterializationIssue
from .runtime_resources import staged


@dataclass(frozen=True, slots=True)
class PreflightMaterializationReport:
    objects: tuple[Any, ...]
    issues: tuple[RuntimeMaterializationIssue, ...]
    committed: bool = False
    cleanup_issues: tuple[RuntimeMaterializationIssue, ...] = ()

    @property
    def ok(self):
        return self.committed and not self.issues


class PreflightMaterializer:
    def __init__(self, target: RuntimeSceneTarget, resource_factory: Callable[[Any, Any], Any]):
        self.target = target
        self.resource_factory = resource_factory

    def _cleanup(self, owned):
        out = []
        for x in reversed(owned):
            try:
                x.release()
            except Exception as e:
                out.append(RuntimeMaterializationIssue("", "runtime.cleanup.failed", str(e)))
        return tuple(out)

    def materialize(self, preflight: BackendPreflightReport, runtime_context=None):
        if not preflight.ok:
            return PreflightMaterializationReport(
                (),
                (RuntimeMaterializationIssue("", "runtime.preflight.failed", "backend preflight contains errors"),),
                False,
            )
        owned = []
        for entry in preflight.entries:
            try:
                made = self.resource_factory(entry.request, runtime_context)
                if isinstance(made, StagedRuntimeObject):
                    x = made
                elif isinstance(made, RuntimeResource):
                    x = staged(made.value, made.dispose)
                else:
                    x = staged(made)
                owned.append(x)
            except Exception as e:
                return PreflightMaterializationReport(
                    (),
                    (RuntimeMaterializationIssue(entry.resolved.binding.object_id, "runtime.resource.failed", str(e)),),
                    False,
                    self._cleanup(owned),
                )
        values = tuple(x.value for x in owned)
        try:
            self.target.commit_objects(values)
        except Exception as e:
            try:
                self.target.remove_objects(values)
            except Exception:
                pass
            return PreflightMaterializationReport(
                (), (RuntimeMaterializationIssue("", "runtime.commit.failed", str(e)),), False, self._cleanup(owned)
            )
        return PreflightMaterializationReport(values, (), True)
