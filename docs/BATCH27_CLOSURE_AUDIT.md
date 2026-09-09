# Phase 4 / Batch 27 Closure Audit

## Scope
Real Scene Viewport rendering seam.

## Delivered
- canonical TileMap -> existing backend-neutral TextureDraw conversion
- layer ordering and opacity
- viewport culling
- Tileset -> SpriteSheet -> SpriteFrame source-rectangle resolution
- Qt texture cache and QPainter TextureDraw adapter
- project-relative texture source resolution
- optional real tile render source in SceneViewportWidget

## Execution path
TileMap
→ Tileset
→ SpriteSheet / SpriteFrame
→ build_tile_draws
→ TextureDraw
→ Qt adapter
→ Scene Viewport

No second editor-only tile representation was introduced.

## Deferred
Tile palette and painting, collision editing, Scene attachment/resource ownership,
entity sprite rendering, animation preview, camera authoring, GPU editor renderer.

## Closure
PASS after cumulative tests and compileall.
