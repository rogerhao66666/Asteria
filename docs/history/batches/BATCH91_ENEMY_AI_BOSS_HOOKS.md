# Batch 91 — Enemy AI, Boss Phase, Multi-action, Battle Hook Integration

Asteria's AI layer is generic and project-defined. The engine provides deterministic selection, seeded weighted choices, memory, phase transitions, multi-action ready windows, and stable extension seams.

## Core types
- `AICondition`: open condition vocabulary via `kind` + serializable params.
- `AIDecisionRule`: priority/weight decision rule with open `action_kind` and `target_selector`.
- `BossPhaseDefinition`: condition-driven phase with optional rule subset, actions-per-ready override, enter/exit hooks.
- `EnemyAIDefinition`: canonical serializable AI data.
- `EnemyAIRuntime`: seeded decision runtime, memory, phase state, custom resolvers and action handlers.

## Battle extension seam
AI actions are not restricted to normal abilities. `action_kind` is an open string. Built-ins include `ability` and `hook`; projects/plugins can register handlers for any system, such as:

- alchemy / mixing / crafting-in-battle
- summon systems
- transform / stance / mode change
- capture / steal / negotiate
- scripted boss mechanics
- project plugins

These remain game-defined systems. Asteria guarantees a stable execution hook and lifecycle events, not a hard-coded rule for how those mechanics must behave.

## Lifecycle hooks
- `rpg.battle.ai.turn_started`
- `rpg.battle.ai.decision`
- `rpg.battle.ai.phase_changed`
- project-defined phase enter/exit hooks
- `rpg.battle.ai.action_executed`
- `rpg.battle.ai.multi_action_step`
- `rpg.battle.ai.turn_finished`
- `rpg.battle.ai.no_decision`

Existing battle hooks for summon/transform/state/resource/reaction remain usable by the same `LifecycleHookBus`.

## Determinism
Weighted choices are driven by caller-supplied RNG. Stable ordering is used before weighted selection. AI memory and active phase have snapshot data, ready for Batch 92 whole-battle snapshot integration.

## Policy boundary
The engine does not decide whether a boss should transform at 50% HP, whether summoned units act immediately, whether alchemy consumes a turn, or whether a phase change cancels a cast. Those are project rules.
