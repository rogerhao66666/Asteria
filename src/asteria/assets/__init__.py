from .cache import ImportArtifact, ImportCache, artifact_key
from .fingerprint import SourceFingerprint, fingerprint_file
from .importers import AssetImporter, ImportRequest, TextureImporter
from .pipeline import ImportPipeline
from .registry import AssetRegistry, AssetEvent
from .resources import *
from .serialization import deserialize_asset_registry, serialize_asset_registry
from .types import VALID_KINDS, AssetRecord, AssetRef, normalize_asset_path

# New canonical asset system. Keep legacy AssetRef above as package-level compatibility API;
# canonical modules use asteria.assets.canonical.AssetRef internally.
from .canonical import CanonicalAsset, AssetSource, ValidationIssue, ValidationReport
from .monster import *
from .tileset import *
from .prop import *
from .icon import *
from .portrait import *
from .vfx import *
from .package import *
from .codecs import *
from .builtin_codecs import *
from .complex_codecs import *
from .store import *
from .browser import *
from .browser_workspace import *
from .scene_placement import *
from .scene_binding import *
from .project_load import *
from .runtime_scene import *
from .runtime_resources import *
from .runtime_adapters import *
from .runtime_adapter_registry import *
from .backend_capabilities import *
from .backend_preflight import *
from .preflight_materialization import *
from .package_installer import *
from .import_transaction import *
from .reconciliation import *
from .editor_import_service import *
from .quality_gate import *
from .rpg_maker_mv_database import *
from .rpg_maker_mv_catalog import *
from .rpg_maker_mv_generator import *
