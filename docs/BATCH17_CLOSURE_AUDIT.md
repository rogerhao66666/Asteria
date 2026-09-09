# Phase 3 / Batch 17 Closure Audit

## Scope
Editor Foundation 1.

## Added
- `asteria.editor` package
- `EditorDocument` / direct runtime-object selection
- PySide6 `AsteriaEditorWindow`
- dock layout: Project / Scene, Inspector, Assets, Console, central viewport placeholder
- Inspector projection from canonical Component Field metadata
- project / scene / entity / asset inspection
- CLI entry point `asteria-editor`

## Decisions
1. No parallel editor-only scene/entity/component model.
2. Selection references canonical objects directly.
3. Component Inspector reads canonical metadata.
4. PySide6 remains editor-only.
5. Viewport stays placeholder until renderer embedding boundary is implemented.

## Deferred
editable field widgets/validation, undo/redo, hierarchy drag/drop, component add/remove UI,
live viewport renderer, asset thumbnails, gizmos, play mode, dirty-document UX.

Closure: PASS.
