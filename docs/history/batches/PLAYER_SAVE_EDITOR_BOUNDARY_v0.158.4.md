# Player Save / Editor Boundary — v0.158.4

Asteria Editor no longer exposes Player Save creation, opening, or saving actions.

Canonical authoring flow:

`Open Project -> Edit Project/Game Start -> Run Project`

Player persistence belongs to the running game:

`Game Runtime -> New Game/Load Game -> Play -> Save Game -> Player Save JSON`

The underlying runtime save serialization and integration code remains available to the game runtime and automated tests. It is intentionally not an Editor authoring workflow.

Developer stress fixtures and playtest infrastructure may construct runtime states programmatically, but those are testing infrastructure rather than Player Save UI.
