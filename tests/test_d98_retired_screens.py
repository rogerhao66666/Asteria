"""D98: the six screen records behind the old "Menu Records" tab are retired.

What the game read of them moves on load: the stats' names and order to the Stats, the
slots' names to the Equipment Slots. The rest was never drawn and is dropped; the library
no longer knows the categories, and the shipped projects hold none.
"""

from __future__ import annotations

import json
from pathlib import Path

from asteria.presentation.library import BattlePresentationLibrary
from asteria.presentation.retired_screens import RETIRED_CATEGORIES, move_retired
from asteria.rpg.actors import RpgDatabase
from asteria.rpg.items import EquipmentSlotDefinition
from asteria.rpg.stat_definitions import SET_ON, StatDefinition

ROOT = Path(__file__).resolve().parents[1]


def _old_library(character, equipment=None):
    categories = {k: {} for k in BattlePresentationLibrary.CATEGORIES}
    categories["rpg_character_screen"] = {"default": character}
    categories["rpg_party_screen"] = {"default": {"group_order": ["active"]}}
    if equipment is not None:
        categories["rpg_equipment_screen"] = {"default": equipment}
    return {
        "schema": BattlePresentationLibrary.SCHEMA,
        "version": BattlePresentationLibrary.VERSION,
        "categories": categories,
    }


def test_an_old_library_loads_and_keeps_its_screen_records_aside():
    library = BattlePresentationLibrary.from_data(_old_library({"stat_labels": {"str": "Might"}}))
    assert not set(RETIRED_CATEGORIES) & set(library.categories())
    assert library.retired["rpg_character_screen"]["default"]["stat_labels"] == {"str": "Might"}
    assert not set(RETIRED_CATEGORIES) & set(library.to_data()["categories"])


def test_names_and_order_move_to_the_stats_without_overwriting_them():
    db = RpgDatabase()
    db.add_stat_definition(StatDefinition("str", "Strength", order=0, set_on=("actors",)))
    db.add_stat_definition(StatDefinition("dex", order=1))  # no name of its own
    retired = {
        "rpg_character_screen": {
            "default": {
                "stat_labels": {"str": "Might", "dex": "Dexterity", "spd": "Speed"},
                "resource_labels": [["hp", "HP"]],
                "stat_order": ["spd"],
            }
        }
    }
    changed = move_retired(retired, db)
    stats = db.stat_definitions
    assert stats["str"].display_name == "Strength"  # its own name stays
    assert stats["dex"].display_name == "Dexterity"
    assert (stats["spd"].display_name, stats["spd"].order) == ("Speed", 2)
    assert (stats["hp"].display_name, stats["hp"].order) == ("HP", 3)
    assert stats["spd"].set_on == ()  # the project's Base Stats lists are its own
    assert set(changed) == {"dex", "spd", "hp"}


def test_a_project_without_stats_still_offers_the_moved_ones_everywhere():
    db = RpgDatabase()
    move_retired({"rpg_character_screen": {"a": {"stat_labels": {"str": "Might"}}}}, db)
    assert db.stat_definitions["str"].set_on == SET_ON


def test_slot_names_move_to_defined_slots_only():
    db = RpgDatabase()
    db.add_equipment_slot(EquipmentSlotDefinition("head"))
    retired = {
        "rpg_character_screen": {"default": {"slot_labels": {"head": "Helm"}}},
        "rpg_equipment_screen": {"default": {"slot_labels": {"ring": "Ring"}}},
    }
    move_retired(retired, db)
    assert db.equipment_slots["head"].display_name == "Helm"
    assert "ring" not in db.equipment_slots  # a new slot would change what it holds


def test_a_project_file_moves_its_names_on_load():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    source = ROOT / "src/asteria/templates/party_rpg/project.asteria.json"
    data = json.loads(source.read_text(encoding="utf-8"))
    data["battle_presentation_library"] = _old_library({"stat_labels": {"luck": "Fortune"}})
    project = Project.from_data(data, EditorDocument().component_registry)
    assert project.rpg_database.stat_definitions["luck"].display_name == "Fortune"
    assert project.battle_presentation_library.retired == {}


def test_the_shipped_projects_hold_no_retired_records():
    files = [
        *ROOT.glob("reference_projects/*/project.asteria.json"),
        *ROOT.glob("src/asteria/templates/*/project.asteria.json"),
    ]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not any(f'"{k}"' in text for k in RETIRED_CATEGORIES), path
