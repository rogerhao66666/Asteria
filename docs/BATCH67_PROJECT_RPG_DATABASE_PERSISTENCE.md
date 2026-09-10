# Phase 7 Batch 67 — Canonical Project / RPG Database Persistence

Version: `v0.67.0a67`

`Project` schema is upgraded from v3 to v4 and now owns a canonical
`RpgDatabase` as `project.rpg_database`.

This removes the standalone-data gap: Actor, Class, Item, Equipment,
Attachment, Enemy, Encounter, and Progression Track definitions now travel
with the same project JSON as scenes, assets, event programs, and scene event
bindings.

Project v2 and v3 remain backward-readable. They load with an empty
`RpgDatabase`; no RPG defaults are silently injected into old projects.

The RPG database keeps its own versioned schema, so future RPG toolkit
evolution does not require flattening all domain records into Project.

Architecture:

Project
- Scenes
- Assets
- Event Programs / Bindings
- RPG Database
  - Actors / Classes
  - Items / Equipment / Attachments
  - Enemies / Encounters
  - Progression Tracks

This establishes the persistence seam required for later Database Editor GUI
work without creating an editor-only copy of RPG data.

Next: Batch 68 — Phase 7 database validation / cross-reference integrity and
lifecycle-event binding persistence.
