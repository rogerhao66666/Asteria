from pathlib import PurePosixPath

from .cache import ImportArtifact, artifact_key
from .change_detection import detect_import_status, settings_hash


class ImportPipeline:
    def __init__(self, cache):
        self.cache = cache

    def plan(self, *, source_file, asset_record):
        previous = self.cache.get(asset_record.id)
        return detect_import_status(source_file, asset_record, previous)

    def commit(self, *, asset_record, fingerprint, artifact_extension=".bin"):
        key = artifact_key(
            asset_id=asset_record.id,
            source_hash=fingerprint.content_hash,
            importer=asset_record.importer,
            importer_version=asset_record.importer_version,
            settings=asset_record.import_settings or {},
        )
        ext = (
            artifact_extension if artifact_extension.startswith(".") else "." + artifact_extension
        )
        relative_path = str(PurePosixPath(key[:2]) / f"{key}{ext}")
        artifact = ImportArtifact(
            asset_id=asset_record.id,
            key=key,
            relative_path=relative_path,
            fingerprint=fingerprint,
            importer=asset_record.importer,
            importer_version=asset_record.importer_version,
            settings_hash=settings_hash(asset_record.import_settings or {}),
        )
        self.cache.put(artifact)
        return artifact
