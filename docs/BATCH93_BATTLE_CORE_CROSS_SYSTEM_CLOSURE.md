# Batch 93 — Battle Core Cross-System Closure & Freeze

Version: `v0.93.0a93`

Batch 93 intentionally adds no new named combat subsystem. Its purpose is to verify that the Battle Core built in Batches 81–92 composes safely and deterministically across subsystem boundaries.

## Closure acceptance

The closure suite validates representative high-risk intersections:

- equal-speed deterministic scheduling + snapshot continuation;
- generic gauge threshold → state → lifecycle hook → cast interrupt → transaction refund;
- multi-hit sequence where a threshold/state changes between hits and later hits observe the new state;
- KO/incapacitation mid-sequence using authored targeting + sequence interruption policy;
- reaction chains + battle RNG producing identical results after snapshot restore;
- boss phase transition after battle state changes through normal AI reevaluation/hook seams;
- JSON-safe whole-battle snapshot after cross-system activity.

## Responsibility boundary

Asteria guarantees mechanism correctness, deterministic ordering where defined, safe bounded recursion, serialization/restore continuity, and open composition seams.

Asteria does **not** decide whether a game should allow hitting incapacitated targets, whether Break must interrupt casts, how boss phase transitions should be timed, whether counters can counter counters, or whether a multi-hit action should stop after KO. Those are authored policies/data.

The closure specifically confirmed that these choices can be expressed without engine-source special cases.

## Freeze decision

Battle Core is frozen at `v0.93.0a93`.

Future work should not redesign the frozen core preemptively. If Battle Presentation, RPG GUI, or the playable vertical slice exposes a concrete abstraction hole, fix the smallest generic seam and re-run the closure suite.
