# Batch 117 — Progression Graph / Skill Tree Runtime UI

Batch 117 adds the generic progression-graph presentation layer for Runtime RPG UI.

`ProgressionScreenRuntime` consumes canonical `ProgressionAllocationRuntime` and project-defined `ProgressionGraphDefinition` values read-only.

It projects arbitrary graphs, nodes, current ranks, max ranks, tags, prerequisite edges, any-prerequisite edges, exclusive groups, next-rank costs, canonical allocation eligibility/reasons, balances, query state and presentation-only selection.

The screen calls canonical `preview_allocate()` only to display already-defined progression policy. It never calls `allocate()` or `refund()`.

`visible_limits` are presentation limits only. They control how many node IDs a default graph navigator exposes at once; the full node view remains present and gameplay graphs are never capped.

No fixed skill-tree topology, currency name, node type, branch count or rank model is assumed.
