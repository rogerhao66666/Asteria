# Batch 104 — Generic Resource Presentation Policy

Batch 104 removes the remaining presentation assumption that every battle-facing resource is rendered as the same horizontal gauge.

## Resource presentation policy

`BattleHudResourceStyle` now carries project-owned visual metadata:

- `presentation`
- `segments`
- `group`
- `priority`
- `show_label`
- `show_value`
- `compact`
- optional icon

Built-in presentation roles are:

- `bar`
- `segmented_bar`
- `pips`
- `number`
- `icon_stack`
- `ring`
- `action_gauge`
- `timeline`
- `contextual`
- `hidden`

Custom role strings are preserved instead of rejected, allowing a project UI adapter to introduce completely new visualizations.

These roles are presentation semantics only. They do not alter resource values, battle rules, costs, scheduler behavior, gauge thresholds, or action availability.

## Beginner defaults vs engine rules

`BattleHudProfile.default()` still exposes HP and MP as convenient starter presets, while unmapped canonical resources remain displayable. HP/MP are not engine requirements.

Projects can instead expose BP, SP, TP, stamina, guard/break, shield, ATB/action meters, limit meters, shared resources, or project-defined resources.

## Runtime projection

`BattleHudRuntime` mirrors the canonical resource state and carries the project presentation metadata into `BattleHudGauge`.

`BattleUiComposer` then maps presentation roles into adapter-ready commands:

- number/contextual resources can be text-only,
- pips/segmented/ring/action/timeline/custom roles retain their presentation role,
- hidden resources do not enter the HUD.

The optional pygame adapter now has readable built-in rendering for bars, segmented/pip/icon-stack presentation and rings, with a bar fallback for custom roles.
