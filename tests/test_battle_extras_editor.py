"""The battle extras of an ability (divine boost costs, hits of several damage types, boost gains,
commands, states)
are authored in the Database editor: optional fields are shown, list entries and dict fields can
be added and
removed from the record tree, and Apply stores them (one undo step)."""

import pytest


def test_hits_costs_and_states_are_added_in_the_record_tree_and_applied():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from test_octopath_style_battle import _project

    from asteria.editor import EditorDocument
    from asteria.editor.authoring_hub_widget import AdapterFamilyWidget
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    QApplication.instance() or QApplication([])
    project = _project()
    document = EditorDocument(project)
    family = AdapterFamilyWidget(
        "Database", IntegratedAuthoringControllers(document).rpg_categories(), document=document
    )
    family.category.setCurrentIndex(family.category.findData("abilities"))
    family.select_ids(["oct_sword"])
    tree = family.editor
    record = tree.record()
    assert (
        record["hits"] == [] and record["battle_costs"] == {} and record["apply_states"] == []
    )  # discoverable
    tree.add_entry(("hits",))
    tree.add_entry(("hits",))
    data = tree.record()
    data["hits"][1]["tags"] = ["damage.fire"]
    data["hits"][1]["power"] = 0.5
    tree.set_record(data)
    tree.add_field(("battle_costs",), "momentum", 3.0)
    tree.add_entry(("apply_states",))
    data = tree.record()
    data["apply_states"][0]["state"] = "broken"
    tree.set_record(data)
    family.apply_selected()
    ability = project.gameplay_library.abilities.get("oct_sword")
    assert ability.hits == ({"tags": [], "power": 1.0}, {"tags": ["damage.fire"], "power": 0.5})
    assert ability.battle_costs == {"momentum": 3.0}
    assert ability.apply_states == ({"state": "broken", "to": "targets", "remove": False},)
    tree.remove_entry(("hits", 0))
    family.apply_selected()
    assert len(project.gameplay_library.abilities.get("oct_sword").hits) == 1
    document.undo()
    assert len(project.gameplay_library.abilities.get("oct_sword").hits) == 2
