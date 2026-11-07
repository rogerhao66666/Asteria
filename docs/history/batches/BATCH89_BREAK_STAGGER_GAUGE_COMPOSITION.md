# Batch 89 — Break / Stagger & Advanced Gauge Composition

Asteria does not add a hardcoded `BreakSystem`. Batch 89 proves that break-like mechanics can be authored by composing existing generic primitives.

## Contract

`GaugeCompositionDefinition` maps project-defined battle triggers and outcome tags into arbitrary battle-resource changes. `GaugeImpactRule` chooses source/target ownership, fixed deltas and resolved-value scaling. `GaugeThresholdRule` reacts only when a resource crosses a configured boundary and may reuse existing primitives: apply a normal State, shift the existing battle timeline/cast, reset the resource, and emit a normal lifecycle trigger.

Nothing in the engine assigns meaning to names such as `stagger`, `guard`, `poise`, `break`, `heat`, or `combo`. The same mechanism can author all of them.

Example authored rule:

```text
weakness hit
  -> target stagger -25

stagger crosses <= 0
  -> apply state `broken`
  -> delay target timeline +20
  -> reset stagger to 100
  -> emit `battle.break.triggered`
```

This is data composition, not special engine logic.

## Determinism and corner cases

All matching impact rules for the same member/resource are aggregated before threshold evaluation. One logical impact therefore cannot accidentally trigger the same threshold multiple times merely because several authored rules contributed to it. Impact and threshold rules have deterministic priority/id ordering.

Thresholds are edge-triggered: already being below/above a threshold does not repeatedly fire until the gauge leaves the boundary and crosses it again. Reset behavior is explicit project data.

The engine guarantees bounded resource mutation, deterministic crossing detection, safe state/timeline reuse and lifecycle hooks. Whether a project *should* reset a break gauge, make Break interrupt a cast, permit bosses to resist the State, or use another rule is the game author's decision.
