"""D95: a stat's "Where It Comes From" card lists, step by step in the order the game adds
them up, the page to open and every record there with its number."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture(scope="module")
def project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def test_the_card_names_every_record_and_its_page(project):
    from asteria.editor.stat_usage import stat_usage

    text = stat_usage(project, "str")
    assert "1. Starting value of the actor</b> &nbsp;(Database ▸ Actors ▸ Base Stats)" in text
    assert "Roger 21" in text and "Spirit Rider 19" in text
    assert "Database ▸ Classes / Jobs ▸ Growth per level" in text and "Brave +1.8" in text
    assert "Zealot +1.2" in text  # every job, none hidden behind "and N more"
    assert "Attributes ▸ STR: +1 a rank, up to 30 ranks" in text
    assert "Titan Cleaver +10" in text and "Lion Charm +15" in text
    assert "ATK +2 for each point of STR" in text


def test_a_passive_counts_only_when_it_changes_the_stat(project):
    """D91 counted every passive whose data held the letters "str" (Destruction Mastery)."""
    from asteria.editor.stat_usage import stat_usage

    assert "Passives" not in stat_usage(project, "str")
    evade = stat_usage(project, "evade")
    assert "Database ▸ Passives ▸ Stat changes" in evade and "Oath of the Wanderer +20" in evade


def test_a_derived_stat_is_worked_out_last_and_enemies_use_their_own(project):
    from asteria.editor.stat_usage import stat_usage

    text = stat_usage(project, "evade")
    assert text.index("Learned passives") < text.index("Its stat formula, worked out last")
    assert "Enemies use their own number" in text and "Vaelor 3" in text


def test_a_resource_card_names_the_resource_and_its_maximum(project):
    """The HP card read "Where Materials comes from" (a menu page's name took the stat's) and
    "Nothing sets it yet" (the resource fields were not looked at)."""
    from asteria.editor.stat_usage import stat_usage

    text = stat_usage(project, "vitality")
    assert "Where HP comes from" in text and "What HP changes" in text
    assert "Materials" not in text and "Nothing sets it yet" not in text
    where = "(Database ▸ Actors ▸ HP, MP and other resources)"
    assert f"1. Starting maximum of the actor</b> &nbsp;{where}" in text
    assert "Roger 3200" in text
    assert "Database ▸ Classes / Jobs ▸ Resource bonuses" in text and "Brave +800" in text
    assert "Resource growth per level" in text and "Guardian +150" in text
    assert "Attributes ▸ HP: +100 a rank, up to 50 ranks" in text
    assert "Attributes ▸ MP: +30 a rank" in stat_usage(project, "technique")


def test_every_stat_card_is_headed_by_its_own_name(project):
    from asteria.editor.stat_usage import _name, stat_usage

    for stat_id in project.rpg_database.stat_definitions:
        name = _name(project.rpg_database, stat_id)
        assert f"Where {name} comes from" in stat_usage(project, stat_id).replace("&#x27;", "'")
