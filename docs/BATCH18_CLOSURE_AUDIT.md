# Phase 3 / Batch 18 Closure Audit

## Scope
Editable Inspector + canonical validation + undo/redo.

## Added
- generic `Command` protocol and `CommandStack`
- `SetAttributeCommand`
- document revision / dirty tracking
- component field coercion and canonical `Field.validate()` path
- rejection of runtime-only (`serialize=False`) component properties
- editable Qt Inspector value column
- automatic rollback of invalid UI text to canonical runtime value
- Edit menu Undo / Redo with platform-standard shortcuts
- undo/redo action labels and editor dirty-title indicator

## Execution path
Inspector edit
→ field name + raw UI text
→ canonical ComponentSchema / Field
→ type coercion
→ `Field.validate()`
→ `SetAttributeCommand`
→ `EditorDocument.execute()`
→ canonical Component property
→ undo/redo history.

## Decisions
1. Qt does not own mutation semantics.
2. All successful editor mutations are command-based.
3. Validation remains in Core metadata, not duplicated in UI.
4. Invalid edits never mutate runtime objects or history.
5. Runtime-only fields are visible for debugging but non-editable.
6. Command stack is pure Python and reusable by keyboard, menus, scripts and later editor tools.

## Deferred
- merge/coalescing of continuous edits (drag/spin/gizmo)
- project/scene/entity rename commands
- add/remove/reorder component commands
- structural hierarchy undo
- save/load UI and unsaved-change prompts
- typed Qt widgets (spin box/combo/check box)
- multi-object property editing

## Closure
Batch 18: PASS if full cumulative tests and compileall pass.
