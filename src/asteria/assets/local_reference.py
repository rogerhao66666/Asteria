from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocalReferenceLayout:
    repo_root: Path
    root: Path
    new_data: Path
    dlc: Path

    @classmethod
    def from_root(cls, repo_root: Path, root: Path) -> "LocalReferenceLayout":
        resolved_repo = Path(repo_root).resolve()
        resolved_root = Path(root).resolve()
        return cls(
            resolved_repo,
            resolved_root,
            resolved_root / "NewData",
            resolved_root / "dlc",
        )


@dataclass(frozen=True, slots=True)
class RPGMakerMVProjectLayout:
    reference_root: Path
    root: Path
    relative_path: str
    data: Path
    img: Path | None
    audio: Path | None
    fonts: Path | None
    js: Path | None


@dataclass(frozen=True, slots=True)
class ReferenceFile:
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ReferenceInventory:
    root: str
    files: tuple[ReferenceFile, ...]

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.files)

    def to_data(self) -> dict:
        return {
            "schema": "asteria.local_reference.inventory",
            "version": 1,
            "root": self.root,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "files": [asdict(item) for item in self.files],
        }


@dataclass(frozen=True, slots=True)
class ReferenceMismatch:
    relative_path: str
    reason: str


def _valid_reference_root(root: Path) -> bool:
    return (root / "NewData").is_dir() and (root / "dlc").is_dir()


def resolve_rpg_maker_mv_root(
    repo_root: Path, steam_root: Path | None = None
) -> Path | None:
    local = Path(repo_root).resolve() / "local_reference" / "rpg_maker_mv"
    if _valid_reference_root(local):
        return local
    if steam_root is not None:
        steam = Path(steam_root).expanduser().resolve()
        if _valid_reference_root(steam):
            return steam
    return None


def discover_mv_projects(root: Path) -> tuple[RPGMakerMVProjectLayout, ...]:
    reference_root = Path(root).expanduser().resolve()
    candidates = []
    main = reference_root / "NewData" / "data" / "System.json"
    if main.is_file():
        candidates.append(main)
    dlc = reference_root / "dlc"
    if dlc.is_dir():
        candidates.extend(sorted(dlc.glob("**/data/System.json")))

    projects = []
    for system_path in candidates:
        try:
            system = json.loads(system_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(system, dict):
            continue
        project_root = system_path.parent.parent.resolve()

        def optional(name: str) -> Path | None:
            path = project_root / name
            return path if path.is_dir() else None

        projects.append(
            RPGMakerMVProjectLayout(
                reference_root=reference_root,
                root=project_root,
                relative_path=project_root.relative_to(reference_root).as_posix(),
                data=system_path.parent.resolve(),
                img=optional("img"),
                audio=optional("audio"),
                fonts=optional("fonts"),
                js=optional("js"),
            )
        )
    return tuple(sorted(projects, key=lambda item: (item.relative_path != "NewData", item.relative_path)))


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inventory_tree(root: Path) -> ReferenceInventory:
    resolved = Path(root).expanduser().resolve()
    files = tuple(
        ReferenceFile(
            path.relative_to(resolved).as_posix(),
            path.stat().st_size,
            _hash_file(path),
        )
        for path in sorted(item for item in resolved.rglob("*") if item.is_file())
    )
    return ReferenceInventory(str(resolved), files)


def build_rpg_maker_mv_source_inventory(source_root: Path) -> ReferenceInventory:
    source_root = Path(source_root).expanduser().resolve()
    generator = inventory_tree(
        source_root / "RPG Maker MV.app" / "Contents" / "MacOS" / "Generator"
    )
    new_data = inventory_tree(
        source_root / "RPG Maker MV.app" / "Contents" / "MacOS" / "NewData"
    )
    dlc = inventory_tree(source_root / "dlc")
    files = tuple(sorted(
        (
            *(ReferenceFile(f"Generator/{item.relative_path}", item.size, item.sha256) for item in generator.files),
            *(ReferenceFile(f"NewData/{item.relative_path}", item.size, item.sha256) for item in new_data.files),
            *(ReferenceFile(f"dlc/{item.relative_path}", item.size, item.sha256) for item in dlc.files),
        ),
        key=lambda item: item.relative_path,
    ))
    return ReferenceInventory("rpg_maker_mv", files)


def compare_inventories(
    source: ReferenceInventory, destination: ReferenceInventory
) -> tuple[ReferenceMismatch, ...]:
    actual = {item.relative_path: item for item in destination.files}
    result = []
    for expected in source.files:
        found = actual.get(expected.relative_path)
        if found is None:
            result.append(ReferenceMismatch(expected.relative_path, "missing"))
        elif found.size != expected.size or found.sha256 != expected.sha256:
            result.append(ReferenceMismatch(expected.relative_path, "content_mismatch"))
    return tuple(result)


def synchronize_tree(source: Path, destination: Path) -> int:
    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    copied = 0
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        relative = path.relative_to(source)
        target = destination / relative
        source_stat = path.stat()
        if target.is_file():
            target_stat = target.stat()
            if (
                target_stat.st_size == source_stat.st_size
                and target_stat.st_mtime_ns == source_stat.st_mtime_ns
            ):
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def write_inventory(inventory: ReferenceInventory, output: Path) -> None:
    output = Path(output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(inventory.to_data(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
