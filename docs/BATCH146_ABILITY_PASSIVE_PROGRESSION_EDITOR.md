# Batch 146 — Ability / Passive / Progression / Skill Tree Editor

Batch 146 exposes the full current canonical authoring surface for:
- Gameplay Ability definitions
- Passive definitions
- Progression tracks and milestones
- Progression graphs / skill trees
- Node rank costs
- Node rewards
- all/any prerequisites
- exclusive groups
- tags
- ability evolution rules

All mutations are undoable and replace canonical immutable definitions atomically.
Reference validation protects abilities, passives, progression tracks, graph rewards,
and prerequisite integrity.

## Information architecture

Functional completeness must not become one-screen clutter.

The editor presentation contract is:
- category sidebar for Abilities / Passives / Progression Tracks / Skill Trees / Evolutions
- search + filter browser for the current category
- contextual detail inspector for only the selected definition
- Skill Trees use graph + selected-node detail
- node rank costs / prerequisites / rewards live in focused detail groups
- progressive disclosure is required
- switching category clears contextual selection
- the default view never expands every detail of every system at once

The headless `RpgProgressionWorkspaceModel` encodes these rules so the future Qt
presentation and tests share the same information hierarchy.
