import pytest

from asteria.core import Scene
from asteria.editor import EditorDocument
from asteria.editor.rpg_item_equipment_authoring import (
    RpgItemEquipmentAuthoringController,
    RpgItemEquipmentAuthoringError,
)
from asteria.editor.rpg_item_equipment_workspace import (
    RpgItemEquipmentWorkspaceModel,
)
from asteria.gameplay import AbilityDefinition
from asteria.project import Project
from asteria.rpg import (
    AttachmentDefinition,
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionRuntime,
    CompositionSelection,
    EquipmentDefinition,
    EquipmentGrowthDefinition,
    EquipmentGrowthNodeDefinition,
    EquipmentGrowthReward,
    Inventory,
    ItemDefinition,
    SocketDefinition,
)


def make():
    p = Project("Game")
    p.add_scene(Scene("Main"))
    p.gameplay_library.add_ability(AbilityDefinition("slash"))
    p.gameplay_library.add_ability(AbilityDefinition("fire"))
    doc = EditorDocument(p)
    return p, doc, RpgItemEquipmentAuthoringController(doc)


def test_item_complete_fields_and_undo():
    p, doc, c = make()
    item = c.create_item(ItemDefinition("potion", "Potion", tags=("heal",), stack_limit=50))
    assert item.stack_limit == 50
    edited = c.edit_item(
        "potion", ItemDefinition("potion", "Hi Potion", tags=("heal", "rare"), stack_limit=20)
    )
    assert edited.display_name == "Hi Potion"
    assert doc.undo()
    assert p.rpg_database.items["potion"].display_name == "Potion"


def test_equipment_complete_fields():
    p, doc, c = make()
    growth = EquipmentGrowthDefinition(
        "blade_growth",
        nodes=(EquipmentGrowthNodeDefinition("root"),),
    )
    c.create_growth(growth)
    eq = c.create_equipment(
        EquipmentDefinition(
            "blade",
            "Blade",
            slot="weapon",
            tags=("sword",),
            granted_abilities=("slash",),
            sockets=(SocketDefinition("rune", accepted_tags=("rune",)),),
            required_capabilities=("weapon_use",),
            any_capabilities=("sword_user", "universal_weapon"),
            forbidden_capabilities=("disarmed",),
            growth_id="blade_growth",
        )
    )
    assert eq.slot == "weapon"
    assert eq.sockets[0].socket_id == "rune"
    assert eq.growth_id == "blade_growth"


def test_attachment_complete_fields_and_growth_reference():
    p, doc, c = make()
    c.create_growth(
        EquipmentGrowthDefinition("rune_growth", nodes=(EquipmentGrowthNodeDefinition("root"),))
    )
    att = c.create_attachment(
        AttachmentDefinition(
            "ember_rune",
            "Ember Rune",
            tags=("rune", "fire"),
            granted_abilities=("fire",),
            growth_id="rune_growth",
        )
    )
    assert att.granted_abilities == ("fire",)
    assert att.growth_id == "rune_growth"


def test_growth_graph_supports_ranks_requirements_prereqs_rewards_and_evolution():
    p, doc, c = make()
    c.create_equipment(EquipmentDefinition("blade_plus", "Blade+"))
    root = EquipmentGrowthNodeDefinition(
        "root",
        max_rank=2,
        rank_requirements=({"xp": 10}, {"xp": 30}),
        rewards=(
            EquipmentGrowthReward(granted_abilities=("slash",)),
            EquipmentGrowthReward(unlocked_sockets=("rune",)),
        ),
    )
    evo = EquipmentGrowthNodeDefinition(
        "evolve",
        prerequisites=(("root", 2),),
        auto_unlock=False,
        rewards=EquipmentGrowthReward(evolution_equipment_id="blade_plus"),
        exclusive_group="path",
    )
    growth = c.create_growth(
        EquipmentGrowthDefinition(
            "blade_growth", "Blade Growth", nodes=(root, evo), tags=("weapon",)
        )
    )
    assert growth.require_node("root").max_rank == 2
    assert growth.require_node("evolve").prerequisites == (("root", 2),)
    assert growth.require_node("evolve").reward_for_rank(1).evolution_equipment_id == "blade_plus"


def test_unknown_growth_reference_is_rejected():
    _, _, c = make()
    with pytest.raises(RpgItemEquipmentAuthoringError):
        c.create_equipment(EquipmentDefinition("blade", growth_id="missing"))


def test_unknown_ability_reference_is_rejected():
    _, _, c = make()
    with pytest.raises(RpgItemEquipmentAuthoringError):
        c.create_attachment(AttachmentDefinition("bad", granted_abilities=("missing",)))


def test_canonical_composition_recipe_and_runtime():
    p, doc, c = make()
    for item in (ItemDefinition("herb"), ItemDefinition("vial"), ItemDefinition("tonic")):
        c.create_item(item)
    recipe = c.create_recipe(
        CompositionRecipeDefinition(
            "tonic_recipe",
            "Tonic",
            selections=(
                CompositionSelection("base", ("herb",)),
                CompositionSelection("container", ("vial",)),
            ),
            outputs=(CompositionOutput("tonic", 1),),
            tags=("alchemy",),
        )
    )
    runtime = CompositionRuntime((recipe,))
    inv = Inventory()
    inv.add("herb")
    inv.add("vial")
    result = runtime.craft(inv, {"base": ("herb",), "container": ("vial",)})
    assert result.recipe_id == "tonic_recipe"
    assert inv.count("herb") == 0
    assert inv.count("vial") == 0
    assert inv.count("tonic") == 1


def test_recipe_references_are_validated():
    _, _, c = make()
    c.create_item(ItemDefinition("herb"))
    with pytest.raises(RpgItemEquipmentAuthoringError):
        c.create_recipe(
            CompositionRecipeDefinition(
                "bad",
                selections=(CompositionSelection("base", ("missing",)),),
                outputs=(CompositionOutput("herb"),),
            )
        )


def test_database_v21_roundtrip_preserves_recipes():
    p, doc, c = make()
    c.create_item(ItemDefinition("a"))
    c.create_item(ItemDefinition("b"))
    c.create_recipe(
        CompositionRecipeDefinition(
            "r",
            selections=(CompositionSelection("s", ("a",)),),
            outputs=(CompositionOutput("b", 2),),
        )
    )
    raw = p.to_data()
    clone = Project.from_data(raw, doc.component_registry)
    assert clone.rpg_database.composition_recipes["r"].outputs[0].amount == 2
    assert clone.to_data() == raw


def test_old_database_without_recipes_remains_readable():
    p, doc, c = make()
    raw = p.rpg_database.to_data()
    raw["version"] = 20
    raw.pop("composition_recipes")
    from asteria.rpg import RpgDatabase

    restored = RpgDatabase.from_data(raw)
    assert restored.composition_recipes == {}


def test_delete_growth_protects_equipment_and_attachment_refs():
    _, _, c = make()
    c.create_growth(EquipmentGrowthDefinition("g", nodes=(EquipmentGrowthNodeDefinition("n"),)))
    c.create_equipment(EquipmentDefinition("blade", growth_id="g"))
    with pytest.raises(RpgItemEquipmentAuthoringError):
        c.delete_growth("g")


def test_delete_item_protects_recipe_refs():
    _, _, c = make()
    c.create_item(ItemDefinition("a"))
    c.create_item(ItemDefinition("b"))
    c.create_recipe(
        CompositionRecipeDefinition(
            "r",
            selections=(CompositionSelection("s", ("a",)),),
            outputs=(CompositionOutput("b"),),
        )
    )
    with pytest.raises(RpgItemEquipmentAuthoringError):
        c.delete_item("a")


def test_information_architecture_is_progressively_disclosed():
    _, _, c = make()
    ia = c.information_architecture
    assert ia.primary_navigation == "category_sidebar"
    assert ia.browser_pattern == "search_filter_list"
    assert ia.inspector_pattern == "contextual_detail"
    assert ia.progressive_disclosure
    assert not ia.show_all_details_simultaneously
    assert ia.section("growth").mode == "graph_detail"


def test_workspace_keeps_one_category_and_context_at_a_time():
    _, _, c = make()
    c.create_item(ItemDefinition("herb", "Red Herb", tags=("material",)))
    c.create_equipment(EquipmentDefinition("blade", "Blade", tags=("weapon",)))
    w = RpgItemEquipmentWorkspaceModel(c)
    assert w.snapshot().visible_ids == ("herb",)
    w.set_section("equipment")
    assert w.snapshot().visible_ids == ("blade",)
    w.select("blade")
    assert w.snapshot().selected_id == "blade"
    w.set_section("items")
    assert w.snapshot().selected_id is None


def test_workspace_search_and_growth_node_focus():
    _, _, c = make()
    c.create_item(ItemDefinition("herb", "Red Herb", tags=("material",)))
    c.create_item(ItemDefinition("potion", "Potion", tags=("consumable",)))
    c.create_growth(
        EquipmentGrowthDefinition(
            "g",
            "Growth",
            nodes=(
                EquipmentGrowthNodeDefinition("root"),
                EquipmentGrowthNodeDefinition("branch"),
            ),
        )
    )
    w = RpgItemEquipmentWorkspaceModel(c)
    w.set_query("material")
    assert w.visible_ids() == ("herb",)
    w.set_section("growth")
    w.set_query("")
    w.select("g")
    w.select_node("branch")
    assert w.snapshot().selected_node_id == "branch"


def test_project_validation_after_full_item_authoring():
    p, _, c = make()
    c.create_item(ItemDefinition("ore"))
    c.create_item(ItemDefinition("ingot"))
    c.create_recipe(
        CompositionRecipeDefinition(
            "forge",
            selections=(CompositionSelection("material", ("ore",)),),
            outputs=(CompositionOutput("ingot"),),
        )
    )
    assert c.validate() == ()
    assert p.validate()
