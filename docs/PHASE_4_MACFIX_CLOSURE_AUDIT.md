# Asteria Phase 4 MacFix Closure Audit

Baseline:
- User-provided `Asteria_v0.34.0a34_Phase4_MacFix.zip`

Closure status before this batch:
- REOPENED

Observed Editor integration gaps:
- Reference World opened without TileMap rendering in Scene Viewport.
- Tile Palette was empty.
- Layers was empty.
- Animation Preview showed `No animation selected`.
- Tile authoring GUI therefore could not be exercised on the canonical reference project.

Root cause:
- Reference World TileMap existed only as a sidecar consumed by the runtime path.
- TileMap was not a first-class project asset with a persistent scene binding.
- EditorDocument had no generic project-resource resolution step on project open.
- EditorAssetViews only cached sprite sheets and animation clip sets.
- Scene Viewport / Tile Palette / Layers / Animation widgets required resources to be injected manually.

Batch 35 fix:
- Added canonical `tilemap` asset kind.
- Added persistent `TileMap2DComponent` scene binding.
- Reference World now registers `reference_data/tilemap.json` as a canonical asset and binds it through a `World Map` entity.
- Added generic Editor project resource resolver for sprite sheets, tilesets, tilemaps, and animation sets.
- Added cross-resource validation.
- Added scene-to-TileMap render source resolution.
- Project open now resolves resources automatically.
- Selection changes refresh Animation context automatically.
- TileMap edits are persisted back to the canonical sidecar on Save.
- No Reference-World-specific Editor special case is required.

Architecture invariants preserved:
1. Python-first orchestration.
2. Qt remains Editor-only.
3. pygame remains Platform/Runtime-only.
4. Editor still edits canonical Project/Scene/Entity/Component/Asset data.
5. No duplicate persistent editor world model was introduced.
6. Stable asset/entity IDs remain canonical references.
7. Editor ViewportCamera remains separate from gameplay Camera2D.
8. 2.5D remains presentation-only.

Automated closure requirements:
- Full pytest regression passes.
- compileall passes.
- Core/Project remain free of Qt and pygame imports.
- Reference World resource resolution and save/reopen are regression-tested.

Manual Mac GUI verification still required:
- Viewport displays actual Town & River TileMap immediately after Open.
- Tile Palette shows 16 environment tiles.
- Layers shows Ground / Props / Collision.
- Paint / Erase / Rectangle / Fill work.
- Layer reorder / visibility work.
- Collision overlay renders correctly.
- Selecting Hero populates all 8 animation clips.
- Save / reopen preserves authored TileMap changes.

Phase 4 may be re-frozen only after the above manual Mac GUI checks pass.
