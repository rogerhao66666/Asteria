# Asteria Current Specification and Status

## Authority and scope

Current full cumulative base: v0.94.0a94, assembled from v0.93 full source plus
the Batch 94 delta. Current incremental development state: **v0.97.0a97**, which
adds Batch 95 animation/runtime integration, Batch 96 resolved combat-feedback presentation, and Batch 97 camera/screen/target-indicator presentation. Historical batch
documents preserve design and closure detail at their original checkpoints.

This active specification is authoritative through Batch 97 / v0.97.0a97. The active architecture, handoff, and next-phase plan must agree with
it. Batch-specific documents and `docs/history/` are historical evidence and
must not be read as current work orders.

## Engine and Phase 5–7 foundation

Core lifecycle/entity/scene mechanisms, asset registry/import/cache, graphics,
animation/render, editor/runtime preview, Event VM/dialogue and Python authoring
are included. Generic gameplay provides stats/resources/tags, formulas,
modifiers/effects, states, conditions/triggers, abilities and Timeline seams.
Phase 7 extends these with actor/class, inventory/equipment/attachments,
enemy/encounter/rewards, progression/party/battle and persistent runtime state.

Phase 7 milestones (supported by corresponding BATCH60–73 docs and tests):


| Batches | Recorded delivered scope |
| --- | --- |
| 60–64 | Actor/class; items/equipment/sockets/attachments; loadout contributions and consumables; enemy/encounter/loot/rewards; generic progression/rank |
| 65–66 | Party, deterministic turn order, thin BattleRuntime; universal lifecycle hooks, Event VM bridge, outcome/reward/progression handoff |
| 67–68 | Project v4 RpgDatabase with v2/v3 backward reading; Project v5 RPG reference validation and persistent lifecycle-event bindings |
| 69–71 | Stable equipment identity and socket/loadout persistence without arbitrary socket caps; RPG runtime inventory/progression/loadout/party/currency save state; actor snapshots and non-baked derived stats/tags/abilities |
| 72–73 | Reward transaction/rollback and public state replacement; Project v6 canonical GameplayLibrary ownership and RPG ability reference validation; Phase 7 closure/FROZEN at v0.73.0a73 |


## Phase 7B implemented composition

| Batch | Canonical source under src/asteria/rpg | Delivered contract |
| --- | --- | --- |
| 75 | actors.py | ClassAssignment: opaque roles, enabled layers, deterministic priorities, independent progression tracks; no two-job limit |
| 76 | ability_build.py, actors.py | Learned abilities, active passives, evolution selection and ability provenance |
| 77 | progression_graph.py | Ranked graph nodes, currencies, prerequisites, allocation preview and dependency-aware refund |
| 78 | items.py | Project-defined slot capacity and capability requirements, equipment instances and attachments |
| 79 | equipment_growth.py | Per-instance counters/ranks and rule-driven growth contributions |
| 80 | resolved_build.py | ResolvedActorBuild with effective values, ability grants, equipment/class identities and contribution provenance |
| 81 | battle_resources.py | Authored resource/gauge policies and lifecycle |
| 82 | interactions.py | Rule-driven interaction/value/outcome resolution |
| 83 | battle_states.py | Status/state restrictions and lifecycle |
| 84 | targeting.py | Relation/filter/formation/position selectors |
| 85 | battle_lifecycle.py | Participation, summon/remove/transform, objectives and escape |
| 86 | battle_scheduler.py | Round, speed and continuous scheduling |
| 87 | battle_timing.py | Cast/startup/recovery/interrupt and timeline shifts |
| 88 | action_sequences.py | Multi-hit, combo and cooperative sequences |
| 89 | gauge_composition.py | Gauge threshold → state composition |
| 90 | reactions.py | Deterministic reaction queue and recursion protection |
| 91 | enemy_ai.py | AI rules, boss phases and custom action hooks |
| 92 | battle_snapshot.py, battle_transactions.py | RNG/snapshot continuation and action-cost reservation/commit/refund |
| 93 | tests/test_rpg_battle_core_closure.py | Cross-system closure; Battle Core FROZEN at v0.93.0a93 |

`resolve_actor_build` combines the supplied runtime, progression, allocations,
loadout, passives and evolution rules. Intrinsic mutable state stays owned by
RpgActorRuntime. The resolved summary is inspection data, not save-state;
its frozen dataclass does not imply deeply immutable contained objects.
Capabilities are derived from effective tags. This is the shared resolution seam
for consumers; it does not imply every future GUI or presentation adapter exists.

Project serialization writes schema v6 and accepts v2–v6. It owns canonical
GameplayLibrary and RpgDatabase data and lifecycle bindings; RPG runtime save
state and battle snapshots have their own schemas. Battle presentation scene
schema v1 is separate and has no new Project persistence integration in Batch 94.

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


The five Batch 94 foundation tests remain part of the regression suite. Batch 95
adds runtime/reference tests on top of them. Exact full-suite counts for the
current incremental package are recorded in the Batch 95 closure/handoff.

## Batch 95 verified source contract

`src/asteria/presentation/battle_runtime.py` adds a backend-neutral presentation
runtime after the Batch 94 coordinator. It resolves authored clip sets and sprite
sheets through injected callbacks, maps semantic Idle / Attack / Hit / KO roles,
advances the existing `AnimatorState`, and emits existing `TextureDraw` values.
Attack/Hit are transient and return to Idle when their non-looping clips complete.
KO/removal/revive presentation is driven only by already-resolved lifecycle events.
The runtime supports deterministic presentation-only snapshot/restore and rejects
out-of-order presentation events. It does not call Battle Core resolvers.

Batch 95 reference data demonstrates a hero and archive-mimic using Asteria-original
pixel-art assets. These are replaceable development assets, not final commercial art.

## Freeze and completion boundary

Damage, targeting legality, costs, scheduling, status meaning, weakness/break
rules and outcomes remain with frozen Battle Core. Batch 95 adds visible combatant
animation/render-command integration only. Damage numbers, VFX/audio state, camera hit feedback, target indicators, and HP/MP/arbitrary-gauge/status HUD view-state are now covered through Batch 112. Final renderer/UI adapters, turn/timeline UI, and result/reward presentation remain future Battle Presentation work. See [architecture](ARCHITECTURE.md),
[handoff](history/PROJECT_HANDOFF.md), and [next-phase plan](NEXT_PHASE_PLAN.md).


## Batch 96 verified source contract

Battle Presentation may consume resolved combat feedback but may not derive it. `push_resolved_value()` accepts only `ValueResolutionResult` or `OutcomeResolutionResult` and preserves the already-resolved value, disposition and outcome tags. `push_gauge_result()` accepts only `GaugeCompositionResult` and preserves already-crossed threshold results. Project-owned `BattleFeedbackProfile` maps these generic primitives to visible labels.

ActionTimeline VFX and AUDIO cues remain presentation-only. `BattleFeedbackRuntime` owns deterministic temporary view-state, lifetime expiry, one-shot audio draining and presentation snapshot/restore. It does not mutate Battle Core or call its resolvers. Final number/text/UI rendering is intentionally deferred to renderer/UI adapters rather than introducing a new backend dependency.


## Batch 97 verified source contract

Battle Presentation may consume authored `CAMERA` / `SCREEN_FX` Timeline cues and already-selected canonical target IDs. `BattleCameraFeedbackRuntime` stores deterministic camera impulses, screen-effect view state and target-indicator projection only. It does not call target resolvers, infer target legality, alter Battle Core clocks, compute hit/damage, or own gameplay state. The caller's base `Camera2D` remains unchanged.


## Batch 98 verified source contract

`src/asteria/presentation/battle_hud.py` adds a backend-neutral, read-only HUD projection over canonical battle resources and gameplay active states. `BattleHudProfile` owns project-defined labels, icon asset ids, ordering and visibility. HP and MP are convenience defaults only; arbitrary resource ids remain valid and may be displayed generically or hidden by policy. Status icons are likewise project-mapped, with an optional generic fallback.

`BattleHudRuntime` copies `BattleResourceValue` current/min/max/overflow/normalized/full values and `ActiveState` id/stacks/remaining/source data. It does not spend/restore resources, apply/remove states, resolve KO, infer threshold crossings, or assign gameplay semantics. HUD state ordering and snapshot/restore are deterministic; actual typography, bars, icon layout and backend drawing remain UI/renderer-adapter responsibilities.

## Batch 99 verified source contract

`BattleTurnTimelineRuntime` is a backend-neutral read-only projection over canonical `BattleScheduler` and optional `BattleActionTimingRuntime` state. Upcoming turn order, ready times, scheduler mode/round/time and pending action timing are copied from those runtimes. A caller may mark a canonical current actor; presentation does not infer ownership.

Cast/action `remaining` and `progress` are visual values derived only from canonical timing timestamps and current scheduler time. Presentation never pops/shifts scheduler entries, resolves abilities, interrupts actions, validates targets, or mutates Battle Core. The visible-turn cap and final layout are presentation policy.

## Batch 100 verified source contract

`BattleResultPresentationRuntime` accepts canonical `BattleOutcome` plus optional already-applied `RewardApplicationResult`. It mirrors outcome sides/objectives, applied currency/item rewards, and canonical progression advance results including old/new totals, ranks, crossed milestones and milestone-granted abilities/tags.

Presentation does not call `roll_reward()`, `RewardRuntime.apply()`, progression mutation, or battle outcome resolution. Result/reward labels are project-owned presentation policy.

## Batch 101 verified source contract

`BattleUiComposer` consumes Battle Presentation view-state only and produces a backend-neutral `BattleUiFrame`. The frame combines existing combatant texture draws with presentation panel/text/gauge/icon/marker commands plus VFX/screen-FX metadata.

The composition layer owns layout policy only. It does not query or mutate Battle Core and cannot resolve targets, advance scheduler time, alter resources/states, apply rewards, or determine battle outcome. Side placement is caller-supplied presentation metadata. Concrete renderer backends remain separate adapters.

## Batch 102 verified source contract

`BattleUiRenderer` executes an already-composed `BattleUiFrame` against a UI backend using a project-owned `BattleUiTheme`. The renderer has no Battle Core input surface.

`HeadlessBattleUiBackend` provides deterministic renderer verification. `PygameBattleUiBackend` is an optional concrete adapter for panels, gauges, icons, target markers, text, and simple screen-flash effects. Authored VFX remains a separate effect-adapter concern. Missing icon assets may use a presentation fallback but never alter gameplay state.

## Batch 103 verified source contract

`BattleScreenRuntime` is the presentation-only orchestration boundary. It fans one ordered `BattlePresentationCoordinator` event stream into animation, resolved feedback and camera/target presentation runtimes; mirrors canonical battle resources/states and scheduler/action-timing state through the existing HUD/timeline projections; composes a `BattleUiFrame`; and sends world sprite draws plus UI commands to existing renderer adapters.

`sync_battle()` does not call the mutating/side-effectful Battle Core turn path. Current actor identity is supplied by the caller. `render()` drains authored audio cues once and does not execute gameplay. Composite snapshot/restore covers presentation state only and does not replace the Battle Core snapshot.

## Batch 104 verified source contract

Battle-facing resources are generic canonical resources with project-owned presentation metadata. HP/MP remain optional starter presets only. A project may expose arbitrary resource identities and map each one to a presentation role such as bar, segmented bar, pips, number, icon stack, ring, action gauge, timeline, contextual, hidden, or a project-defined custom role.

Presentation metadata cannot modify resource math, costs, thresholds, turn readiness, action availability, or any other gameplay meaning. Gameplay resource freedom and presentation density are separate concerns.

## Batch 105 verified source contract

Canonical party/combatant count is not constrained by runtime HUD capacity. A project owns presentation placement, density and overflow policy separately from gameplay sides/formations.

The default adaptive HUD may reduce detail from expanded to compact to minimal and may summarize hidden viewport members as overflow, but it must preserve the canonical member set and keep a supplied focused/current member visible when possible.

Presentation placement zones are generic metadata. New orchestration code must not infer game semantics from labels such as `hero`, `enemy`, `player`, or `foe`.

## Batch 106 verified source contract

Battle action presentation is not a fixed command taxonomy. The canonical controller may supply arbitrary opaque action entries with project-owned labels, categories, kinds, icons, cost text, tags and availability metadata.

The presentation runtime may browse, group, sort, page, filter and select those opaque entries. It may not execute an action or recompute ownership, costs, conditions, cooldowns, target legality, resource sufficiency, or any other gameplay availability rule.

## Batch 107 verified source contract

A battle action may require a project-defined multi-step input workflow before canonical execution. Presentation may collect opaque selections across ordered steps and return them to the canonical controller.

Workflow presentation must not interpret recipes, consume materials/resources, resolve derived abilities/effects, validate targets, or execute the resulting battle action. Alchemy/concoction is a reference use case, not an engine semantic.

## Batch 108 verified source contract

Already-resolved battle presentation events may pass through a project-authored Presentation Director before reaching animation, feedback and camera runtimes. The Director may delay presentation events, order same-time visual cues, label choreography beats and pause presentation clocks for authored hold/hit-stop windows.

Presentation direction cannot pause or alter canonical gameplay time, Battle Core scheduling, action resolution, resources, targets, outcomes or rewards. With no authored direction metadata, event delivery remains immediate.

## Batch 109 verified source contract

Battle animation presentation may use project-authored playback rate, transition duration/easing and transient recovery hold per semantic animation role. These settings affect presentation clocks and render blending only.

A presentation multi-hit rhythm may generate visual timing offsets for already-resolved repeated impacts, but cannot create or remove gameplay hits. Animation blending cannot change canonical combatant state, position, resources, lifecycle, target selection, scheduler state or action results.

## Batch 110 verified source contract

Already-resolved presentation cues may share project-authored staging metadata such as group, visual/audio layer, intensity, gain, bus and priority. These fields coordinate presentation channels only.

Camera/VFX/screen-FX/audio layering may scale or order copied presentation payloads but cannot change action resolution, hit count, resource values, targets, scheduler state, lifecycle or outcomes.

## Batch 111 verified source contract

Asteria's default Battle UI may provide opinionated premium hierarchy, spacing, focus emphasis and interaction-surface styling, but all such behavior remains presentation policy.

The default UI must continue to accept arbitrary resources, party sizes, action categories, workflow steps and project command types without introducing fixed JRPG command semantics or gameplay limits. Focus/selection/disabled visual roles consume supplied presentation/controller state only.

## Batch 112 Battle Presentation closure contract

The Battle Presentation milestone is validated against multiple distinct battle archetypes and must remain reference-game-neutral.

No presentation path may require canonical resource names such as HP/MP, fixed party counts, fixed action categories, fixed scheduler modes, alchemy-specific workflow semantics, or semantic side identifiers such as hero/enemy.

When explicit presentation placement is unavailable, side/group identifiers may be used only as opaque grouping keys with deterministic presentation allocation.

## Combined Battle System milestone freeze

Battle Core 75–93 and Battle Presentation 94–112 are frozen as one verified milestone.

Battle result presentation is perspective-neutral by default. Victory/Defeat/Escape wording may be derived only from explicitly supplied viewer-side IDs or an explicitly supplied presentation disposition. Canonical battle outcome data is never rewritten by presentation.

## Batch 113 Runtime RPG UI contract

Character Screen presentation consumes the canonical immutable `ResolvedActorBuild` and optional already-existing runtime projections such as equipment loadout and progression runtime.

The default character screen must support arbitrary stat/resource IDs, resource presentation roles, equipment slot IDs/capacities, ability IDs/provenance, progression tracks, tags, capabilities, class assignments and active passives. It must not assume HP/MP, fixed equipment slots, fixed class count or one progression model.

Character-screen navigation is presentation state only and cannot mutate RPG state.

## Batch 114 Runtime Party UI contract

Runtime Party UI consumes caller-owned canonical roster membership plus optional canonical `BattleFormationRuntime` and projects them read-only.

Party group IDs and formation slot IDs/tags are opaque project-defined data. The engine must not assume a four-person party, fixed active/reserve counts, hero/enemy semantics, or front/back gameplay behavior.

Presentation may limit visible rows and retain the focused member in the visible subset, but these are display policies only and cannot change canonical roster membership/order or formation placement.

## Batch 115 Runtime Equipment UI contract

Runtime Equipment UI consumes canonical `EquipmentLoadout` and canonical equipment definitions read-only.

Equipment slot IDs, capacities, tags, socket IDs, attachments, growth IDs and granted abilities are project-defined. The default UI must not require weapon/armor/head/body semantics.

Candidate eligibility must come from canonical RPG capability rules or controller-supplied resolved eligibility. Search, paging and current selection are presentation state only.

## Batch 116 Runtime Ability/Passive UI contract

Runtime Ability UI consumes canonical resolved ability/passive state read-only.
Ability IDs, passive IDs, categories, tags and provenance are project-defined.

The presentation layer must not assume Attack/Skill/Item/Defend, a fixed number
of skill slots, one passive capacity model, or one source of ability ownership.

Collection filtering, grouping, overflow, active tab/category and selected
entry are presentation state only.

## Batch 117 Runtime Progression UI contract

Runtime Progression UI consumes canonical progression graph/allocation state read-only. Graph IDs, node IDs, tags, prerequisite topology, rank counts, currencies and costs are project-defined.

Presentation may call canonical preview APIs to expose allocatability and reasons, but it must not allocate/refund progression or duplicate progression legality rules.

Search, graph/node selection and visible limits are presentation state only.

## Runtime RPG UI milestone freeze

Batches 113–118 form the frozen Runtime RPG UI foundation: Character, Party /
Formation, Equipment / Loadout, Ability / Passive, Progression Graph and
Inventory / Item presentation.

All layers are read-only projections over canonical RPG state. UI-owned
selection, grouping, search, paging and overflow policies must never become
gameplay constraints.
