# Batch 134 — Inventory / Alchemy / Crafting Lab

Batch 134 makes the generic composition workflow actually mutate canonical
inventory state.

The presentation workflow remains deliberately dumb: it only collects
project/controller supplied options and selections. Recipe matching, material
requirements, consumption, and outputs are reference-project policy.

Validated behavior:
- inventory-backed workflow options;
- disabled options when inventory count is zero;
- base/reagent/optional-catalyst multi-step composition;
- project-authored recipe matching;
- canonical inventory material consumption;
- crafted output production;
- repeated crafting;
- same item ID consumed multiple times when selected in multiple steps;
- insufficient-material rejection with no partial mutation;
- unknown recipe rejection with no inventory mutation.

No `AlchemyCommand`, `CraftingSystem`, ingredient enum, or fixed recipe category
was added to the engine. The same controller pattern can express cooking,
smithing, mixing, synthesis, item fusion, ritual assembly, or other project
mechanics.
