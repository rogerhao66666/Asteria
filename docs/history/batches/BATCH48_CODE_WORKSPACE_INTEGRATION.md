# Phase 5 Batch 48 — Code Workspace Integration / Diagnostics

Version: `v0.48.0a48`

## Goal

Make Code mode practical for real authoring work rather than only proving that
Python can execute.

## Added

### Selection-aware authoring context

Scripts now receive convenience globals:

- `project` — current canonical project facade
- `selected` — current selected Scene/Entity, or owning Entity for a Component
- `scene` — selected scene or selected entity's owning scene
- `entity` — selected entity when applicable

These are wrappers over the same canonical Asteria data used by GUI authoring.

### Structured diagnostics

`ScriptRunResult` now records:

- filename
- line
- column for syntax errors
- exception type
- formatted diagnostic

The Code workspace jumps the cursor to the failing line after an exception and
the Console receives the traceback.

### Code workspace ergonomics

- current Editor selection shown above the editor
- API quick reference panel
- `Ctrl+Enter` Run shortcut
- Run tooltip/documentation
- Run disabled when no Project is loaded
- selection context refreshes when Project Tree selection changes

## Safety / architecture boundary

Asteria project scripts remain trusted local Python, not a security sandbox.
The convenience globals are authoring facades, not Qt widgets.

## Authoring invariant

Visual editing, Event Editor editing, and Python authoring operate on the same
canonical Project / Scene / Entity / Component / Event representation.

## Next

Run the Phase 5 closure audit. Any closure blockers found should be fixed before
freezing Phase 5 and proceeding to Phase 6 Generic Gameplay Framework.
