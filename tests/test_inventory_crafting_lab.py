import pytest

from asteria.validation import InventoryCraftingLab


def complete_healing_recipe(lab):
    lab.begin()
    lab.select("red_herb")
    lab.advance()
    lab.select("glass_vial")
    lab.advance()
    lab.advance()


def complete_spark_recipe(lab):
    lab.begin()
    lab.select("red_herb")
    lab.advance()
    lab.select("spark_dust")
    lab.advance()
    lab.select("glass_vial")
    lab.advance()


def test_lab_starts_from_canonical_inventory_counts():
    lab = InventoryCraftingLab()
    snap = lab.snapshot()
    assert dict(snap.counts)["red_herb"] == 4
    assert dict(snap.counts)["spark_dust"] == 2
    assert dict(snap.counts)["glass_vial"] == 3


def test_workflow_options_are_derived_from_inventory():
    lab = InventoryCraftingLab()
    view = lab.begin()
    assert tuple(x.option_id for x in view.options) == ("red_herb",)
    assert view.options[0].enabled


def test_healing_recipe_resolves_from_generic_step_selection():
    lab = InventoryCraftingLab()
    complete_healing_recipe(lab)
    recipe = lab.resolve_recipe()
    assert recipe.recipe_id == "healing_tonic_recipe"


def test_crafting_consumes_materials_and_produces_output():
    lab = InventoryCraftingLab()
    before_herb = lab.inventory.count("red_herb")
    before_vial = lab.inventory.count("glass_vial")
    complete_healing_recipe(lab)
    result = lab.craft()
    assert result.recipe_id == "healing_tonic_recipe"
    assert result.consumed == (("glass_vial", 1), ("red_herb", 1))
    assert lab.inventory.count("red_herb") == before_herb - 1
    assert lab.inventory.count("glass_vial") == before_vial - 1
    assert lab.inventory.count("healing_tonic") == 1


def test_optional_catalyst_can_be_empty():
    lab = InventoryCraftingLab()
    complete_healing_recipe(lab)
    payload = lab.workflow.selection_payload()
    assert payload["selections"]["catalyst"] == []


def test_second_recipe_uses_same_workflow_without_alchemy_engine_enum():
    lab = InventoryCraftingLab()
    complete_spark_recipe(lab)
    recipe = lab.resolve_recipe()
    assert recipe.recipe_id == "spark_tonic_recipe"
    result = lab.craft()
    assert result.produced == (("spark_tonic", 1),)
    assert lab.inventory.count("spark_tonic") == 1


def test_catalyst_and_reagent_can_consume_same_item_id_twice_if_selected_twice():
    lab = InventoryCraftingLab()
    # Author a recipe that intentionally requires two glass_vial selections.
    from asteria.validation import CompositionRecipe

    lab.recipes = lab.recipes + (
        CompositionRecipe(
            "double_vial",
            (
                ("base", ("red_herb",)),
                ("reagent", ("glass_vial",)),
                ("catalyst", ("glass_vial",)),
            ),
            (("healing_tonic", 2),),
        ),
    )
    lab.begin()
    lab.select("red_herb")
    lab.advance()
    lab.select("glass_vial")
    lab.advance()
    lab.select("glass_vial")
    lab.advance()
    # Earlier first matching recipe requires empty catalyst, so double_vial wins.
    recipe = lab.resolve_recipe()
    assert recipe.recipe_id == "double_vial"
    before = lab.inventory.count("glass_vial")
    result = lab.craft()
    assert dict(result.consumed)["glass_vial"] == 2
    assert lab.inventory.count("glass_vial") == before - 2


def test_insufficient_materials_are_rejected_without_partial_mutation():
    lab = InventoryCraftingLab()
    complete_spark_recipe(lab)
    # Simulate inventory changing between selection and commit.
    while lab.inventory.count("spark_dust"):
        lab.inventory.remove("spark_dust")
    before = lab.inventory.to_data()
    with pytest.raises(ValueError, match="insufficient materials"):
        lab.craft()
    assert lab.inventory.to_data() == before
    assert lab.workflow.active


def test_disabled_option_is_not_selected_when_inventory_is_empty():
    lab = InventoryCraftingLab()
    while lab.inventory.count("red_herb"):
        lab.inventory.remove("red_herb")
    view = lab.begin()
    assert not view.options[0].enabled
    lab.select("red_herb")
    assert lab.workflow.selection_payload()["selections"]["base"] == []


def test_unknown_recipe_does_not_consume_inventory():
    lab = InventoryCraftingLab()
    lab.begin()
    lab.select("red_herb")
    lab.advance()
    lab.select("spark_dust")
    lab.advance()
    # No catalyst -> no matching recipe.
    lab.advance()
    before = lab.inventory.to_data()
    with pytest.raises(ValueError, match="no matching"):
        lab.craft()
    assert lab.inventory.to_data() == before


def test_successful_craft_closes_workflow_and_records_history():
    lab = InventoryCraftingLab()
    complete_healing_recipe(lab)
    lab.craft()
    assert not lab.workflow.active
    snap = lab.snapshot()
    assert snap.completed_recipes == ("healing_tonic_recipe",)


def test_multiple_crafts_accumulate_products_and_consume_inventory():
    lab = InventoryCraftingLab()
    for _ in range(2):
        complete_healing_recipe(lab)
        lab.craft()
    assert lab.inventory.count("healing_tonic") == 2
    assert lab.inventory.count("red_herb") == 2
    assert lab.inventory.count("glass_vial") == 1
