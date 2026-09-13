# Batch 147 — Item / Equipment / Attachment / Growth / Crafting Editor

Batch 147 closes the current canonical authoring surface for:
- Item definitions and use effects
- Equipment definitions
- Equipment slots/tags/requirements
- Stat modifiers
- Granted abilities and triggers
- Sockets
- Attachments
- Equipment growth graphs
- Growth ranks and arbitrary counters
- Prerequisites / exclusive branches / auto unlock
- Growth rewards / socket unlocks / evolution targets
- Crafting / alchemy composition recipes

## Canonical composition gap closed

Before this batch, crafting recipes existed only in validation code. That was not
sufficient for a real editor. Batch 147 promotes generic composition recipes into
the canonical RPG model as `CompositionRecipeDefinition` plus `CompositionRuntime`.

RpgDatabase schema advances from v20 to v21 and remains backward-readable.

## Information architecture

Functional completeness is not displayed as a single giant form.

The item workspace uses category navigation:
Items / Equipment / Attachments / Equipment Growth / Crafting & Alchemy.

Each category uses search/filter plus one selected detail target. Equipment Growth
uses graph + selected-node detail. Crafting uses recipe identity, selection steps,
outputs and tags as separate contextual groups. The default presentation explicitly
does not show every field of every subsystem at once.
