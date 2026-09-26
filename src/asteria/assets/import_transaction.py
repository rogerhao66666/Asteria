"""Semantic asset-package import transaction: validate staged package before publication."""
from dataclasses import dataclass
from pathlib import Path
import shutil,tempfile
from .package_installer import AssetPackageInstaller,InstallIssue
from .store import AssetStore,AssetStoreIssue

@dataclass(frozen=True,slots=True)
class ImportTransactionIssue:
 code:str;message:str;path:str="";severity:str="error"

@dataclass(frozen=True,slots=True)
class ImportTransactionReport:
 installed:tuple[str,...]=();loaded_asset_ids:tuple[str,...]=()
 issues:tuple[ImportTransactionIssue,...]=();replaced:tuple[str,...]=()
 @property
 def ok(self):return not any(x.severity=="error" for x in self.issues)

class SemanticAssetImporter:
 def __init__(self,assets_root,store_factory):
  self.assets_root=Path(assets_root);self.store_factory=store_factory
 def import_tree(self,source_root,*,destination="",collision="error"):
  source=Path(source_root)
  parent=self.assets_root.parent;parent.mkdir(parents=True,exist_ok=True)
  stage=Path(tempfile.mkdtemp(prefix=".asteria-semantic-stage-",dir=parent))
  try:
   # Stage exact source tree outside live Assets/.
   staged_pkg=stage/"package";shutil.copytree(source,staged_pkg)
   store=self.store_factory()
   rep=store.load(staged_pkg)
   issues=tuple(ImportTransactionIssue(x.code,x.message,x.path,x.severity) for x in rep.issues)
   if not rep.ok:return ImportTransactionReport(issues=issues)
   # Semantic PASS; only now publish through Batch64 filesystem transaction.
   inst=AssetPackageInstaller(self.assets_root).install_tree(staged_pkg,destination=destination,collision=collision)
   if not inst.ok:
    return ImportTransactionReport(issues=tuple(ImportTransactionIssue(x.code,x.message,x.path) for x in inst.issues))
   return ImportTransactionReport(inst.installed,tuple(x.manifest.asset_id for x in rep.loaded),issues,inst.replaced)
  except Exception as e:
   return ImportTransactionReport(issues=(ImportTransactionIssue("asset.import.failed",str(e)),))
  finally:shutil.rmtree(stage,ignore_errors=True)
