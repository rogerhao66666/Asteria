# Local RPG Maker MV Reference Library Design

Date: 2026-09-26

## Goal

Create a complete, local-only reference copy of the installed RPG Maker MV
`NewData` and `dlc` trees inside the Asteria working repository. Asteria tests
and future research tools can use this stable local path without depending on
the Steam installation path.

The copied content is reference material only. It must never be committed,
pushed, packaged, or redistributed. Future Asteria starter content may imitate
the source taxonomy, dimensions, metadata relationships, and supported engine
capabilities, but must use independently created names, data, images, audio,
and text.

## Source and destination

Source root:

`~/Library/Application Support/Steam/steamapps/common/RPG Maker MV`

Source trees:

- `RPG Maker MV.app/Contents/MacOS/NewData`
- `dlc`

Destination root:

`~/Documents/Vscode/Asteria/local_reference/rpg_maker_mv`

Destination trees preserve all relative paths:

- `local_reference/rpg_maker_mv/NewData`
- `local_reference/rpg_maker_mv/dlc`

The expected initial source inventory is approximately 2.7 GB and 9,639
files. Exact counts and byte totals will be recorded after copying.

## Git and licensing isolation

`.gitignore` will exclude the entire
`/local_reference/rpg_maker_mv/` destination before any content is copied.
The implementation must verify with `git check-ignore` and `git status` that
no copied asset is staged or shown as an untracked file.

Only these derived artifacts may be committed:

- loader/test code;
- this design and its implementation plan;
- an aggregate inventory report containing counts and byte totals by file
  extension and top-level category;
- a manifest of relative paths, sizes, and SHA-256 hashes when needed for
  integrity checking.

The manifest must not contain file contents. Any future Asteria-owned starter
database must be authored independently and must not copy MV text, graphics,
audio, maps, database records, or distinctive content.

## Copy behavior

The copy is additive and repeatable. A synchronization tool will preserve the
source directory topology and update changed files. It will not delete files
from the destination unless a later request explicitly authorizes mirror
deletion.

Before copying, the implementation will verify sufficient free disk space and
that both source trees exist. Copy progress will be bounded and visible. The
source installation remains read-only.

## Runtime and test integration

The RPG Maker MV fixture resolver will prefer the repository-local reference
root. It may fall back to the Steam installation when the local copy is absent,
so tests remain usable before the optional reference library is provisioned.

Coverage will include:

- MV database JSON for maps, actors, classes, skills, items, weapons, armor,
  enemies, troops, states, animations, tilesets, common events, system data,
  and map metadata;
- images for characters, faces, icons/system UI, tilesets, animations,
  side-view actors/enemies, battlebacks, pictures, parallaxes, and titles;
- BGM, BGS, ME, and SE audio inventory;
- fonts, JavaScript runtime files, plugins, and DLC sample-project topology;
- current importer, walking-frame, side-view-motion, canonical-registry, and
  pygame rendering paths.

Tests that need licensed fixtures will skip clearly when neither the local
reference library nor the Steam source exists. They must not silently pass
with synthetic substitutes.

## Validation and acceptance

The integration is accepted when all of the following hold:

1. Both complete source trees exist under the destination root.
2. Destination file counts and byte totals match their corresponding sources.
3. A deterministic inventory/manifest is generated successfully.
4. Representative JSON files parse, representative PNGs decode, and every
   required image/audio/data category is present.
5. Existing real-MV adapter and bounded pygame render validation pass against
   the repository-local path.
6. The complete Asteria regression suite, compile check, dependency check, and
   `git diff --check` pass.
7. `git status` contains no copied MV content.

## Failure handling

If copying is interrupted, rerunning synchronization resumes by comparing
source and destination files. Validation reports mismatched counts, sizes,
missing categories, unreadable JSON, or undecodable images explicitly. No
source files are modified, and no destructive cleanup occurs automatically.

## Follow-up boundary

Building Asteria's own initial database is a separate implementation phase.
That phase will use the inventory to define generic schemas and coverage, then
populate them with original Asteria content and assets under an appropriate
license. It is intentionally outside this copy-and-validation change.
