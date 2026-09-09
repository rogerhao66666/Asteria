# Phase 3 / Batch 21 Closure Audit

## Scope
Hierarchy ordering and entity transfer.

## Added
- `Scene.entity_index()`
- `Scene.move_entity()`
- `ReorderEntityCommand`
- `MoveEntityToSceneCommand`
- same-scene reorder builder
- cross-scene entity move builder
- identity-preserving undo/redo for scene transfer
- regression tests for order restoration

## Architectural decisions
1. Hierarchy order is canonical Scene order, not a Qt-only presentation order.
2. Drag/drop semantics map to pure-Python commands.
3. Cross-scene moves preserve Entity identity and Component instances.
4. Undo restores the original source index.
5. The Qt tree can later emit these commands without owning reparenting logic.

## Deferred
- actual Qt drag/drop gesture implementation
- scene creation/deletion/reorder
- multi-entity drag
- nested entity parenting/Transform hierarchy
- transaction coalescing
- prefab hierarchy rules

## Closure
Batch 21 hierarchy command foundation: PASS.
