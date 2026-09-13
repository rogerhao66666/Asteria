# Batch 92 — Deterministic Battle Snapshot / Transaction Closure

Asteria Battle Core now owns a serializable deterministic runtime checkpoint and an explicit action-cost commitment seam.

## BattleSnapshot

`BattleRuntime.snapshot()` captures mutable battle state while authored definitions remain canonical project data. The snapshot includes:

- combatant subject stats/resources/tags/state runtime
- dynamic combatant topology, including summons
- combatant lifecycle state and summon provenance
- transformation revert stacks
- round/continuous scheduler state and current timeline time
- pending casts/action timing queue
- battle resources/gauges
- formation placement
- objective flags and escaped sides
- enemy AI memory and boss phase
- battle-owned RNG state
- pending action transaction reservations

`restore_snapshot()` restores into a compatible battle definition and does not replay lifecycle hooks for historical events. It emits only `rpg.battle.snapshot_restored` after restoration.

## Deterministic RNG ownership

`BattleRuntime` now owns a seeded `random.Random` instance (`rng_seed`). Battle APIs use that RNG whenever a caller does not supply an explicit RNG. The RNG state is serialized in `BattleSnapshot`, enabling continuation/replay from a checkpoint.

## Action transaction policy

`ActionTransactionPolicy` separates *when* an ability cost commits from the ability effect itself:

- `resolution` — legacy/default behavior; cost and effect commit atomically when the action resolves.
- `start` — cost commits when a delayed cast starts and is marked prepaid at resolution.

Interrupted/cancelled start-paid casts can use:

- `keep`
- `refund`

The engine does not decide which policy is correct for a game. Project-authored policy is canonical RpgDatabase data.

## Schema

RpgDatabase schema is v20 and adds `action_transactions`. v1–v19 remain backward-readable.

## Responsibility boundary

The engine guarantees stable state capture/restore, deterministic internal RNG continuation, and correct single-payment/refund mechanics. The game author decides whether a particular spell pays at cast start or resolution and whether interruption refunds its cost.
