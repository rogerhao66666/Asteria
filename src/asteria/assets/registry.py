from dataclasses import dataclass
from .canonical import AssetRef as CanonicalAssetRef


@dataclass(frozen=True, slots=True)
class AssetEvent:
    operation: str
    asset_id: str
    kind: str


class AssetRegistry:
    """Compatibility registry supporting both legacy AssetRecord and canonical assets."""

    def __init__(self):
        self._by_id = {}
        self._by_path = {}
        self._assets = {}
        self._events = []

    # Legacy project-asset API
    def add(self, record):
        record.validate()
        if record.id in self._by_id:
            raise ValueError("duplicate asset id")
        if record.source_path in self._by_path:
            raise ValueError("duplicate source path")
        self._by_id[record.id] = record
        self._by_path[record.source_path] = record.id
        return record

    def get(self, asset_id):
        return self._by_id.get(asset_id)

    def records(self):
        return tuple(self._by_id.values())

    def validate(self):
        for record in self._by_id.values():
            record.validate()

    # Canonical asset-system API
    def register(self, asset, replace=False):
        if asset.asset_id in self._assets and not replace:
            raise KeyError(asset.asset_id)
        self._assets[asset.asset_id] = asset
        self._events.append(AssetEvent("replace" if replace else "register", asset.asset_id, asset.kind))
        return CanonicalAssetRef(asset.asset_id)

    def resolve(self, ref):
        key = ref.asset_id if hasattr(ref, "asset_id") else ref
        return self._assets[key]

    def remove(self, ref):
        asset = self.resolve(ref)
        del self._assets[asset.asset_id]
        self._events.append(AssetEvent("remove", asset.asset_id, asset.kind))
        return asset

    def query(self, kind=None, tags=()):
        wanted = set(tags)
        return tuple(a for a in self._assets.values() if (kind is None or a.kind == kind) and wanted.issubset(a.tags))

    def snapshot(self):
        return tuple(self._assets.values())

    @property
    def events(self):
        return tuple(self._events)
