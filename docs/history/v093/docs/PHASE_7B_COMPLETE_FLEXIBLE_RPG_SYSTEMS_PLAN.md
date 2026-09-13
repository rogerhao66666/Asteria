
## Canonical batch mapping (v0.93 — Battle Core frozen)

Implementation inserted additional required integration work after the original plan was written. The canonical implemented numbering is now: Batch 80 Resolved Actor Build; Batch 81 Battle Resources/Gauges; Batch 82 Interaction/Weakness/Resistance/Outcome Resolution; Batch 83 Battle State/Status Integration; Batch 84 Advanced Targeting/Formation/Position; Batch 85 Combatant Lifecycle/Objectives/Escape; Batch 86 Speed/Turn/Continuous Timeline Scheduler; Batch 87 Advanced Action Timing; Batch 88 Multi-hit/Action Sequence/Combo/Cooperative Ability; Batch 89 Break/Stagger via generic gauge composition; Batch 90 Reactions; Batch 91 Enemy AI/Boss Runtime and battle hooks; Batch 92 Deterministic Battle Snapshot and action transaction closure; Batch 93 cross-system closure audit and freeze. Battle Core is now FROZEN at v0.93.0a93. The next phase is Battle Presentation, followed by RPG GUI + playable vertical slice. Older numbered sections below are design-history notes; this mapping is authoritative for implementation packages.

# Asteria Phase 7B --- Complete & Flexible RPG Systems Plan

**Status:** Battle Core FROZEN at Batch 93 / v0.93.0a93\
**Foundation:** Phase 7A v0.73.0a73 (frozen and Mac-verified)\
**Phase 8:** Batch 74 is parked until Phase 7B closure.

## 1. Goal

Phase 7A established the RPG foundation: Stats, Resources, Tags,
Formula, Modifier, Effect, State, Ability, Timeline, Actor, Class, Item,
Equipment, Socket/Attachment, Enemy, Encounter, Reward, Progression,
Party, basic Battle, lifecycle hooks, project persistence and runtime
save state.

Phase 7B raises the acceptance bar from "the primitive exists" to:

> Asteria must compose complete, complex RPG rules without requiring an
> engine-source modification for each game mechanic.

Complex commercial JRPGs are coverage benchmarks only. Their rules are
not Asteria's specification.

> Reference games define minimum capability coverage. Project data and
> composable rules define the actual game.

## 2. Non-negotiable invariants

-   No reference-game hardcoding: no fixed Break/BP system, elemental
    chart, job count, equipment layout, or stat semantics.
-   No arbitrary engine caps on classes, equipment, sockets, roster,
    passives, resources, etc. UI presentation may be
    bounded/virtualized.
-   Composition over special cases: Resource, Tag, Condition, Trigger,
    Effect, Modifier, State, Formula, Ability, Timeline, Targeting and
    scheduling policies.
-   GUI, Python Authoring API, serialization and runtime use canonical
    data.
-   Derived job/equipment/state/progression data never contaminates
    intrinsic actor state.
-   Resolution, scheduling, reactions, seeded randomness and
    save/restore are deterministic.
-   Meaningful workflows remain lifecycle/event-connectable.
-   RPG/gameplay/core remain independent of PySide6, pygame and renderer
    backends.
-   JRPG and ARPG share gameplay semantics rather than maintaining two
    damage/ability engines.
-   Simple defaults remain easy despite advanced flexibility.

## 3. Additional gaps found in second review

The first Batch 75--88 proposal was strong, but a second review found
several items that must be explicit.

### 3.1 Rule-driven value/outcome resolution

`ValueFormula` exists, but complete RPG combat also needs canonical
outcome resolution without creating a fixed damage calculator. It must
support configurable mitigation/amplification stages, critical-like
rules, clamp/rounding, miss/evade/block/parry-like outcomes,
damage/healing/resource/shield-like channels, and provenance explaining
the final result.

### 3.2 Ability availability

Ownership is not enough. Ability use may depend on required/forbidden
tags, weapon capabilities, resources, battle state, target availability,
class/job state, cooldown/charges and arbitrary conditions. GUI, AI and
runtime need one canonical availability query with rejection reasons.

### 3.3 Ability upgrades, variants and mastery

Progression must be able to unlock, replace or upgrade abilities, modify
cost/formula/hit count/targeting, and support branches without a
hardcoded skill-tree engine.

### 3.4 Action transaction and reaction ordering

An action can cascade through hit → weakness → resource → break → state
→ counter → KO → on-KO. A deterministic reaction/action transaction is
required with ordering, provenance, recursion protection and
rollback/staging where practical.

### 3.5 Battle snapshot/restore

Complex battles need scheduler, cast/pending action, temporary state,
battle resource, AI phase/memory and deterministic RNG continuation.

### 3.6 Generic logical formation

Targeting should understand optional project-defined
slots/groups/relations (front/back, rows, lanes, boss parts, etc.)
without hardcoding any particular formation.

### 3.7 Summons and transformations

Runtime combatants must be addable/removable/transformable for summons,
adds, clones, boss forms and temporary allies without a bespoke
SummonSystem.

### 3.8 Alternate objectives

Victory/defeat cannot assume all enemies reach HP zero. Support
survive/protect/escape/scripted/condition-based objectives.

### 3.9 Deterministic RNG policy

Critical-like rolls, random targeting, AI and other battle randomness
use injected/seedable RNG; no hidden global randomness in canonical
battle logic.

### 3.10 Validation and explainability

Flexible rules require validation and reasons: dangling refs, malformed
scheduling/resources/targeting, detectable cycles, and messages such as
"missing weapon.greatsword_access" or "insufficient mana".

# 4. Batch Plan

## Batch 75 --- Multi-Class / Job Composition

**Goal:** arbitrary composable job/class layers.

Deliver: - canonical `ClassAssignment` concept; - arbitrary number of
assignments; - project-defined role/tag such as
primary/secondary/special, not engine-fixed roles; -
enable/disable/switch assignments; - deterministic contribution order; -
independent progression per job; - class
stat/tag/resource/ability/passive/capability contributions; - Phase 7A
backward compatibility.

Acceptance: character level and job levels may be independent; three
simultaneous classes work; a project may have no conventional character
level. No two-job maximum.

## Batch 76 --- Ability Ownership, Learning, Passives & Evolution

**Goal:** distinguish ability provenance and persistence.

Sources include intrinsic, learned, class, equipment, attachment,
progression, passive, state and temporary/runtime grants.

Deliver: - learned ability persistence; - project-defined/unlimited
passive/support loadout; - provenance; - deterministic conflict/dedup
policy; - unlock/upgrade/replacement/variant/mastery seams; - branching
through progression/rules rather than a fixed skill-tree type.

Passives compose modifiers, triggers, conditions, effects, tags,
capabilities/resources and abilities.

## Batch 77 --- Progression Graph / Skill Tree / Point Allocation

**Goal:** generic progression graphs for skill trees, stat boards, job boards, mastery systems and point allocation.

Deliver: - arbitrary graph topology; - ranked nodes; - multiple project-defined currencies; - rank-dependent costs; - prerequisites; - mutually exclusive branches; - stat/resource/tag/ability/passive/capability rewards; - allocation preview with explainable rejection reasons; - respec/refund with dependency protection; - save/load; - derived actor contributions without mutating intrinsic actor state.

No fixed SP/JP semantics, fixed tree shape, or engine-wide node/rank limit.

## Batch 78 --- Flexible Equipment, Weapon Proficiency & Capability Rules

**Goal:** make equipment layout/access project-defined.

Deliver: - arbitrary slots and capacities, including unlimited; -
multiple weapon/armor/accessory instances; - requirements and forbidden
conditions; - capability/tag-based weapon proficiency; - capability
grants from actor/class/passive/equipment/state/rules; - data-driven
multi-hand/multi-weapon behavior; - stable unique instances and
socket/attachment persistence.

Acceptance includes 8 weapon slots, 12 armor slots, unlimited
accessories, or a conventional left/right-hand game. No engine quantity
cap.

## Batch 79 --- Canonical Resolved Actor Build

**Goal:** one canonical resolution seam for battle/editor/AI.

Resolve Actor + classes + progression + equipment + attachments +
learned abilities + passives + states/runtime contributions into: -
effective stats/resources/tags; - capabilities; - available/owned
abilities with provenance; - active passives/rules; - equipment
contributions; - validation/explanation information.

Resolution is deterministic and never mutates intrinsic actor state.

## Batch 80 --- Battle Resources, Gauges & Lifecycle

**Goal:** fully composable battle resources.

Project-defined initialization, min/max, battle start/end, regen, decay,
trigger gain/loss, spending, overflow and persistence/reset rules.

Same primitive must represent MP, TP, rage, guard, stagger, combo,
charge, morale, boost-like points, or custom resources.

## Batch 81 --- Interaction, Weakness, Resistance & Outcome Resolution

**Goal:** generic interaction rules plus canonical value/outcome
pipeline.

Deliver: - action/attack tags vs target tags/rules; -
weak/resist/immune/absorb/reflect-like compositions; - interaction
effects on values, resources, states, tags and triggers; - configurable
mitigation/amplification; - critical-like rules; -
clamp/rounding/min/max; - miss/evade/block/parry-like outcomes; -
resolution provenance.

No fixed element or weapon enum is required.

## Batch 82 --- Advanced Targeting, Formation & Logical Position

**Goal:** complex targeting without hardcoded rows.

Selectors include self, single/multiple ally/enemy, all, random N,
tag/condition filtered, stat/resource filtered, incapacitated
candidates, and group/position/adjacency relations.

Logical formation is project-defined slots/groups/relations/tags.
Front/back, rows, lanes and boss parts are optional project concepts.

## Batch 83 --- Battle State, KO/Revival, Combatants & Objectives

**Goal:** remove hidden assumptions about death and victory.

Deliver: - generic combatant participation states; - rule-driven
incapacitation/KO/removal/revival; - runtime add/remove combatants; -
summon/add/clone/transformation seams; - alternate objectives; -
escape/surrender/scripted outcomes; - lifecycle hooks.

One template may map HP\<=0 to KO; another may use a downed countdown.

## Batch 84 --- Turn Scheduling Foundation

**Goal:** policy-driven scheduling.

Initial policies: - round-based; - speed-ordered round; -
timeline/continuous initiative.

Timeline scheduling permits speed to affect action frequency, so a fast
actor can naturally act multiple times before a slow enemy. Traditional
games can still enforce one action per round.

## Batch 85 --- Advanced Action Timing

**Goal:** let abilities alter scheduling.

Support: - cast time; - action delay/cost; - recovery; - priority; -
interruptibility; - advance/delay; - cancel cast; - extra action; - skip
action.

Acceptance: quick skills can allow another action before a monster;
heavy skills delay the user; charged spells can be interrupted; support
abilities can advance allies.

## Batch 86 --- Multi-Hit, Action Sequences & Break-like Composition

**Goal:** deterministic action sequences instead of one opaque effect.

Deliver: - multi-hit/action sequence; - per-hit
formula/condition/interaction/trigger; - variable or rule-driven hit
counts; - resource spending that changes sequence behavior; - generic
gauge depletion → condition → state composition.

A break-like mechanic is Resource + Condition + Trigger + State, not
`BreakSystem`.

## Batch 87 --- Reactive Combat, Transactions & Reaction Queue

**Goal:** safe predictable counters/follow-ups/interrupts.

Deliver reaction seams for before/after action/hit, value received,
critical/interaction match, ally affected, resource change, state
change, KO, recovery, etc.

Add: - deterministic reaction queue; - priority/order; -
recursion/depth/loop protection; - action-resolution
transaction/provenance; - staged mutation/rollback where practical; -
lifecycle hooks.

## Batch 88 --- Enemy AI, Boss Phases, Multi-Action & RNG

**Goal:** generic complex enemy decisions.

Deliver: - condition → candidate action → weight/priority → target
selector; - AI memory/counters; - phase transitions; - phase-driven
definition/tag/state/resource changes; - multi-action via
scheduler/rules rather than Boss-only code; - injected/seedable
canonical battle RNG.

Acceptance: conditional dispel/heal, every-third-action specials, phase
changes, reproducible seeded behavior.

## Batch 89 --- Battle Snapshot/Restore, Validation & Phase 7B Closure

**Goal:** prove the complete system composes, persists and remains
general.

Snapshot where logically safe: - scheduler/timeline; - pending/casting
action; - battle resources; - temporary states; - combatant
participation/transformation; - AI phase/memory; - RNG state; - reaction
state or explicit safe-point restrictions.

Validation covers dangling refs, capability/ability/equipment errors,
scheduler/resource/targeting/rule errors, malformed definitions and
detectable reaction cycles.

Explainability exposes why abilities/equipment are unavailable and where
effective contributions/outcome changes came from.

# 5. Closure Reference Scenarios

## Reference A --- Complex Job JRPG

Demonstrate using ordinary project data/rules: - four-person party; -
multiple jobs and independent job progression; - weapon proficiency; -
flexible equipment; - learned/passive abilities; - weapon/custom and
element-like interactions; - special resource; - stagger/break-like
gauge; - multi-hit; - buffs/debuffs; - counter/follow-up; - revival; -
boss phases; - speed-aware scheduling; - rewards; - save/restore.

This is a capability benchmark, not a copied game ruleset.

## Reference B --- Deliberately Different RPG

Demonstrate: - three simultaneous classes; - six weapon slots; -
unlimited accessories; - no elemental system; - rage-style resource; -
timeline scheduling; - fast actor acting multiple times; -
charged/interrupted spell; - dynamic interactions; - alternate battle
objective; - runtime summon/transformation.

If Reference A works but Reference B needs an engine-source change,
Phase 7B fails.

# 6. Closure Gate

For each major mechanic:

> Can the mechanic be substantially changed using Project Data /
> canonical Rules / Authoring API without modifying engine source?

**YES:** candidate PASS.\
**NO:** abstraction gap; no closure.

Also require: - full regression PASS; - compileall PASS; - no
PySide6/pygame leakage in backend-neutral layers; - explicit backward
compatibility tests; - deterministic seeded tests; - project
save/reopen; - battle snapshot round-trip; - lifecycle hook coverage; -
no arbitrary dynamic-collection caps; - no reference-game special
cases; - documented deferred scope.

# 7. Explicitly Deferred

## Phase 8 ARPG Toolkit

Real-time hitbox/hurtbox, spatial queries, dodge, knockback, movement
combat and attack windows. Existing Batch 74 is parked and later
integrated.

## World Systems

Quest, shop, crafting, NPC/world interaction and broader map/world
systems.

## GUI/UI milestones

Polished Job/Equipment/Roster editors, battle HUD, runtime menus and
final visual polish.

Phase 7B must nevertheless expose canonical data, validation and
explanation seams these interfaces can consume.

# 8. Intended Execution Path

``` text
Project RPG Data
      |
      +--> Actor / Classes / Progression
      +--> Equipment / Attachments / Passives
      +--> Ability Definitions / Rules
      |
      v
ResolvedActorBuild
      |
      +--> Availability / Capability Query
      |
      v
Battle Runtime
      |
      +--> Objectives / Combatant State
      +--> Action Scheduler
      +--> Targeting / Formation
      +--> Resources / Gauges
      +--> AI
      |
      v
Action Resolution
      |
      +--> Ability / Action Sequence
      +--> Formula / Interaction Rules
      +--> Effect / Modifier / State
      +--> Resource Changes
      |
      v
Deterministic Reaction Queue
      |
      +--> Counter / Follow-up / Interrupt
      +--> KO / Phase / State transitions
      |
      v
Lifecycle Hooks / Event Bridge
```

Phase 8 ARPG reuses the same resolved actor, ability, formula, effect,
state, resource, reaction and lifecycle semantics while adding
real-time/spatial execution policy.

# 9. Definition of Complete RPG Systems Foundation

Phase 7B does not mean Asteria contains every mechanic ever invented. It
means:

1.  Common simple RPGs remain easy to configure.
2.  Complex job/equipment/battle systems do not require engine forks.
3.  Reference mechanics can be substantially changed through project
    rules.
4.  Very different RPG structures coexist on the same primitives.
5.  New mechanics usually emerge by composition rather than new engine
    special cases.
6.  Runtime behavior remains deterministic, serializable, testable and
    explainable.
7.  GUI and Python workflows can expose the same canonical model.
8.  JRPG and ARPG share gameplay semantics.

That is the Phase 7B closure standard.
