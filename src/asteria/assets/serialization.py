from .cache import ImportArtifact, ImportCache
from .registry import AssetRegistry
from .types import AssetRecord


def serialize_asset(record):
    record.validate()
    return {
        "id": record.id,
        "kind": record.kind,
        "source_path": record.source_path,
        "name": record.name,
        "importer": record.importer,
        "importer_version": record.importer_version,
        "import_settings": record.import_settings,
        "metadata": record.metadata,
    }


def deserialize_asset(data):
    expected = {
        "id",
        "kind",
        "source_path",
        "name",
        "importer",
        "importer_version",
        "import_settings",
        "metadata",
    }
    if set(data) != expected:
        raise ValueError("invalid asset record")
    r = AssetRecord(**data)
    r.validate()
    return r


def serialize_asset_registry(registry):
    registry.validate()
    return {
        "schema": "asteria.assets",
        "version": 1,
        "assets": [serialize_asset(r) for r in registry.records()],
    }


def deserialize_asset_registry(data):
    if set(data) != {"schema", "version", "assets"}:
        raise ValueError("invalid assets document")
    if data["schema"] != "asteria.assets" or data["version"] != 1:
        raise ValueError("unsupported asset registry")
    reg = AssetRegistry()
    for d in data["assets"]:
        reg.add(deserialize_asset(d))
    return reg


def serialize_import_cache(cache):
    return {
        "schema": "asteria.import-cache",
        "version": 1,
        "artifacts": [a.to_data() for a in cache.records()],
    }


def deserialize_import_cache(data):
    if set(data) != {"schema", "version", "artifacts"}:
        raise ValueError("invalid import cache")
    if data["schema"] != "asteria.import-cache" or data["version"] != 1:
        raise ValueError("unsupported import cache")
    cache = ImportCache()
    for d in data["artifacts"]:
        cache.put(ImportArtifact.from_data(d))
    return cache
