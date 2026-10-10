"""Atomic filesystem installation of asset packages into a project's Assets directory."""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import os, shutil, tempfile, uuid


@dataclass(frozen=True, slots=True)
class InstallIssue:
    code: str
    message: str
    path: str = ""


@dataclass(frozen=True, slots=True)
class InstallReport:
    installed: tuple[str, ...] = ()
    issues: tuple[InstallIssue, ...] = ()
    replaced: tuple[str, ...] = ()

    @property
    def ok(self):
        return not self.issues


def _safe_rel(raw: str) -> Path:
    p = Path(raw)
    if p.is_absolute() or not p.parts or any(x in ("..", "") for x in p.parts):
        raise ValueError(f"unsafe package path: {raw}")
    return p


class AssetPackageInstaller:
    def __init__(self, assets_root):
        self.assets_root = Path(assets_root)

    def install(self, source_root, files: Iterable[str], *, destination="", collision="error"):
        source = Path(source_root)
        try:
            dest = _safe_rel(destination) if destination else Path()
            rels = tuple(_safe_rel(x) for x in files)
        except ValueError as e:
            return InstallReport(issues=(InstallIssue("install.unsafe_path", str(e)),))
        if len(set(rels)) != len(rels):
            return InstallReport(issues=(InstallIssue("install.duplicate_path", "duplicate package path"),))
        if collision not in ("error", "replace"):
            return InstallReport(issues=(InstallIssue("install.bad_collision_policy", collision),))
        missing = [str(x) for x in rels if not (source / x).is_file()]
        if missing:
            return InstallReport(
                issues=tuple(InstallIssue("install.source_missing", "source file missing", x) for x in missing)
            )
        target_root = self.assets_root / dest
        collisions = [x for x in rels if (target_root / x).exists()]
        if collisions and collision == "error":
            return InstallReport(
                issues=tuple(InstallIssue("install.collision", "destination exists", str(dest / x)) for x in collisions)
            )
        self.assets_root.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".asteria-install-", dir=self.assets_root))
        backup = Path(tempfile.mkdtemp(prefix=".asteria-backup-", dir=self.assets_root))
        written = []
        replaced = []
        try:
            for rel in rels:
                out = stage / rel
                out.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / rel, out)
            target_root.mkdir(parents=True, exist_ok=True)
            for rel in rels:
                dst = target_root / rel
                if dst.exists():
                    b = backup / rel
                    b.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(dst, b)
                    replaced.append(rel)
                dst.parent.mkdir(parents=True, exist_ok=True)
                os.replace(stage / rel, dst)
                written.append(rel)
            return InstallReport(tuple(str(dest / x) for x in rels), (), tuple(str(dest / x) for x in replaced))
        except Exception as e:
            for rel in reversed(written):
                dst = target_root / rel
                try:
                    if dst.exists():
                        dst.unlink()
                except Exception:
                    pass
            for rel in replaced:
                b = backup / rel
                dst = target_root / rel
                try:
                    if b.exists():
                        dst.parent.mkdir(parents=True, exist_ok=True)
                        os.replace(b, dst)
                except Exception:
                    pass
            return InstallReport(issues=(InstallIssue("install.failed", str(e)),))
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            shutil.rmtree(backup, ignore_errors=True)

    def install_tree(self, source_root, *, destination="", collision="error"):
        source = Path(source_root)
        files = tuple(str(p.relative_to(source)) for p in sorted(source.rglob("*")) if p.is_file())
        return self.install(source, files, destination=destination, collision=collision)
