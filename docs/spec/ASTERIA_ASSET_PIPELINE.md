# ASTERIA_ASSET_PIPELINE.md

**Status:** Canonical consolidation draft\
**Canonical role:** Source → canonical asset processing architecture and
operational SOPs\
**Merged sources:** old `ASTERIA_ASSET_PIPELINE.md` +
`ASTERIA_SPRITE_PRODUCTION_SOP.md`

Sprite Production is an SOP chapter here. Future Tileset/VFX/etc. SOPs
should extend this document rather than become additional top-level
canonical MD files.

------------------------------------------------------------------------

# Part A --- Asset Pipeline Architecture

# Asteria Asset Pipeline Architecture

**Status:** Draft baseline\
**Purpose:** Define the canonical pipeline that converts generated,
imported, or existing visual material into validated Asteria runtime
assets.

------------------------------------------------------------------------

## 1. Core objective

Asteria must support this end-to-end flow:

``` text
Prompt / Image / Video / Existing Asset
                ↓
        Asteria Import Pipeline
                ↓
        Normalized Game Asset
                ↓
      Animation + Event + VFX
                ↓
             Runtime
```

The engine must not depend on any single image-generation or
video-generation provider.

Asteria owns the asset contract, validation rules, metadata, import
logic, animation semantics, and runtime behavior.

External tools only provide source material.

------------------------------------------------------------------------

# 2. Design principles

## 2.1 Provider-independent

Supported sources may include:

``` text
GPT Image
Gemini
local image model
img2video model
artist-created PNG
RPG Maker-style spritesheet
itch.io asset pack
video file
GIF/APNG
legacy project asset
custom external tool
```

None of these may become a required runtime dependency.

------------------------------------------------------------------------

## 2.2 Canonical internal representation

All sources must converge to the same canonical Asteria asset
representation before runtime use.

``` text
External Source
      ↓
Import
      ↓
Normalize
      ↓
Validate
      ↓
Canonical Asset
      ↓
Runtime
```

Runtime code must not contain special cases such as:

``` text
if source == "GPT"
if source == "RPGMaker"
if source == "Video"
```

Source-specific behavior belongs in adapters and import processors.

------------------------------------------------------------------------

## 2.3 Visual quality and runtime correctness are separate concerns

AI may generate visually excellent content while violating technical
requirements.

Therefore:

``` text
Generation = art creation
Processing = technical correctness
```

Asteria must never assume a visually correct image is already a
technically valid game asset.

------------------------------------------------------------------------

# 3. High-level architecture

``` text
┌────────────────────────────────────────────┐
│                SOURCE LAYER                │
│                                            │
│ Prompt | Image | Video | Existing Asset    │
└──────────────────────┬─────────────────────┘
                       ↓
┌────────────────────────────────────────────┐
│              SOURCE ADAPTERS               │
│                                            │
│ ImageAdapter                               │
│ SpriteSheetAdapter                         │
│ VideoAdapter                               │
│ GeneratedAssetAdapter                      │
│ LegacyAssetAdapter                         │
└──────────────────────┬─────────────────────┘
                       ↓
┌────────────────────────────────────────────┐
│            ASTERIA IMPORT PIPELINE         │
│                                            │
│ Decode                                     │
│ Background / Alpha handling                │
│ Frame extraction                           │
│ Grid slicing                               │
│ Crop                                       │
│ Resize                                     │
│ Alignment                                  │
│ Pivot normalization                        │
│ Direction mapping                          │
│ Timing normalization                       │
│ Atlas packing                              │
└──────────────────────┬─────────────────────┘
                       ↓
┌────────────────────────────────────────────┐
│               VALIDATION                   │
│                                            │
│ Dimensions                                 │
│ Frame count                                │
│ Alpha                                      │
│ Pivot                                      │
│ Bounds                                     │
│ Consistency                                │
│ Missing frames                             │
│ Style/palette warnings                     │
└──────────────────────┬─────────────────────┘
                       ↓
┌────────────────────────────────────────────┐
│          CANONICAL ASTERIA ASSET           │
│                                            │
│ PNG / Atlas                                │
│ Metadata                                   │
│ Animation clips                            │
│ Events                                     │
│ Tags                                       │
│ Collision / interaction data               │
└──────────────────────┬─────────────────────┘
                       ↓
┌────────────────────────────────────────────┐
│          PRESENTATION INTEGRATION          │
│                                            │
│ Animation                                  │
│ VFX                                        │
│ Audio                                      │
│ Camera                                     │
│ Lighting                                   │
│ Hit-stop                                   │
│ Choreography                               │
└──────────────────────┬─────────────────────┘
                       ↓
┌────────────────────────────────────────────┐
│                 RUNTIME                    │
└────────────────────────────────────────────┘
```

------------------------------------------------------------------------

# 4. Source layer

The source layer describes where content originates.

## 4.1 Prompt source

Example:

``` text
"brown-haired young swordsman,
blue cape,
pixel art,
four-direction RPG character"
```

A prompt is not itself an asset.

It produces one or more source images that then enter the import
pipeline.

------------------------------------------------------------------------

## 4.2 Image source

Supported examples:

``` text
single transparent character image
character turnaround
sprite strip
sprite sheet
tileset
portrait
icon
VFX sheet
prop image
```

------------------------------------------------------------------------

## 4.3 Video source

Supported examples:

``` text
MP4
MOV
WebM
GIF
APNG
```

A video source may be converted into:

``` text
frame sequence
sprite animation
VFX animation
environment animation
```

Video must not automatically become a runtime video texture unless
explicitly requested.

------------------------------------------------------------------------

## 4.4 Existing asset source

Examples:

``` text
RPG Maker-format sprite
generic 4×4 walking sheet
existing tileset
old Asteria asset
third-party asset pack
artist-made source
```

------------------------------------------------------------------------

# 5. Source adapters

Adapters convert source-specific structure into an intermediate
representation.

Recommended interfaces:

``` text
BaseAssetSourceAdapter
├── ImageSourceAdapter
├── SpriteSheetSourceAdapter
├── VideoSourceAdapter
├── GeneratedImageSourceAdapter
├── GeneratedVideoSourceAdapter
└── LegacyAssetSourceAdapter
```

Common output:

``` text
ImportedAssetSource
├── source_type
├── source_files
├── decoded_frames
├── source_metadata
├── detected_layout
└── warnings
```

Adapters must remain separate from runtime asset classes.

------------------------------------------------------------------------

# 6. Import pipeline stages

The import pipeline should be modular.

Recommended processor chain:

``` text
DecodeProcessor
AlphaProcessor
FrameExtractionProcessor
CropProcessor
ScaleProcessor
AlignmentProcessor
PivotProcessor
DirectionProcessor
TimingProcessor
AtlasProcessor
ValidationProcessor
```

Each processor should be independently testable.

------------------------------------------------------------------------

# 7. Decode

Decode converts source material into a standard in-memory
representation.

Target:

``` text
RGBA image/frame sequence
```

Avoid retaining provider-specific image formats internally.

------------------------------------------------------------------------

# 8. Alpha/background handling

Possible source cases:

``` text
already transparent
solid-color background
checkerboard baked into image
generated image with opaque background
video with opaque background
```

Processing options:

``` text
preserve alpha
background removal
chroma-key
manual mask
AI-assisted segmentation
```

Result must have valid RGBA transparency when the asset type requires
it.

------------------------------------------------------------------------

# 9. Frame extraction

For video/GIF/APNG:

``` text
source frames
      ↓
candidate frames
      ↓
selected gameplay frames
```

Do not assume every source frame should become a runtime frame.

Frame selection may use:

``` text
fixed interval
motion difference
keyframe detection
pose change
manual selection
```

------------------------------------------------------------------------

# 10. Grid slicing

For spritesheets:

``` text
frame_width
frame_height
margin
spacing
columns
rows
```

The importer should visualize detected slices before committing.

Automatic detection is helpful, but manual override must always exist.

------------------------------------------------------------------------

# 11. Crop and padding

Each frame may contain unnecessary transparent space.

Processing:

``` text
detect visible bounds
crop
apply canonical padding
restore target frame size
```

Cropping must not destroy the intended world-space pivot.

------------------------------------------------------------------------

# 12. Scaling

Scaling modes:

``` text
nearest-neighbor
pixel-perfect integer scale
fit-with-padding
manual
```

Pixel-art assets must default to nearest-neighbor scaling.

No bilinear filtering by default.

------------------------------------------------------------------------

# 13. Alignment

AI-generated or video-derived frame sequences commonly drift.

Asteria should support:

``` text
bottom-center alignment
feet alignment
bounding-box alignment
center-of-mass alignment
manual anchor alignment
```

Recommended default for RPG characters:

``` text
feet / bottom-center
```

------------------------------------------------------------------------

# 14. Pivot normalization

All runtime frames need a stable world anchor.

Example:

``` text
48×48 character frame
pivot = (24, 44)
```

Asteria should allow:

``` text
global animation pivot
per-direction pivot
per-frame pivot override
```

Default workflow should avoid per-frame override unless necessary.

------------------------------------------------------------------------

# 15. Direction mapping

Canonical direction names:

``` text
down
left
right
up
```

Optional:

``` text
down_left
down_right
up_left
up_right
```

The runtime must not assume four directions globally.

Direction count belongs to the asset.

------------------------------------------------------------------------

# 16. Timing normalization

Imported material may contain arbitrary timing.

Canonical animation data should support:

``` text
fps
or
per-frame duration
```

Example:

``` json
"frame_durations_ms": [100, 80, 120, 80]
```

Per-frame timing should take precedence when present.

------------------------------------------------------------------------

# 17. Atlas packing

Frames may be stored as:

``` text
separate PNGs
animation sheet
shared atlas
```

Recommended production path:

``` text
source images
   ↓
canonical animation sheets
   ↓
optional runtime atlas
```

Do not require source authors to manually create the atlas.

------------------------------------------------------------------------

# 18. Validation pipeline

Validation should distinguish:

``` text
ERROR
WARNING
INFO
```

Errors block use.

Warnings allow use but inform the user.

------------------------------------------------------------------------

# 19. Hard validation errors

Examples:

``` text
metadata references missing file
PNG cannot decode
frame dimensions invalid
declared grid does not fit image
pivot lies outside frame
zero-frame animation
required direction missing
unsupported metadata version
```

------------------------------------------------------------------------

# 20. Validation warnings

Examples:

``` text
visible pixels touch frame edge
character scale changes significantly
probable frame drift
possible background artifact
empty frame detected
palette changes unexpectedly
weapon shape changes strongly
animation loop discontinuity detected
```

AI-derived assets may generate warnings frequently without being
unusable.

------------------------------------------------------------------------

# 21. Auto-fix

Auto-fix should remain deterministic where possible.

Safe auto-fixes:

``` text
crop transparent border
pad frame
resize with nearest-neighbor
align pivot
shift frame
normalize alpha
remove empty outer rows/columns
repack atlas
```

Potentially destructive fixes should require preview/confirmation.

------------------------------------------------------------------------

# 22. Canonical asset types

Phase 1:

``` text
Character
NPC
Monster
Tileset
Prop
Icon
Portrait
VFX
```

Future:

``` text
AnimatedProp
EnvironmentLayer
Projectile
Decal
UITheme
ParticleTexture
BackgroundLayer
ParallaxLayer
```

------------------------------------------------------------------------

# 23. Canonical character asset

Suggested structure:

``` text
CharacterAsset
├── id
├── display_name
├── tags
├── render
├── directions
├── animations
├── events
├── collision
├── interaction
└── metadata
```

------------------------------------------------------------------------

# 24. Canonical animation clip

``` text
AnimationClip
├── id
├── frame_source
├── frame_size
├── frame_count
├── direction
├── timing
├── loop
├── pivot
├── events
└── playback_tags
```

The engine must not hardcode a fixed list such as idle/walk/attack.

Those are conventions, not engine limitations.

------------------------------------------------------------------------

# 25. Animation events

Events allow animation to coordinate gameplay/presentation.

Examples:

``` text
footstep
weapon_swing
damage_window_open
damage_window_close
spawn_projectile
spawn_vfx
play_sfx
camera_shake
hit_stop
character_move
```

Example:

``` json
{
  "frame": 3,
  "event": "spawn_vfx",
  "params": {
    "effect": "slash_blue"
  }
}
```

------------------------------------------------------------------------

# 26. Gameplay separation

Animation must not contain hidden gameplay logic.

Bad:

``` text
frame 3 directly subtracts enemy HP
```

Better:

``` text
frame 3 emits "damage_window"
combat system handles damage
```

This keeps presentation reusable and testable.

------------------------------------------------------------------------

# 27. VFX integration

VFX may be:

``` text
sprite animation
particle effect
shader effect
light effect
screen-space effect
composite effect
```

Animation events reference VFX assets through IDs.

Example:

``` text
spawn_vfx("slash_blue")
```

The character sprite itself should not need to contain every effect.

------------------------------------------------------------------------

# 28. Audio integration

Animation/event metadata may emit semantic audio events:

``` text
footstep_stone
sword_swing_light
sword_hit_flesh
spell_cast_fire
```

Runtime audio resolution decides the actual sound asset.

This supports project-level theme replacement.

------------------------------------------------------------------------

# 29. Camera integration

Animation/presentation events may request:

``` text
camera_shake
camera_pan
camera_zoom
camera_focus
camera_impulse
```

Camera logic remains in the presentation system.

------------------------------------------------------------------------

# 30. Hit-stop

Battle presentation may synchronize:

``` text
damage event
VFX impact
audio impact
camera impulse
hit-stop
```

Example timeline:

``` text
0 ms     attack starts
140 ms   weapon swing event
210 ms   damage window
210 ms   hit-stop starts
210 ms   impact VFX
210 ms   impact audio
270 ms   hit-stop ends
430 ms   recovery
```

This matches Asteria's broader choreography architecture.

------------------------------------------------------------------------

# 31. Runtime responsibilities

Runtime should only consume canonical assets.

Runtime responsibilities:

``` text
load
cache
animate
render
dispatch animation events
integrate presentation channels
stream/unload when needed
```

Runtime should not perform heavyweight source cleanup or AI inference.

------------------------------------------------------------------------

# 32. Editor workflow

Target UI:

``` text
Import Asset
    ↓
Choose Source
    ↓
Auto Detect
    ↓
Preview
    ↓
Normalize
    ↓
Validate
    ↓
Fix Warnings
    ↓
Save Canonical Asset
```

Beginner mode:

``` text
Import → Auto Fix → Use
```

Advanced mode exposes:

``` text
grid
frame timing
pivot
direction mapping
events
atlas
collision
tags
metadata
```

------------------------------------------------------------------------

# 33. Prompt-generated workflow

Future workflow:

``` text
Create Character
      ↓
Enter prompt
      ↓
Choose provider
      ↓
Generate reference
      ↓
Generate animation source
      ↓
Asteria Import Pipeline
      ↓
Validate
      ↓
Canonical CharacterAsset
```

Generation providers must plug in behind an interface.

------------------------------------------------------------------------

# 34. AI provider interface

Potential architecture:

``` text
AssetGenerationProvider
├── generate_image()
├── generate_variation()
├── generate_animation_source()
├── capabilities()
└── provider_metadata()
```

Possible implementations:

``` text
GPTImageProvider
GeminiImageProvider
LocalImageProvider
CustomProvider
```

This interface is optional and belongs after the core import pipeline is
stable.

------------------------------------------------------------------------

# 35. Character reference system

To improve cross-animation consistency:

``` text
CharacterReferenceAsset
├── front
├── left
├── right
├── back
├── palette
├── outfit_reference
├── weapon_reference
├── proportion_reference
└── style_tags
```

All generated animations should reference the same character reference.

------------------------------------------------------------------------

# 36. Video-to-sprite workflow

``` text
walk.mp4
   ↓
VideoSourceAdapter
   ↓
decode frames
   ↓
background removal
   ↓
motion/frame analysis
   ↓
select key frames
   ↓
alignment
   ↓
pivot normalization
   ↓
timing
   ↓
animation sheet
   ↓
CharacterAsset
```

Asteria should support reducing 24/30/60 FPS source video into a much
smaller gameplay animation.

------------------------------------------------------------------------

# 37. Existing spritesheet workflow

``` text
existing_sheet.png
       ↓
SpriteSheetSourceAdapter
       ↓
detect grid
       ↓
manual confirmation
       ↓
direction mapping
       ↓
pivot
       ↓
timing
       ↓
canonical AnimationClip
```

This should support common external RPG asset conventions without
embedding those conventions into runtime.

------------------------------------------------------------------------

# 38. Tileset workflow

``` text
tiles.png
   ↓
detect tile size/grid
   ↓
validate
   ↓
tile metadata
   ↓
optional:
collision
terrain tags
autotile rules
animation
footstep type
```

A scene screenshot is not a tileset.

------------------------------------------------------------------------

# 39. Environment asset integration

Environment assets may contain presentation components such as:

``` text
WindReactive
WaterSurface
FireFlicker
LeafEmitter
ClothFlutter
LightFlicker
AmbientMotion
```

These are engine components, not baked requirements of the source PNG.

------------------------------------------------------------------------

# 40. HD-2D composition

Asteria should enable composition like:

``` text
2D sprite assets
+ world depth
+ lighting
+ particles
+ shadows
+ camera
+ post-processing
```

The quality target comes from composition of systems, not from forcing
all visual information into one generated image.

------------------------------------------------------------------------

# 41. Performance rules

Import-time processing may be relatively expensive.

Runtime must remain lightweight.

Prefer:

``` text
preprocessed assets
prepacked atlas
cached metadata
GPU-friendly texture layout
batched rendering where practical
```

Avoid:

``` text
runtime background removal
runtime AI generation
runtime frame extraction
runtime expensive normalization
```

------------------------------------------------------------------------

# 42. Determinism

Canonical asset builds should be reproducible where practical.

Given the same source and import settings:

``` text
same crop
same pivot
same atlas layout
same metadata
```

Generation itself may be nondeterministic, but import processing should
not be.

------------------------------------------------------------------------

# 43. Source preservation

Asteria should optionally retain source data separately.

Example:

``` text
.asset/
├── runtime/
└── source/
```

Runtime builds should include only what is required.

Source preservation allows later reprocessing when import algorithms
improve.

------------------------------------------------------------------------

# 44. Asset versioning

Metadata should include:

``` text
schema_version
asset_version
importer_version
```

This allows migrations when the canonical format evolves.

------------------------------------------------------------------------

# 45. Recommended implementation phases

## Phase 1 --- Canonical Asset Foundation

Implement:

``` text
asset schema
AnimationClip
CharacterAsset
basic metadata loader
validation framework
```

No AI dependency.

------------------------------------------------------------------------

## Phase 2 --- Sprite Importer

Implement:

``` text
PNG import
RGBA handling
grid slicing
direction mapping
preview
pivot
timing
```

------------------------------------------------------------------------

## Phase 3 --- Normalization

Implement:

``` text
crop
padding
nearest-neighbor resize
frame alignment
pivot normalization
```

------------------------------------------------------------------------

## Phase 4 --- Validation + Auto Fix

Implement:

``` text
hard errors
warnings
auto-fix preview
frame-edge checks
empty-frame detection
drift checks
```

------------------------------------------------------------------------

## Phase 5 --- Runtime Integration

Connect canonical assets to existing:

``` text
animation runtime
event dispatch
VFX
audio
camera
battle presentation
```

Do not duplicate existing presentation systems.

------------------------------------------------------------------------

## Phase 6 --- Atlas + Performance

Implement:

``` text
atlas packing
texture caching
batch-friendly metadata
resource lifecycle
```

------------------------------------------------------------------------

## Phase 7 --- Video Import

Implement:

``` text
video decode
frame extraction
frame selection
alpha/background workflow
alignment
conversion to AnimationClip
```

------------------------------------------------------------------------

## Phase 8 --- Character Reference

Implement:

``` text
turnaround references
palette
weapon/outfit reference
generation consistency metadata
```

------------------------------------------------------------------------

## Phase 9 --- Environmental Animation

Implement:

``` text
WindReactive
WaterSurface
FireFlicker
LeafEmitter
LightFlicker
AmbientMotion
```

------------------------------------------------------------------------

## Phase 10 --- AI Provider Layer

Only after the importer is stable:

``` text
AssetGenerationProvider
GPT image provider
other provider adapters
prompt workflow
generation settings
```

Asteria must still work fully without any AI provider.

------------------------------------------------------------------------

# 46. Minimal first milestone

The first useful milestone should be:

**Asteria 2D Asset & Animation Pipeline Phase 1**

Deliver:

``` text
1. Canonical animation asset schema
2. Character asset schema
3. Sprite importer
4. 48×48 and arbitrary frame-size support
5. Grid slicing
6. Direction mapping
7. Pivot editing
8. Animation preview
9. FPS/per-frame timing
10. Animation events
11. Validation
12. Save/load canonical asset
13. Runtime playback integration
```

This already allows real production assets to be imported and used.

AI generation is intentionally not part of the first milestone.

------------------------------------------------------------------------

# 47. What already exists vs. what is new

Existing Asteria architecture should be reused wherever available:

``` text
animation playback concepts
generic presentation channels
VFX integration concepts
camera choreography
audio coordination
hit-stop
battle presentation
runtime asset handling
```

This pipeline adds the missing front half:

``` text
Source
→ Import
→ Normalize
→ Validate
→ Canonical Asset
```

The work should connect into existing systems, not redesign them.

------------------------------------------------------------------------

# 48. Definition of done

An asset pipeline feature is not complete merely because a preview looks
correct.

It is complete only when:

``` text
source can be imported
output follows canonical schema
validation passes
asset saves and reloads
runtime loads it
animation plays correctly
pivot remains stable
events fire correctly
project build can package it
```

------------------------------------------------------------------------

# 49. Final architecture rule

The permanent Asteria rule is:

> **Prompt, image, video, or external asset are only sources.\
> Asteria normalizes them into its own canonical game-asset format
> before runtime use.**

The engine should remain usable even if every AI provider disappears
tomorrow.

------------------------------------------------------------------------

# Part B --- Sprite Production SOP

# ASTERIA_SPRITE_PRODUCTION_SOP.md

**Status:** Phase 1 Baseline **Purpose:** Canonical SOP for converting
generated, artist-made, purchased, legacy, or extracted sprite sources
into production-ready Asteria assets.

## Permanent principle

Asteria separates art creation from runtime-format engineering. Source
tools provide visual quality; Asteria owns extraction, normalization,
correction, packing, metadata, validation, and runtime compatibility. AI
is optional and provider-independent.

## Standard flow

``` text
MASTER REFERENCE
→ SOURCE ART
→ SOURCE ANALYSIS
→ FRAME EXTRACTION
→ BACKGROUND / ALPHA CLEANUP
→ BOUNDING BOX ANALYSIS
→ ALIGNMENT + CROSS-FRAME STABILIZATION
→ SCALE NORMALIZATION
→ CANONICAL FRAME CANVAS
→ HUMAN PREVIEW / MANUAL FIX
→ PACKING
→ VALIDATION
→ IN-ENGINE REVIEW
→ PRODUCTION ASSET
```

## 0 --- Master Reference

Important characters use a locked visual source of truth before
animation production. It defines identity, proportions, front/side/back
appearance, hair/face, outfit/equipment, equipment placement, palette,
materials, and motifs. Reference quality is independent of runtime
resolution.

## 1 --- Source Art

Accepted sources include generated images, artist-authored sheets,
individual frames, existing spritesheets, licensed assets, legacy
assets, and later video/keyframe extraction.

Generated sources should prioritize art quality and preferably use
isolated characters, removable backgrounds, clear pose separation,
predictable ordering, and no UI/labels/logos/fake metadata inside the
extraction area.

## 2 --- Source Analysis

Detect image dimensions, alpha, background, grid candidates, sprite
regions, likely frame count, and ordering. Auto-detection is assistance,
never mandatory.

Manual alternatives must include grid definition, editable extraction
boxes, add/remove regions, and frame reordering.

## 3 --- Frame Extraction

Support exact grid, detected grid, connected-region detection, manual
rectangles, and individual-file import. Retain original source and crop
coordinates; never destructively overwrite source art.

## 4 --- Background / Alpha Cleanup

Support existing alpha, background-key removal, masks, edge/halo
cleanup, and transparent padding. Automatic cleanup must be previewable
and reversible.

## 5 --- Bounding Box Analysis

Calculate occupied bounds, dimensions, bottom contact, candidate
center/feet anchor, and overflow risk. Bounding boxes are analysis data,
not automatically the final pivot.

## 6 --- Alignment

Default character anchor preset is `bottom_center`. Support
bottom-center, center, custom pivot, shared clip pivot, and per-frame
offsets.

### Cross-frame stabilization

Do not independently center every frame by its bounding box. Analyze the
sequence to prevent visible jitter from hair, cloak, weapons, and
asymmetric poses. Stable world anchoring takes priority over
bounding-box symmetry.

## 7 --- Scale Normalization

Canonical frame sizes are arbitrary. Presets may include 32×32, 48×48,
64×64, 96×96, and custom sizes. Current Starter movement-character baseline is 48×48. Larger canvases (for example 64×64 or above) are required when preserving the complete authored motion needs more space; 48×48 is never a hard engine limit.

For pixel art preserve aspect ratio, use nearest-neighbor for pixel
scaling, never silently blur, and warn on destructive downscaling. Do
not hardcode 48 or 64 into the canonical model.

## 8 --- Canonical Frame Canvas

Place normalized art on a transparent RGBA frame. Frame canvas, visible
bounds, collision bounds, and pivot remain separate concepts.

Example:

``` text
frame_size = [64,64]
pivot = [32,61]
visible_bounds = [...]
```

## 9 --- Human Preview / Manual Correction

Before production lock, preview must support play/pause, direction,
timing, nearest-neighbor zoom, overlay/onion comparison, pivot marker,
frame bounds, sprite bounds, and background switching.

Manual fixes include crop, alpha, X/Y offset, scale, pivot, frame order,
direction, exclusion, and replacement. One bad frame must be fixable
without rebuilding the asset.

## 10 --- Packing

Produce individual canonical frames, spritesheet or atlas, and metadata.
Packing is deterministic; runtime layout never depends on decorative
source-sheet layout.

## 11 --- Validation

Technical Gate: image readability, mode/alpha, dimensions, frame count,
bounds, pivot, direction mapping, schema/references, clipping.

Art Gate: identity, silhouette, pixel quality, materials, extraction
artifacts.

Motion Gate: jitter, foot sliding, loop quality, continuity, movement
readability.

Technical PASS alone never makes an official Starter Asset.

## 12 --- In-Engine Review

Test world scale, movement, collision relationship, pivot,
sorting/occlusion, camera scaling, lighting, performance, and scene
cohesion before production lock.

## RPG Maker-style Starter Preset

Phase 1 starts with:

``` text
3 columns × 4 rows
row 0: down
row 1: left
row 2: right
row 3: up
3 movement frames per direction
middle frame may serve as standing frame
```

This is a preset, not an engine limitation.

## Kael Regression Case

Current expected canonical result:

``` text
directions: 4
frames/direction: 3
total frames: 12
frame size: 64×64
sheet: 192×256 RGBA
pivot baseline: bottom-center, currently (32,61)
```

Regression:

``` text
Kael source
→ detect/extract 12 sprites
→ clean alpha
→ normalize
→ stabilize
→ 64×64 frames
→ preview
→ pack 192×256
→ metadata
→ validate
```

## Editor Workflow

Beginner:

``` text
Import Sprite → Auto Detect → Auto Fix → Preview → Import
```

Advanced controls are progressively disclosed for Detection, Extraction,
Alpha, Alignment, Scale, Pivot, Ordering, Timing, Packing, and
Validation.

## Non-destructive Import Session

Retain source reference, detection results, extraction rectangles,
cleanup parameters, normalization settings, manual overrides, output
settings, and validation results. Reimport should preserve compatible
manual corrections when possible.

## Phase 1 Components

``` text
AssetImportSession
SpriteSourceAnalyzer
GridDetector
RegionDetector
FrameExtractor
AlphaCleaner
BoundsAnalyzer
AnchorEstimator
FrameStabilizer
PixelNormalizer
CanonicalFrameBuilder
SpritePacker
SpriteValidator
ImportPreviewModel
ManualOverrideSet
```

## Phase 1 Scope

Implement PNG loading, existing alpha, regular-grid detection,
connected-region extraction, manual rectangle override, background
cleanup, per-frame bounds, bottom-center anchor, cross-frame
stabilization, arbitrary frame sizes, nearest-neighbor pixel scaling,
4×3 preset, preview data model, deterministic packing, JSON metadata,
validator, and Kael regression test.

Defer video extraction, AI-provider integration, advanced segmentation
models, automatic animation synthesis, and complex atlas optimization.

## Definition of Done

A user can provide a sprite source and, without manually cutting files
in an external editor: import it; detect or define 12 movement frames;
clean background; normalize/stabilize; preview/fix individual frames;
produce a canonical 4×3 sheet; save metadata; pass technical validation;
and load it in Asteria.

## Permanent SOP Rule

**Generate or author for visual quality; normalize for engineering
correctness; review both before production lock.**

------------------------------------------------------------------------

# 55. Composable Asset Production and Attachment Pipeline

The production pipeline must distinguish reusable components from combinations that are intentionally baked for artistic reasons.

Recommended decision flow:

``` text
source art
→ identify reusable visual components
→ preserve intentionally baked components
→ normalize each independent component
→ define pivots / sockets / per-frame attachment transforms
→ preview composition
→ validate transform stability and layer ordering
→ package stable asset references
→ runtime presentation composition
```

The importer must not automatically split art merely because composition is supported. Decomposition is an authoring choice and must preserve visual fidelity.

## 55.1 Socket stabilization

For frame animation, socket transforms must be evaluated across the complete clip. Hand/weapon/effect anchors must not jitter because frames were independently bbox-centered. Socket validation should detect discontinuities, missing frame transforms, implausible jumps, and clipping risks while allowing intentional fast motion.

## 55.2 Attachment preview and correction

The Editor pipeline should allow an author to overlay an attached asset on the parent animation, scrub all frames, edit socket/key transforms, change z-order, and preview flip/direction variants. Manual correction is first-class and saved as canonical metadata.

## 55.3 Skill/VFX production

Reusable skill presentation should normally separate components such as cast cue, projectile/travel loop, trail/light, impact, lingering effect, audio, and camera choreography when those components are independently reusable. A single baked effect remains valid when separation would harm the intended art.

## 55.4 Animated text production

Runtime text does not require pre-rendering every numeric/string combination. The pipeline instead validates referenced font/material/icon/VFX resources and the animated-text preset. Bitmap-number sheets remain an optional project-defined technique.


# 13 --- Formal Asset Production Contract (2026-09-25)

For formal Asteria asset production, source generation is an internal production step, not a deliverable. For animation, the user requests and receives one complete animation unit. Internal production may proceed one frame at a time, like an animator, to preserve identity and motion continuity.

Before canonicalization, every source frame must pass a **Source Integrity Gate**: the complete authored subject must exist with safe margin, including head/hair, arms/hands, legs/feet, clothing/cape, and authored attachments where applicable. Source-level clipping is a hard failure and cannot be repaired by a later canonical bounding-box check. Failed frames are reworked or regenerated internally.

Canonicalization preserves the complete authored subject and aspect ratio. Never crop content merely to force a 48×48 preset; scale proportionally or select a larger canonical canvas.

Formal animation acceptance order is: Source Integrity → Technical → Cross-animation → Visual Continuity → Motion Readability → Character Identity → Assistant Art/Motion Review. Any failed gate returns to the smallest affected production unit and reruns downstream gates. Technical PASS alone is never final.

A completed animation package contains canonical frames, canonical spritesheet/atlas, timing/anchor metadata, and validation evidence. Intermediate failed frames and raw generator sheets are not user deliverables.

------------------------------------------------------------------------

# 37. Deterministic animation production control

Prompt generation is a source adapter, not the authority for animation semantics. Formal production animation must be driven by an explicit production plan before pixels are generated.

``` text
Master Reference
      +
AnimationProductionPlan
      ↓
Frame Specification 0 → source render → Source Integrity → accept/rework
Frame Specification 1 → source render → Source Integrity → accept/rework
...
      ↓
accepted source sequence
      ↓
canonicalization + stabilization
      ↓
Technical Gate
      ↓
Cross-animation Gate
      ↓
Visual Continuity Gate
      ↓
Motion Readability Gate
      ↓
Character Identity Gate
      ↓
Art/Motion Review
      ↓
canonical packaged animation
```

`AnimationProductionPlan` owns directions, frame count, timing, pose progression, motion phases, contact states, root/foot targets, loop seam, sockets/grips, expected silhouette envelope, identity invariants, and canvas policy. A generation provider must not silently invent or replace these semantics.

Formal animation production should use the Master Reference plus the current frame specification and adjacent accepted frames. Source Integrity runs **before** destructive cleanup, cropping, scaling, or canonicalization. A failed frame is regenerated/reworked at the smallest affected unit; accepted frames need not be discarded.

Cross-frame stabilization may remove import/generation jitter but must not conceal wrong anatomy, costume drift, identity drift, or an incorrect pose. Such defects return to source production.

The delivery unit remains the complete useful animation. Frame-by-frame work is an internal production strategy, not a user delivery strategy.

------------------------------------------------------------------------

# 38. Production validation evidence

Technical and visual evidence are separate. Objective validation records dimensions, alpha, clipping/edge contact, anchors, frame/direction counts and metadata. Visual validation records identity, continuity, motion readability and art quality. Formal PASS requires both applicable classes.

Animation review must inspect canonical individual frames **and temporal playback/sequence**. A plausible static spritesheet is insufficient evidence of motion correctness.

Generated labels, checkerboards, frame borders, or text such as `PASS` are never validation evidence and must not enter canonical runtime assets.
