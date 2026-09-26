# ASTERIA_SPEC.md

**Status:** Canonical migration candidate\
**Canonical role:** Overall product / engine / editor / runtime /
gameplay specification\
**Source coverage:** Exact content of legacy `SPEC.md` preserved below.

> Detailed asset taxonomy/formats live in `ASTERIA_ASSET_SPEC.md`;
> processing SOPs live in `ASTERIA_ASSET_PIPELINE.md`; art-quality rules
> live in `ASTERIA_ART_DIRECTION.md`; implementation state lives in
> `ASTERIA_PROGRESS.md`.

------------------------------------------------------------------------

# Asteria --- Product & Functional Specification

**Status:** Initial Product Specification\
**Target:** Python-first 2D RPG / ARPG game engine and creation toolkit

## 1. Product Vision

Asteria is a Python-first 2D game engine and visual creation toolkit
designed to preserve the accessibility of tools such as RPG Maker while
supporting substantially more advanced RPG and action-RPG systems
without forcing users to build core gameplay infrastructure themselves.

Primary target families:

-   2D JRPG / turn-based RPG
-   2D Action RPG / side-scrolling or top-down ARPG

Reference complexity targets include system complexity comparable to
**Octopath Traveler** and **ASTLIBRA Revision**. These are architectural
stress targets, not templates or gameplay clones.

## 2. Core Product Principle

> Simple things must remain simple, while complex things must remain
> possible.

A conventional RPG should be creatable almost entirely through GUI
workflows. Advanced systems should be available progressively without
overwhelming beginners.

Common RPG and ARPG mechanics should not require custom Python code.
Python is an escape hatch for genuinely unique mechanics, not a
prerequisite for ordinary use.

## 3. Progressive Complexity

### Basic

-   Name, presentation and assets
-   Basic stats
-   Damage/healing
-   Costs
-   Targets
-   Basic animation
-   Basic conditions

### Advanced

-   Multi-hit
-   Weakness interactions
-   Resource interactions
-   Conditional effects
-   Cast/recovery timing
-   Buff/debuff rules
-   Combo behavior
-   Trigger rules
-   Custom targeting
-   Boss phases

### Expert

-   Action timelines
-   Modifier pipelines
-   Complex formulas
-   Event hooks
-   Gameplay-system definitions
-   Python scripting
-   Plugins

Advanced functionality must not make Basic workflows significantly
harder.

## 4. Python-First, Not Python-Only

Python is the primary language for:

-   Engine architecture
-   Editor implementation
-   Gameplay framework
-   User scripting
-   Plugins
-   Tool scripting
-   Game-specific extensions

Performance-critical internals may later use optimized libraries or
native extensions. Public gameplay and scripting APIs should remain
stable and Python-facing where practical.

## 5. GUI Is a First-Class System

Asteria shall provide a full editor with:

-   Project/hierarchy panel
-   Scene/map workspace
-   Inspector
-   Asset browser
-   Structured database
-   Event editor
-   Animation editor
-   Action timeline
-   AI editor
-   VFX tools
-   Script editor
-   Debugger
-   Play-test controls

Productivity requirements:

-   Undo/redo
-   Copy/paste/cut
-   Duplicate/delete
-   Multi-select
-   Drag/drop
-   Search/filter/sort
-   Context menus
-   Keyboard shortcuts
-   Asset preview
-   Bulk editing where useful
-   Validation
-   Error navigation
-   Play current scene

GUI, runtime, serialization and scripting should operate on one coherent
canonical data model.

## 6. Core Object Model

Asteria uses composition as the primary model.

Typical entity composition may include:

-   Transform
-   SpriteRenderer
-   Animator
-   Collider
-   CharacterController
-   Stats
-   Health
-   Resource
-   AbilitySet
-   Equipment
-   Inventory
-   PlayerInput or AIController

Components should be reusable, serializable, inspectable and
script-accessible. Large gameplay inheritance hierarchies should be
avoided.

## 7. System-Oriented Runtime

Runtime processing should be organized into focused systems where
appropriate:

-   AnimationSystem
-   PhysicsSystem
-   AISystem
-   AbilitySystem
-   RenderSystem

Asteria should avoid naive unrestricted per-frame dynamic dispatch
across every component when more efficient system-oriented processing is
practical.

## 8. Engine Core

Core capabilities:

-   Application lifecycle
-   Game loop
-   Time/delta time
-   Fixed update where required
-   Scene lifecycle
-   Entity/component lifecycle
-   System scheduling
-   Event bus
-   Resource lifetime
-   Serialization boundaries

Scene: - Load/unload - Transitions - Hierarchy - Persistent entities -
Scene serialization

Transform: - Position - Rotation - Scale - Parent/child relations

Rendering: - Sprites - Tiles - Layers - Transparency - Batching -
Parallax - Render groups - Screen-space UI

Input: - Keyboard - Mouse - Gamepad - Input actions - Rebinding -
Multiple control schemes

Collision/physics: - Collider - Trigger - Layers/masks - Broad phase -
Character collision - Hitbox/hurtbox - Ground/platform detection

Audio: - BGM - Ambient - SFX - Mixer/groups - Fades - Spatial behavior
where useful

## 9. Asset System

Supported concepts should include:

-   Sprite
-   Sprite sheet
-   Tile set
-   Animation
-   Audio
-   Font
-   Shader/material
-   Scene
-   Prefab
-   VFX
-   Script
-   Database resource

Stable project identifiers should be preferred over fragile raw path
references.

## 10. Prefab / Template / Variant

Reusable objects should support:

-   Prefabs/templates
-   Variants
-   Overrides
-   Scene placement
-   Propagation of base changes

Use cases include enemies, NPCs, treasure chests, shops, interactive
props and gameplay objects.

## 11. Animation and Action Timeline

Animation support: - Sprite-sheet import - Frame slicing - Clips -
Looping - State machines - Transition parameters - Frame events -
Preview

Action timelines may contain: - Animation - Movement - Hitbox/hurtbox -
I-frame - Cancel window - Combo window - VFX - SFX - Camera - Gameplay
events

## 12. Camera / Lighting / VFX

Camera: - Follow - Smooth follow - Dead zone - Look ahead - Zoom -
Bounds - Shake - Target groups - Boss camera - Cutscene camera -
Transitions

Visual systems may include: - 2D lights - Normal maps - Shadows -
Bloom - Color grading - Screen shaders - Fog/weather/water - Particles -
Trails - Afterimages - Hit flash - Damage numbers - Screen effects

## 13. Generic Gameplay Framework

Core gameplay primitives:

-   Attribute / Stats
-   Resource
-   Ability
-   Effect
-   Modifier
-   Condition
-   Trigger
-   State
-   Tag
-   Targeting
-   Timeline
-   Cooldown
-   Reaction
-   Action

Game-specific mechanics should be composed from these primitives rather
than built into Engine Core.

## 14. Stats / Resources / Abilities

Stats must support arbitrary game-defined attributes, including base,
derived and modified values.

Resources may represent HP, MP, stamina, rage, guard, shield, boost
points, heat, combo meters, limit gauges, poise or custom concepts.

Abilities may define: - Cost - Cooldown - Targeting - Cast/recovery -
Animation - Timeline - Hit behavior - Effects - Conditions - Tags - AI
metadata

## 15. Effects / Triggers / Conditions / Modifiers

Effects may include: - Damage/heal - Resource change - State changes -
Attribute changes - Knockback - Movement - Spawn - Item changes - EXP -
Event start

Triggers may include: - Battle/turn boundaries - Before/after action -
On hit/critical/weakness/break - On damage/kill - State changes -
Thresholds - Interaction - Item/equipment changes - Custom events

Conditions must support AND/OR/NOT composition.

Modifiers may affect stats, damage, healing, costs, cooldowns, hit
counts, timing, weakness/resistance, loot, EXP, crafting and interaction
outcomes.

## 16. Gameplay Tags and Formula Rules

Hierarchical tags allow generalized rules such as:

-   Creature.Undead
-   Creature.Boss
-   Element.Fire
-   Weapon.Sword
-   Ability.Magic
-   Ability.Projectile
-   State.Poison

Common formulas should be authorable without Python for damage, healing,
EXP, drops, critical chance, steal checks, crafting, pricing and growth.

## 17. Action Resolution Pipeline

Complex actions should follow an extensible conceptual pipeline:

Ability selection → validation → target resolution → pre-action triggers
→ cost → timeline → hit resolution → accuracy/critical → base result →
attacker/defender modifiers → element/weapon interaction →
weakness/guard/break → final result → effects/states →
reactions/counters → death/phase transitions → post-action triggers.

Controlled extension points are preferred over hard-coded special cases.

## 18. State / Status Framework

Support: - Buff/debuff - Damage-over-time - Crowd control -
Break/stagger - Invulnerability - Custom states

Configurable properties: - Duration - Stacks - Refresh rules -
Modifiers - Trigger effects - Periodic effects - Removal rules -
Presentation

## 19. Turn-Based RPG Framework

Eventually support:

-   Party/enemy groups
-   Turn scheduling
-   Action order
-   Speed-based ordering
-   Multi-hit
-   Counter/follow-up/reaction
-   Buff/debuff
-   Weakness/resistance
-   Break/stagger-like systems
-   Custom resources
-   Turn manipulation
-   Boss phases
-   Battle events
-   Battle AI

The target is architectural capability comparable to sophisticated
modern JRPG systems.

## 20. Real-Time ARPG Framework

Eventually support:

-   Realtime movement
-   Jump
-   Dash/dodge
-   I-frames
-   Combo chains
-   Cancel windows
-   Startup/active/recovery
-   Hitbox/hurtbox
-   Knockback
-   Stagger/poise
-   Projectiles
-   Targeting/lock-on
-   Cooldowns/resources
-   Enemy/boss AI
-   Hitstop
-   Action timelines

The target is architectural capability comparable to sophisticated 2D
ARPG systems.

## 21. Inventory / Equipment / Progression

Inventory: - Stackable/unique items - Categories - Capacity rules - Key
items - Consumables - Equipment - Currency-like resources

Equipment: - Slots - Requirements - Stats/modifiers - Tags - Passives -
Trigger effects - Set bonuses - Mastery - Upgrade paths - Variants

Progression: - Level/EXP - Character growth - Skill/stat points -
Unlocks - Mastery - Weapon/equipment proficiency - Job progression

## 22. Job / Class / Skill Tree / Mastery

Support should be generalized so games may opt in or ignore these
systems.

Possible capabilities:

-   Jobs and secondary jobs
-   Requirements
-   Job skills/passives
-   Job resources
-   Equipment restrictions
-   Skill-tree nodes/dependencies/costs
-   Multiple unlock currencies
-   Weapon/equipment/skill/crafting mastery

## 23. Loot / Economy / Crafting

Loot: - Weighted/guaranteed/rare drops - Quantity ranges - Conditional
drops - Difficulty/luck modifiers

Economy: - Buy/sell - Multiple currencies - Stock/restock - Pricing
modifiers - Conditional inventories - Reputation or dynamic pricing
hooks

Crafting: - Recipes - Ingredients - Requirements - Stations - Outputs -
Success chance - Quality - Craft EXP/mastery - Recipe discovery -
Failure rules

## 24. World Interaction

Generic interaction framework should support:

-   Talk
-   Inspect
-   Open
-   Buy
-   Steal
-   Challenge
-   Recruit
-   Persuade
-   Capture
-   Search
-   Gather
-   Fish
-   Craft
-   Custom actions

Interactions may define: - Actor capability - Target type -
Requirements - Cost - Check - Success/failure - Reward - Consequence -
Follow-up event

## 25. Creature / Companion

Reusable primitives may support:

-   Capture
-   Collection
-   Summoning
-   Companion abilities
-   Growth
-   Party/storage
-   Creature-specific skills

Games that do not use these features should not pay significant UX
complexity.

## 26. Quest / World State / Relationship

Quest support: - Quests/objectives - Dependencies - Optional
objectives - Rewards - Conditions - Chains - Event/world-state
integration

World systems may include: - NPC state - Reputation - Relationships -
Faction-like values - Persistent flags - Achievements/statistics -
Bestiary/encyclopedia

## 27. Dialogue / Event VM / Sequencer

The event system should use a resumable Event VM rather than simply
emitting arbitrary Python.

Support: - Wait/resume - Parallel events - Autorun - Common events -
Battle events - Cutscenes - Save/load/resume - Switches - Variables -
Local/self-state - Branches - Dialogue/choices - Scene transfer -
Animation/audio/screen effects - Inventory/party/world-state actions

A sequencer should coordinate movement, animation, dialogue, camera,
music, SFX, VFX, events and scene transitions on parallel tracks.

## 28. AI / Boss / Encounter

Basic AI: - Idle - Patrol - Chase - Attack - Flee

Advanced: - State machines - Weighted actions - Cooldowns - Distance
checks - HP/resource thresholds - Phase logic - Behavior trees where
justified - Utility AI where justified

Bosses should be composed from generic systems rather than a special
monolith.

Spawn/encounter support: - Random encounters - Visible encounters -
Spawn zones/points - Waves - Respawn - Rare/elite enemies - Boss
encounters - Conditional/world-state-dependent spawns

## 29. Game UI Framework

Reusable templates/systems:

-   Title/main menu
-   HUD
-   Dialogue
-   Inventory/equipment/status
-   Skills
-   Shop
-   Quest
-   Battle UI
-   Pause/settings
-   Save/load
-   Game over

Templates should be customizable and not dictate a single game style.

## 30. Structured Database

Potential categories:

-   Actors
-   Classes/jobs
-   Skills/abilities
-   Items/equipment
-   Enemies
-   States
-   Elements
-   Resources
-   Recipes
-   Loot tables
-   NPC interactions
-   AI profiles
-   Quests
-   Maps
-   Tags

Editor operations: - Search/filter/sort - Duplicate - Bulk edit -
Reference navigation - Validation

## 31. Gameplay System Builder

Asteria should eventually provide a higher-level authoring layer that
lets creators assemble reusable gameplay systems from:

-   Inputs
-   Conditions/checks
-   Actions
-   Effects
-   Resources
-   Triggers
-   Data
-   Rewards/consequences
-   Events

The purpose is to let non-programmers invent game systems rather than
limiting them to predefined mechanics.

## 32. Python Scripting and Plugins

Integrated Python scripting should eventually provide:

-   Syntax highlighting
-   Autocomplete
-   Engine API completion
-   Type hints
-   Error navigation
-   Runtime traceback
-   Script reload where safe
-   Object/script linking

Scripts should operate through stable public APIs rather than private
registries.

Plugins may add: - Components - Systems - Editor panels - Importers -
Gameplay nodes - Event commands - Inspector fields - Asset types - Tools

Uncontrolled monkey-patching of internals should be avoided.

## 33. Serialization / Project / Save Data

Editor-authored data must remain distinct from transient runtime
objects.

Project data requirements: - Stable IDs - References - Versioning -
Validation - Migration - Human-readable representation where practical

Runtime saves may include: - Player/party - Inventory/equipment -
Quests - Variables/switches - NPC state - Scene/world state -
Game-defined persistent data

## 34. Play Test / Debug / Profiling

Play test: - Run project - Run current scene - Spawn at selected point -
Fast restart - Logs - Runtime inspection

Live debugger: - Stats/resources - Position - States/effects -
Abilities - Animation - AI - Quest/world state - Variables/switches

Debug actions: - Give/remove item - Change stats/resources - Add/remove
state - Teleport - Trigger event - Spawn/kill enemy - Change quest/world
state

Profiling should eventually expose: - Frame/update/render time - AI -
Collision - Entity counts - Particles - Draw calls where measurable -
Memory - Asset usage

## 35. Stress Tests

### JRPG Stress Test

Demonstrate: - Four-character party - Jobs/secondary jobs -
Weapon/element weaknesses - Multi-hit - Guard/shield resource -
Break-like mechanic - Boost-like resource - Passives - Turn-order
manipulation - Equipment interactions - NPC interactions -
Capture/companion - Multi-phase boss

### ARPG Stress Test

Demonstrate: - Realtime movement - Jump/dash/dodge - I-frames -
Combos/cancel windows - Skills/magic/resources - Hitbox/hurtbox -
Knockback/hitstop - Projectiles - Enemy/boss AI - Equipment/mastery -
Loot - Crafting/alchemy - Exploration/progression

Both must run on the same Engine Core without core redesign.

## 36. Starter Projects and Assets

Potential templates: - Empty Project - Classic JRPG - Advanced JRPG - 2D
ARPG - Side-scrolling ARPG

Bundled assets only need to support testing, tutorials and examples.
Asteria does not need to compete on art quantity.

## 37. Non-Goals

Asteria is not responsible for: - Story quality - Art direction -
Character design - Music composition - Game balance - Creative
concepts - Automatically creating complete games

Asteria is primarily a 2D engine. Full 3D engine scope is not a primary
target.

## 38. Extensibility Order

A new mechanic should ideally be implementable through:

1.  Existing GUI configuration
2.  Existing gameplay-system composition
3.  Gameplay System Builder
4.  Small Python extension
5.  Plugin
6.  Engine-core modification only as a last resort

Frequent need for step 6 indicates an architecture problem.

## 39. Success Criteria

Asteria succeeds when:

-   Beginners can make conventional RPGs without programming.
-   Intermediate creators can build sophisticated RPG/ARPG mechanics
    visually.
-   Advanced creators can extend the framework cleanly with Python.
-   Engine internals can evolve without routinely breaking ordinary
    projects.
-   Complex JRPG and ARPG stress tests coexist on the same Engine Core.

## 40. Learning Goal

Asteria is also a serious engine-architecture learning project.

Development should deliberately expose and document:

-   Game loop
-   Scene management
-   Entity/component architecture
-   Systems
-   Rendering
-   Animation
-   Input
-   Collision/physics
-   Asset lifetime
-   Serialization
-   Editor/runtime separation
-   Gameplay architecture
-   Scripting
-   Performance
-   Debugging

## 41. Development Philosophy

For each major subsystem:

1.  Explain why it exists.
2.  Compare reasonable engine approaches.
3.  Choose and document the architecture.
4.  Implement a minimal usable version.
5.  Build a practical example.
6.  Test behavior and usability.
7.  Review architecture.
8.  Extend only after the boundary is proven.

Avoid large speculative infrastructure before the boundary has been
validated.

## 42. Initial Technical Vertical Slice

First implementation:

Application → Game Loop → Scene → Entity → Component → Transform →
Renderer → Input → Movable Sprite.

RPG-specific systems should not precede validation of the runtime
foundation.

## 43. Product Definition

> **Asteria is a Python-first 2D RPG / ARPG game engine combining a
> low-barrier visual authoring experience with advanced data-driven
> gameplay frameworks capable of supporting highly complex JRPG and
> action-RPG systems without requiring creators to write core-level
> engine code.**

> **Creators should spend their time designing games, not rebuilding the
> engine functionality required to express those designs.**

------------------------------------------------------------------------

# 44. Composable Presentation and Visual Attachment Model

Asteria must treat presentation as composition of reusable visual/audio primitives rather than requiring every visible result to be baked into a character or skill asset.

The canonical model must support all of these authoring modes concurrently:

``` text
Baked       = one authored asset already contains the complete visual
Layered     = multiple independently animated visual layers
Attached    = an asset follows a named socket/anchor on another visual
Procedural  = runtime text/particles/material/shader/generated presentation
Hybrid      = any combination of the above
```

No mode is mandatory. Projects may freely mix them per actor, action, scene, or presentation sequence.

## 44.1 Generic visual attachments

Attachments are not weapon-specific. Any compatible project asset may be attached, including weapons, shields, hats, hair, capes, wings, held props, lights, VFX, status visuals, equipment, or project-defined visuals.

An attachment/socket contract must support, where applicable:

``` text
stable socket/anchor ID
parent visual/entity reference
child asset/entity reference
position / rotation / scale
flip / visibility / opacity
z-order / render layer
per-frame or keyed transform overrides
inheritance rules
offset and pivot
attach / detach / swap
lifetime / ownership
serialization / save-load identity
```

Sockets are semantic attachment points, not a requirement for skeletal animation. Sprite-frame animation may provide per-frame socket transforms.

## 44.2 Reusable action composition

A character action must not require a separate complete sprite sheet for every weapon, skill, element, status, or cosmetic combination.

A project may compose, for example:

``` text
actor swing motion
+ attached weapon
+ independent trail VFX
+ projectile
+ impact VFX
+ target reaction
+ animated text
+ material/shader effect
+ camera
+ audio
+ hit-stop
```

The same motion, equipment asset, and VFX may be reused independently by other actors and sequences.

Baked character+weapon or character+effect animations remain fully supported when artistic quality requires them.

## 44.3 Generic animated text / popup presentation

Damage numbers are a preset/use case, not an Engine Core gameplay concept. Asteria must provide generic animated text/popup presentation usable in world space or screen space.

It must be possible to present arbitrary project-defined content such as numeric values, localized text, icons, labels, healing, misses, status feedback, interaction feedback, or non-combat notifications without adding a new Engine Core feature.

Authoring may control font/material, outline/shadow, alignment, anchor, motion/easing, scale, opacity, duration, stacking/merging policy, and optional VFX/audio. Gameplay decides the semantic value; Presentation decides whether and how it appears.

## 44.4 Editor and runtime parity

The Editor and Python API must author the same canonical attachment and composition model. The Editor should provide socket/anchor inspection, visual placement, attachment preview, layer ordering, timeline/key editing, asset replacement, and validation without creating a GUI-only representation.

Runtime must resolve the same stable asset IDs and attachment identities used by serialization. Missing or incompatible attachments must produce structured diagnostics rather than silent visual degradation.

## 44.5 Presentation invariant extension

No gameplay event implies a mandatory visual presentation. No presentation component requires a predefined gameplay meaning. Attachments, VFX, text, camera, audio, materials, and animation are reusable presentation channels that projects may replace, suppress, compose, or extend.

## Character Generator
Asteria provides an optional Editor-side layered Character Generator for projects that want built-in character authoring. It is not a runtime character type and never restricts custom artwork. Generated characters and user-authored/imported characters converge on the same canonical asset/runtime path. The starter preset targets clean RPG-style 48x48 characters, while projects may define other resolutions and animation layouts.
