# Asteria Project Handoff

Current canonical baseline: **v0.159.0 Complex Reference RPG acceptance**.
The active checkout is `/Users/roger/Documents/Vscode/Asteria`; do not assemble
it from older zip files or the former `ChatGPT/Asteria` copy. Earlier batch
instructions below are retained as provenance and are not the current assembly
procedure.

## Current development baseline

Use the checked-in v0.159.0 tree directly. Open
`reference_projects/complex_reference_rpg/project.asteria.json` from the
Editor with **File → Open Project**, then use **Run Project**. The acceptance
flow starts with Runtime **New Game** and keeps Player Save inside Runtime;
Editor Save remains project authoring only.

Phase 7 RPG Toolkit remains FROZEN at v0.73.0a73. Phase 7B Battle Core remains **FROZEN at Batch 93 / v0.93.0a93**. Batch 94 established Battle Presentation scene/event foundations; Batch 95 added combatant sprite/animation runtime integration; Batch 96 adds resolved combat feedback state and VFX/audio cue routing; Batch 97 adds presentation-only camera/screen hit feedback and canonical target-indicator state; Batch 98 adds read-only Battle HUD view-state for canonical resources and active statuses. Do not redesign or re-resolve frozen Battle Core behavior.

## Batch 98 delivered

`BattleHudRuntime` mirrors canonical `BattleResourceRuntime` values and active gameplay states into backend-neutral HUD view-state. HP/MP are profile defaults only; arbitrary project-defined gauges and state-icon mappings are supported. The HUD never mutates gameplay or infers KO, thresholds, status semantics, or resource rules. HUD state supports deterministic snapshot/restore.

## Batch 97 delivered

`BattleCameraFeedbackRuntime` consumes ActionTimeline `CAMERA` / `SCREEN_FX` cues and already-selected target IDs only. Deterministic camera impulses derive a presentation camera view without mutating the caller's base `Camera2D`. Screen effects remain backend-neutral view state, including hit-stop metadata; they do not freeze Battle Core simulation.

`BattlePresentationCoordinator.push_target_selection()` mirrors canonical selection into presentation without resolving legality or existence. Target indicators project existing battle-scene visual anchors into screen space; members without visuals remain selected canonically but are omitted from the visual frame. Camera/screen/target state supports deterministic lifetime and snapshot/restore.

## Architecture invariants

Mechanism → policy → game-defined rules. GUI and Python authoring share canonical data. Core/gameplay/RPG remain backend-neutral. `GAMEPLAY_ABILITY` Timeline cues execute gameplay; animation/VFX/audio/camera/light/screen cues remain presentation. Presentation must never recompute damage, targeting, weakness, Break/Stagger, costs, turn ownership, AI decisions or KO criteria.

No second character/equipment/ability model exists in presentation. Existing Actor/Class/Progression/Equipment/Passive/Ability data resolves through canonical RPG build/battle systems before presentation consumes results.

## Current Battle Presentation coverage

- Batch 94: scene/combatant bindings, ordered coordinator, lifecycle/timeline bridge.
- Batch 95: Idle/Attack/Hit/KO animation, lifecycle KO/revive/visibility, TextureDraw frame output, presentation snapshot.
- Batch 96: resolved value feedback, WEAK/RESIST/IMMUNE/ABSORB-style project mappings, generic threshold/BREAK-style mappings, VFX queue, audio queue, deterministic feedback lifetime/snapshot.
- Batch 97: deterministic camera hit impulses, screen-FX/hit-stop presentation metadata, canonical target indicator projection.
- Batch 98: HP/MP/arbitrary battle-resource gauges, status-icon view-state, data-driven HUD profile, deterministic HUD snapshot/restore.
- Batch 99: read-only scheduler/timing projection for upcoming turns, current-actor marking, pending cast/action progress, deterministic timeline snapshot/restore.
- Batch 100: battle outcome/applied reward projection with project-owned labels, progression rank crossings and milestone-grant presentation.
- Batch 101: unified backend-neutral Battle UI composition frame joining combatants, HUD, timeline, feedback, targets, VFX/screen FX and result overlay.
- Batch 102: project-owned UI theme, deterministic Battle UI renderer executor, headless test backend and concrete optional pygame UI backend.
- Batch 103: complete Battle Screen presentation orchestration joining coordinator events, animation, feedback, camera, HUD, timeline, result, composition, rendering and one-shot audio.
- Batch 104: generic resource presentation policy; arbitrary battle resources can select bar/pips/number/ring/action/timeline/contextual/hidden/custom UI roles without changing gameplay.
- Batch 105: adaptive party/combatant presentation layout; expanded/compact/minimal density, project placement zones, focused-member retention and presentation-only overflow without gameplay party caps.
- Batch 106: generic action-menu/ability presentation; opaque project actions, categories, paging, filtering/search, disabled reasons and deterministic selection without gameplay resolution.
- Batch 107: generic multi-step action workflow/composition; supplied options, single/multiple selections, optional steps, backtracking and opaque completion payload without recipe/action resolution.
- Batch 108: presentation director; project-authored beats, deterministic event delays, cue priorities and presentation-only hold/hit-stop windows before existing animation/feedback/camera runtimes.
- Batch 109: animation/timing polish; role-specific playback rates, easing-driven sprite cross-fades, recovery holds and presentation-only multi-hit rhythm.
- Batch 110: coordinated camera/VFX/audio layering; shared staging groups, layer/intensity/gain/bus/priority metadata and deterministic presentation ordering.
- Batch 111: premium adaptive Battle UI hierarchy; project-owned polish profile, focused HUD emphasis, interaction surfaces, selected/disabled/muted roles, and richer theme styling.
- Batch 112: diverse battle validation/presentation closure; validates classic turn-based, boost/break, ATB, 12-member party, custom composition, and single-character configurations; removes final side-name semantic heuristic.

## Next direction

Adaptive + Premium Battle Presentation Batches 104–112 are now closure-complete. Next phase should move to runtime RPG UI (character/party/equipment/abilities/progression/inventory) rather than reopening frozen Battle Presentation without a proven abstraction gap. Damage numbers and interaction/break labels now have canonical backend-neutral view-state but still need their final renderer/UI adapter. RPG GUI and the playable vertical slice come after Battle Presentation reaches a human-testable checkpoint.

Current automated regression: **1151 passed, 0 failed**; `compileall -q src tests`
also passes. The full manual checklist and managed-session GUI limitation are
documented in `REAL_MACHINE_ACCEPTANCE_REPORT.md` and `START_HERE_MAC.md`.

See `docs/BATCH103_BATTLE_SCREEN_ORCHESTRATION.md`, `docs/BATCH103_CLOSURE_AUDIT.md`, `docs/ARCHITECTURE.md`, and `docs/NEXT_PHASE_PLAN.md`.

## Battle System Milestone Freeze

Battle Core Batches 75–93 and Battle Presentation Batches 94–112 have completed a combined milestone closure audit and are **FROZEN**.

Closure verification confirmed the current `src/asteria/gameplay` and `src/asteria/rpg` source are byte-identical to the v0.94 canonical Core baseline. Presentation contains no gameplay resolver/mutator execution path.

One closure correction was applied only in Presentation: battle-result headlines now require explicit viewer perspective or controller disposition to say Victory/Defeat/Escaped; otherwise finished outcomes use the neutral complete label.

Next development phase: Runtime RPG UI. Do not reopen Battle Core/Presentation without a proven abstraction gap.

## Runtime RPG UI Phase

- Batch 113: Character Screen Foundation; read-only `ResolvedActorBuild` projection, adaptive/project-owned sections, arbitrary stats/resources/equipment/abilities/progression, and presentation-only section navigation.
- Batch 114: Party / Formation Runtime UI; arbitrary roster groups, formation-slot projection, presentation-only focus, and adaptive overflow without gameplay party caps.

- Batch 115: Equipment / Loadout Runtime UI; arbitrary slots/capacities, equipped instances, sockets/attachments, growth/evolution summary, candidate eligibility, search/paging, and presentation-only selection.

- Batch 116: Ability / Passive Collections and Loadouts; resolved/learned ability projection, provenance, arbitrary categories, active passive/capacity summary, search, adaptive overflow, and presentation-only navigation.

- Batch 117: Progression Graph / Skill Tree Runtime UI; arbitrary graphs/nodes/prerequisites/ranks/costs, canonical preview eligibility, search, large-tree navigation, and presentation-only selection.

- Batch 118: Inventory / Item Runtime UI complete. Runtime RPG UI Batches 113–118 are now FROZEN; next phase is Asteria Engine Editor GUI / RPG UX.

- Batch 119: Playable RPG Systems Integration Harness complete. Reference actor now proves multiclass + progression + equipment + attachment + equipment growth + passive + inventory/composition can resolve through one canonical build/action projection. Next: enemy/AI and battle execution integration.

- Batch 120 complete: Batch119 complex actor now enters canonical BattleRuntime; enemy AI and player input share AbilityRuntime/BattleRuntime execution. No EnemySkillSystem split. Next: status/resources/interactions and richer enemy/boss integration.

- Batch 121 complete: playable validation now covers status duration/tick/expiry,
  buff modifiers, arbitrary battle gauges, tag-driven weakness-like interaction,
  outcome-driven stagger/break-like composition, multi-hit, heal and revive.

- Batch 122 complete: canonical transform/revert now validated as a generic
  stance/mode stack. Current form can replace stats/resources/tags/initiative/
  abilities; inactive-form actions are not legal. Snapshot preserves nested
  mode stack. No Core changes.

- Batch 123 complete: player summon and boss adds now validated through the same
  canonical summon/combatant lifecycle. Temporary combatants share BattleAction,
  owner provenance, snapshot/restore, and removal behavior. No Core changes.

- Batch 124 complete: 12-member complex party validated with 4 active / 8
  reserve, generic lifecycle-based swap, stable roster identity, formation slot
  reuse, canonical action execution, turn filtering, and snapshot/restore.
  No frozen Core changes.

- Batch 125 complete: Battle Interaction Architecture now layers complex input
  through root/action/workflow-or-modifier/target/confirm stages. Stress case:
  4 weapons + 80 skills remain operable without flat-button explosion.
  Contextual mechanics are hidden until relevant. No frozen Core changes.

- Batch 126 complete: Battle Information Hierarchy / Clutter Control formalizes
  persistent/contextual/focused/compact/hidden/overflow presentation. Stress
  cases cover 7 resources, 12 statuses, 12 party members, 18 timeline entries,
  boss + adds + summon. Octopath Traveler may inform quality/hierarchy only;
  Asteria remains generic/adaptive/project-configurable. No Core changes.

- Batch 127 complete: Combatant Visual System separates battlefield body,
  portrait, small portrait and icon; supports idle/attack/cast/hit/guard/KO/
  revive/status/transform states; supports large-boss scale/anchor/offset/z-order;
  supports portrait-party hidden battlefield bodies. No frozen Core changes.

- Batch 128 complete: Battle HUD + Action UI Assembly combines B125 interaction,
  B126 information hierarchy, B127 combatant visuals and roster density into one
  renderer-ready frame. 12-member stress case resolves as 4 full + 4 compact +
  4 overflow; skills remain paged; boss/add/summon share visual path.

- Batch 129 complete: high-precision Battle Motion Sequence integrates authored
  animation/VFX/camera/audio/UI/timing beats, sub-frame release, presentation-only
  hit stop, multi-hit rhythm, persistent status VFX and generic transform/summon/
  boss-phase transitions. Premium JRPG smoothness is a capability target.

- Batch 129A Animation Runtime Closure Review complete. Fixed arbitrary custom
  animation roles, replaced quantum-wide beat scanning with event-driven motion
  boundaries, added motion metrics, cached sprite-sheet resolution/member order/
  timing rules. 5000-beat dense choreography validation added. Renderer-specific
  batching/culling/pooling/streaming remains intentionally deferred to concrete
  backend stress validation.

- Batch 130 complete: Side-view JRPG Template adds an explicit presentation-only
  left/right battle grammar. Default left combatants face right, right combatants
  face left, both toward center. Opaque member IDs are bound explicitly; no
  player/enemy/boss semantics are inferred and no gameplay cap is introduced.

- Batch 131 complete: Dungeon / Portrait Party Template proves the same gameplay
  can hide party battlefield bodies while retaining portrait/HUD representation,
  with opponents/bosses/adds remaining on the battlefield. No side or player/
  enemy semantics are inferred.

- Batch 131A complete: Renderer & Animation Performance Foundation adds
  backend-neutral atlas/material/layer batching, visibility culling, bounded
  transient object pooling, asset preload readiness, and frame-budget/dropped-
  frame metrics. Representative 12-party + boss + 4 adds + summon + 300 VFX
  stress planning validated. Concrete GPU/backend 60-FPS validation remains
  deferred until real renderer/assets are present.

- Batch 132 complete: Character / Job / Progression Lab is now operable, not
  read-only. It exercises EXP/level, project-owned job unlock, primary/secondary
  job switching, multiclass, arbitrary Skill Point/Ability Point allocation and
  refund, skill-tree rewards, and passive loadout through existing canonical RPG
  runtimes. No frozen gameplay/RPG source changes.

- Batch 133 complete: Equipment / Accessory / Attachment Lab is operable. It
  validates equip/unequip, multiweapon capacity, accessories, socket attachment/
  detachment, equipment growth progress and authored auto-unlock, with immediate
  ResolvedActorBuild stat/ability/capability changes. No frozen gameplay/RPG
  source changes.

- Batch 134 complete: Inventory / Alchemy / Crafting Lab now performs real
  inventory-backed multi-step composition. Generic BattleActionWorkflowRuntime
  collects selections; project/controller recipes validate and transactionally
  consume canonical Inventory materials and generate outputs. No alchemy-specific
  engine command or recipe taxonomy was added.

- Batch 135 complete: Party / Formation Lab is operable. Canonical Party owns a
  12-member roster, canonical BattleFormationRuntime owns logical slots, while
  active/reserve grouping and active capacity remain project policy. Swaps,
  slot moves, roster reorder, add/remove, 4-active and 6-active configurations
  are validated without frozen gameplay/RPG source changes.

- Batch 136 complete: Asteria RPG Validation Project Assembly composes the
  operable Character/Job/Progression, Equipment, Inventory/Composition,
  Party/Formation labs and Battle Arena into one project flow. Character,
  Equipment and Inventory share one canonical reference actor scenario, and
  Battle Arena is constructed from the current ResolvedActorBuild. Battle
  execution remains isolated from persistent outside-battle project state.

- Batch 137 complete: Everything Combined Scenario now executes one deterministic
  journey across progression, equipment/attachment/growth, composition,
  party/formation, Battle Arena, status/interaction/multi-hit, transform,
  summon/boss add, and explicit RewardRuntime post-battle application.

- Batch 138 complete: UI + Renderer / Animation Stress Test exercises a dense
  backend-neutral presentation load (12 party, boss/adds/summon, 80 actions,
  96 indicators, 3000 VFX draws, 1000 offscreen draws, 5000 motion beats).
  Evidence-backed tuning removed per-call tuple(draws) copies from culling and
  batching. Pooling, preload, culling, batching, motion-event release and
  frame-budget accounting all pass. This is CPU-side planning validation, not a
  real-hardware 60 FPS claim.

- Batch 139 complete: Non-Octopath Generality Proof validates solo reactive,
  ATB-like squad, 18-member monster collection, and 24-unit raid presentation
  shapes with the same generic interaction/information/layout mechanisms.
  Octopath-like capability is confirmed as a benchmark, not an engine template.

- Batch 140: Playable RPG Systems Validation milestone FROZEN.
- Persistent FULL CANONICAL is produced at this boundary.
- `reference_projects/` contains direct-use side-view JRPG, portrait dungeon,
  large-party stress, and non-Octopath generality presets plus executable smoke.
- Next: Asteria Engine Editor GUI.
