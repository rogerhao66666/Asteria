# Batch 145 — Character / Actor / Class Editor Authoring

This batch exposes the complete canonical ActorDefinition, ClassDefinition and
ClassAssignment data model to the editor authoring layer.

Coverage:
- Class create/edit/delete/duplicate
- display name
- stat bonuses
- resource bonuses
- granted tags
- granted abilities
- Actor create/edit/delete/duplicate
- base stats
- arbitrary base resources with min/max/current
- actor tags
- intrinsic abilities
- arbitrary number of class/job assignment layers
- assignment id / class / role / enabled / priority
- progression-track ownership per assignment
- assignment tags
- undo/redo for every mutation
- validation of class, ability, and progression references
- prevention of class deletion while referenced

Actor and Class definitions remain immutable canonical RPG records. Editor edits
replace canonical definitions atomically; no mutable editor-only RPG model exists.

The authoring API is intentionally generic: there are no hard-coded primary /
secondary slot limits. `role` remains project-defined data.
