# MV-Backed Character Creator Design

Date: 2026-09-26

## Goal

Replace Asteria's visually weak character generator preview with an RPG
Maker-style creator backed by the local, Git-ignored MV generator parts. A
created character must include walking, face, and side-view visuals and must
stand naturally in a 48×48 map cell using one consistent feet anchor in the
Editor and runtime.

## Scope and licensing boundary

The creator reads licensed source material only from
`local_reference/rpg_maker_mv`, which remains ignored by Git. Generated output
that contains MV-derived pixels defaults to a local ignored output directory
and is never committed, packaged, or redistributed by Asteria tooling.

The MV adapter may reproduce source topology, layer ordering, dimensions, and
filename relationships. A future distributable Asteria starter library must
use independently created parts, names, images, portraits, battlers, and text.

## Coordinate and grid contract

A character's world position is its standing point at the center of a tile's
bottom edge. Standard map cells are 48×48 pixels. Standard MV walking frames
use normalized pivot `(0.5, 1.0)` and pixel anchor `(frame_width / 2,
frame_height)`.

Editor preview, scene placement, map event conversion, sprite draw commands,
selection bounds, and runtime animation must use this same contract. Taller
art may extend above the cell without changing the standing point. `$` large
characters retain native frame dimensions and are never scaled down merely to
fit one cell. `!` object characters retain MV's object-alignment semantic while
still exposing an explicit anchor.

The preview draws a visible 48×48 cell and ground line. Pixel art is enlarged
with nearest-neighbor sampling at an integer scale; it is not stretched to a
fixed 288×288 box.

## Generator source adapter

`RPGMakerMVGeneratorCatalog` discovers all generator-part roots under the
local reference library and translates MV-specific names and directories to
generic Asteria categories. It recognizes body/face, eyes, eyebrows, front and
rear hair, clothing, armor, beard, ears, tails, wings, and accessories when
present.

Each logical part groups every available representation:

- walking character (`TV` and compatible sheets);
- face portrait (`FG` and compatible layers);
- side-view battler (`SV` and compatible sheets);
- thumbnails and variation/color-mask data when available.

The adapter records unavailable representations explicitly. One incomplete
part does not prevent unrelated parts from loading. MV filename, gender/body,
variation, color-mask, canvas, and layer-order rules remain inside the adapter
and do not enter generic character-generator code.

## Generic composition model

The generic generator accepts a recipe of category-to-part selections plus
palette choices. It produces a coordinated `GeneratedCharacterBundle` with:

- a four-direction, three-frame walking sheet;
- a face portrait sheet or selected portrait;
- a side-view battler sheet;
- character metadata containing frame dimensions, direction order, anchor,
  source-part identities, and representation availability;
- canonical assets for every generated visual.

Composition uses deterministic layer ordering per representation. Every input
layer must match that representation's expected canvas. Invalid dimensions,
missing masks, or incompatible body types produce precise issues rather than
silently offset artwork.

## Editor experience

The creator uses three functional areas:

1. Body/profile controls and selected-part summary.
2. Searchable, scrollable part thumbnails grouped by category.
3. Synchronized walking, face, and side-view previews.

The walking preview displays the character inside a real 48×48 map cell,
supports Down/Left/Right/Up, and animates the three frames. The face preview
uses the final composed portrait. The side-view preview animates idle motion.
Changing any selection refreshes all available representations together.

Missing face or side-view variants are shown as an explicit unavailable state;
the Editor never substitutes unrelated artwork. Existing custom Asteria parts
remain supported through the generic catalog API.

## Asteria character creation

Creating a character generates the visual bundle and adds:

- canonical assets to the project asset registry;
- an `ActorDefinition` with stable Asteria-owned ID;
- optional imported/default class and ability references;
- a scene entity with `Transform`, `SpriteRenderer2D`, and animator metadata;
- directional walking clips with the feet pivot;
- a placement request snapped to the selected map cell's standing point.

This operation is command-based so Editor undo removes all generated project
records and scene objects together. Redo restores the same stable IDs.

## Integration with current MV plan

Current MV integration Task 5 owns map cells, event placement, and feet-anchor
rendering. Task 6 owns conversion to Asteria actors, assets, abilities, and
scene entities. Generator-part discovery/composition and the redesigned Editor
surface are inserted after those foundations, before real runtime validation.

Audio remains outside this character-creator phase except for retaining
existing reference metadata.

## Error handling

- Missing local MV reference library: show a clear unavailable state and keep
  custom Asteria catalogs usable.
- Malformed or incomplete generator part: report its path and omit only that
  representation or part.
- Incompatible canvas/body type: reject the selection before generation.
- Missing generated output directory: create it only under the configured
  ignored local output root.
- Failed multi-record project creation: roll back all records and files created
  by the command.

## Acceptance criteria

1. Standard walking characters stand at the bottom-center of a 48×48 cell in
   Editor screenshots and pygame runtime captures.
2. Taller and `$` large characters preserve native size and the same standing
   point without clipping or forced scale-down.
3. Local discovery indexes the available MV generator parts deterministically
   and exposes their walking, face, and side-view relationships.
4. A recipe can compose all three representations when compatible source parts
   exist.
5. The redesigned Editor provides category thumbnails and synchronized
   walking/face/side-view previews with nearest-neighbor pixel rendering.
6. Create/undo/redo produces or removes the canonical assets, actor record,
   animator metadata, and scene entity atomically.
7. A generated character can be placed on an imported MV map and rendered in
   a bounded real pygame run.
8. No source or generated licensed pixel asset appears in Git status, staging,
   commits, or packages.
9. Focused tests, Cocoa Editor E2E, runtime capture, compile checks, dependency
   checks, and the complete regression suite pass.
