"""Atomic project asset + saved-scene load orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
import json
from .store import AssetStore, AssetStoreIssue
from .scene_binding import SceneAssetBinding, binding_from_dict, SceneAssetResolver, ResolvedSceneAsset


@dataclass(frozen=True, slots=True)
class ProjectLoadIssue:
    path: str
    code: str
    message: str
    severity: str = "error"


@dataclass(frozen=True, slots=True)
class ProjectLoadReport:
    assets: tuple[Any, ...]
    bindings: tuple[SceneAssetBinding, ...]
    resolved: tuple[ResolvedSceneAsset, ...]
    issues: tuple[ProjectLoadIssue, ...]
    activated: bool = False

    @property
    def ok(self):
        return not any(x.severity == "error" for x in self.issues)


class ProjectLoader:
    def __init__(self, asset_store: AssetStore):
        self.asset_store = asset_store

    def _scene_documents(self, paths: Iterable[str | Path]):
        bindings = []
        issues = []
        for p0 in sorted(map(Path, paths), key=lambda p: str(p)):
            try:
                data = json.loads(p0.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                issues.append(ProjectLoadIssue(str(p0), "scene.document.invalid_json", str(e)))
                continue
            if not isinstance(data, Mapping):
                issues.append(
                    ProjectLoadIssue(str(p0), "scene.document.not_object", "scene document must be an object")
                )
                continue
            raw = data.get("asset_bindings", [])
            if not isinstance(raw, list):
                issues.append(ProjectLoadIssue(str(p0), "scene.bindings.not_list", "asset_bindings must be a list"))
                continue
            for i, item in enumerate(raw):
                try:
                    bindings.append(binding_from_dict(item))
                except (TypeError, ValueError) as e:
                    issues.append(ProjectLoadIssue(str(p0), f"scene.binding.invalid[{i}]", str(e)))
        return tuple(bindings), issues

    def load(self, asset_root, scene_paths=()):
        # AssetStore itself is atomic on failure.
        ar = self.asset_store.load(asset_root)
        issues = [ProjectLoadIssue(x.path, x.code, x.message, x.severity) for x in ar.issues]
        if not ar.ok:
            return ProjectLoadReport((), (), (), tuple(issues), False)
        bindings, sissues = self._scene_documents(scene_paths)
        issues.extend(sissues)
        resolved = []
        if not any(x.severity == "error" for x in issues):
            resolver = SceneAssetResolver(self.asset_store.registry)
            for b in bindings:
                try:
                    resolved.append(resolver.resolve(b))
                except KeyError as e:
                    issues.append(ProjectLoadIssue(b.object_id, "scene.asset.unresolved", str(e)))
                except ValueError as e:
                    issues.append(ProjectLoadIssue(b.object_id, "scene.asset.kind_mismatch", str(e)))
        ok = not any(x.severity == "error" for x in issues)
        # Activation is represented only by a fully valid report; actual runtime activation stays external.
        return ProjectLoadReport(tuple(ar.loaded), bindings, tuple(resolved) if ok else (), tuple(issues), ok)
