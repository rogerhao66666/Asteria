# Batch 97 — Camera / Screen Hit Feedback + Target Indicator

Batch 97 extends Battle Presentation only. Phase 7B Battle Core remains FROZEN at Batch 93 / v0.93.0a93.

## Delivered

- `BattleCameraFeedbackRuntime` consumes existing `ActionTimeline` `CAMERA` and `SCREEN_FX` presentation cues.
- Deterministic camera impulse/shake state with finite lifetime and snapshot/restore.
- Screen-effect view state, including authored hit-flash / hit-stop metadata, without owning gameplay timing semantics.
- `BattlePresentationCoordinator.push_target_selection()` mirrors already-selected canonical target IDs into presentation.
- `BattleTargetIndicator` exposes member ID, primary/secondary state, world anchor and camera-projected screen anchor.
- Missing/offscreen visuals are skipped by the renderer-facing frame without changing canonical target selection.
- Reference camera/screen/indicator data under `reference_data/battle_presentation_batch97.json`.

## Ownership boundary

Presentation does not call targeting resolvers, re-check target legality, choose targets, compute damage, change turn ownership, or infer hit results. Camera/screen cues are authored presentation instructions. Target selection is supplied by the canonical caller and merely mirrored.

`hit_stop` in this batch is presentation metadata/state only. It does not freeze Battle Core simulation or modify gameplay clocks. A later runtime adapter may decide how presentation clocks use that cue without moving gameplay ownership into presentation.

## Next

Proceed to Battle HUD/view-state: HP/MP/project-defined gauges, status icons, and turn/timeline presentation. Final renderer styling remains project/backend-owned.
