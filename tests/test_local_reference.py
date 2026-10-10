import hashlib
from pathlib import Path

from asteria.assets.local_reference import (
    build_rpg_maker_mv_source_inventory,
    compare_inventories,
    inventory_tree,
    resolve_rpg_maker_mv_root,
)


def _write(root: Path, relative: str, payload: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def test_local_reference_prefers_repo_copy(tmp_path):
    repo = tmp_path / "repo"
    local = repo / "local_reference" / "rpg_maker_mv"
    steam = tmp_path / "steam"
    for root in (local, steam):
        (root / "NewData").mkdir(parents=True)
        (root / "dlc").mkdir()

    assert resolve_rpg_maker_mv_root(repo, steam) == local.resolve()


def test_inventory_is_deterministic(tmp_path):
    _write(tmp_path, "NewData/data/Actors.json", b"actors")
    _write(tmp_path, "dlc/Zeta/readme.txt", b"z")
    _write(tmp_path, "dlc/Alpha/icon.png", b"png")

    first = inventory_tree(tmp_path)
    second = inventory_tree(tmp_path)

    assert first == second
    assert tuple(item.relative_path for item in first.files) == (
        "NewData/data/Actors.json",
        "dlc/Alpha/icon.png",
        "dlc/Zeta/readme.txt",
    )
    assert first.file_count == 3
    assert first.total_bytes == 10
    assert first.files[0].sha256 == hashlib.sha256(b"actors").hexdigest()


def test_partial_copy_is_reported(tmp_path):
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    _write(source, "NewData/data/Actors.json", b"actors")
    _write(source, "dlc/sample.txt", b"complete")
    _write(destination, "NewData/data/Actors.json", b"wrong")
    _write(destination, "orphan.txt", b"allowed")

    mismatches = compare_inventories(inventory_tree(source), inventory_tree(destination))

    assert tuple((item.relative_path, item.reason) for item in mismatches) == (
        ("NewData/data/Actors.json", "content_mismatch"),
        ("dlc/sample.txt", "missing"),
    )


def test_reference_root_is_git_ignored():
    repo = Path(__file__).resolve().parents[1]
    patterns = (repo / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "/local_reference/rpg_maker_mv/" in patterns


def test_source_inventory_reads_core_generator_new_data_and_dlc(tmp_path):
    _write(tmp_path, "RPG Maker MV.app/Contents/MacOS/NewData/data/Actors.json", b"a")
    _write(tmp_path, "RPG Maker MV.app/Contents/MacOS/Generator/TV/Male/TV_Body_p01.png", b"g")
    _write(tmp_path, "RPG Maker MV.app/Contents/Resources/unrelated.bin", b"ignore")
    _write(tmp_path, "dlc/sample/readme.txt", b"d")

    inventory = build_rpg_maker_mv_source_inventory(tmp_path)

    assert tuple(item.relative_path for item in inventory.files) == (
        "Generator/TV/Male/TV_Body_p01.png",
        "NewData/data/Actors.json",
        "dlc/sample/readme.txt",
    )
