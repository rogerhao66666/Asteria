# Batch 87 — Advanced Action Timing

Batch 87 adds a backend-neutral temporal layer between battle command selection and ability resolution.

## Canonical data

`ActionTimingDefinition` is keyed by ability id and provides:

- `startup`: pre-resolution startup time.
- `cast_time`: sustained cast/channel time before resolution.
- `recovery`: extra delay before the actor's next scheduler readiness.
- `priority`: deterministic ordering for actions resolving at the same timestamp.
- `interruptible`: whether ordinary interrupts may cancel the pending action.
- `interrupt_threshold`: minimum interrupt power required.

Startup and cast time stay separate even though both contribute to `windup`; presentation can later use them as distinct animation phases.

## Runtime

`BattleActionTimingRuntime` owns pending action intents and deterministic ordering. It supports:

- queueing delayed actions;
- same-time priority ordering;
- cancellation;
- threshold-based interruption;
- timeline shifting of pending casts;
- snapshot/restore without replaying side effects.

It deliberately does not mutate gameplay subjects. `BattleRuntime` remains the owner of ability validation and effect execution.

## Scheduler integration

The continuous scheduler can now shift a member's next readiness. Positive values delay; negative values advance, clamped to the current scheduler time.

`BattleRuntime.submit_action()` uses timing metadata:

- zero-windup actions resolve immediately;
- delayed actions become pending and resolve when timeline time reaches `resolve_at`;
- recovery shifts the actor's next readiness;
- pending casts may be interrupted or cancelled;
- target/action validity is checked again at resolution time.

## Cost commitment seam

Phase 6 `AbilityRuntime` currently applies costs and effects atomically at resolution. Therefore delayed actions currently commit their cost at resolution. Batch 92's battle transaction layer is the intended seam for projects that need reserve-on-start, pay-on-start, partial refund, or other commitment policies.

This is intentional: Batch 87 does not split the existing ability transaction prematurely.

## No hardcoded RPG semantics

There is no engine concept of `Quick`, `Heavy`, `Magic`, or `Meteor`. Those are content conventions. Any ability can use arbitrary timing values.

## Presentation handoff

Battle presentation can later consume startup/cast/resolution/recovery hooks without changing gameplay semantics. Ability logic and presentation timeline remain separate.
