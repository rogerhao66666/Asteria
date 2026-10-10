import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.runtime_rpg_ui_authoring import RuntimeRpgUiAuthoringController
from asteria.editor.runtime_rpg_ui_workspace import RuntimeRpgUiWorkspaceModel
from asteria.presentation import (
    AbilityScreenProfile,
    CharacterScreenProfile,
    EquipmentScreenProfile,
    InventoryScreenProfile,
    PartyScreenProfile,
    ProgressionScreenProfile,
)
from asteria.project import Project


def make():
    p = Project("Game")
    p.add_scene(Scene("Main"))
    d = EditorDocument(p)
    return p, d, RuntimeRpgUiAuthoringController(d)


def profiles():
    return {
        "rpg_character_screen": CharacterScreenProfile(
            section_order=("overview", "resources", "equipment", "abilities", "progression", "status"),
            resource_labels={"vitality": "HP", "technique": "SP"},
        ),
        "rpg_equipment_screen": EquipmentScreenProfile(page_size=12),
        "rpg_ability_screen": AbilityScreenProfile(
            ability_categories={"slash": "combat", "heal": "support"}, visible_limits={"combat": 8}
        ),
        "rpg_progression_screen": ProgressionScreenProfile(
            graph_labels={"blade": "Blade Mastery"}, visible_limits={"blade": 12}
        ),
        "rpg_inventory_screen": InventoryScreenProfile(
            item_groups={"potion": "consumables"}, visible_limits={"consumables": 20}
        ),
        "rpg_party_screen": PartyScreenProfile(group_order=("active", "reserve"), visible_limits={"reserve": 8}),
    }


def test_all_runtime_rpg_screen_profiles_are_project_owned():
    p, d, c = make()
    for cat, val in profiles().items():
        c.create(cat, "default", val)
    for cat in profiles():
        assert c.library.ids(cat) == ("default",)
    assert d.commands.can_undo


def test_runtime_rpg_ui_roundtrips_with_project_v7():
    p, d, c = make()
    for cat, val in profiles().items():
        c.create(cat, "default", val)
    raw = p.to_data()
    clone = Project.from_data(raw, d.component_registry)
    assert clone.to_data() == raw
    assert (
        clone.battle_presentation_library.require("rpg_character_screen", "default").resource_label("vitality") == "HP"
    )


def test_runtime_ui_edit_and_undo():
    _, d, c = make()
    c.create("rpg_equipment_screen", "default", EquipmentScreenProfile(page_size=10))
    c.edit("rpg_equipment_screen", "default", EquipmentScreenProfile(page_size=18))
    assert c.library.require("rpg_equipment_screen", "default").page_size == 18
    assert d.undo()
    assert c.library.require("rpg_equipment_screen", "default").page_size == 10


def test_runtime_ui_delete_and_duplicate():
    _, _, c = make()
    c.create("rpg_party_screen", "default", PartyScreenProfile())
    c.duplicate("rpg_party_screen", "default", "large_party")
    assert c.library.ids("rpg_party_screen") == ("default", "large_party")
    c.delete("rpg_party_screen", "large_party")
    assert c.library.ids("rpg_party_screen") == ("default",)


def test_non_runtime_category_is_rejected():
    _, _, c = make()
    with pytest.raises(KeyError):
        c.create("hud", "x", CharacterScreenProfile())


def test_information_architecture_does_not_dump_all_runtime_systems():
    _, _, c = make()
    ia = c.information_architecture
    assert ia.primary_navigation == "runtime_ui_section_sidebar"
    assert ia.secondary_navigation == "screen_profile_tabs"
    assert ia.live_preview_expected and ia.progressive_disclosure
    assert not ia.show_all_screens_simultaneously
    assert not ia.show_all_details_simultaneously
    assert ia.section("build").categories == ("rpg_equipment_screen", "rpg_ability_screen", "rpg_progression_screen")


def test_workspace_build_section_uses_tabs_not_one_giant_page():
    _, _, c = make()
    c.create("rpg_equipment_screen", "equip", EquipmentScreenProfile())
    c.create("rpg_ability_screen", "skills", AbilityScreenProfile())
    w = RuntimeRpgUiWorkspaceModel(c)
    w.set_section("build")
    assert w.snapshot().category == "rpg_equipment_screen"
    assert w.snapshot().visible_ids == ("equip",)
    w.set_category("rpg_ability_screen")
    assert w.snapshot().visible_ids == ("skills",)


def test_workspace_contextual_focus_and_preview_density():
    _, _, c = make()
    c.create("rpg_character_screen", "default", CharacterScreenProfile())
    w = RuntimeRpgUiWorkspaceModel(c)
    w.select("default")
    w.focus_child("section:equipment")
    w.set_preview_mode("compact")
    s = w.snapshot()
    assert s.focused_child_id == "section:equipment"
    assert s.preview_mode == "compact"
    with pytest.raises(ValueError):
        w.set_preview_mode("show_everything")


def test_search_filters_current_profile_category_only():
    _, _, c = make()
    c.create("rpg_party_screen", "standard", PartyScreenProfile())
    c.create("rpg_party_screen", "large_party", PartyScreenProfile())
    w = RuntimeRpgUiWorkspaceModel(c)
    w.set_section("party")
    w.set_query("large")
    assert w.visible_ids() == ("large_party",)


def test_validation_runs_through_canonical_project():
    p, _, c = make()
    c.create("rpg_inventory_screen", "default", InventoryScreenProfile())
    assert c.validate() == () and p.validate()
