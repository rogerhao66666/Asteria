"""D95, D108: a stat's Usage card says in a summary what adds up to it and what it changes,
then lists, step by step in the order the game adds them up, each kind of source with how many
records, the range of their numbers and every record by name, with where it opens."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture(scope="module")
def project():
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    return Project.load_json(DEMO / "project.asteria.json", default_component_registry())


def _rows(usage):
    return {row.what: row for section in usage.sections for row in section.rows}


def test_the_card_names_every_record_and_its_page(project):
    from asteria.editor.rpg.stat_usage import stat_usage

    usage = stat_usage(project, "str")
    text = usage.text()
    assert usage.summary == (  # D108: two sentences; the numbers are in the rows
        "Strength comes from the starting value, level ups, skill trees, gear and attachments.",
        "It changes Critical Damage %, Physical Defence and Physical Attack.",
    )
    start = _rows(usage)["Starting value of each actor"]
    assert start.page == "Database ▸ Actors ▸ Base Stats"
    assert (start.count(), start.span()) == ("5 actors", "12 – 32")
    assert start.opens() == ("record", "rpg", "actors", "hero_01")
    assert "Roger 32" in text and "Spirit Rider 30" in text
    assert "Brave +1.8" in text and "Zealot +1.2" in text  # every job, none hidden
    assert "Attributes ▸ STR +1 a rank, 30 ranks" in text
    assert "Titan Cleaver +10" in text and "Lion Charm +15" in text
    changes = _rows(usage)["Physical Attack +2 for each point of Strength"]
    assert changes.opens() == ("game_system", "derived_stats", "power")


def test_a_passive_counts_only_when_it_changes_the_stat(project):
    """D91 counted every passive whose data held the letters "str" (Destruction Mastery)."""
    from asteria.editor.rpg.stat_usage import stat_usage

    assert "Learned passives" not in stat_usage(project, "str").text()
    evade = stat_usage(project, "evade").text()
    assert "Database ▸ Passives ▸ Stat changes" in evade and "Oath of the Wanderer +20" in evade


def test_a_derived_stat_is_worked_out_last_and_enemies_use_their_own(project):
    from asteria.editor.rpg.stat_usage import stat_usage

    usage = stat_usage(project, "evade")
    steps = [row.what for row in usage.sections[0].rows]
    assert steps[-1].startswith("Then its stat formula adds")
    assert steps.index("Learned passives") < len(steps) - 1
    enemies = _rows(usage)["Each enemy's own number"]
    assert "Vaelor 3" in enemies.text() and enemies.noun == "enemy"


def test_a_resource_card_names_the_resource_and_its_maximum(project):
    """The HP card read "Where Materials comes from" (a menu page's name took the stat's) and
    "Nothing sets it yet" (the resource fields were not looked at); D99: it says damage and
    healing change what is left of it."""
    from asteria.editor.rpg.stat_usage import stat_usage

    usage = stat_usage(project, "vitality")
    text = usage.text()
    assert "Where HP comes from" in text and "What HP changes" in text
    assert "Materials" not in text and "Nothing sets it yet" not in text
    first = usage.sections[0].rows[0]
    assert first.what == "Starting maximum of each actor"
    assert first.page == "Database ▸ Actors ▸ HP, MP and other resources"
    assert "Roger 3200" in text and "Brave +800" in text and "Guardian +150" in text
    assert "Attributes ▸ HP +100 a rank, 50 ranks" in text
    assert "Damage and healing change what is left of it" in text
    assert usage.summary[1] == "Damage and healing change what is left of it."
    assert "Attributes ▸ MP +30 a rank" in stat_usage(project, "technique").text()


def test_a_job_that_adds_nothing_is_left_out(project):
    from asteria.editor.rpg.stat_usage import stat_usage

    growth = _rows(stat_usage(project, "vitality"))["Added to the maximum on every level up"]
    assert all(link.amount for link in growth.links) and growth.span() == "+70 – +160"


def test_every_stat_card_is_headed_by_its_own_name(project):
    from asteria.editor.rpg.stat_usage import _full_name, stat_usage

    for stat_id in project.rpg_database.stat_definitions:
        name = _full_name(project.rpg_database, stat_id)
        assert f"Where {name} comes from" in stat_usage(project, stat_id).text()


def test_every_row_opens_a_page_the_window_knows(project):
    """Each row's button and each record opens through ``navigate_to_problem``: a record of
    the database, a battle rule or a Game Systems record."""
    from asteria.editor.rpg.stat_usage import stat_usage

    kinds = set()
    for stat_id in ("str", "speed", "power", "vitality", "crit"):
        for row in _rows(stat_usage(project, stat_id)).values():
            kinds.update(link.target[0] for link in row.links)
            if row.opens():
                kinds.add(row.opens()[0])
    assert kinds <= {"record", "game_system", "combat"}
    assert {"record", "game_system"} <= kinds


def test_the_card_speaks_chinese(project):
    from asteria.editor.rpg.stat_usage import stat_usage
    from asteria.editor.ui import i18n

    before = i18n.CURRENT["language"]
    i18n.CURRENT["language"] = "zh_TW"
    i18n._shown.clear()
    try:
        text = stat_usage(project, "vitality").text()
    finally:
        i18n.CURRENT["language"] = before
        i18n._shown.clear()
    assert "HP 來自起始值、職業、升級和技能樹。" in text
    assert "HP 從哪裡來（依此順序相加）" in text
    assert "每個角色的起始上限 · 5 個角色 · 2000 – 3200" in text
    assert "每階 +100，共 50 階" in text and "傷害與治療改變剩下的量" in text
