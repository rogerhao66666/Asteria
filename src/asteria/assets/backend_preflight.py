"""Whole-scene backend capability preflight before resource allocation."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .backend_capabilities import BackendCapabilities, CapabilityIssue, CapabilityValidatorRegistry
from .runtime_adapter_registry import RuntimeAdapterRegistry
from .scene_binding import ResolvedSceneAsset


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    object_id: str
    asset_id: str
    component_type: str
    code: str
    message: str
    field: str = ""
    required: Any = None
    supported: Any = None
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class PreflightEntry:
    resolved: ResolvedSceneAsset
    request: Any
    fallback_applied: bool = False


@dataclass(frozen=True, slots=True)
class BackendPreflightReport:
    entries: tuple[PreflightEntry, ...]
    issues: tuple[PreflightIssue, ...]

    @property
    def ok(self):
        return not any(x.severity == "error" for x in self.issues)

    @property
    def error_count(self):
        return sum(x.severity == "error" for x in self.issues)


FallbackSelector = Callable[
    [ResolvedSceneAsset, Any, BackendCapabilities, tuple[CapabilityIssue, ...]], Any
]


class BackendPreflight:
    def __init__(
        self,
        adapters: RuntimeAdapterRegistry,
        validators: CapabilityValidatorRegistry,
        caps: BackendCapabilities,
    ):
        self.adapters = adapters
        self.validators = validators
        self.caps = caps

    def run(self, resolved_assets, *, fallback_selector: FallbackSelector | None = None):
        entries = []
        issues = []
        for resolved in resolved_assets:
            b = resolved.binding
            aid = b.asset_ref.asset_id
            try:
                request = self.adapters.adapt(resolved.canonical)
            except Exception as e:
                issues.append(
                    PreflightIssue(
                        b.object_id, aid, b.component_type, "backend.adapter.failed", str(e)
                    )
                )
                continue
            fallback = None
            if fallback_selector is not None:

                def fallback(req, caps, iss, r=resolved):
                    return fallback_selector(r, req, caps, iss)

            try:
                result = self.validators.validate(request, self.caps, fallback=fallback)
            except Exception as e:
                issues.append(
                    PreflightIssue(
                        b.object_id, aid, b.component_type, "backend.preflight.failed", str(e)
                    )
                )
                continue
            entries.append(PreflightEntry(resolved, result.request, result.fallback_applied))
            for x in result.issues:
                issues.append(
                    PreflightIssue(
                        b.object_id,
                        aid,
                        b.component_type,
                        x.code,
                        x.message,
                        x.field,
                        x.required,
                        x.supported,
                        x.severity,
                    )
                )
        return BackendPreflightReport(tuple(entries), tuple(issues))
