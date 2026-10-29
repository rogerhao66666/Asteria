# ASTERIA_ASSET_SPEC.md

**Status:** Canonical consolidation draft\
**Canonical role:** Complete asset taxonomy + canonical usable-asset
contracts\
**Merged sources:** `ASTERIA_ASSET_CATALOG_SPEC.md` +
`Asteria_USABLE_ASSET_GENERATION_SPEC.md`

Defaults/presets are not engine hard limits unless explicitly declared
as such.

------------------------------------------------------------------------

# Part A --- Asset Catalog

# ASTERIA_ASSET_CATALOG_SPEC.md

**Status:** Draft baseline\
**Purpose:** Define the complete first-class asset taxonomy for Asteria
so generation, import, validation, editor UX, packaging, and runtime all
use the same vocabulary.

------------------------------------------------------------------------

# 1. Core rule

Every Asteria asset belongs to a known **asset type** with:

-   canonical file format
-   default dimensions or sizing rules
-   metadata schema
-   importer behavior
-   validation rules
-   editor representation
-   runtime responsibility

Asteria must distinguish between:

``` text
SOURCE ASSET
    ↓
CANONICAL ASSET
    ↓
RUNTIME ASSET
```

Source material may come from AI, video, artist-created files, existing
asset packs, or legacy projects.

Runtime never depends on the source format.

------------------------------------------------------------------------

# 2. Top-level asset taxonomy

``` text
Assets/
├── Characters/
├── NPCs/
├── Monsters/
├── Tilesets/
├── Terrain/
├── Props/
├── Buildings/
├── Environment/
├── Portraits/
├── Icons/
├── UI/
├── VFX/
├── Particles/
├── Projectiles/
├── Skills/
├── Items/
├── Equipment/
├── Audio/
├── Music/
├── Fonts/
├── Shaders/
├── Materials/
├── Backgrounds/
├── Parallax/
├── Cutscenes/
├── Dialogue/
├── Animations/
├── Prefabs/
└── Scenes/
```

Not every category needs a dedicated file format in Phase 1, but every
category is defined now so later expansion does not require
architectural renaming.

------------------------------------------------------------------------

# 3. Character assets

Use for player-controlled actors.

Example:

``` text
Characters/Hero_Swordsman/
├── idle.png
├── walk.png
├── run.png
├── attack_01.png
├── hurt.png
├── death.png
├── portrait_neutral.png
└── Hero_Swordsman.asset.json
```

Recommended defaults:

``` text
movement frame: 48×48
attack frame: 64×64 or larger
directions: 4 by default
```

Supported animation IDs are project-defined.

Common conventions:

``` text
idle
walk
run
attack_01
attack_02
cast
guard
hurt
death
interact
jump
dash
```

These are conventions, not hardcoded engine limits.

------------------------------------------------------------------------

# 4. NPC assets

NPCs use the same core representation as Character assets.

Minimum useful set:

``` text
idle
walk
portrait
```

Optional:

``` text
work
sit
sleep
talk
gesture
emote
combat
```

NPC-specific metadata may include:

``` text
interaction_anchor
dialogue_id
schedule_id
default_facing
```

------------------------------------------------------------------------

# 5. Monster assets

Monster sizes are flexible.

Recommended classes:

``` text
small   48×48
medium  64×64
large   96×96
boss    128×128+
```

Common animations:

``` text
idle
move
attack
cast
hurt
death
special
```

Monsters may use:

``` text
1 direction
2 directions
4 directions
8 directions
```

Direction count belongs to the asset.

------------------------------------------------------------------------

# 6. Tilesets

Default tile size:

``` text
32×32 px
```

Canonical format:

``` text
RGBA PNG
strict grid
no baked labels
no margins unless declared
```

Example:

``` text
Tilesets/Forest_Village/
├── forest_village.png
└── forest_village.tileset.json
```

Metadata may define:

``` text
tile_size
columns
rows
collision
terrain_type
navigation_cost
autotile_group
animation
footstep_surface
tags
```

------------------------------------------------------------------------

# 7. Terrain definitions

Terrain is semantic data layered over tiles.

Examples:

``` text
grass
mud
sand
stone
snow
water
lava
ice
bridge
cliff
```

Terrain can affect:

``` text
movement
footstep audio
VFX
navigation
encounter rules
vehicle behavior
```

Tileset graphics and terrain semantics must remain separable.

------------------------------------------------------------------------

# 8. Props

Props are scene objects such as:

``` text
tree
crate
barrel
chest
lamp
bench
sign
fountain
market stall
statue
door
```

Preferred image dimensions are multiples of tile size.

Examples:

``` text
32×32
32×64
64×64
96×64
```

Metadata can define:

``` text
pivot
collision footprint
interaction anchor
occlusion behavior
animation
shadow behavior
```

------------------------------------------------------------------------

# 9. Buildings

Buildings are larger structured environment assets.

Examples:

``` text
house
inn
shop
castle
tower
gate
temple
```

A building may contain:

``` text
sprite
collision
doors
interaction anchors
roof layer
foreground layer
interior scene link
lighting anchors
```

Buildings should usually be represented as prefabs rather than only PNG
files.

------------------------------------------------------------------------

# 10. Environment assets

Environment systems include:

``` text
water
fire
smoke
fog
wind
rain
snow
leaves
dust
clouds
light shafts
```

These may be implemented using:

``` text
animated sprite
particles
shader
lighting
composite prefab
```

Environmental animation should not require every effect to be baked into
the map image.

------------------------------------------------------------------------

# 11. Portraits

Default:

``` text
128×128 RGBA PNG
```

Common expression files:

``` text
neutral
happy
sad
angry
surprised
hurt
confused
```

Portraits contain only the portrait image.

Do not bake dialogue windows or text into portrait assets.

------------------------------------------------------------------------

# 12. Icons

Default:

``` text
32×32 RGBA PNG
```

Categories:

``` text
items
equipment
skills
status effects
currency
quest markers
map markers
UI actions
```

Icons may be stored individually during authoring and packed into
runtime atlases.

------------------------------------------------------------------------

# 13. UI assets

UI assets include:

``` text
window frames
panels
buttons
tabs
cursor
selection frame
HP/MP bars
dialogue box
tooltip frame
inventory slots
minimap frame
battle HUD
```

Preferred architecture:

``` text
UI theme
    ↓
9-slice / scalable components
```

Avoid requiring full UI screenshots as runtime assets.

------------------------------------------------------------------------

# 14. VFX

VFX types:

``` text
slash
impact
explosion
fire
ice
lightning
heal
poison
buff
debuff
magic circle
teleport
smoke
spark
```

Typical frame sizes:

``` text
64×64
96×96
128×128
256×256
```

Metadata should support:

``` text
frame_size
frame_count
fps
loop
pivot
blend_mode
lifetime
```

------------------------------------------------------------------------

# 15. Particle assets

Particle assets consist of:

``` text
texture
emitter settings
lifetime
velocity
gravity
spread
scale curve
alpha curve
rotation
spawn rate
```

Typical texture sizes:

``` text
16×16
32×32
64×64
```

Examples:

``` text
spark
leaf
ash
snowflake
dust
ember
rain_drop
```

------------------------------------------------------------------------

# 16. Projectile assets

Projectiles are visual + motion presentation assets.

Examples:

``` text
arrow
fireball
ice shard
magic missile
bullet
throwing knife
```

Projectile metadata may include:

``` text
sprite/VFX
pivot
trail
rotation mode
impact VFX
audio event
```

Gameplay trajectory and damage remain gameplay-system responsibilities.

------------------------------------------------------------------------

# 17. Skills

A Skill is not merely an image.

Example:

``` text
Skills/Fireball/
└── Fireball.skill.json
```

A skill may reference:

``` text
caster animation
cast VFX
projectile asset
impact VFX
audio events
camera events
animation events
gameplay action ID
```

Example flow:

``` text
cast
↓
spawn projectile
↓
travel
↓
impact
↓
gameplay effect
```

Visual presentation and gameplay logic must remain separable.

------------------------------------------------------------------------

# 18. Items

Item definitions are data assets.

Examples:

``` text
potion
ether
key item
material
quest item
food
```

Metadata may include:

``` text
id
display_name
icon
description
category
stack_limit
use_action
tags
```

------------------------------------------------------------------------

# 19. Equipment

Equipment definitions include:

``` text
weapon
armor
accessory
shield
helmet
boots
```

Metadata may reference:

``` text
icon
world sprite
character attachment
attack animation
VFX
audio
stats
tags
```

------------------------------------------------------------------------

# 20. Audio

Supported categories:

``` text
SFX
UI sound
ambient sound
voice
battle sound
environment sound
```

Preferred canonical formats can be selected by build target.

Authoring metadata should support:

``` text
volume
loop
priority
spatial mode
category
random variants
pitch variance
```

------------------------------------------------------------------------

# 21. Music

Music assets may include:

``` text
field theme
town theme
battle theme
boss theme
cutscene theme
ambient music
```

Metadata may define:

``` text
loop points
intro segment
loop segment
crossfade
music state
```

------------------------------------------------------------------------

# 22. Fonts

Font assets support:

``` text
UI text
dialogue
damage numbers
titles
debug/editor
```

Projects should support font fallback.

Localization must not assume one font covers all languages.

------------------------------------------------------------------------

# 23. Shaders

Shader assets support:

``` text
sprite tint
outline
dissolve
water
heat distortion
damage flash
bloom mask
lighting
fog
screen transition
```

Shaders must be treated as reusable presentation assets.

------------------------------------------------------------------------

# 24. Materials

A material binds:

``` text
shader
textures
parameters
blend mode
render properties
```

Examples:

``` text
water material
glowing magic material
ghost material
wet stone material
```

------------------------------------------------------------------------

# 25. Backgrounds

Backgrounds are static or animated visual layers.

Examples:

``` text
battle background
sky
interior backdrop
menu background
cutscene backdrop
```

Do not use a background image to replace structured gameplay map data
unless intentionally designed that way.

------------------------------------------------------------------------

# 26. Parallax layers

Parallax assets support:

``` text
foreground layer
midground layer
background layer
scroll factor
looping
depth
```

Useful for:

``` text
HD-2D scenes
mountains
clouds
city skyline
forest depth
```

------------------------------------------------------------------------

# 27. Cutscene assets

Cutscene assets coordinate:

``` text
camera
character animation
dialogue
audio
VFX
timing
scene transitions
```

A cutscene is a timeline/orchestration asset, not a single video by
default.

Pre-rendered video may still be supported separately.

------------------------------------------------------------------------

# 28. Dialogue assets

Dialogue data may include:

``` text
speaker
portrait
expression
text
choices
events
voice
conditions
localization key
```

Dialogue content should not be embedded into image files.

------------------------------------------------------------------------

# 29. Animation assets

AnimationClip is a reusable first-class asset.

It should support:

``` text
frames
timing
loop
pivot
direction
events
tags
```

Animation clips may be referenced by:

``` text
characters
NPCs
monsters
props
VFX
UI
environment
```

------------------------------------------------------------------------

# 30. Prefabs

Prefabs package reusable scene configurations.

Examples:

``` text
TreasureChest.prefab
Torch.prefab
VillageHouse.prefab
EnemyGoblin.prefab
SavePoint.prefab
```

A prefab may contain:

``` text
render assets
collision
scripts
interaction
audio
particles
lights
child objects
```

------------------------------------------------------------------------

# 31. Scenes

Scenes are structured world/level assets.

A scene may reference:

``` text
tilesets
terrain
props
buildings
NPCs
monsters
lights
audio
VFX
prefabs
navigation
scripts
camera settings
```

Scene files must reference assets by stable IDs rather than duplicate
asset contents.

------------------------------------------------------------------------

# 32. Canonical source-to-runtime flow

All supported asset categories follow:

``` text
Prompt
Image
Video
Existing Asset
Artist Source
       ↓
Source Adapter
       ↓
Import
       ↓
Normalize
       ↓
Validate
       ↓
Canonical Asset
       ↓
Optional Atlas / Build Processing
       ↓
Runtime
```

------------------------------------------------------------------------

# 33. Starter Pack scope

The first official Asteria Starter Pack should contain enough material
to build a small playable RPG slice.

``` text
Asteria_Starter_Assets/
├── Characters/
│   └── Default_Hero/
├── NPCs/
│   ├── Villager_Male/
│   └── Villager_Female/
├── Monsters/
│   ├── Slime/
│   └── Goblin/
├── Tilesets/
│   └── Forest_Village/
├── Props/
│   ├── Tree/
│   ├── Chest/
│   ├── Lamp/
│   └── Market_Stall/
├── Buildings/
│   ├── House/
│   └── Inn/
├── Portraits/
│   └── Default_Hero/
├── Icons/
│   ├── Items/
│   ├── Equipment/
│   └── Skills/
├── VFX/
│   ├── Slash_Blue/
│   ├── Fireball/
│   ├── Impact/
│   └── Heal/
├── Particles/
│   ├── Leaves/
│   └── Embers/
├── Projectiles/
│   └── Fireball/
├── Skills/
│   ├── Slash/
│   └── Fireball/
├── Items/
│   ├── Potion/
│   └── Ether/
├── Equipment/
│   ├── Iron_Sword/
│   └── Wooden_Shield/
├── UI/
│   └── Default_Theme/
├── Audio/
│   ├── SFX/
│   └── Ambient/
└── Scenes/
    └── Starter_Village/
```

------------------------------------------------------------------------

# 34. Golden test coverage

Golden assets should not exist only for visual demonstration.

They must be used by automated tests.

Minimum golden test suite:

``` text
golden_character
golden_npc
golden_monster
golden_tileset
golden_prop
golden_icon
golden_vfx
golden_projectile
golden_skill
golden_ui
golden_scene
```

Validation must confirm:

``` text
import succeeds
metadata parses
dimensions match
assets reload
runtime resolves references
animations play
events fire
scene packages correctly
```

------------------------------------------------------------------------

# 35. Phase priority

## Phase A --- Required for first playable RPG

``` text
Character
NPC
Monster
Tileset
Prop
Portrait
Icon
VFX
Projectile
Skill
Item
Equipment
UI
Animation
Prefab
Scene
Audio
```

## Phase B --- Visual polish

``` text
Particles
Environment
Buildings
Backgrounds
Parallax
Shaders
Materials
Music
```

## Phase C --- Advanced authoring

``` text
Cutscenes
Dialogue tooling
AI generation providers
video-to-animation
advanced environment animation
asset retargeting
style consistency tools
```

------------------------------------------------------------------------

# 36. Generation policy

When the user asks for a **usable asset**, generation must target one of
these canonical types.

Examples:

``` text
"Generate a usable RPG hero"
→ CharacterAsset

"Generate a forest tileset"
→ TilesetAsset

"Generate a fireball skill"
→ SkillAsset + ProjectileAsset + VFX assets + icon

"Generate a treasure chest"
→ Prop/Prefab

"Generate a battle UI"
→ UI Theme assets

"Generate a village"
→ Tileset + Props + Buildings + Scene
```

Do not replace a requested usable asset with a showcase image.

------------------------------------------------------------------------

# 37. Final rule

Asteria should be able to answer this question for every file in a
project:

> What asset type is this, what contract does it obey, how is it
> imported, how is it validated, and which runtime system consumes it?

If the answer is unclear, the asset type is not sufficiently defined.

------------------------------------------------------------------------

# Part B --- Usable Asset Generation / Canonical Physical Contract

# Asteria Usable Asset Generation Spec

**Status:** Draft baseline\
**Goal:** Every generated asset must be directly importable into
Asteria.\
**Non-goal:** Do not output showcase sheets, posters, labels, decorative
borders, or "looks-like-a-spritesheet" concept images as runtime assets.

------------------------------------------------------------------------

## 1. Core rule

Asteria asset generation uses a **two-stage pipeline**:

``` text
Image generation
    ↓
Deterministic post-processing
    ↓
Exact PNG + metadata
    ↓
Asteria import
```

The image generator is only responsible for visual content.

The post-processor is responsible for all hard technical guarantees:

-   exact canvas dimensions
-   exact frame dimensions
-   exact grid layout
-   transparent RGBA background
-   frame cropping
-   pivot alignment
-   padding
-   nearest-neighbor resampling
-   atlas packing
-   metadata generation
-   validation

**Asteria must never trust an AI-generated image to already be
frame-perfect.**

------------------------------------------------------------------------

# 2. Deliverable format

Every usable generated asset is delivered as a folder.

Example:

``` text
Hero_Swordsman/
├── idle.png
├── walk.png
├── run.png
├── attack_01.png
├── hurt.png
├── death.png
└── Hero_Swordsman.asset.json
```

Optional development/reference files:

``` text
Hero_Swordsman/
└── source/
    ├── character_reference.png
    └── generated_source.png
```

Only the canonical PNG files and `.asset.json` are consumed by runtime.

------------------------------------------------------------------------

# 3. Default character standard

Default movement-frame size:

``` text
48 × 48 px
```

Default direction order:

``` text
row 0 = down
row 1 = left
row 2 = right
row 3 = up
```

Default pivot for 48×48:

``` text
x = 24
y = 44
```

Coordinates are measured from the top-left of the frame.

The visible feet should land close to the pivot baseline.

------------------------------------------------------------------------

# 4. Walk sprite

Canonical walk sheet:

``` text
4 directions
4 frames per direction
48 × 48 px per frame
```

Final image:

``` text
192 × 192 px
RGBA PNG
```

Layout:

``` text
          frame0  frame1  frame2  frame3

down       [ ]     [ ]     [ ]     [ ]
left       [ ]     [ ]     [ ]     [ ]
right      [ ]     [ ]     [ ]     [ ]
up         [ ]     [ ]     [ ]     [ ]
```

Requirements:

-   no margin
-   no spacing
-   no text
-   no labels
-   no borders
-   no baked checkerboard
-   transparent background
-   every cell is exactly 48×48
-   body scale remains consistent
-   pivot remains consistent
-   animation loops cleanly

Default playback:

``` text
fps = 8
loop = true
```

------------------------------------------------------------------------

# 5. Idle sprite

Canonical idle sheet:

``` text
4 directions
4 frames per direction
48 × 48 px
```

Final image:

``` text
192 × 192 px
```

Default:

``` text
fps = 6
loop = true
```

Idle movement should be subtle:

-   breathing
-   hair motion
-   cloth motion
-   tiny stance changes

The character must not drift around the frame.

------------------------------------------------------------------------

# 6. Run sprite

Recommended:

``` text
4 directions
6 frames per direction
48 × 48 px
```

Final image:

``` text
288 × 192 px
```

Default:

``` text
fps = 12
loop = true
```

------------------------------------------------------------------------

# 7. Attack sprite

Attack may require larger frames so the weapon/VFX does not get clipped.

Recommended baseline:

``` text
4 directions
6 frames per direction
64 × 64 px
```

Final image:

``` text
384 × 256 px
```

Default pivot:

``` text
x = 32
y = 60
```

The character's world-space feet position must still correspond to the
same logical pivot used by the movement animations.

Default:

``` text
fps = 12
loop = false
```

VFX should preferably be a separate asset unless it is intentionally
part of the animation.

------------------------------------------------------------------------

# 8. Hurt sprite

Recommended:

``` text
4 directions
3 frames per direction
48 × 48 px
```

Final image:

``` text
144 × 192 px
```

Default:

``` text
fps = 10
loop = false
```

------------------------------------------------------------------------

# 9. Death sprite

Recommended:

``` text
4 directions
6 frames per direction
64 × 64 px
```

Final image:

``` text
384 × 256 px
```

Default:

``` text
fps = 8
loop = false
hold_last_frame = true
```

------------------------------------------------------------------------

# 10. Pixel-art image requirements

Canonical generated pixel-art assets must satisfy:

-   PNG
-   RGBA
-   transparent background
-   nearest-neighbor resizing only
-   no blur
-   no photographic texture
-   no antialiased halo around transparent edges
-   consistent pixel density
-   consistent palette
-   consistent outline style
-   no text or UI chrome inside runtime assets

------------------------------------------------------------------------

# 11. Character consistency

All files belonging to one character must preserve:

-   hairstyle
-   hair color
-   eye color
-   face structure
-   body proportions
-   armor/clothing design
-   cape design
-   weapon identity
-   palette
-   outline style
-   pixel density

A generation pipeline should use the same character reference for every
animation.

Recommended reference set:

``` text
reference_front.png
reference_left.png
reference_right.png
reference_back.png
palette.png
weapon_reference.png
```

These are generation references, not runtime animation files.

------------------------------------------------------------------------

# 12. Metadata

Example:

``` json
{
  "asset_type": "character",
  "id": "hero_swordsman",
  "version": 1,
  "directions": ["down", "left", "right", "up"],

  "animations": {
    "idle": {
      "file": "idle.png",
      "frame_size": [48, 48],
      "frames_per_direction": 4,
      "pivot": [24, 44],
      "fps": 6,
      "loop": true
    },

    "walk": {
      "file": "walk.png",
      "frame_size": [48, 48],
      "frames_per_direction": 4,
      "pivot": [24, 44],
      "fps": 8,
      "loop": true
    },

    "run": {
      "file": "run.png",
      "frame_size": [48, 48],
      "frames_per_direction": 6,
      "pivot": [24, 44],
      "fps": 12,
      "loop": true
    },

    "attack_01": {
      "file": "attack_01.png",
      "frame_size": [64, 64],
      "frames_per_direction": 6,
      "pivot": [32, 60],
      "fps": 12,
      "loop": false
    },

    "hurt": {
      "file": "hurt.png",
      "frame_size": [48, 48],
      "frames_per_direction": 3,
      "pivot": [24, 44],
      "fps": 10,
      "loop": false
    },

    "death": {
      "file": "death.png",
      "frame_size": [64, 64],
      "frames_per_direction": 6,
      "pivot": [32, 60],
      "fps": 8,
      "loop": false,
      "hold_last_frame": true
    }
  }
}
```

------------------------------------------------------------------------

# 13. Animation events

Animation metadata may contain events.

Example:

``` json
{
  "events": [
    {
      "frame": 2,
      "event": "weapon_swing"
    },
    {
      "frame": 3,
      "event": "damage_window"
    },
    {
      "frame": 3,
      "event": "spawn_slash_vfx"
    }
  ]
}
```

Asteria can use these events to synchronize:

-   combat
-   sound
-   VFX
-   camera shake
-   hit-stop
-   projectile spawning

------------------------------------------------------------------------

# 14. NPC format

NPCs use the same character format.

Minimum package:

``` text
NPC_Villager_01/
├── idle.png
├── walk.png
└── NPC_Villager_01.asset.json
```

Combat animations are optional.

------------------------------------------------------------------------

# 15. Monster format

Monsters are not forced into 48×48.

Recommended size classes:

``` text
small   = 48 × 48
medium  = 64 × 64
large   = 96 × 96
boss    = 128 × 128 or custom
```

Every monster asset explicitly declares:

``` text
frame size
pivot
animation frame count
direction count
```

------------------------------------------------------------------------

# 16. Tile format

Default Asteria tile size:

``` text
32 × 32 px
```

Canonical tileset:

``` text
PNG RGBA
exact grid
no spacing
no margin
no labels
```

Example:

``` text
8 columns × 8 rows
32 × 32 per tile
```

Final image:

``` text
256 × 256 px
```

A pretty town screenshot is **not** a tileset.

A tileset must be a deterministic grid that the engine can index.

------------------------------------------------------------------------

# 17. Tile metadata

Example:

``` json
{
  "asset_type": "tileset",
  "id": "forest_village",
  "file": "forest_village.png",
  "tile_size": [32, 32],
  "columns": 8,
  "rows": 8
}
```

Future fields may include:

-   collision
-   terrain type
-   navigation cost
-   autotile rules
-   animation
-   footstep sound
-   tags

------------------------------------------------------------------------

# 18. Props

Props should usually be individual transparent PNG files.

Examples:

``` text
wooden_chest.png
lamp_post.png
market_stall.png
fountain.png
tree_large.png
```

Recommended dimensions should usually be multiples of the tile size:

``` text
32 × 32
32 × 64
64 × 64
96 × 64
```

Metadata may define:

-   pivot
-   collision footprint
-   interaction point
-   animation

------------------------------------------------------------------------

# 19. Item icons

Default:

``` text
32 × 32 px
PNG RGBA
transparent background
```

Example:

``` text
potion_red.png
iron_sword.png
wooden_shield.png
gold_coin.png
```

Icons may later be packed into an atlas.

------------------------------------------------------------------------

# 20. Portraits

Default dialogue portrait:

``` text
128 × 128 px
PNG RGBA
```

Expressions should be separate files:

``` text
portrait_neutral.png
portrait_happy.png
portrait_angry.png
portrait_sad.png
portrait_surprised.png
```

Dialogue-window graphics must not be baked into portraits.

------------------------------------------------------------------------

# 21. VFX

Recommended VFX frame sizes:

``` text
64 × 64
96 × 96
128 × 128
```

Examples:

``` text
slash_blue
fireball
impact
heal_ring
magic_circle
smoke
spark
```

VFX metadata should define:

-   frame size
-   frame count
-   fps
-   loop
-   blend mode
-   pivot

------------------------------------------------------------------------

# 22. Generated screenshots are reference images only

These are **not runtime assets**:

-   town showcase screenshot
-   battle screenshot
-   field screenshot
-   promotional sheet
-   HD-2D concept image
-   labeled spritesheet mockup

They may be used for art direction, but must never be passed off as
directly importable Asteria assets.

------------------------------------------------------------------------

# 23. Project folder convention

Recommended:

``` text
Assets/
├── Characters/
├── Monsters/
├── Tilesets/
├── Props/
├── Icons/
├── Portraits/
└── VFX/
```

Example:

``` text
Assets/
└── Characters/
    └── Hero_Swordsman/
        ├── idle.png
        ├── walk.png
        ├── run.png
        ├── attack_01.png
        ├── hurt.png
        ├── death.png
        └── Hero_Swordsman.asset.json
```

------------------------------------------------------------------------

# 24. Drop-in workflow

Target user experience:

``` text
1. Generate/download an Asteria asset package.
2. Copy the package into Assets/.
3. Asteria detects the .asset.json.
4. Asteria validates dimensions and metadata.
5. The animation preview becomes available.
6. The asset appears in Asset Browser.
7. Drag the character/prop/tile into the scene.
```

If the package already conforms to this specification, the user should
**not need to manually slice the image**.

------------------------------------------------------------------------

# 25. Validation

For every import:

``` text
✓ PNG exists
✓ PNG dimensions match metadata
✓ image dimensions divide into the declared grid
✓ expected frame count exists
✓ frame size is exact
✓ pivot is valid
✓ required directions exist
✓ alpha channel is valid
```

Warnings:

``` text
⚠ visible pixels touch the frame edge
⚠ character scale varies too much
⚠ probable pivot drift
⚠ empty frame detected
⚠ palette/style inconsistency detected
```

Only errors that make the asset unsafe or impossible to interpret should
block import.

------------------------------------------------------------------------

# 26. Generation contract

When generating a **usable Asteria asset**, the request must specify
technical output instead of presentation styling.

Example:

``` text
Asset:
4-direction RPG walking character

Canonical output:
walk.png

Pixel format:
RGBA PNG

Frame:
48 × 48 px

Grid:
4 columns × 4 rows

Canvas:
192 × 192 px

Rows:
0 = down
1 = left
2 = right
3 = up

Columns:
4 sequential walk frames

Pivot:
24, 44

Background:
fully transparent

Forbidden:
text
labels
frame borders
grid lines
decorative background
checkerboard background
UI
poster layout
```

**Important:** Image generation alone is not accepted as proof that this
contract is satisfied.

The final output must be programmatically post-processed and validated
before it is delivered as a usable asset.

------------------------------------------------------------------------

# 27. Asteria generation policy

From this specification onward, there are two distinct output modes:

## Reference / concept mode

Used when the user asks:

-   show me a style
-   give me visual ideas
-   make a mockup
-   show several possible assets
-   design an HD-2D scene

Output may be a normal generated image.

## Usable asset mode

Used when the user asks:

-   give me something I can put into the engine
-   generate a sprite
-   generate a spritesheet
-   make a tile
-   make an icon
-   make an animation asset
-   give me production material

Output must follow the canonical asset contract and include
deterministic post-processing/validation.

Asteria should never silently substitute reference mode for usable asset
mode.

------------------------------------------------------------------------

# 28. Initial recommended baseline

For the first implementation phase, support these production-ready types
first:

``` text
Character Walk
Character Idle
Character Run
Character Attack
Character Hurt
Character Death

NPC Walk / Idle

32×32 Tileset

Transparent Props

32×32 Item Icons

128×128 Portraits

64/96/128 VFX
```

This is sufficient to build a complete small RPG while keeping the first
version manageable.

------------------------------------------------------------------------

# 29. Implementation principle

The long-term pipeline should be provider-independent.

``` text
GPT Image
Gemini
local model
artist-made source
existing spritesheet
video source
        ↓
Asteria Asset Processor
        ↓
canonical PNG + metadata
        ↓
Asteria Runtime
```

Asteria owns the **asset contract**.

The image generator does not.

------------------------------------------------------------------------

# 52. Composable Visual Assets, Sockets, and Attachments

Canonical assets must be able to participate in Baked, Layered, Attached, Procedural, and Hybrid presentation without requiring duplicated variants for every combination.

## 52.1 Socket / anchor metadata

Sprite and animation assets may declare named sockets/anchors. A socket may provide a default transform and optional per-frame/keyed transforms:

``` text
socket_id
position
rotation
scale
flip
visibility
z_offset
inherit_transform
```

Examples such as `hand_r`, `hand_l`, `head`, `back`, `effect_anchor`, and `projectile_origin` are presets/examples only. Projects may define arbitrary names.

Socket metadata must preserve fractional coordinates and must not assume a fixed frame size, direction count, or skeletal representation.

## 52.2 Attachment definitions

An attachment definition references stable asset IDs and a socket/anchor rather than embedding fragile source paths. Metadata may include local transform, render ordering, material override, visibility rules, animation binding, and lifecycle policy.

Attachment is generic: equipment, cosmetics, props, VFX, lights, project-defined visual resources, and other compatible assets use the same contract.

## 52.3 Reuse instead of variant explosion

Canonical asset design should avoid requiring:

``` text
actor × weapon × skill × element × status × direction
```

as separately authored full sprite sheets. Independent reusable components are preferred when artistic fidelity permits. Fully baked variants remain valid and first-class.

## 52.4 Animated text assets/presets

Fonts, materials, icons, VFX, and animation curves may be referenced by reusable animated-text/popup presets. Damage-number styling is one preset family, not a unique asset type required by Engine Core.

## 52.5 Quality and fidelity

Composition must not reduce source fidelity. Independent layers must preserve native resolution, alpha, timing, pivot/socket precision, blend/material behavior, and ordering. If decomposition would visibly reduce quality, projects may use baked or hybrid presentation instead.

------------------------------------------------------------------------

# Production-controlled animation source contract

For formal generated Starter assets, animation structure is canonical input rather than generator output. An animation production definition must specify required directions, frame count, per-frame timing, pose/motion phase, contact state where relevant, anchor/root targets, loop requirements, sockets/grips where relevant, Master Reference identity, and canvas policy before final source-frame generation.

Generation may proceed frame-by-frame internally. Each frame remains subordinate to the same Master Reference and animation definition. The user-facing asset remains one complete animation package.

Preset frame dimensions and example frame counts in this specification are **starter defaults/examples**, not Engine Core limits and not permission to crop authored content. Canonical canvas size may grow to preserve complete art and motion. Runtime and serialization must continue to support arbitrary valid frame dimensions, variable frame counts, and per-frame timing.

A formal animation cannot reach production status from technical validation alone. Source Integrity, cross-animation compatibility, visual continuity, motion readability, character identity, and final art/motion review are required when applicable.

## Generated Character Assets
Character-generator parts are layered authoring sources sharing a frame topology, direction set, frame size, and anchor convention. Categories are extensible authoring data; the starter catalog includes body, eyes, rear/front hair, outfit, armor, and accessory layers. Generation emits ordinary RGBA sprite assets plus recipe metadata; runtime must not require a special generated-character type.

## Character Generator modular-part contract (Phase 3)
Built-in generated characters and custom-authored characters remain equal inputs to the canonical asset system. Starter generator parts are authored against an explicit `CharacterAnimationTopology`; every interchangeable part shares canvas size, direction/frame topology, foot anchor, and frame indexing. Parts are independent transparent RGBA layers in canonical layer order. Palette variation is represented by optional masks/metadata rather than duplicated runtime character types. `rpg_like_48_walk_v1` is a Starter preset only, never an engine resolution or animation limit.
