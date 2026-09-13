# Batch 106 — Generic Action Menu / Ability Presentation

Batch 106 adds a generic presentation layer for arbitrary battle commands without introducing gameplay command semantics.

## Action entries

`BattleActionEntry` is an opaque presentation description supplied by the canonical controller. It can represent an ability, weapon action, item, stance, summon, job command, transform, workflow, or any project-defined command through project metadata.

Presentation fields include:

- action ID
- label
- category
- kind
- icon
- detail text
- cost text
- enabled/disabled state
- disabled reason
- order / priority
- tags / search terms

The presentation layer does not evaluate costs, conditions, ownership, cooldowns, targets, or legality. Those values arrive already resolved as presentation metadata.

## Large collections

`BattleActionMenuRuntime` supports:

- stable project-defined ordering
- category browsing
- all-category view
- paging
- text/search-term filtering
- cursor navigation
- supplied disabled reasons
- deterministic snapshot/restore

No engine-defined `Attack / Skill / Item / Defend` command list exists.

## UI composition

`BattleUiComposer` can project a `BattleActionMenuView` into existing panels, text and icons. It displays categories, filter state, page position, selected action, cost text and disabled reasons without invoking gameplay.

`BattleScreenRuntime` now owns the presentation menu runtime and can receive opaque action entries from the canonical controller.
