# Asteria Phase 4 / Batch 35 — Editor Reference World Integration Fix

Baseline: user-supplied `Asteria_v0.34.0a34_Phase4_MacFix.zip`

## Root cause

The runtime could load Reference World sidecars, but the Editor did not have a
generic Project-open resource-resolution path. TileMap was not represented as a
first-class project asset bound to a scene, so the authoring UI had nothing to
bind to.

This caused:
- Viewport: entity markers/camera overlay only
- Tile Palette: empty
- Layers: empty
- Animation dock: no resolved clip set

## Fix

- `tilemap` added as a canonical AssetRecord kind.
- Added persistent `TileMap2DComponent` scene binding using stable asset ID.
- Reference World now registers `reference_data/tilemap.json` as a TileMap asset.
- Reference World scene includes a stable-ID `World Map` entity with TileMap2D.
- Added generic `resolve_project_resources(document)`:
  - SpriteSheet
  - Tileset
  - TileMap
  - AnimationClipSet
- Added generic scene-authoring context resolution:
  - Scene -> TileMap2D -> TileMap -> Tileset -> SpriteSheet -> Viewport/Palette/Layers
- Added selection-driven animation context:
  - selected Entity -> Animator2D -> clip_set_id -> Animation dock
- Project Open and Set Project now resolve resources automatically.
- TileMap edits are written back to their canonical sidecar on Save.
- Switching project/render source resets stale active-layer state.

## Regression coverage

New tests prove:
- opening Reference World resolves a real TileMap render source
- palette exposes all 16 tiles
- layers are Ground / Props / Collision
- viewport emits real textured tile draw commands
- collision overlay has authored collision cells
- selecting Hero resolves all 8 animation clips and `idle_down`
- tile edit -> Save -> reopen persists to TileMap sidecar

## Verification

- 88/88 tests pass
- compileall passes
- Core/Project/Assets Qt import audit passes
- Core/Project/Assets pygame import audit passes

## Closure status

The software integration gap is fixed.

Phase 4 should remain **Mac GUI verification pending** until the updated package
is opened on macOS and the actual Qt widgets are visually/operationally checked:
Paint, Erase, Rectangle, Fill, layer reorder/visibility, collision overlay, and
Hero animation selection.
