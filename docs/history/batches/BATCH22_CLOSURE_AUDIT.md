# Phase 3 / Batch 22 Closure Audit

## Scope
Qt hierarchy interaction foundation, Scene structural editing, and multi-selection.

## Added
- Project scene ordering API
- reversible Scene add/remove/reorder commands
- startup-scene restoration on undo
- homogeneous multi-selection model
- Project tree switched to extended selection
- drag/drop-enabled tree presentation
- pure-Python hierarchy drop-intent mapper
- entity drop semantics:
  - reorder in current Scene
  - move to another Scene
- scene drop semantics:
  - reorder canonical Project scene order
- Editor Scene actions:
  - Add Scene
  - Delete Scene

## Architectural decisions
1. Qt drag/drop is presentation only; canonical mutation remains command-based.
2. Scene order is stored in Project, not only the tree widget.
3. Multi-selection is represented in EditorSelection without changing runtime Entity/Scene models.
4. Mixed-kind tree selection collapses to one primary item; batch editing is homogeneous-only for now.
5. Removing a startup Scene updates startup deterministically and undo restores it.

## Deferred
- custom Qt dropEvent adapter with visual insertion line semantics
- multi-entity move transaction
- property batch editing
- parent/child entity hierarchy
- cut/paste scenes
- scene duplication
- Scene viewport selection sync

## Closure
Batch 22: PASS.
