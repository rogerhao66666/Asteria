"""Live AssetStore reconciliation with atomic registry publication and diff events."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from .store import AssetStore, AssetStoreReport
from .registry import AssetRegistry
from .canonical import CanonicalAsset


@dataclass(frozen=True, slots=True)
class AssetChange:
    operation: str
    asset_id: str
    kind: str
    old: CanonicalAsset | None = None
    new: CanonicalAsset | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    changes: tuple[AssetChange, ...] = ()
    store_report: AssetStoreReport | None = None

    @property
    def ok(self):
        return self.store_report is not None and self.store_report.ok


class LiveAssetReconciler:
    def __init__(self, store_factory, registry: AssetRegistry):
        self.store_factory = store_factory
        self.registry = registry

    def reconcile(self, assets_root):
        # Load into an isolated registry so live state is untouched on parse/decode/validation failure.
        temp = AssetRegistry()
        store = self.store_factory(temp)
        rep = store.load(assets_root)
        if not rep.ok:
            return ReconciliationReport((), rep)
        old = {a.asset_id: a for a in self.registry.snapshot()}
        new = {a.asset_id: a for a in temp.snapshot()}
        changes = []
        for aid in sorted(old.keys() - new.keys()):
            a = old[aid]
            changes.append(AssetChange("removed", aid, a.kind, a, None))
        for aid in sorted(new.keys() - old.keys()):
            a = new[aid]
            changes.append(AssetChange("added", aid, a.kind, None, a))
        for aid in sorted(old.keys() & new.keys()):
            if old[aid] != new[aid]:
                changes.append(AssetChange("changed", aid, new[aid].kind, old[aid], new[aid]))
        # Commit only after complete successful isolated load/diff.
        for c in changes:
            if c.operation == "removed":
                self.registry.remove(c.asset_id)
            elif c.operation == "added":
                self.registry.register(c.new)
            else:
                self.registry.register(c.new, replace=True)
        return ReconciliationReport(tuple(changes), rep)
