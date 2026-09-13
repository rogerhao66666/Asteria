# Batch 95 — Battle Scene / Combatant Animation Runtime

Batch 95 is the first runtime-facing Battle Presentation batch after the Batch 94
foundation. It does **not** reopen Battle Core. Battle Core remains frozen at
Batch 93 / v0.93.0a93 and continues to own all combat meaning and outcomes.

## Delivered

- `BattlePresentationRuntime`: consumes ordered Batch 94 presentation events.
- `BattleCombatantAnimator`: presentation-only animation state per canonical
  battle `member_id`.
- Semantic Idle / Attack / Hit / KO role selection through the existing
  `BattleCombatantVisual.animation_roles` binding.
- Timeline `ANIMATION` cue consumption. The cue must identify the affected
  combatant and may request a semantic role or a concrete clip.
- Lifecycle-driven KO/removal/revive presentation from already-resolved Battle
  Core lifecycle hooks.
- Transient Attack/Hit clips return deterministically to Idle when their
  non-looping animation completes.
- Existing `AnimatorState`, `AnimationClipSet`, `SpriteSheet`, `TextureDraw`, and
  `Camera2D` abstractions are reused. No battle-only renderer or sprite engine was
  created.
- Deterministic presentation snapshot/restore, including animation cursor/time,
  role, visibility and event sequence position.
- Backend-neutral `BattlePresentationFrame` carrying background asset identity
  plus sorted combatant texture draws.

## Explicit ownership boundary

Presentation does not calculate or infer damage, hit success, target legality,
resource cost, weakness/resistance, Break/Stagger, status meaning, turn order,
AI choice, KO criteria or battle outcome. A Hit animation is played because an
already-authored presentation cue requests it. KO is played because frozen
Battle Core lifecycle state already reports incapacitation/defeat.

## Reference scenario

`reference_data/batch95_battle_presentation_scene.json` demonstrates one hero
and one Asteria archive-mimic opponent. It intentionally reuses Asteria-original
reference pixel assets and the canonical sprite/animation loaders rather than
programmer-art rectangles. This is a pipeline/reference scenario, not final
commercial battle art.

The hero uses the existing hero sheet with a battle-specific reference clip set.
The archive mimic reuses the original chest prop as a coherent temporary monster
concept. Dedicated polished battle art remains replaceable data and can be added
without changing the runtime model.

## Deferred

Batch 95 does not add damage numbers, VFX, sound playback, camera hit feedback,
weakness/break feedback, target indicators, HP/MP/gauge HUD, status icons,
turn/timeline UI, or result/reward presentation. Those remain later Battle
Presentation layers on the same event stream.
