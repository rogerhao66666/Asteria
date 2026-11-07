# Batch 109 — Animation / Transition / Timing Polish

Batch 109 adds project-owned animation timing and transition policy without changing battle gameplay timing.

## Animation timing profile

`BattleAnimationTimingProfile` and `BattleAnimationTimingRule` can configure per semantic animation role:

- playback rate
- sprite transition duration
- transition easing
- recovery hold

The default profile keeps playback at 1.0 with zero transition and zero recovery hold, preserving pre-Batch-109 behavior.

## Transition rendering

When a configured role changes, `BattleCombatantAnimator` can retain the previous sprite frame temporarily. `BattlePresentationRuntime.build_frame()` emits both previous and current sprite draws with easing-driven cross-fade opacity.

This is presentation blending. It does not alter canonical position, lifecycle, action timing, damage, resource state, or turn ownership.

## Recovery timing

Transient attack/hit roles may retain their completed pose for a project-authored recovery window before returning to Idle. The recovery window advances only on the presentation animation clock.

## Multi-hit rhythm

`BattleHitRhythm` is a small presentation helper that generates deterministic visual timing offsets for repeated hits. It supports repeating interval patterns and optional accent spacing.

The helper does not create gameplay hits and does not invoke abilities. A canonical multi-hit action remains responsible for its gameplay results; presentation can use the rhythm only to stage already-known visual hits.

## Easing

Built-in backend-neutral easing functions:

- linear
- ease_in
- ease_out
- ease_in_out
- smoothstep

These are presentation interpolation functions and can be shared by future transition/camera/UI polish.
