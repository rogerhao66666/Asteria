"""Common .asset.json manifest -> validation -> registry intake."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from .canonical import AssetSource, CanonicalAsset, ValidationIssue, ValidationReport
from .registry import AssetRegistry


@dataclass(frozen=True, slots=True)
class AssetManifest:
    schema_version: int
    asset_id: str
    kind: str
    source: str
    tags: tuple[str, ...] = ()
    metadata: tuple[tuple[str, Any], ...] = ()
    dependencies: tuple[str, ...] = ()

    def __post_init__(self):
        if self.schema_version < 1:
            raise ValueError("schema_version")
        if not self.asset_id or not self.kind or not self.source:
            raise ValueError("required manifest field")
        p = PurePosixPath(self.source)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("source must be project-relative")

    def canonical(self):
        return CanonicalAsset(
            self.asset_id,
            self.kind,
            AssetSource(self.source),
            self.schema_version,
            frozenset(self.tags),
            self.metadata,
        )


def manifest_from_dict(d: Mapping[str, Any]):
    return AssetManifest(
        int(d.get("schema_version", 1)),
        d["asset_id"],
        d["kind"],
        d["source"],
        tuple(d.get("tags", ())),
        tuple(sorted(d.get("metadata", {}).items())),
        tuple(d.get("dependencies", ())),
    )


@dataclass(frozen=True, slots=True)
class IntakeResult:
    manifest: AssetManifest
    report: ValidationReport
    registered: bool = False


class AssetIntake:
    def __init__(
        self,
        registry: AssetRegistry,
        validators: Mapping[str, Callable[[CanonicalAsset], ValidationReport]] | None = None,
    ):
        self.registry = registry
        self.validators = dict(validators or {})

    def inspect(self, m: AssetManifest):
        a = m.canonical()
        issues = []
        validator = self.validators.get(m.kind)
        if validator:
            report = validator(a)
            issues.extend(report.issues)
        for dep in m.dependencies:
            try:
                self.registry.resolve(dep)
            except KeyError:
                issues.append(ValidationIssue("asset.dependency.missing", dep))
        return ValidationReport(m.asset_id, tuple(issues))

    def ingest(self, m: AssetManifest, replace=False):
        report = self.inspect(m)
        if not report.ok:
            return IntakeResult(m, report, False)
        self.registry.register(m.canonical(), replace=replace)
        return IntakeResult(m, report, True)


def discover_asset_manifests(paths):
    return tuple(sorted(str(p) for p in paths if str(p).endswith(".asset.json")))
