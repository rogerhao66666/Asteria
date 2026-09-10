from dataclasses import dataclass
from pathlib import PurePosixPath

from asteria.core.ids import new_id, validate_id

VALID_KINDS = frozenset(
    {
        "texture",
        "sprite_sheet",
        "tileset",
        "tilemap",
        "animation",
        "audio",
        "font",
        "shader",
        "data",
    }
)


def normalize_asset_path(path):
    if not isinstance(path, str) or not path:
        raise ValueError("non-empty path required")
    p = PurePosixPath(path.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts:
        raise ValueError("asset path must stay inside project")
    normalized = str(p)
    if normalized in ("", "."):
        raise ValueError("invalid asset path")
    return normalized


@dataclass(frozen=True, slots=True)
class AssetRef:
    asset_id: str
    expected_kind: str | None = None

    def __post_init__(self):
        validate_id(self.asset_id)
        if self.expected_kind is not None and self.expected_kind not in VALID_KINDS:
            raise ValueError("unknown expected asset kind")


@dataclass(slots=True)
class AssetRecord:
    id: str
    kind: str
    source_path: str
    name: str
    importer: str
    importer_version: int = 1
    import_settings: dict | None = None
    metadata: dict | None = None

    @classmethod
    def create(
        cls,
        *,
        kind,
        source_path,
        name=None,
        importer="raw",
        importer_version=1,
        import_settings=None,
        metadata=None,
    ):
        if kind not in VALID_KINDS:
            raise ValueError("unknown asset kind")
        src = normalize_asset_path(source_path)
        return cls(
            new_id(),
            kind,
            src,
            name or PurePosixPath(src).stem,
            importer,
            importer_version,
            dict(import_settings or {}),
            dict(metadata or {}),
        )

    def validate(self):
        validate_id(self.id)
        if self.kind not in VALID_KINDS:
            raise ValueError("unknown asset kind")
        self.source_path = normalize_asset_path(self.source_path)
        if not self.name or not self.importer:
            raise ValueError("name/importer required")
        if self.importer_version < 1:
            raise ValueError("importer version must be >= 1")
        if self.import_settings is None:
            self.import_settings = {}
        if self.metadata is None:
            self.metadata = {}
        if not isinstance(self.import_settings, dict) or not isinstance(
            self.metadata, dict
        ):
            raise TypeError("settings/metadata must be dict")
