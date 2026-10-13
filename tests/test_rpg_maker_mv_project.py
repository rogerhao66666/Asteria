from pathlib import Path

import pytest

from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_project import RPGMakerMVProjectImporter
from asteria.project import Project
from asteria.runtime.preview import build_preview_registry

pytestmark = pytest.mark.mv_reference


def _import(map_ids=(1,)):
    repo = Path(__file__).resolve().parents[1]
    layout = discover_mv_projects(resolve_rpg_maker_mv_root(repo))[0]
    return RPGMakerMVProjectImporter.import_project(layout, map_ids=map_ids)


def test_real_mv_records_convert_to_asteria_project():
    result = _import()
    project = result.project

    assert len(project.rpg_database.actors) == 4
    assert len(project.rpg_database.classes) == 4
    assert len(project.gameplay_library.abilities.ids()) == 10
    assert len(project.rpg_database.items) == 4
    assert len(project.rpg_database.equipment) == 8
    assert (
        len([a for a in project.assets.snapshot() if a.kind != "icon"]) == 498
    )  # images; plus menu icons (AST-07)
    assert len(project.scenes()) == 1
    assert result.source_ids["actors"][1] == "mv.actor.1"
    assert result.source_ids["skills"][1] == "mv.skill.1"
    assert result.source_ids["maps"][1] == project.scenes()[0].id


def test_imported_project_serializes_reloads_and_validates():
    result = _import()
    encoded = result.project.to_data()
    restored = Project.from_data(encoded, build_preview_registry())

    assert restored.validate()
    assert len(restored.rpg_database.actors) == 4
    assert len([a for a in restored.assets.snapshot() if a.kind != "icon"]) == 498
    assert len(restored.scenes()) == 1


def test_icons_and_unsupported_mv_semantics_are_retained_as_metadata_and_issues():
    result = _import(map_ids=())
    skill = result.source_metadata["skills"][1]
    item = result.source_metadata["items"][1]

    assert skill["icon_index"] == 76
    assert skill["icon_box"] == (384, 128, 416, 160)
    assert item["icon_index"] == 176
    assert "damage" in skill["mv_metadata"]
    assert any(issue.code == "skill.unsupported_semantics" for issue in result.issues)


def test_imported_weapon_keeps_mv_type_for_attack_visuals():
    result = _import(map_ids=())
    sword = result.project.rpg_database.equipment["mv.weapon.1"]

    assert "mv-weapon-type:sword" in sword.tags
    assert result.source_metadata["equipment"][1]["weapon_type"] == "Sword"
