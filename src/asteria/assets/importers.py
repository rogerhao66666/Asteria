from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from .types import AssetRecord, normalize_asset_path


@dataclass(frozen=True, slots=True)
class ImportRequest:
    source_path: str
    kind: str
    settings: dict


class AssetImporter:
    name = "raw"
    version = 1

    def supports(self, kind, path):
        return True

    def inspect(self, request):
        return {}

    def create_record(self, request):
        src = normalize_asset_path(request.source_path)
        if not self.supports(request.kind, src):
            raise ValueError("unsupported import")
        return AssetRecord.create(
            kind=request.kind,
            source_path=src,
            importer=self.name,
            importer_version=self.version,
            import_settings=request.settings,
            metadata=self.inspect(request),
        )


class TextureImporter(AssetImporter):
    name = "texture"
    version = 1
    EXT: ClassVar[set[str]] = {".png", ".jpg", ".jpeg", ".webp"}

    def supports(self, kind, path):
        return (
            kind in {"texture", "sprite_sheet", "tileset"}
            and PurePosixPath(path).suffix.lower() in self.EXT
        )

    def inspect(self, request):
        return {"extension": PurePosixPath(request.source_path).suffix.lower()}
