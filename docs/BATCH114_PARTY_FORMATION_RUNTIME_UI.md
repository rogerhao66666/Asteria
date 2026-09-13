# Batch 114 — Party / Formation Runtime UI

Batch 114 adds the generic party/formation presentation layer for Runtime RPG UI.

## Party projection

`PartyScreenRuntime` projects caller-owned canonical roster membership into a read-only `PartyScreenView`.

The default convenience grouping is `active` / `reserve`, but projects may supply arbitrary opaque group IDs such as:
- deployed
- bench
- summons
- expedition
- support

The presentation layer does not interpret their gameplay meaning.

## Formation projection

An optional canonical `BattleFormationRuntime` may be supplied. Runtime UI mirrors:
- formation ID
- arbitrary slot IDs
- authored x/y coordinates
- arbitrary slot tags
- explicit adjacency
- current member placement

Tags such as front/back are data only. Party UI does not infer combat rules from them.

## Adaptive roster presentation

`PartyScreenProfile.visible_limits` controls only the number of entries shown by the default presentation for a group. The complete canonical `member_ids` remain in the view.

When a focused member would be hidden by overflow, presentation may retain it in the visible subset without changing canonical membership/order.

## Focus

`focus(member_id)` changes presentation focus only. It never changes:
- active/reserve membership
- party roster order
- formation placement
- battle eligibility
- canonical save data

## Genericity

There is no fixed four-person party limit and no required active/reserve vocabulary. Formation slots and group IDs are project-defined.
