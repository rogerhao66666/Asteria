# Asteria Current Specification and Status

## Authority and scope

Sole input: `Asteria_BattlePresentation_Batch94_v0.94.0a94.zip`; project version
`0.94.0a94`. This active document consolidates the supplied source and records;
it is not a replacement reconstruction of missing full-project specifications.
Batch 95 is on hold. No executable behavior is changed.

## Phase 7 / 7B recorded systems

The original next-phase plan records these Phase 7 milestones:

| Batches | Recorded delivered scope |
| --- | --- |
| 60–64 | Actor/class; items/equipment/sockets/attachments; loadout contributions and consumables; enemy/encounter/loot/rewards; generic progression/rank |
| 65–66 | Party, deterministic turn order, thin BattleRuntime; universal lifecycle hooks, Event VM bridge, outcome/reward/progression handoff |
| 67–68 | Project v4 RpgDatabase with v2/v3 backward reading; Project v5 RPG reference validation and persistent lifecycle-event bindings |
| 69–71 | Stable equipment identity and socket/loadout persistence without arbitrary socket caps; RPG runtime inventory/progression/loadout/party/currency save state; actor snapshots and non-baked derived stats/tags/abilities |
| 72–73 | Reward transaction/rollback and public state replacement; Project v6 canonical GameplayLibrary ownership and RPG ability reference validation; Phase 7 closure/FROZEN at v0.73.0a73 |

Phase 7B Batches 75–92 are recorded as the flexible RPG/Battle Core implementation;
Batch 93 records cross-system closure PASS / **FROZEN at v0.93.0a93**. The supplied
handoff lists build composition, resources, interaction/outcomes, status/state,
targeting/formations, lifecycle/summon/transform, objectives/escape, scheduling,
action timing, sequences/co-op actions, gauges, reactions, AI/boss phases/custom
hooks, deterministic RNG/snapshot, and action cost transactions. Exact contracts
and regression results cannot be revalidated because these modules are absent.
No unsupported Batch 74 detail or new mechanics are inferred.

## Batch 94 verified source contract

`src/asteria/presentation/battle.py` defines:

- `BattleVisualAnchor`: finite numeric x/y/depth and a nonempty facing identifier.
  Facing is not restricted to a left/right enumeration.
- `BattleCombatantVisual`: member, sprite-sheet and clip-set identifiers, typed
  anchor, sorted semantic-role mappings. Missing or empty role maps use default
  idle/attack/hit/ko mappings. Unknown roles return `None` from `clip_for`.
- `BattlePresentationScene`: unique combatant member identifiers, background and
  camera identifiers, `visual_for` lookup (`KeyError` for missing members), and
  `to_data`/`from_data` with schema `asteria.battle_presentation_scene`, version 1.
  Asset identifiers are data; asset existence and runtime playback are not checked.
- `BattlePresentationEvent`: sequence, event kind, source identifier and dict
  payload. Scene data supports JSON serialization; arbitrary event payloads are
  not validated as JSON-safe or deeply immutable.
- `BattlePresentationCoordinator`: monotonically increasing, in-memory event
  sequence and an insertion-ordered queue. `drain` returns a tuple and clears the
  queue without resetting the sequence. Start/finish are idempotent with respect
  to the active flag; cue/hook/custom ingestion is not gated by that flag.
- `consume_timeline_cues`: checks `PresentationCue` instances and copies each
  cue's serialized data and timeline identifier into events, in input order.
  It does not run an ActionTimelinePlayer or execute gameplay.
- `attach`/`detach`: observe a single lifecycle bus, avoid duplicate attachment
  to that bus, and unsubscribe on detach. Finish does not implicitly detach.
- Custom events carry an event identifier and caller payload. No gameplay
  execution or renderer/audio/editor backend is implemented by this package.

The five supplied tests specify scene round-trip/role lookup, ordered cue
forwarding, selected lifecycle hook observation, custom events without a UI
backend, and attach/detach behavior. Their execution is not a passing result in
this distribution; see [audit](CONSISTENCY_AUDIT.md).

## Freeze and completion boundary

Batch 94 is a presentation foundation above the recorded frozen core, not a new
combat model. Damage, targeting legality, costs, turn order, status meaning,
weakness/break rules and outcomes stay with Battle Core. Rendering, automatic
animation transitions, assets, UI/VFX/camera and playable integration are deferred.
See [architecture](ARCHITECTURE.md), [handoff](../PROJECT_HANDOFF.md), and
[next-phase plan](NEXT_PHASE_PLAN.md). Historical batch/closure records retain
their original assertions; they do not certify this revision's missing code.
