# Asteria Phase 6 Closure Audit

Version: `v0.59.0a59`
Status: **FROZEN**

Phase 6 establishes the generic gameplay framework used by later RPG and ARPG
toolkits. The audit covers Batches 50–59.

## Closed scope

- Generic Stats / Resources / Tags
- Modifier evaluation
- Atomic Effects
- Structured ValueFormula / scaling
- State / Status lifecycle and snapshot/restore
- Generic Conditions
- Generic string-key Triggers
- Ability / Targeting runtime with atomic cost/effect execution
- Action Timeline gameplay/presentation seam
- Beginner-ready Defaults / Presets
- Canonical GameplayLibrary
- Formula-driven Effect values
- State-contributed tag ownership

## Closure fixes

### State tag ownership

The known Phase 6 tag ownership footgun was not deferred. StateDefinition now
has explicit `contributed_tags`. StateRuntime tracks overlapping contributors
and preserves tags that existed independently before the state contribution.

This is distinct from instantaneous Effect `TAG_ADD` / `TAG_REMOVE`, which
remain explicit direct mutations by design.

StateDefinition schema is now version 2 and remains backward-readable from v1.

### Prior Batch 58 fixes retained

- STACK `on_apply` executes once per application event.
- Periodic effects do not tick past state expiry when `dt` is large.
- Trigger event keys are project-defined strings; TriggerEvent is convenience only.
- Effects can use ValueFormula values.
- AbilityRuntime evaluates formula effects with per-target context.

## Frozen architecture invariants

1. Gameplay primitives are generic; no engine-semantic HP/MP/ATK/Fire/etc.
2. Project/template defaults are canonical data, not hardcoded runtime rules.
3. Beginner, Advanced, and Python authoring converge on the same definitions.
4. Formula data is structured/inspectable; no arbitrary expression eval.
5. Effects stage mutations atomically.
6. Ability execution stages costs/effects atomically.
7. JRPG and ARPG controllers share AbilityRuntime; selection/spatial queries remain outside it.
8. Trigger event vocabulary is extensible through string keys.
9. State lifecycle is deterministic and snapshot/restorable.
10. State-contributed tags have explicit ownership semantics.
11. ActionTimeline separates gameplay timing from presentation.
12. Presentation timeline data contains no renderer/audio/Qt/pygame runtime objects.
13. GameplayLibrary is the canonical definition container for formulas, abilities,
    states, triggers, and timelines.
14. Gameplay/Event/Core/Authoring architecture remains backend-neutral.
15. pygame and Qt do not leak into gameplay core.

## Verification

- Full regression: 246/246 tests PASS
- compileall: PASS
- Qt dependency scan in Gameplay/Authoring/Events/Core: 0
- pygame dependency scan in Gameplay/Authoring/Events/Core: 0
- StateDefinition v1 backward read: PASS
- State contribution overlap/base ownership: PASS
- Formula-driven multi-target Ability execution: PASS
- Timeline save/resume no replay: PASS
- GameplayLibrary roundtrip: PASS

The only eval/exec scan hit is the intentional trusted-local Python Authoring
runner from Phase 5. It is not used by ValueFormula or gameplay runtime and is
already governed by the Phase 5 trusted-project-script boundary.

## Deferred to later phases

These are integrations/tooling rather than missing Phase 6 primitives:

- visual Gameplay Database editors
- Formula/Condition/Trigger GUI builders
- Action Timeline Editor
- spatial hitbox/projectile/area query systems
- cooldown/combo/input-window systems
- battle turn controller
- ARPG realtime combat controller
- richer default/template content
- final VFX/audio/camera presentation adapters
- project migration/UI for future schema evolution

## Freeze decision

**Phase 6 is accepted and frozen at v0.59.0a59.**

Later phases may extend these APIs through backward-compatible additions, but
must not replace the generic gameplay model with RPG-specific hardcoded rules.
