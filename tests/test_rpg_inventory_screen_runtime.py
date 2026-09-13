from asteria.presentation import InventoryScreenProfile, InventoryScreenRuntime
from asteria.rpg.items import Inventory, ItemDefinition

def _inventory():
    inv=Inventory(); inv.add("potion",5); inv.add("ether",2); inv.add("ore",12)
    return inv

def _catalog():
    return (
        ItemDefinition("potion","Potion",tags=("healing","consumable")),
        ItemDefinition("ether","Ether",tags=("focus","consumable")),
        ItemDefinition("ore","Iron Ore",tags=("material",)),
        ItemDefinition("key_fragment","Key Fragment",tags=("key",),stack_limit=1),
    )

def test_projects_counts_catalog_and_zero_count_catalog_entries_read_only():
    inv=_inventory(); before=inv.to_data()
    view=InventoryScreenRuntime().project(inv,_catalog())
    counts={x.item_id:x.count for x in view.items}
    assert counts["potion"]==5 and counts["ore"]==12 and counts["key_fragment"]==0
    assert inv.to_data()==before

def test_project_owned_groups_and_labels_are_generic():
    profile=InventoryScreenProfile(
        item_labels={"ore":"Forging Ore"},
        item_groups={"potion":"supplies","ether":"supplies","ore":"crafting","key_fragment":"quest"},
        group_labels={"crafting":"Crafting"},
    )
    view=InventoryScreenRuntime(profile).project(_inventory(),_catalog())
    assert next(x for x in view.items if x.item_id=="ore").label=="Forging Ore"
    assert next(x for x in view.groups if x.group_id=="crafting").label=="Crafting"

def test_query_searches_labels_tags_and_groups():
    profile=InventoryScreenProfile(item_groups={"ore":"crafting"})
    runtime=InventoryScreenRuntime(profile); runtime.set_query("material")
    view=runtime.project(_inventory(),_catalog())
    assert [x.item_id for x in view.items]==["ore"]

def test_large_inventory_overflow_is_presentation_only():
    inv=Inventory()
    catalog=[]
    groups={}
    for i in range(20):
        item_id=f"item_{i}"; inv.add(item_id,1); catalog.append(ItemDefinition(item_id)); groups[item_id]="bag"
    profile=InventoryScreenProfile(item_groups=groups,visible_limits={"bag":6})
    view=InventoryScreenRuntime(profile).project(inv,tuple(catalog))
    group=view.groups[0]
    assert len(group.item_ids)==20 and len(group.visible_item_ids)==6 and group.overflow_count==14
    assert len(inv.to_data()["counts"])==20

def test_selection_snapshot_and_restore_are_presentation_only():
    inv=_inventory(); before=inv.to_data()
    runtime=InventoryScreenRuntime(); runtime.project(inv,_catalog()); runtime.select("ore")
    snap=runtime.snapshot(); restored=InventoryScreenRuntime(); restored.restore(snap)
    assert restored.snapshot()==snap
    assert inv.to_data()==before

def test_profile_roundtrip():
    profile=InventoryScreenProfile(
        item_labels={"a":"A"},item_groups={"a":"materials"},
        group_labels={"materials":"Materials"},visible_limits={"materials":8},default_group="misc"
    )
    assert InventoryScreenProfile.from_data(profile.to_data())==profile

def test_no_fixed_consumable_material_key_item_taxonomy():
    inv=Inventory(); inv.add("memory_shard",3)
    profile=InventoryScreenProfile(item_groups={"memory_shard":"dream_archive"})
    view=InventoryScreenRuntime(profile).project(inv,(ItemDefinition("memory_shard",tags=("story_memory",)),))
    assert view.groups[0].group_id=="dream_archive"
