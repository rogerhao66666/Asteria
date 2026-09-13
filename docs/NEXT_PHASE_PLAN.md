# Asteria Next Phase Plan

## Current checkpoint: v0.112.0a112 incremental development state

Full cumulative base: v0.94.0a94. Apply Batch 95 through Batch 112 incremental overlays in order. Phase 7B Battle Core remains FROZEN at Batch 93 / v0.93.0a93.

| Area | Delivered status |
| --- | --- |
| Engine / rendering / editor / runtime | cumulative foundation |
| Phase 5 Event VM / Dialogue / Python authoring | FROZEN |
| Phase 6 Generic Gameplay | FROZEN |
| Phase 7 RPG Toolkit | FROZEN |
| Phase 7B Battle Core | FROZEN at Batch 93 |
| Batch 94 Battle Presentation | scene/bindings/coordinator/cue-hook bridge |
| Batch 95 Battle Presentation | sprite/animation runtime; Idle/Attack/Hit/KO; texture draws; presentation snapshots |
| Batch 96 Battle Presentation | resolved floating-value/interaction/gauge feedback state; VFX/audio queues; feedback snapshots |
| Batch 97 Battle Presentation | camera/screen hit feedback state; target indicator projection; deterministic snapshots |
| Batch 98 Battle Presentation | read-only HP/MP/arbitrary gauge HUD; status icons; project HUD profile; deterministic snapshots |
| Batch 99 Battle Presentation | read-only scheduler/timing timeline; upcoming turns; current actor marker; pending cast progress; deterministic snapshot |
| Batch 100 Battle Presentation | canonical battle outcome/applied reward result view; currencies/items/progression crossings; project-owned result labels |
| Batch 101 Battle Presentation | unified adapter-ready battle UI frame; panels/text/gauges/icons/markers; composition of prior presentation view-state |
| Batch 102 Battle Presentation | project-owned UI theme; deterministic renderer executor; headless renderer backend; optional concrete pygame UI backend |
| Batch 103 Battle Presentation | full presentation orchestration; event fan-out; HUD/timeline mirror; composed render path; one-shot audio; composite snapshot |
| Batch 104 Battle Presentation | generic resource presentation policy; bars, pips, numbers, rings, action/timeline/contextual/hidden/custom resource roles |
| Batch 105 Battle Presentation | adaptive party/combatant HUD layout; density reduction, overflow, focus retention, generic placement zones |
| Batch 106 Battle Presentation | generic project action menu; categories, paging, filtering/search, supplied availability/disabled reasons, opaque selection |
| Batch 107 Battle Presentation | generic multi-step action workflow/composition; supplied options, selection steps, optional/back navigation, opaque completion payload |
| Batch 108 Battle Presentation | presentation director; authored choreography beats, event delays, priority and presentation-only hold/hit-stop windows |
| Batch 109 Battle Presentation | animation timing/transition polish; easing, playback rate, sprite cross-fade, recovery hold, multi-hit presentation rhythm |
| Batch 110 Battle Presentation | coordinated staging/layering across animation, VFX, camera, screen FX and audio with shared groups and deterministic ordering |
| Batch 111 Battle Presentation | premium adaptive Battle UI hierarchy; interaction surfaces, focused HUD emphasis, selected/disabled roles, project-owned polish/theme |
| Batch 112 Battle Presentation | diverse archetype validation and closure; removes residual side-name semantics and freezes Adaptive + Premium Battle Presentation milestone |

## Next Battle Presentation work

Batch 112 closes the Battle Presentation milestone. Proceed to Runtime RPG UI: character screen, party/formation, equipment/loadout, abilities, progression graph UI and inventory. Exact batching may be adjusted to keep each batch independently testable.

No presentation layer may infer gameplay outcomes. Damage values, interaction outcomes, target validity, KO, Break-like gauge transitions, costs, AI and turn ownership remain frozen/core-resolved inputs.

After Battle Presentation reaches a coherent playable checkpoint: RPG GUI + playable vertical slice, then broad Mac human playtesting.

## Battle System milestone closure

Battle Core 75–93 + Battle Presentation 94–112: **FROZEN**.

Batch 118 Inventory / Item Runtime UI and Runtime RPG UI closure are complete. Next: Asteria Engine Editor GUI / RPG UX. Battle-system changes should be treated as exceptions requiring a demonstrated abstraction gap rather than normal roadmap work.

## Runtime RPG UI phase

| Batch | Scope |
|---|---|
| Batch 113 Runtime RPG UI | Character Screen Foundation: canonical resolved-build projection, generic sections/resources/equipment/abilities/progression, presentation-only navigation |
| Batch 114 Runtime RPG UI | Party / formation runtime UI |
| Batch 115 Runtime RPG UI | Equipment / loadout runtime UI |
| Batch 116 Runtime RPG UI | Ability/passive collections and loadouts |
| Batch 117 Runtime RPG UI | Progression graph / skill-tree rendering |
| Batch 118 Runtime RPG UI | Inventory/item runtime UI + phase closure |

## Playable RPG Systems Validation

Batch 119 complete: cross-system reference harness.
Next: Batch 120 enemy/AI + shared battle action execution validation, using the
same reference-project philosophy. Later batches converge on a human-playable
reference battle and multiple presentation presets.

### Batch 120 complete
Enemy AI + player input shared battle execution validated. Next integration
expands status/resources/interactions and boss behavior while preserving
presentation clarity under high system complexity.

### Batch 121 complete
Status/resources/interactions integrated. Next: Batch 122 transform / stance /
mode validation, including build/action changes without adding a dedicated
TransformSystem taxonomy.

### Batch 122 complete
Transform / stance / mode integration validated over canonical member
replacement and form stack. Next: Batch 123 summon / temporary combatants /
boss adds and lifecycle integration.

### Batch 123 complete
Summon / temporary combatant / boss-add integration validated. Next: Batch 124
swap / reserve / formation / complex-party validation before Battle Interaction
& Information Architecture.

### Batch 124 complete
Swap / reserve / formation / complex-party integration validated. Gameplay
capability integration 121-124 is complete. Next: Batch 125 Battle Interaction
& Information Architecture, including multi-weapon/many-skill/special-system
action organization and clutter-control policy.

### Batch 125 complete
Complex battle interaction routing validated. Next: Batch 126 Battle Information
Hierarchy / Clutter Control: persistent/contextual/focused/compact/hidden/
overflow policies for large parties, many resources/statuses, boss+adds+summon,
and dense timelines.

### Batch 126 complete
Information hierarchy/clutter policy validated. Next: Batch 127 Combatant Visual
System, separating battlefield visual, portrait, small portrait and icon, with
animation states and large-boss scale/anchor/offset/z-order support.

### Batch 127 complete
Combatant visual profiles/states validated. Next: Batch 128 Battle HUD + Action
UI assembly, combining Batch125 interaction architecture, Batch126 information
hierarchy and Batch127 combatant visuals into a concrete runtime battle UI.

### Batch 128 complete
Concrete Battle HUD + Action UI assembly validated. Next: Batch 129 Animation /
VFX / Camera Integration to exercise the visible action chain from input through
cast/impact/hit-stop/damage/status/recovery and special transitions.

### Batch 129 complete
Animation/VFX/Camera integration validated. Next: Batch 130 Side-view JRPG
Template using the same generic gameplay/presentation mechanisms with enemies on
the left, players on the right, both facing center. This is a presentation preset
only and must not encode side semantics in Battle Core.

### Batch 129A complete
Animation runtime closure review passed after removing the fixed-role leak and
substep-wide beat scanning hot path. Continue to Batch 130 Side-view JRPG
Template. Renderer-specific 60-FPS claims remain gated on concrete backend +
representative asset stress tests.

### Batch 130 complete
Side-view JRPG presentation template validated. Next: Batch 131 Dungeon /
Portrait Party Template using the same gameplay with player battlefield bodies
optionally hidden while portraits/HUD remain visible. Then Batch 131A concrete
Renderer & Animation Performance Foundation.

### Batch 131 complete
Second battle presentation grammar validated. Next: Batch 131A Renderer &
Animation Performance Foundation: concrete batching/culling/pooling/preload and
frame-time instrumentation seams, followed by representative stress validation.

### Batch 131A complete
Renderer/animation performance foundation is now present. Continue to Batch 132
Character / Job / Progression Lab, where outside-battle RPG systems become
actually operable rather than read-only validation projections.

### Batch 132 complete
Character / Job / Progression Lab is operable. Next: Batch 133 Equipment /
Accessory / Attachment Lab: equip/unequip, multiple weapons, accessory,
socket/attachment, upgrade/growth/evolution, with immediate ResolvedActorBuild
changes.

### Batch 133 complete
Equipment / Accessory / Attachment Lab is operable. Next: Batch 134 Inventory /
Alchemy / Crafting Lab: real inventory consumption/production, generic
multi-step composition, recipe resolution, and reversible validation without
hardcoding an Alchemy command into the engine.

### Batch 134 complete
Inventory / Alchemy / Crafting Lab is operable. Next: Batch 135 Party /
Formation Lab: party roster, active/reserve assignment, formation placement,
swap, and large-party operation outside battle before full Validation Project
assembly.

### Batch 135 complete
Party / Formation Lab is operable. Next: Batch 136 Asteria RPG Validation
Project Assembly — connect Character/Job/Progression, Equipment, Inventory/
Composition, Party/Formation, and Battle Arena into one coherent reference
project flow instead of isolated labs.

### Batch 136 complete
The RPG Validation Project is assembled across outside-battle systems and Battle
Arena. Next: Batch 137 Everything Combined Scenario — exercise the full authored
sequence in one deterministic end-to-end validation: build/multiclass,
progression, equipment/attachment/growth, composition, party swap, battle
interaction, transform/summon/boss-phase/status/cleanse style mechanics where
available, victory/reward application, then verify post-battle progression and
inventory state.

### Batch 137 complete
Everything Combined Scenario passes. Next: Batch 138 UI + Renderer/Animation
Stress Test and performance tuning. Exercise dense party/action/status/resource/
VFX presentation together, collect frame-budget/batching/culling/pool metrics,
and tune only evidence-backed hot paths before generality proof.

### Batch 138 complete
Dense UI/renderer/animation stress validation passes and two unnecessary
per-frame draw-container copies were removed. Next: Batch 139 Non-Octopath
Generality Proof — validate materially different RPG/battle structures against
the same mechanisms and presentation policies so the engine is not accidentally
optimized around the reference JRPG shape.

### Batch 139 complete
Non-Octopath generality proof passes. Next: Batch 140 Playable RPG Systems
Closure Audit / Freeze. Audit the full 119–139 validation milestone, resolve
only proven generic gaps, then produce a persistent FULL CANONICAL milestone
before the Editor GUI phase.

### Batch 140 — Playable RPG Systems Closure / Freeze
Batches 119–139 are closed and frozen. Direct-use local reference presets and a
runnable smoke script are included under `reference_projects/`.

Next milestone: Asteria Engine Editor GUI. The editor must remain polished,
modern, beginner-usable, and code/script friendly, with GUI and Python APIs
editing the same canonical Project/Scene/RPG data.
