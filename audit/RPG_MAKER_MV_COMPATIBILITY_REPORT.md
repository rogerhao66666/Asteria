# RPG Maker MV Compatibility Report — 2026-09-26

Status: **PARTIAL — real source import boundary validated; interactive runtime playback remains external**.

The local Steam installation was found at:

`/Users/roger/Library/Application Support/Steam/steamapps/common/RPG Maker MV`

Real files were tested from characters, faces, side-view actors, enemies, side-view enemies, tilesets, animations, pictures, and parallaxes. The adapter validates source image structure and translates MV-specific layouts to generic canonical metadata. It handles normal character sheets, `$` single-character sheets, `!` object-character alignment, Down/Left/Right/Up walking rows, middle idle frame, and the 18 side-view motions without adding MV assumptions to Animation Core, Runtime, Scene, Battle, or Presentation.

Fifteen real-fixture tests pass. No original MV file was modified, and no MV binary asset is tracked in the Asteria repository.

Remaining: interactive runtime playback, visual tile sampling/seams, side-view transitions, and hardware rendering/audio verification.
