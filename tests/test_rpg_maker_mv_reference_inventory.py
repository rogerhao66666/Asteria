import json
from pathlib import Path

from asteria.assets.local_reference import (
    discover_mv_projects,
    resolve_rpg_maker_mv_root,
)


def _project(root: Path, relative: str, *, optional=True) -> Path:
    project = root / relative
    data = project / "data"
    data.mkdir(parents=True)
    (data / "System.json").write_text(json.dumps({"gameTitle": relative}))
    if optional:
        for name in ("img", "audio", "fonts", "js"):
            (project / name).mkdir()
    return project


def test_discovery_prefers_repository_local_reference(tmp_path):
    repo = tmp_path / "repo"
    local = repo / "local_reference" / "rpg_maker_mv"
    steam = tmp_path / "steam"
    for root in (local, steam):
        _project(root, "NewData")
        (root / "dlc").mkdir()

    resolved = resolve_rpg_maker_mv_root(repo, steam)
    projects = discover_mv_projects(resolved)

    assert resolved == local.resolve()
    assert tuple(project.root.name for project in projects) == ("NewData",)


def test_discovers_all_valid_projects_deterministically(tmp_path):
    _project(tmp_path, "NewData")
    _project(tmp_path, "dlc/Zeta/Sample")
    _project(tmp_path, "dlc/Alpha/Demo")

    projects = discover_mv_projects(tmp_path)

    assert tuple(project.relative_path for project in projects) == (
        "NewData",
        "dlc/Alpha/Demo",
        "dlc/Zeta/Sample",
    )


def test_missing_optional_directories_are_none(tmp_path):
    project = _project(tmp_path, "NewData", optional=False)

    (layout,) = discover_mv_projects(tmp_path)

    assert layout.root == project.resolve()
    assert layout.data == project.resolve() / "data"
    assert layout.img is None
    assert layout.audio is None
    assert layout.fonts is None
    assert layout.js is None


def test_malformed_dlc_directory_does_not_hide_valid_siblings(tmp_path):
    _project(tmp_path, "NewData")
    _project(tmp_path, "dlc/Good/Sample")
    bad = tmp_path / "dlc" / "Bad" / "Sample" / "data"
    bad.mkdir(parents=True)
    (bad / "System.json").write_text("not json")

    projects = discover_mv_projects(tmp_path)

    assert tuple(project.relative_path for project in projects) == (
        "NewData",
        "dlc/Good/Sample",
    )


def test_real_local_reference_discovers_main_and_dlc_projects():
    repo = Path(__file__).resolve().parents[1]
    root = resolve_rpg_maker_mv_root(repo)
    assert root is not None

    projects = discover_mv_projects(root)

    assert len(projects) == 11
    assert projects[0].relative_path == "NewData"
    assert all(project.data.joinpath("System.json").is_file() for project in projects)
