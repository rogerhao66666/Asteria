# Asteria Active Architecture

Canonical input: `Asteria_BattlePresentation_Batch94_v0.94.0a94.zip`.
Phase 7B Battle Core remains recorded FROZEN at Batch 93 (`v0.93.0a93`).
Batch 94 adds the presentation foundation; Batch 95 is on hold.

## Observed dependency direction

`asteria.presentation.battle` imports `LifecycleEvent` and `LifecycleHookBus`
from `asteria.core.lifecycle`, and `PresentationCue` from
`asteria.gameplay.action_timeline`. Those dependencies are absent in this ZIP.
The included presentation module imports no pygame or PySide6 backend. The
missing core cannot be inspected for reverse dependencies or integration behavior.

Expected flow from the supplied code and historical boundary:

1. Existing gameplay resolves battle meaning and emits hooks/timeline cues.
2. Callers explicitly pass cues to the coordinator; attachment observes hooks.
3. The coordinator emits ordered presentation data.
4. Future renderer/audio/UI adapters consume drained events.

No adapter, automatic animation selection, clock, or playback loop is supplied.
Scene asset and camera identifiers are references, not loaded resources. Scene
schema v1 is distinct from the historically recorded Project schema v6; this ZIP
does not implement Project persistence integration for presentation scenes.

## Lifecycle bridge implemented in Batch 94

All names below have the `rpg.battle.` prefix:

| Hook suffix | Presentation kind |
| --- | --- |
| combatant_state_changed, combatant_incapacitated, combatant_revived, combatant_removed, combatant_transformed, combatant_form_reverted | combatant_state |
| turn_ready | turn_ready |
| turn_ended | turn_ended |
| sequence_started | sequence_started |
| sequence_step_resolved | sequence_step |
| sequence_finished | sequence_finished |
| finished | battle_result |

Other hooks are ignored. Mapped events preserve the hook name, source and a
shallow copy of hook data. A battle-result hook does not automatically finish the
presentation scene. The bridge observes events; it does not infer or decide
combat results, resource spending, targeting, weakness/break or status semantics.

## Ownership and invariants

Frozen Battle Core owns combat execution and game-rule outcomes. Presentation
owns scene visual data and event ordering. Authors own rules/balance and asset
choices; future backends own rendering/audio/UI. Mechanism → policy → game rules
and shared canonical data remain the recorded project direction. No speculative
abstraction changes, duplicate combat model, or completed-system redesign is
part of this revision.

Ordering is deterministic for a given input call/event order; this does not
establish a persisted presentation snapshot or full-engine replay guarantee.
Event payloads are shallow dicts and must not be described as deeply immutable.
The [current spec](CANONICAL_SPEC.md) documents the included API behavior;
[consistency audit](CONSISTENCY_AUDIT.md) records limits of verification.
