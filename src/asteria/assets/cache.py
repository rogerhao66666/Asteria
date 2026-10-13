import hashlib
import json
from dataclasses import dataclass
from pathlib import PurePosixPath

from asteria.core.ids import validate_id

from .fingerprint import SourceFingerprint


def canonical_settings(settings):
    if not isinstance(settings, dict):
        raise TypeError("import settings must be a dict")
    return json.dumps(settings, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def artifact_key(*, asset_id, source_hash, importer, importer_version, settings):
    validate_id(asset_id)
    payload = {
        "asset_id": asset_id,
        "source_hash": str(source_hash),
        "importer": str(importer),
        "importer_version": int(importer_version),
        "settings": json.loads(canonical_settings(settings)),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class ImportArtifact:
    asset_id: str
    key: str
    relative_path: str
    fingerprint: SourceFingerprint
    importer: str
    importer_version: int
    settings_hash: str

    def __post_init__(self):
        validate_id(self.asset_id)
        p = PurePosixPath(self.relative_path)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("artifact path must be cache-relative")
        if len(self.key) != 64:
            raise ValueError("artifact key must be sha256 hex")

    def to_data(self):
        return {
            "asset_id": self.asset_id,
            "key": self.key,
            "relative_path": self.relative_path,
            "fingerprint": self.fingerprint.to_data(),
            "importer": self.importer,
            "importer_version": self.importer_version,
            "settings_hash": self.settings_hash,
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "asset_id",
            "key",
            "relative_path",
            "fingerprint",
            "importer",
            "importer_version",
            "settings_hash",
        }
        if set(data) != expected:
            raise ValueError("invalid import artifact record")
        return cls(
            asset_id=data["asset_id"],
            key=data["key"],
            relative_path=data["relative_path"],
            fingerprint=SourceFingerprint.from_data(data["fingerprint"]),
            importer=data["importer"],
            importer_version=int(data["importer_version"]),
            settings_hash=data["settings_hash"],
        )


class ImportCache:
    def __init__(self):
        self._by_asset = {}

    def put(self, artifact):
        self._by_asset[artifact.asset_id] = artifact
        return artifact

    def get(self, asset_id):
        return self._by_asset.get(asset_id)

    def remove(self, asset_id):
        return self._by_asset.pop(asset_id, None)

    def records(self):
        return tuple(self._by_asset.values())
