# Batch 111 — Premium Adaptive Battle UI

Batch 111 turns the generic Battle UI components from Batches 104–110 into a stronger default visual hierarchy without changing gameplay semantics.

## Premium default hierarchy

The default composer now distinguishes:

- focused/current combatant HUD from ordinary HUD members,
- interaction surfaces from passive HUD panels,
- selected actions from ordinary/disabled actions,
- selected workflow options from available/disabled options,
- muted secondary metadata from primary content.

`BattleUiPolishProfile` owns spacing and interaction-surface presentation such as panel width, padding, row height, selected prefixes and page separator text. These values are project-owned defaults rather than engine gameplay rules.

## Adaptive interaction surfaces

Action menus and multi-step workflows now share a coherent interaction-surface layout:

- centered readable panel width,
- stable padding and row rhythm,
- category/filter header hierarchy,
- selected action emphasis,
- disabled-state de-emphasis,
- footer space for details, disabled reasons and paging,
- workflow title/step/option hierarchy.

The menu remains generic: no Attack/Skill/Item/Defend taxonomy is introduced.

## Focus emphasis

When a current/focused combatant is supplied, its HUD panel can receive a dedicated focus visual role. This is presentation emphasis only and does not change turn ownership.

## Theme hierarchy

`BattleUiTheme` now includes project-overridable focus/interactions/disabled/selected colors, while preserving existing result and feedback semantics.

The renderer derives panel and text appearance from presentation roles and still has no access to Battle Core.
