# Batch 143 — Editor Project Workspace

This batch starts the formal Asteria Editor phase.

Implemented a headless-testable ProjectWorkspaceController behind the GUI shell:
- create a canonical Project with startup Scene
- open/load canonical project files
- save and Save As
- persistent recent-project list
- project validation surfaced as editor diagnostics
- Run creates an isolated canonical runtime snapshot
- Stop discards the play session
- opening another project is blocked during active play mode
- workspace state exposes dirty/run/scene/startup/recent state

The controller deliberately does not introduce a second project model.
Qt presentation can consume this controller while Python authoring continues to
operate on the same Project model.

Visual polish is not the closure criterion for this phase; functional coverage is.
