# Phase 3 / Batch 19 Closure Audit

## Scope
Structural Editing.

## Added
- reversible `Component._detach()` lifecycle seam
- `Entity.detach_component()`
- `Scene.detach_entity()`
- rename command
- add/remove entity commands
- add/remove component commands
- hierarchy component nodes
- editor actions for:
  - Rename
  - Add Entity
  - Delete Entity
  - Add Transform
  - Delete Component
- all structural edits participate in the same undo/redo history

## Important lifecycle decision
Destructive runtime removal and reversible editor detachment are distinct operations:

- `remove_*` means destroy/terminal runtime removal.
- `detach_*` means release ownership while preserving object identity so an editor command can undo.

This prevents the editor from resurrecting destroyed runtime objects or manipulating private containers directly.

## Invariants
1. Structural edits never bypass the command stack.
2. Undo/redo preserves Entity and Component object identity.
3. Scene/Entity ownership remains explicit.
4. Component lifecycle remains deterministic.
5. Editor does not introduce a second hierarchy model.

## Deferred
- generic Add Component picker from ComponentRegistry
- scene add/remove/reorder
- hierarchy drag/drop/reparent
- duplicate/copy/paste
- multi-selection
- prefab operations
- command transactions/grouping
- save/dirty recovery UX

## Closure
Batch 19 Structural Editing: PASS.
