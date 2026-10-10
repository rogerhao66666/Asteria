"""Common canonical asset contracts shared by all Asteria asset families."""

from dataclasses import dataclass, field
from typing import Any, Mapping
import re

ID = re.compile(r"^[A-Za-z0-9_.:/-]+$")


@dataclass(frozen=True, slots=True)
class AssetSource:
    uri: str
    provider: str = "project"
    provenance: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class AssetRef:
    asset_id: str

    def __post_init__(self):
        if not self.asset_id or not ID.match(self.asset_id):
            raise ValueError("invalid asset id")


@dataclass(frozen=True, slots=True)
class CanonicalAsset:
    asset_id: str
    kind: str
    source: AssetSource
    version: int = 1
    tags: frozenset[str] = frozenset()
    metadata: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self):
        AssetRef(self.asset_id)
        if not self.kind:
            raise ValueError("kind")
        if self.version < 1:
            raise ValueError("version")

    def meta(self):
        return dict(self.metadata)


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"
    path: str = ""


@dataclass(frozen=True, slots=True)
class ValidationReport:
    asset_id: str
    issues: tuple[ValidationIssue, ...] = ()

    @property
    def ok(self):
        return not any(x.severity == "error" for x in self.issues)


class AssetValidator:
    def validate(self, a: CanonicalAsset):
        issues = []
        if not a.source.uri:
            issues.append(ValidationIssue("source.missing", "source URI is required"))
        if len(set(k for k, _ in a.metadata)) != len(a.metadata):
            issues.append(ValidationIssue("metadata.duplicate", "metadata keys must be unique"))
        return ValidationReport(a.asset_id, tuple(issues))
