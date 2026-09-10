# Phase 7 Batch 73 — Canonical GameplayLibrary Project Ownership

Version: `v0.73.0a73`

Phase 7 pre-closure audit found one blocking ownership gap: RPG definitions
reference ability IDs, while the Phase 6 `GameplayLibrary` was serializable but
was not owned by `Project`.

This batch closes that gap.

## Project schema v6

`Project` now canonically owns:

- assets
- scenes
- EventPrograms / scene event bindings
- lifecycle event bindings
- `RpgDatabase`
- `GameplayLibrary`

`gameplay_library` is persisted as ordinary canonical project data. Presets are
still templates; they are never implicit runtime rules.

## Cross-reference validation

For canonical v6 projects, Project validation checks RPG ability references
from:

- Actor definitions
- Class definitions
- Equipment definitions
- Attachment definitions
- Enemy definitions
- Progression milestones

against `Project.gameplay_library.abilities`.

Unknown ability references fail loudly.

## Backward reading

Project schema v2-v5 remains readable. Those schemas predate canonical
GameplayLibrary ownership, so loading them does not invent placeholder ability
definitions. If such a legacy project contains RPG ability references, saving
it as canonical v6 requires the author/tooling to resolve those references
explicitly.

This avoids both data loss and fake migration content.

## Closure effect

The main Phase 7 definition ownership graph is now closed:

Project
├── GameplayLibrary
└── RpgDatabase
    └── ability IDs -> GameplayLibrary abilities

RPG runtime save state remains separate from Project definition data.
