# Asteria Source Recovery Manifest

Date: 2026-09-25

## Canonical integration inputs

1. `Asteria_v0.159.0_COMPLEX_REFERENCE_RPG_ACCEPTANCE_CURRENT_FULL.zip` — latest recovered full Engine/Editor/RPG/Runtime canonical baseline (4,067,021 bytes in Library).
2. `Asteria_Canonical_PreAssetValidation_Batch106` / cumulative Asset + Composable Presentation implementation through Batch 106.
3. Latest five canonical documents: `ASTERIA_SPEC.md`, `ASTERIA_ASSET_SPEC.md`, `ASTERIA_ASSET_PIPELINE.md`, `ASTERIA_ART_DIRECTION.md`, `ASTERIA_PROGRESS.md`.
4. `.agents/skills/asteria-asset-production/SKILL.md`.

## Merge policy

The v0.159.0 full tree is the structural base. Asset/Presentation Batch 106 is additive except for five overlapping integration files. Those overlaps were reconciled instead of blindly overwritten:

- `src/asteria/__init__.py` — retained canonical repo version metadata.
- `src/asteria/presentation/__init__.py` — retained the existing battle-presentation exports and added generic composable-presentation exports.
- `src/asteria/assets/registry.py` — compatibility registry supports both legacy `AssetRecord` add/get/records/validate and canonical register/resolve/remove/query/snapshot/events APIs.
- `src/asteria/assets/resources.py` — retained legacy texture resource/cache and added canonical audio/font/material resources.
- `src/asteria/assets/__init__.py` — retained legacy public Asset API while exposing the new canonical asset subsystems without replacing the legacy package-level `AssetRef` contract.

All other Asset/Presentation source and test files were additive because they did not collide with the v0.159.0 source paths.

## Exclusions

Rejected/FAIL art attempts, promotional/showcase boards, and Technical-PASS-only Starter assets are not promoted into canonical production assets. They remain historical artifacts outside this source package.

## Input checksums

- v0.159.0 full baseline SHA-256: `183fd32f29a4ca61c5490e23e5c30e62b4b0d43b17d646ee1af0255f8ff610ce`
- Batch106 cumulative asset/presentation package SHA-256: `90ea30ecda7ed27550e38e5581a9baf719dd1f9d5243c853298910ef6f76f905`
