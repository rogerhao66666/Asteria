# Batch 83 — Battle State / Status Integration

Version: `0.83.0a83`

## Goal

Integrate the Phase 6 generic `StateDefinition` / `StateRuntime` primitives into the RPG battle layer without introducing engine-owned poison, stun, silence, sleep, haste, slow, doom, or break enums.

## Canonical model

`GameplayLibrary.states` continues to own what a state *is*: duration, stacking, modifiers, apply/remove/expire effects, periodic effects, and contributed tags.

`RpgDatabase.battle_state_policies` now owns how that state behaves in battle:

- application chance
- source-stat and target-stat chance terms
- tag-driven immunity
- duration scaling/resistance
- full action prevention
- ability-tag blocking
- lifecycle tick trigger
- lifecycle tick amount
- trigger-driven removal

This keeps battle semantics project-defined while reusing the same generic state primitive outside battle.

## Important capabilities

A project can compose familiar behavior without hardcoded names:

- Poison/Burn/Bleed: periodic effects + turn/action lifecycle ticking.
- Stun/Sleep: `prevent_action=True`.
- Silence: block `ability.magic` or any project tag.
- Haste/Slow: ordinary state modifiers; the future scheduler consumes the resulting effective speed/timeline rules.
- Doom/countdown: `on_expire`, distinct from manual removal.
- Sleep wake-on-hit: `remove_triggers=("rpg.battle.damage_received",)`.
- Boss control immunity: arbitrary target tags such as `immune.control`.
- Partial resistance: chance coefficients and duration multipliers driven by arbitrary stats.

No status name has special engine behavior.

## State runtime hardening

`ActiveState` now preserves optional `source_id`. State snapshots are schema v2 and remain backward-readable from v1. Restore does not replay `on_apply`.

`StateRuntime.advance(state_id, amount)` advances one state independently, allowing different battle lifecycle clocks to coexist. `StateRuntime.expire()` distinguishes natural expiration from manual removal and runs `on_expire` only on expiration.

`StateDefinition` is schema v3 with backward reading for v1/v2 and adds `on_expire`.

## Battle integration

`BattleRuntime` now exposes:

- `apply_state(...)`
- `ability_availability(...)`

Action execution rejects abilities blocked by active state policies. Battle lifecycle hooks can advance or remove states through `BattleStateRuntime.apply_trigger(...)`.

Current fixed `TurnQueue` does not yet implement advanced skip/reordering semantics for Haste/Slow/Stun. The state-side contract is complete; Batch 86 scheduler will consume it rather than duplicate status logic.

## Canonical persistence

`RpgDatabase` schema is now v11 and owns `battle_state_policies`. v1–v10 databases remain readable.

## Demo

`AsteriaPhase7B_BattleStatesDemo.asteria.json`

The reference demo covers Poison, Stun, Silence, Slow, Sleep, and Doom as ordinary project content and validates immunity, resistance, ability blocking, turn ticking, trigger removal, expiry-only effects, source provenance, and snapshot restore.
