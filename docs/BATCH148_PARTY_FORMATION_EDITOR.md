# Batch 148 — Party / Formation Editor

Batch 148 closes the current canonical authoring surface for party structure:
- project-owned party setup definitions
- roster
- active / reserve membership
- active capacity
- swap / reserve / reorder policies
- formation definitions
- slot coordinates / tags / adjacency
- active-member placement
- project-owned party presentation policies

## Canonical gap closed

Previously, active/reserve party setup and project presentation policy were mostly
expressed in validation/presentation controllers. They are now persistent project
definitions in RpgDatabase.

RpgDatabase schema advances from v21 to v22 and remains backward-readable.

## Information architecture

Large rosters must not become a wall of cards.

The editor contract is:
- Roster Browser
- Active / Reserve grouping
- Formation Canvas
- Selected Member / Selected Slot contextual inspector
- Policy settings
- Party UI profile section

The default workspace never renders every member as a full-detail card and never
opens every policy/detail group simultaneously.
