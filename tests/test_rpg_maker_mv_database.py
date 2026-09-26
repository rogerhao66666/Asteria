import json
from pathlib import Path

import pytest

from asteria.assets.local_reference import (
    RPGMakerMVProjectLayout,
    discover_mv_projects,
    resolve_rpg_maker_mv_root,
)
from asteria.assets.rpg_maker_mv_database import RPGMakerMVDatabase


def _real_layout():
    repo = Path(__file__).resolve().parents[1]
    root = resolve_rpg_maker_mv_root(repo)
    assert root is not None
    return discover_mv_projects(root)[0]


def _write(path: Path, name: str, value) -> None:
    (path / name).write_text(json.dumps(value), encoding="utf-8")


def _fixture_layout(tmp_path, *, invalid=None, missing=()):
    root = tmp_path / "project"
    data = root / "data"
    data.mkdir(parents=True)
    records = {
        "Actors.json": [None, {"id": 1, "name": "Hero", "classId": 99,
            "characterName": "Actor1", "characterIndex": 0,
            "faceName": "Actor1", "faceIndex": 0, "battlerName": "Actor1_1",
            "extraField": {"preserved": True}}],
        "Classes.json": [None],
        "Skills.json": [None, {"id": 1, "name": "Hit", "iconIndex": 2}],
        "Items.json": [None, {"id": 1, "name": "Potion", "iconIndex": 3}],
        "Weapons.json": [None, {"id": 1, "name": "Sword", "iconIndex": 4}],
        "Armors.json": [None, {"id": 1, "name": "Coat", "iconIndex": 5}],
        "Tilesets.json": [None, {"id": 1, "name": "Outside"}],
        "System.json": {"gameTitle": "Fixture", "startMapId": 1,
            "startX": 2, "startY": 3, "partyMembers": [1]},
    }
    for name, value in records.items():
        if name not in missing:
            _write(data, name, value)
    if invalid:
        (data / invalid).write_text("not json", encoding="utf-8")
    return RPGMakerMVProjectLayout(tmp_path, root, "project", data, None, None, None, None)


def test_real_new_data_record_counts_and_ids():
    database = RPGMakerMVDatabase.load(_real_layout())

    assert tuple(map(len, (database.actors, database.classes, database.skills,
                           database.items, database.weapons, database.armors))) == (4, 4, 10, 4, 4, 4)
    assert database.actors[0].id == 1
    assert database.skills[0].id == 1
    assert database.items[0].id == 1


def test_real_actor_skill_item_and_system_fields_are_typed():
    database = RPGMakerMVDatabase.load(_real_layout())
    actor = database.actors[0]

    assert (actor.character_name, actor.character_index) == ("Actor1", 0)
    assert (actor.face_name, actor.face_index) == ("Actor1", 0)
    assert actor.battler_name == "Actor1_1"
    assert database.skills[0].icon_index == 76
    assert database.items[0].icon_index == 176
    assert (database.system.start_map_id, database.system.start_x,
            database.system.start_y) == (1, 8, 6)
    assert database.tilesets[0].id == 1


def test_null_index_is_skipped_and_unknown_fields_are_preserved(tmp_path):
    database = RPGMakerMVDatabase.load(_fixture_layout(tmp_path))

    assert [actor.id for actor in database.actors] == [1]
    assert dict(database.actors[0].metadata)["extraField"] == (("preserved", True),)
    assert any(issue.code == "actor.unknown_class" for issue in database.issues)


def test_missing_database_file_is_reported_without_losing_other_records(tmp_path):
    database = RPGMakerMVDatabase.load(
        _fixture_layout(tmp_path, missing=("Armors.json",))
    )

    assert database.items[0].name == "Potion"
    assert database.armors == ()
    assert any(issue.source == "Armors.json" and issue.code == "missing_file"
               for issue in database.issues)


def test_invalid_json_names_the_source_file(tmp_path):
    layout = _fixture_layout(tmp_path, invalid="Skills.json")

    with pytest.raises(ValueError, match="Skills.json"):
        RPGMakerMVDatabase.load(layout)
