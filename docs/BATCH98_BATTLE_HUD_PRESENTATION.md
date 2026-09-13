# Batch 98 — Battle HUD Presentation

Batch 98 adds a backend-neutral, read-only Battle HUD projection over canonical battle resources and gameplay states.

## Delivered

- `BattleHudProfile`: project-defined resource/status presentation policy.
- `BattleHudResourceStyle`: arbitrary resource label/icon/order/visibility mapping.
- `BattleHudStatusStyle`: arbitrary state icon/label/order mapping.
- `BattleHudRuntime`: deterministic projection from canonical `BattleResourceRuntime` and `StateRuntime` values.
- `BattleHudMember`, `BattleHudGauge`, and `BattleHudStatusIcon` view-state records.
- Snapshot/restore for HUD presentation state.
- Reference HUD profile with HP, MP, LIMIT and two example state-icon mappings.

## Boundary

HP and MP are not engine semantics. They are merely defaults in `BattleHudProfile.default()`. Any project-defined battle resource can be displayed, including rage, stagger, combo, boost, heat, guard, or custom gauges.

The HUD never changes resources, applies/removes states, checks KO, resolves thresholds, computes percentages from gameplay rules, or infers status meaning. `normalized`, `overflow`, and `full` are copied from the canonical `BattleResourceValue`; active-state stacks, remaining duration and source are copied from canonical `StateRuntime.active_states()`.

Final typography, bars, icon atlases, layout and backend-specific drawing remain adapter/UI work. Batch 98 establishes the canonical view-state only.
