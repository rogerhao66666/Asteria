# Asteria Next Phase Plan

Canonical baseline:
`Asteria Phase 1–4 corrected baseline (user-provided f22ec74)`

## Phase 5 — Event VM + Dialogue

Goal: turn the walkable 2D world into an actual RPG world with behavior.

Recommended first batches:

1. Event VM core
   - instruction format
   - program counter
   - wait/resume
   - deterministic state
   - save/load/resume seam

2. Event context/state
   - switches
   - variables
   - local/self state
   - conditions

3. Interaction
   - Interaction component
   - proximity/facing checks
   - action button
   - NPC/chest/door event start

4. Dialogue
   - dialogue command
   - choice command
   - dialogue UI boundary
   - variable/switch consequences

5. World commands
   - transfer scene/map position
   - give/remove item placeholder API
   - play animation/audio/screen effect boundaries

6. Common/parallel/autorun events
   - scheduling
   - cancellation
   - debugger hooks

7. Reference World RPG slice
   - NPC
   - dialogue
   - choice
   - chest
   - door/transfer
   - simple cutscene

Do not hardcode game-specific quest/battle mechanics in Phase 5.


## Current progress

- Phase 5 Batch 36: Event VM Core implemented in v0.36.0a36.
- Phase 5 Batch 37: Event context/state implemented in v0.37.0a37.
- Phase 5 Batch 38: Interaction foundation implemented in v0.38.0a38.
- Phase 5 Batch 39: Event Runner / program registry integration implemented in v0.39.0a39.
- Phase 5 Batch 40: Dialogue runtime boundary + choice-state foundation implemented in v0.40.0a40.
- Phase 5 Batch 41: control flow + world-command service boundaries implemented in v0.41.0a41.\n- Phase 5 Batch 42: reusable/common event calls + call-stack foundation implemented in v0.42.0a42.\n- Phase 5 Batch 43: autorun / parallel event scheduling foundation implemented in v0.43.0a43.\n- Phase 5 Batch 44: scene/event binding + trigger condition model implemented in v0.44.0a44.\n- Phase 5 Batch 45: first Asteria Event Editor GUI vertical slice implemented in v0.45.0a45.\n- Phase 5 Batch 46: central Scene ↔ Code ↔ Event ↔ Animation workspace architecture implemented in v0.46.0a46.
- Next: Batch 47 Asteria Python Authoring API v1 + safe Code workspace Run integration.

- Phase 5 Batch 47: Python Authoring API v1 + Code workspace Run integration implemented in v0.47.0a47.
- Next: Batch 48 Code workspace integration/polish, then Phase 5 closure audit.

- Phase 5 Batch 48: Code workspace integration/diagnostics implemented in v0.48.0a48.
- Next: Phase 5 closure audit; fix blockers before freeze, then Phase 6 Generic Gameplay Framework.

## Phase 5 Closure

Phase 5 is FROZEN at `v0.49.0a49` after closure audit and blocker fixes. See `PHASE_5_CLOSURE_AUDIT.md`.

Next: Phase 6 — Generic Gameplay Framework.

## Phase 6 — Generic Gameplay Framework

- Batch 50: Stats / Resources / Tags foundation implemented in `v0.50.0a50`.
- Next: Batch 51 — Modifier / Effect foundation.
\n- Phase 6 Batch 51: Modifier / Effect foundation implemented in `v0.51.0a51`.\n- Next: Batch 52 — State / Status lifecycle foundation.\n
- Phase 6 Batch 52: Formula / Scaling foundation implemented in `v0.52.0a52`.
- Next: Batch 53 — State / Status lifecycle foundation.

- Phase 6 Batch 53: Generic State / Status lifecycle implemented in `v0.53.0a53`.
- Next: Batch 54 — Generic Conditions / Triggers foundation.

- Phase 6 Batch 54: Generic Conditions / Triggers foundation implemented in `v0.54.0a54`.
- Next: Batch 55 — Ability / Targeting foundation.

- Phase 6 Batch 55: Ability / Targeting foundation implemented in `v0.55.0a55`.
- Next: Batch 56 — Gameplay execution / timeline seam.

- Phase 6 Batch 56: Action Timeline / presentation seam implemented in `v0.56.0a56`.
- Next: Batch 57 — Phase 6 canonical registry/authoring integration.

- Phase 6 Batch 57: Gameplay defaults/presets and canonical GameplayLibrary implemented in `v0.57.0a57`.
- Next: Batch 58 — Phase 6 hardening before closure.

- Phase 6 Batch 58: State lifecycle, generic trigger keys, and formula-driven Effect hardening implemented in `v0.58.0a58`.
- Next: Phase 6 closure audit.

- Phase 6 closure: FROZEN at `v0.59.0a59` after tag-contribution ownership closure fix.
- Next: Phase 7 — RPG Toolkit built on frozen generic gameplay primitives.

- Phase 7 Batch 60: Actor/Class RPG Toolkit implemented in `v0.60.0a60`.
- Next: Batch 61 — Item / Equipment Toolkit.

- Phase 7 Batch 61: Item/Equipment/Socket/Attachment Toolkit implemented in `v0.61.0a61`.
- Next: Batch 62 — loadout contribution integration + consumable item effects.

- Phase 7 Batch 62: Loadout + consumable integration implemented in `v0.62.0a62`.
- Next: Batch 63 — Enemy / encounter / loot-reward toolkit.

- Phase 7 Batch 63: Enemy/Encounter/Loot-Reward toolkit implemented in `v0.63.0a63`.
- Next: Batch 64 — progression / level / experience toolkit.

- Phase 7 Batch 64: generic progression/rank toolkit implemented in `v0.64.0a64`.
- Next: Batch 65 — party + battle/turn-order foundation.

- Phase 7 Batch 65: Party + deterministic turn-order + thin BattleRuntime implemented in `v0.65.0a65`.
- Next: Batch 66 — battle outcome + reward/progression handoff.

- Phase 7 Batch 66: universal lifecycle hooks + Event VM bridge + battle outcome/reward handoff implemented in `v0.66.0a66`.
- Architectural invariant: any meaningful workflow must remain event-connectable.
- Next: Batch 67 — Project persistence integration for Phase 7 RPG data.

- Phase 7 Batch 67: canonical Project v4 now persists RpgDatabase; Project v2/v3 remain backward-readable.
- Next: Batch 68 — RPG cross-reference validation + lifecycle-event binding persistence.

- Phase 7 Batch 68: RPG cross-reference validation + persistent universal lifecycle-event bindings; Project v5.
- Next: Batch 69 — unique equipment instances / socketed loadout persistence.

- Phase 7 Batch 69: stable equipment instance identity + socket/loadout persistence; no arbitrary socket cap; slot capacity may be unlimited.
- Next: Batch 70 — RPG runtime save-state container + restore validation.

- Phase 7 Batch 70: canonical RPG runtime save-state for inventory, progression, loadouts, party identity, currencies.
- Next: Batch 71 — actor mutable runtime snapshots + derived equipment/progression integration.

- Phase 7 Batch 71: actor runtime snapshots + non-baked effective progression/equipment stats/tags/abilities.
- Next: Batch 72 — Phase 7 integration hardening before closure.

- Phase 7 Batch 72: reward transaction/rollback, public state replacement seams, stable equipment lifecycle identity.
- Next: Phase 7 pre-closure audit; resolve GameplayLibrary/ability persistence ownership before freeze.

- Phase 7 Batch 73: Project schema v6 owns canonical GameplayLibrary; RPG ability refs validated.
- Phase 7: CLOSURE PASS / FROZEN at v0.73.0a73.
- Next checkpoint: RPG Authoring GUI integration, then Phase 8 ARPG Toolkit.
