import hashlib
from dataclasses import dataclass

from .cache import canonical_settings
from .fingerprint import fast_unchanged, fingerprint_file


@dataclass(frozen=True, slots=True)
class ImportStatus:
    needs_import: bool
    reason: str
    fingerprint: object


def settings_hash(settings):
    return hashlib.sha256(canonical_settings(settings).encode("utf-8")).hexdigest()


def detect_import_status(source_file, asset_record, previous_artifact):
    if previous_artifact is None:
        fp = fingerprint_file(source_file)
        return ImportStatus(True, "missing_artifact", fp)

    expected_settings_hash = settings_hash(asset_record.import_settings or {})
    if previous_artifact.importer != asset_record.importer:
        fp = fingerprint_file(source_file)
        return ImportStatus(True, "importer_changed", fp)
    if previous_artifact.importer_version != asset_record.importer_version:
        fp = fingerprint_file(source_file)
        return ImportStatus(True, "importer_version_changed", fp)
    if previous_artifact.settings_hash != expected_settings_hash:
        fp = fingerprint_file(source_file)
        return ImportStatus(True, "settings_changed", fp)

    if fast_unchanged(source_file, previous_artifact.fingerprint):
        return ImportStatus(False, "unchanged_fast_path", previous_artifact.fingerprint)

    fp = fingerprint_file(source_file)
    if fp.content_hash == previous_artifact.fingerprint.content_hash:
        return ImportStatus(False, "metadata_only_change", fp)
    return ImportStatus(True, "source_changed", fp)
