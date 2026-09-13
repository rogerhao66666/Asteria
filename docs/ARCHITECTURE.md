# Asteria Active Architecture

Current full cumulative base: v0.94.0a94. Current incremental development state: v0.97.0a97 (Batch 95 + Batch 96 + Batch 97 overlays).
Phase 7B Battle Core remains FROZEN at Batch 93 / v0.93.0a93.
Batch 94 adds presentation foundation; Batch 95 adds runtime/animation integration; Batch 96 adds resolved combat-feedback state and VFX/audio queues; Batch 97 adds camera/screen hit feedback and target-indicator projection.

This is the active architecture through Batch 97 / v0.97.0a97. Historical batch
documents and the copies under `docs/history/` explain prior checkpoints only;
they cannot reopen frozen ownership boundaries or redefine the current roadmap.

## Canonical layers and ownership

- Core: entities/scenes and lifecycle bus; assets and graphics/render/animation
  provide reusable resource and visual mechanisms.
- Editor and runtime: author and execute shared Project data through their
  existing backends. Python authoring and Event VM connect to these mechanisms.
- Generic gameplay: stats/resources/tags, conditions, formulas, modifiers,
  effects/states, AbilityRuntime and ActionTimelinePlayer.
- RPG: definitions, RpgDatabase, mutable runtime/save state and resolved build
  composition; Battle Core handles authored combat policies and outcomes.
- Presentation: scene/combatant visual data, ordered events, and a backend-neutral
  runtime that maps semantic animation roles onto existing sprite/animation/render
  abstractions. Later adapters own VFX/audio/UI/camera integration.

`Project` schema v6 owns GameplayLibrary, RpgDatabase and lifecycle bindings.
RpgActorRuntime owns intrinsic mutable actor state; `resolve_actor_build` resolves
supplied class/progression/allocation/loadout/passive/evolution inputs for consumers.
No second character/equipment/ability model is introduced by presentation.

## Observed presentation dependency and flow

`presentation/battle.py` imports LifecycleEvent/HookBus from `core/lifecycle.py`
and PresentationCue from `gameplay/action_timeline.py`. All dependencies are
present. Core/gameplay/RPG have no imports of asteria.presentation.

1. Gameplay executes effects and battle rules, emitting lifecycle events.
2. ActionTimelinePlayer executes GAMEPLAY_ABILITY cues via AbilityRuntime and
   emits other cues as PresentationCue values.
3. Callers explicitly feed those cues to the coordinator; attach observes hooks.
4. The coordinator queues events for later renderer/audio/UI adapters to drain.

Batch 95 adds an explicit presentation runtime after the Batch 94 coordinator. It
selects authored animation roles/clips, advances existing AnimatorState objects,
observes already-resolved lifecycle KO/revive state, and produces TextureDraw
commands. Asset resolution remains injected; no pygame/Qt dependency enters the
presentation package. Scene schema v1 remains separate from Project v6.

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

Game authors own rules and balance; Battle Core owns combat execution.
Presentation owns visual binding data and event ordering, not gameplay decisions.
Ordering is deterministic for a given input order. The queue is in memory;
its payloads are shallow dicts, not deeply immutable data, and it is not a
persisted whole-engine replay mechanism. See [current spec](CANONICAL_SPEC.md)
and [audit](CONSISTENCY_AUDIT.md).


## Batch 95 runtime flow

`BattlePresentationCoordinator` -> ordered `BattlePresentationEvent` ->
`BattlePresentationRuntime` -> `BattleCombatantAnimator` -> existing
`AnimatorState` / `AnimationClipSet` / `SpriteSheet` -> `TextureDraw`.

Attack and Hit are transient presentation roles and return to Idle when their
non-looping clip completes. KO/revive are driven by lifecycle events, never by
checking HP inside presentation. Runtime snapshot/restore covers presentation
state only and is not a Battle Core snapshot replacement.


## Batch 96 resolved-feedback flow

`BattlePresentationCoordinator` may translate an existing `ValueResolutionResult` / `OutcomeResolutionResult` into a `RESOLVED_VALUE` presentation event and an existing `GaugeCompositionResult.thresholds` sequence into `GAUGE_THRESHOLD` events. These adapters copy resolved primitives only; they never invoke interaction, gauge, target, damage or lifecycle rules.

`BattleFeedbackRuntime` consumes those events plus ActionTimeline VFX/AUDIO cues. `BattleFeedbackProfile` is project data mapping arbitrary outcome tags, dispositions and threshold ids to labels such as WEAK, RESIST, IMMUNE, ABSORB or BREAK. Therefore the engine still does not know what an element, weakness or Break mechanic means. Floating values, labels and VFX have deterministic lifetimes; pending audio is an explicit one-shot drain queue; presentation state supports snapshot/restore. Final rendering of text/numbers remains adapter-owned.


## Batch 97 camera/target presentation flow

`ActionTimeline CAMERA/SCREEN_FX cues -> BattlePresentationCoordinator -> BattleCameraFeedbackRuntime -> derived Camera2D view / screen-effect state`. Canonical target selection is mirrored through `push_target_selection()` and projected using existing `BattlePresentationScene` anchors. No target resolver or Battle Core rule is invoked by this path.


## Batch 98 Battle HUD projection

`BattleResourceRuntime / GameplaySubject.states -> BattleHudRuntime -> BattleHudMember -> BattleHudGauge / BattleHudStatusIcon`.

The HUD path is deliberately read-only. `BattleHudProfile` supplies project-owned labels, icons, ordering and visibility. HP/MP are convenience defaults rather than engine semantics; arbitrary resources and statuses remain valid. The presentation layer copies canonical resource values and active-state records and does not mutate, re-resolve, or infer gameplay rules. Final bar/icon/text drawing is renderer/UI-adapter owned.

## Batch 99 Battle turn/timeline projection

`BattleScheduler.pending() / BattleActionTimingRuntime.pending() -> BattleTurnTimelineRuntime -> BattleTurnTimelineView`.

This path is read-only. It mirrors canonical scheduling and timing into upcoming-turn and pending-cast presentation entries. Presentation may cap visible entries and compute a visual progress ratio from canonical timestamps, but it cannot pop/shift turns, interrupt/resolve actions, validate targets, or infer gameplay ownership. Final timeline widgets remain UI/renderer-adapter owned.

## Batch 100 battle result/reward projection

`BattleOutcome + RewardApplicationResult -> BattleResultPresentationRuntime -> BattleResultView`.

The result layer consumes only resolved battle outcome and already-applied reward/progression outputs. Loot RNG, reward application, progression mutation and outcome criteria remain RPG/Battle Core responsibilities. Presentation owns labels/layout only.

## Batch 101 unified Battle UI composition

`BattlePresentationFrame + BattleHudMember[] + BattleTurnTimelineView + BattleFeedbackRuntime + BattleCameraFeedbackFrame + BattleResultView -> BattleUiComposer -> BattleUiFrame`.

The composed frame is renderer-neutral and contains world sprite draws plus UI panel/text/gauge/icon/marker commands and already-authored VFX/screen-FX metadata. This creates a single rendering seam without introducing a second gameplay model. Renderer backends consume this frame; they do not own battle semantics.

## Batch 102 concrete Battle UI rendering seam

`BattleUiFrame -> BattleUiRenderer + BattleUiTheme -> Battle UI backend`.

The executor is backend-neutral and deterministic. `HeadlessBattleUiBackend` records operations for tests; `PygameBattleUiBackend` converts those operations to pygame-ce primitives and text without exposing pygame objects back into core/gameplay/RPG layers. Theme/palette/font sizes are project presentation policy. Battle semantics remain upstream.

## Batch 103 Battle Screen orchestration

`BattlePresentationCoordinator`
→ `BattlePresentationRuntime` / `BattleFeedbackRuntime` / `BattleCameraFeedbackRuntime`
+ read-only `BattleHudRuntime` / `BattleTurnTimelineRuntime`
+ `BattleResultPresentationRuntime`
→ `BattleUiComposer`
→ `TextureRenderer` + `BattleUiRenderer`.

`BattleScreenRuntime` owns this wiring and presentation clock only. The canonical battle controller remains responsible for current actor, action execution, scheduler advancement, targeting, resources/states, rewards and battle outcome. The screen runtime may mirror those resolved states but cannot derive or mutate them.

## Batch 104 generic resource presentation

Canonical battle resources remain gameplay-owned. `BattleHudResourceStyle` is the presentation-policy seam between generic resource state and runtime UI. It carries visual role, grouping, priority, compactness and visibility metadata while `BattleHudRuntime` carries canonical values unchanged into a presentation view.

Asteria distinguishes:
- gameplay resource semantics: project/Battle Core owned,
- presentation role: project presentation policy,
- actual drawing: runtime UI adapter/theme owned.

This lets a project use HP/MP, BP/SP, guard/break, shields, ATB, cast/recovery, limit meters, shared meters, or entirely custom resources without adding engine-specific battle rules.

## Batch 105 adaptive party/combatant presentation

`BattlePartyLayoutPolicy` is a presentation-only capacity layer between canonical `BattleHudMember` projections and `BattleUiComposer`.

The policy resolves:
canonical member list
+ explicit project presentation zones
+ current/focused member
+ available screen height
→ expanded / compact / minimal visible HUD layout
+ overflow metadata.

The policy can reduce visible detail but cannot reduce canonical party membership. Resource detail selection uses Batch 104 presentation priority metadata. Gameplay side/formation semantics remain outside this layer.

`BattleScreenRuntime` now supplies explicit member placement to `BattleUiComposer`. Optional project side→zone mappings are supported; otherwise side identifiers are assigned to visual zones deterministically without interpreting their names.

## Batch 106 generic action-menu presentation

Canonical action availability remains gameplay/controller-owned. `BattleActionMenuRuntime` receives opaque `BattleActionEntry` values and owns only browsing state: category, query, page and cursor.

This separates:
- action definition/execution: gameplay-owned,
- action availability: canonical controller-owned,
- action presentation metadata: project-owned,
- browsing/layout: presentation-owned.

The resulting menu can represent ordinary abilities, equipment actions, items, summons, stances, transformations, multi-step workflows or project-defined commands without a fixed engine command list.

## Batch 107 generic action workflow/composition

`BattleActionWorkflowRuntime` is a transient interaction-state seam between generic action presentation and canonical gameplay execution.

The flow is:
canonical controller supplies workflow definition/options
→ presentation collects selections
→ presentation returns opaque selection payload
→ canonical controller interprets/resolves/executes.

This supports alchemy, concoction, rune/card composition, summons, transformations and other multi-step commands through one mechanism without hardcoding any of those systems.

## Batch 108 Presentation Director

The presentation execution path is now:

Battle Core / ActionTimeline resolved output
→ BattlePresentationCoordinator
→ BattlePresentationDirector
→ Animation / Feedback / Camera presentation runtimes
→ BattleUiComposer / render adapters.

The Director is a choreography scheduler, not a gameplay scheduler. It owns presentation release time, beat labels, same-time priority and presentation-clock hold windows only. Default policy is passthrough for backward compatibility.

## Batch 109 animation timing / transition layer

`BattleAnimationTimingProfile` sits beside the Presentation Director and configures how semantic animation roles are visually played rather than when gameplay occurs.

The path is:
Director releases presentation event
→ BattlePresentationRuntime selects semantic role/clip
→ timing profile controls playback rate, transition easing and recovery hold
→ renderer receives one draw or a temporary previous/current cross-fade pair.

`BattleHitRhythm` is a reusable presentation cadence utility. It emits only timing offsets and has no access to ability execution or Battle Core hit resolution.

## Batch 110 coordinated presentation layering

The premium presentation path is now:

resolved presentation events
→ Presentation Director (release timing / holds)
→ Presentation Layering Runtime (shared staging group / channel metadata)
→ animation, feedback/VFX/audio and camera/screen-FX runtimes
→ UI/render adapters.

The layering runtime works on copied presentation cue payloads. It enables one authored impact to coordinate camera strength, VFX layer/intensity, screen-FX ordering and audio gain/bus without introducing gameplay coupling.

## Batch 111 premium adaptive Battle UI

`BattleUiPolishProfile` sits above the generic Batch 104–107 presentation view models and below `BattleUiComposer`.

Generic presentation state
→ adaptive layout/polish profile
→ semantic UI roles
→ `BattleUiTheme`
→ backend renderer.

This gives Asteria an opinionated, beginner-friendly default visual hierarchy while keeping layout/theme/prefix/spacing values project-owned and replaceable.

## Batch 112 Battle Presentation milestone freeze

Batches 104–112 establish the complete presentation architecture:

generic canonical projections
→ resource/party/action/workflow presentation policy
→ Presentation Director
→ animation timing and transition policy
→ coordinated channel layering
→ premium adaptive UI composition/theme
→ backend adapters.

Diverse validation confirms this architecture supports substantially different RPG battle models without reference-game semantics. The Battle Presentation milestone should now be treated as frozen unless a later runtime/UI integration test proves a genuine generic abstraction gap.

## Combined Battle System freeze boundary

The full battle execution architecture is frozen:

Battle Core resolved state/events
→ Presentation Coordinator
→ Presentation Director
→ Presentation Layering
→ animation/feedback/camera
→ adaptive UI composition
→ backend render adapters.

Presentation is downstream-only. It may transform timing, layout, visual/audio intensity and labels from supplied perspective, but cannot invoke gameplay resolution or mutate canonical battle state.

## Runtime RPG UI — Character Screen Foundation

The Runtime RPG UI path begins with canonical read-only projection:

RPG mutable runtime/definitions
→ `ResolvedActorBuild`
→ `CharacterScreenRuntime`
→ `CharacterScreenView`
→ future adaptive runtime UI composer/renderer.

Optional equipment/progression views remain read-only supporting projections. Project-owned `CharacterScreenProfile` supplies labels, section ordering and visual resource roles rather than gameplay semantics.

## Runtime RPG UI — Party / Formation

Party presentation is downstream from canonical roster/formation state:

canonical roster membership + optional `BattleFormationRuntime`
→ `PartyScreenRuntime`
→ `PartyScreenView`
→ future adaptive runtime UI composer/renderer.

Group membership and formation tags remain project data. Presentation focus and overflow are local UI state only.

## Runtime RPG UI — Equipment / Loadout

canonical EquipmentLoadout + EquipmentDefinition catalog
→ `EquipmentScreenRuntime`
→ generic slot/item/socket/growth/candidate view models
→ future adaptive Runtime RPG UI composer/renderer.

Mutation remains outside presentation. Equipment browsing may expose canonical eligibility/reasons but cannot equip, detach, unlock growth or consume inventory.

## Runtime RPG UI — Ability / Passive Collections

`ResolvedActorBuild` + optional `ActorAbilityState` + canonical ability/passive catalogs
→ `AbilityScreenRuntime`
→ generic collection/group/loadout view models
→ future adaptive Runtime RPG UI composer/renderer.

Ownership and active passive state remain canonical data. Presentation only
projects provenance and collection organization.

## Runtime RPG UI — Progression Graph / Skill Tree

`ProgressionAllocationRuntime` + `ProgressionGraphDefinition`
→ `ProgressionScreenRuntime`
→ graph/node/prerequisite/cost view models
→ future adaptive Runtime RPG UI composer/renderer.

Canonical `preview_allocate()` remains the single source of allocation eligibility; presentation performs no progression mutation.

## Runtime RPG UI milestone

Canonical RPG state
→ read-only Runtime RPG presentation models
→ reusable adaptive UI components/templates
→ renderer/backend adapters.

The next architecture phase is Engine Editor GUI / RPG UX, editing the same
canonical model rather than maintaining an editor-only data model.
