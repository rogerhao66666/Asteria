# ASTERIA_ART_DIRECTION.md

**Status:** Canonical\
**Canonical role:** Official visual language, art-quality requirements
and production-quality gates

> **Where Asteria stands (2026-10-29).** This is a design specification: it records the goals and
> principles the engine is built towards. What is implemented today is described in
> [`docs/ENGINE_HANDBOOK.md`](../ENGINE_HANDBOOK.md), the user manual
> ([`docs/manual/`](../manual/)) and the decision log
> ([`docs/audits/DECISION_LOG.md`](../audits/DECISION_LOG.md)). Decisions that changed this
> specification:
>
> - **No generated art.** Asteria ships no AI-generated art and has no image generator in its
>   pipeline. The bundled art is third-party CC0 packs (mainly Foozle's Lucifer packs, in
>   `asset_library/`; licences in [`THIRD_PARTY_ASSETS.md`](../../THIRD_PARTY_ASSETS.md)).
> - **The Character Generator is cancelled** (decision log D2). Characters come from sprite sheets
>   the author imports; the canonical asset path below still applies to them.
> - The demos use the Foozle Lucifer packs as their main art; Ninja Adventure and a few other CC0
>   packs fill gaps. The quality rules below still describe what official art should meet.

# ASTERIA_ART_DIRECTION.md

**Status:** Baseline v1\
**Scope:** Official Asteria Starter Assets and showcase content\
**Role:** Product requirement + engineering input

## 1. Product rule

Official Asteria art is not a placeholder layer added after engine
development.

A user-visible official asset must pass all four gates:

1.  Technical Quality
2.  Art Quality
3.  Animation / Motion Quality
4.  In-Scene Cohesion

Test fixtures may be visually crude, but they remain under test-only
paths and are never presented as Starter Assets.

## 2. Visual target

Asteria Starter Pack targets a polished modern JRPG pixel-art
presentation:

-   readable silhouettes
-   detailed but controlled pixel clusters
-   attractive hand-crafted impression
-   coherent proportions
-   deliberate material rendering
-   strong animation poses
-   layered environment depth
-   modern lighting/VFX compatibility
-   suitable for an HD-2D-style composition pipeline

The target is not to imitate RPG Maker defaults or any specific
commercial game's copyrighted characters/assets. Asteria uses an
original visual identity.

## 3. Reference quality floor

The current brown-haired swordsman reference supplied during design
discussion establishes the **minimum character finish level**, not a
sheet-layout specification.

Qualities to preserve conceptually:

-   immediately readable JRPG character
-   expressive silhouette
-   detailed hair
-   readable armor/material separation
-   cloth/cape secondary motion
-   directional consistency
-   strong attack pose
-   attractive pixel shading

Do not copy the reference character design exactly.

## 4. Default Hero direction

Initial original Asteria hero:

-   young adventurer / swordsman
-   warm brown hair
-   dark steel/light armor
-   deep blue travel cloak
-   restrained warm leather accents
-   readable sword silhouette
-   adventurous rather than overly ornate
-   compact JRPG proportions

The design must remain recognizable from front, side and rear views.

## 5. Character rendering

Default movement frame target: 48×48 canonical runtime frame.

A source image may be generated at higher resolution and normalized
later.

Important rules:

-   stable head/body proportion across frames
-   feet/world anchor does not drift
-   outlines remain coherent
-   face remains readable at runtime scale
-   equipment does not randomly change between directions
-   left/right views remain logically consistent
-   rear view is genuinely designed, not a corrupted front view
-   no accidental semi-transparent edge halo

Attack/cast animations may use larger canonical frames when needed.
Never crop a good pose merely to preserve 48×48.

## 6. Pixel language

Pixel art should feel intentional rather than like a low-resolution
smooth illustration.

Prefer:

-   deliberate clusters
-   controlled highlight placement
-   restrained sub-pixel-looking noise
-   readable edges
-   consistent density of detail

Reject:

-   blurry downscales
-   inconsistent pixel sizes
-   excessive noisy dithering
-   photographic textures
-   AI-smear details
-   random outline thickness

## 7. Palette and materials

The Starter Pack uses a coherent world palette rather than forcing every
asset into one tiny palette.

Material families must remain recognizable:

-   foliage: natural greens with controlled hue variation
-   wood/leather: warm earth tones
-   stone/metal: cooler neutral families
-   water/magic: cleaner saturated accents
-   UI: dark neutral foundation with restrained premium accents

Characters must remain readable against common terrain.

## 8. Lighting philosophy

Base sprites should contain enough authored shading to read without
scene lighting, while avoiding baked lighting so strong that dynamic
lighting looks wrong.

Engine lighting may add:

-   directional light
-   local lamps
-   spell light
-   rim/highlight
-   shadows
-   atmospheric depth

Do not bake an entire scene's lighting into reusable character sprites.

## 9. Environment direction

Initial visual slice: **Forest Village**.

Required visual families:

-   grass
-   dirt and stone paths
-   water
-   trees/bushes/flowers
-   rocks
-   fences
-   lamps
-   signs
-   chests
-   village houses
-   inn/shop-like building
-   environmental decoration

The village should look intentionally composed, not like a technical
tile-grid demo.

## 10. Tiles

Default canonical tile: 32×32.

Tiles must:

-   tile without obvious unintended seams
-   share perspective
-   share scale
-   share lighting assumptions
-   provide useful transition pieces
-   support natural-looking map composition

Autotile/transition needs must influence importer and editor
architecture.

## 11. Props and buildings

Props need stable pivots, collision footprints and occlusion behavior.

Tall assets must support correct character layering.

Buildings may require:

-   base layer
-   roof/foreground layer
-   doorway anchor
-   shadow
-   light anchors
-   interior scene reference

Therefore the engine must not assume every environment object is one
flat sprite.

## 12. Depth / HD-2D composition

Asteria should support visual composition using:

-   2D pixel assets
-   world depth
-   foreground/background layers
-   shadows
-   particles
-   dynamic lighting
-   atmospheric effects
-   camera movement
-   post-processing where appropriate

The art pipeline must preserve clean source assets so these systems can
operate independently.

## 13. Animation quality

Animation acceptance is not based only on frame count.

Good animation considers:

-   anticipation
-   acceleration/deceleration
-   weight
-   contact
-   follow-through
-   recovery
-   secondary hair/cloth motion
-   readable key poses
-   looping continuity

The engine supports arbitrary animation clip names and frame counts;
Starter Pack defaults are templates only.

## 14. Movement

Walk and run must visibly differ.

Walk: - grounded - readable foot alternation - subtle body bob -
restrained cloak/hair motion

Run: - stronger forward intent - larger limb motion - stronger secondary
motion - faster cadence

Idle should feel alive without distracting constant motion.

## 15. Combat

Combat presentation should support:

-   startup
-   active/action phase
-   impact
-   recovery
-   hit-stop
-   VFX
-   audio
-   camera response
-   optional movement/displacement

A sword attack should not look like four unrelated generated poses.

## 16. VFX language

Starter VFX should be vivid and readable while complementing pixel
characters.

Initial families:

-   physical slash
-   impact
-   fire
-   ice
-   lightning
-   heal
-   buff/debuff
-   smoke/spark

VFX can use sprite animation, particles, shader effects, lights, or
composites.

Do not bake all VFX into character sheets.

## 17. Fireball baseline

Fireball presentation should conceptually separate:

-   cast cue
-   projectile
-   trail/light
-   impact
-   optional lingering particles

This allows timing and gameplay events to remain independent.

## 18. UI direction

Official RPG UI must look intentional and product-ready.

Target:

-   modern JRPG readability
-   dark neutral panels
-   restrained decorative framing
-   strong hierarchy
-   scalable/9-slice components
-   coherent icons
-   good controller/mouse/touch states where relevant

Reject generic debug/developer-tool widgets as game UI.

## 19. Portraits and icons

Portraits must preserve character identity and outfit details.

Icons must remain recognizable at 32×32 and share:

-   perspective
-   outline language
-   lighting direction
-   detail density

Do not generate each icon as an unrelated illustration style.

## 20. Art consistency system

Every production generation batch should reference a shared style
package:

-   character turnaround
-   proportion guide
-   palette/material guide
-   environment reference
-   icon reference
-   VFX reference
-   UI reference

Generated content that violates identity/style consistency is rejected
or repaired.

## 21. Quality gates

### Gate A --- Technical

Must pass:

-   canonical dimensions/schema
-   alpha correctness
-   valid frames
-   stable pivot
-   valid references
-   load/save
-   runtime compatibility

### Gate B --- Art

Review:

-   silhouette
-   anatomy/proportion
-   pixel quality
-   material readability
-   lighting consistency
-   asset identity
-   absence of AI artifacts

### Gate C --- Motion

Review:

-   pose continuity
-   timing
-   weight
-   drift
-   loop quality
-   secondary motion
-   combat readability

### Gate D --- In-Scene

Review assets together in the Starter Village.

The scene must look like one game.

Check:

-   character/environment scale
-   palette harmony
-   perspective
-   lighting
-   visual hierarchy
-   VFX integration
-   UI integration
-   animation during actual play

Passing Technical alone is never sufficient for official Starter Assets.

## 22. Engineering consequences

Art requirements explicitly affect engine architecture.

The asset/runtime systems must allow:

-   arbitrary frame dimensions
-   variable animation frame counts
-   stable/custom pivots
-   per-frame timing
-   animation events
-   sprites larger than logical collision bounds
-   foreground/background layering
-   occlusion
-   VFX outside actor bounds
-   particles
-   lighting hooks
-   shader/material hooks
-   atlas padding
-   pixel-perfect sampling
-   camera choreography
-   source-to-runtime normalization

Do not simplify these away merely because a placeholder does not need
them.

## 23. Starter visual slice

The first production art milestone should demonstrate one coherent
playable slice:

``` text
Forest Village
├── Default Hero
├── 2+ NPCs
├── Slime
├── Goblin
├── grass/path/water/stone tiles
├── trees and vegetation
├── houses / inn
├── props
├── item/equipment/skill icons
├── Slash
├── Fireball
├── Impact / Heal VFX
├── ambient particles
└── Default RPG UI
```

The slice is the visual integration test for the entire asset pipeline.

## 24. Production workflow

``` text
Art Direction
      ↓
Reference / Style Package
      ↓
Generate or author source material
      ↓
Asteria Import Pipeline
      ↓
Normalize / Validate
      ↓
Art Review
      ↓
Animation Review
      ↓
In-Scene Review
      ↓
Official Starter Asset
```

## 25. Definition of done

An official asset is complete only when:

-   it is technically valid;
-   it looks production-ready at intended runtime scale;
-   animated assets move convincingly;
-   it remains visually coherent with the Starter Pack;
-   it works in an actual Asteria scene;
-   it does not require hidden manual repair to function.

## 26. Permanent rule

**Asteria does not trade visual quality for technical correctness, or
technical correctness for visual quality. Official assets require
both.**

------------------------------------------------------------------------

# 28. Art Direction for Composable Presentation

Official Asteria examples should demonstrate that composition can produce polished presentation rather than looking like disconnected programmer-art layers.

When art is separated into body/equipment/VFX/other layers:

- silhouettes and contact points must remain convincing;
- attached equipment must not visibly float, lag, or jitter;
- socket motion must respect anticipation, follow-through, perspective, and direction;
- z-order changes must correctly handle front/behind-body motion;
- VFX must visually connect to the originating motion;
- lighting/material treatment should make independently authored layers feel coherent;
- composition must not be used when a baked animation produces materially better art.

Starter examples should include at least one polished layered/attached presentation and one baked or hybrid example so users understand both workflows are first-class.

Animated text examples should demonstrate high-quality typography, timing, easing, hierarchy, and readability. A technically functioning damage-number popup is not Art PASS merely because the value renders correctly.

------------------------------------------------------------------------

# Production animation art-control rule

The image generator is an art rendering tool, not the animator of record. Pose progression, timing, contacts, weight transfer, anticipation/action/recovery, loop seam and socket/grip trajectories are defined before generation. Generated frames are accepted only when they realize that authored motion plan while preserving the approved Master Reference.

Character consistency is judged against the Master Reference on every accepted frame, not merely against the previous generated frame. Adjacent frames are continuity references, never replacement identity references.

A technically clean image with wrong motion, weak weight, identity drift, costume drift, source clipping, or unstable proportions fails art acceptance. Stabilization may remove positional jitter but must not be used to disguise incorrect drawing or morphing.

Final animation art review includes temporal playback. Static sheet appearance alone is not sufficient for Art/Motion PASS.
