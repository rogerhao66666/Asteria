# Asteria v0.35.0a35 — Phase 4 MacFix / Editor Integration Candidate

This build is based on the user-supplied v0.34 Phase 4 MacFix and fixes the
remaining Reference World Editor integration gap.

Opening `AsteriaReferenceWorld.asteria.json` now has a canonical path for:
TileMap -> Viewport, Tileset -> Tile Palette, TileMap layers -> Layers dock,
and selected Hero Animator2D -> Animation dock.

Automated result: **88 tests passed**, compileall passed.

Phase 4 is not re-frozen until the updated package completes the Mac GUI smoke
test. See `docs/BATCH35_EDITOR_INTEGRATION_FIX.md`.
