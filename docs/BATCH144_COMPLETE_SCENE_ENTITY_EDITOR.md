# Batch 144 — Complete Scene / Entity Editor Coverage

Batch 144 closes the Scene / Entity / Component authoring surface over existing
canonical Asteria structures.

Added:
- startup-scene authoring
- scene create/rename/delete/reorder
- entity create/rename/delete/duplicate/reorder
- move entity between scenes
- entity enabled/disabled authoring
- component add/remove plus existing metadata-driven field editing
- multi-entity duplicate/delete as one undoable transaction
- explicit headless SceneEntityAuthoringController for GUI and tests
- shell actions for startup scene, move up/down, enable/disable, and multi-select
  duplicate/delete

No parallel editor scene/entity model was introduced. All operations mutate the
canonical Project / Scene / Entity / Component structures through undoable editor
commands.

Visual polish is intentionally not the closure criterion. Functional coverage,
undo/redo integrity, serialization compatibility, and canonical-model ownership are.
