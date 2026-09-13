# Batch 108 — Presentation Director

Batch 108 introduces a presentation-only choreography scheduler between the canonical presentation event stream and the existing animation/feedback/camera runtimes.

## Direction metadata

A project may define `BattlePresentationDirectorRule` mappings by presentation event kind and ActionTimeline cue kind. A direction contains:

- `beat`: authored choreography label such as anticipation, impact or recovery
- `delay`: presentation-only release delay
- `hold`: presentation-clock pause / hit-stop window
- `priority`: deterministic ordering for cues released at the same presentation time

Timeline cue payloads may override profile defaults with a `director` object. This metadata remains presentation-only.

## Runtime behavior

`BattlePresentationDirector` receives already-resolved `BattlePresentationEvent` values. It can queue delayed events and release them deterministically when presentation time reaches their authored release point.

A presentation hold consumes frame `dt` before animation, feedback and camera clocks advance. BattleScreen wall-clock bookkeeping still advances, while Battle Core scheduler/action/resource state is untouched.

The default profile is zero-delay / zero-hold, preserving the existing immediate Batch 103–107 behavior unless a project opts into authored choreography.

## Boundary

The Director cannot compute damage, targets, action legality, turn order, rewards or outcomes. It only changes when already-existing presentation events reach presentation runtimes.
