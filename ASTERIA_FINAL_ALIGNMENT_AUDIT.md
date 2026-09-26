# Asteria Final Chat-Side Alignment Audit

**Scope:** Clean engine-only canonical handoff before Codex real-environment integration.
**Asset policy:** No generated/rejected Starter art and no RPG Maker assets are included in this package.

## Canonical documents reviewed

1. `ASTERIA_SPEC.md`
2. `ASTERIA_ASSET_SPEC.md`
3. `ASTERIA_ASSET_PIPELINE.md`
4. `ASTERIA_ART_DIRECTION.md`
5. `ASTERIA_PROGRESS.md`
6. `.agents/skills/asteria-asset-production/SKILL.md`

## Alignment result

The repository preserves the generic, data-driven architecture described by the canonical documents: Editor and scripting share canonical models; Runtime consumes canonical project/asset data; RPG/JRPG/ARPG and Battle systems remain data-driven; Presentation is separated from gameplay semantics; animation, VFX, audio, camera, text/UI, materials, attachments and sequencing are composable; asset import/canonicalization is separate from runtime consumption; Character Generator remains an optional authoring framework rather than a runtime character type.

The package intentionally does **not** claim that official Starter content is complete. The art-direction and asset-production documents define the quality contract; satisfying that contract requires actual approved art. Previously generated/derived art did not satisfy that gate and has been removed from this canonical handoff.

## Requirement status classes

- **IMPLEMENTED / CHAT-TESTED:** source implementation exists and is covered by the repository's automated/headless tests.
- **IMPLEMENTED / EXTERNAL VALIDATION:** implementation exists, but final confidence requires the real GUI/GPU/audio/filesystem/hardware environment.
- **DEFERRED CONTENT:** engine capability exists, but production content is intentionally absent.

## Implemented / Chat-tested areas

- Project/scene/entity/component canonical model and serialization.
- Editor/runtime shared project data contracts and undoable authoring foundations.
- RPG data model, equipment, classes, abilities, resources, status/progression systems and battle scheduling/action foundations.
- Generic Presentation Sequence architecture and executors.
- Animation/timeline/property animation foundations, layered/attached/baked/hybrid presentation contracts.
- Generic attachment/socket/transform/weapon-compositing foundations without weapon-specific Core coupling.
- VFX/material/camera/audio/text presentation contracts.
- Asset source adapters, canonicalization/validation/store/package/install/load foundations.
- Character Generator recipe/catalog/compositor/topology framework and custom-import path.
- Python/script-first workflow alongside GUI-facing APIs.

## Implemented but requiring Codex / real-environment validation

- Full PySide6 interaction and visual-quality pass across the Editor.
- ModernGL/Pygame rendering, shader/material/lighting behavior on a real GPU/backend.
- Audio-device playback/latency behavior.
- Hardware profiling under final/high-resolution assets and heavy VFX/animation load.
- Real filesystem/project migration and packaging workflows outside the headless test environment.
- RPG Maker MV compatibility against the user's actual MV installation/project assets.
- Final end-to-end vertical slice with production-quality content.

## Deferred content (not an engine failure)

- Official Asteria Starter character/environment/VFX/audio art pack.
- Production-ready Character Generator modular art library.
- Final human art/motion review of Starter content.

## RPG Maker MV development-fixture policy

The user's legally obtained RPG Maker MV installation/project may be supplied to Codex as a **private development fixture**. MV-specific parsing/import logic must terminate at Asteria's generic Asset Pipeline/canonical asset boundary. Core Runtime, Battle, Scene and Presentation must not acquire RPG Maker-specific gameplay semantics. MV assets are not part of this ZIP and must not be treated as redistributable Asteria Starter assets.

## Removed from this handoff

- Rejected/generated Character Generator Starter art.
- Generated/cropped/source-reference boards and previews.
- Reference art atlases/sprites that are not approved production assets.
- Art-promotion tests whose only purpose was to assert rejection state of removed content.

## Closure rule

This package is the clean **engine/code/docs/tests** baseline for Codex integration. “All specs aligned” means implemented code remains consistent with the canonical architectural contracts; it does **not** convert explicitly deferred production art or external hardware/UI validation into false PASS states.
