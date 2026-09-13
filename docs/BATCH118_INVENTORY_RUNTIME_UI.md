# Batch 118 — Inventory / Item Runtime UI

Adds a generic read-only inventory presentation layer.

`InventoryScreenRuntime` consumes canonical `Inventory` and `ItemDefinition`
catalogs and projects counts, stack limits, tags, usability metadata, project
labels/groups, search, selection and adaptive overflow.

Inventory grouping is project vocabulary. The engine does not require
consumable/material/key-item categories.

Presentation never calls `Inventory.add/remove()` or `use_inventory_item()`.
