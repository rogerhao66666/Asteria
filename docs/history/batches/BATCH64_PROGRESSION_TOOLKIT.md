# Phase 7 Batch 64 — Progression / Rank / Experience Toolkit

Version: `v0.64.0a64`

Added generic RPG progression tracks with milestone rewards.

A progression track is identified by a project-defined string. The runtime has
no special knowledge of Character Level, Job Level, EXP, weapon mastery,
crafting mastery, reputation, or similar concepts.

Milestones may provide data for stat bonuses, granted abilities, and tags.
`ProgressionRuntime.add()` reports every crossed milestone so a higher-level
RPG controller can apply or present those rewards without embedding progression
semantics in the Phase 6 gameplay core.

The Simple RPG template supplies a conventional `level` track as editable
starter data. RpgDatabase is schema v4 with v1-v3 backward reading.

Next Batch 65: party + battle/turn-order foundation.
