# Phase 3 / Batch 23 Closure Audit

## Scope
Scene Viewport Integration foundation.

## Added
- pure-Python `ViewportCamera`
- world ↔ screen transforms
- anchored zoom
- pan
- viewport marker generation from canonical `Transform`
- entity hit-testing/picking
- selected Scene resolution from EditorDocument
- PySide6 `SceneViewportWidget`
- editor grid/origin rendering
- entity marker/name rendering
- selected marker highlighting
- click-to-select
- Ctrl-click multi-selection
- middle mouse / Alt+left pan
- mouse-wheel zoom
- viewport refresh synchronized with hierarchy/inspector selection

## Architectural decisions
1. The Editor viewport reads canonical Scene/Entity/Transform directly.
2. Qt paints editor overlays only; it is not the game renderer backend.
3. pygame remains outside the Editor model.
4. Viewport navigation is pure editor state and is not serialized into game Project data.
5. Entity picking is based on a backend-neutral marker model, making a future GPU scene canvas possible.
6. Entities without Transform are valid but have no world marker.

## Why not embed pygame now?
Embedding the runtime window inside Qt would couple Editor lifetime, input, and rendering to one backend.
Batch 23 intentionally proves the editor-world data boundary first. A future scene-render adapter can consume the
same backend-neutral draw commands while Qt continues to own editor overlays and tools.

## Deferred
- actual sprite/tile rendering in the viewport
- selection rectangle
- gizmo translate/rotate/scale
- viewport camera persistence per Scene
- snapping/grid settings
- renderer adapter for TextureDraw/TileDraw
- play mode

## Closure
Batch 23 Scene Viewport foundation: PASS.
