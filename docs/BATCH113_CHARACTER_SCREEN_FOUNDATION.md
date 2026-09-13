# Batch 113 — Runtime RPG UI / Character Screen Foundation

Batch 113 begins Runtime RPG UI after the Battle System milestone freeze.

## Canonical source

The screen projects from `ResolvedActorBuild`, the immutable canonical actor-build view already shared by battle/editor/UI layers. It does not reconstruct actor stats/resources/abilities from lower-level definitions.

Optional supporting runtime sources:
- `EquipmentLoadout` via portable `to_data()`
- `ProgressionRuntime`
- project-owned display/profile metadata

## Character screen view model

`CharacterScreenRuntime` produces a read-only `CharacterScreenView` containing:

- arbitrary stats
- arbitrary resources with project-defined visual presentation role
- arbitrary equipment slots and capacities
- resolved abilities with provenance
- arbitrary progression tracks
- tags/capabilities
- class assignment IDs
- active passive IDs
- ordered screen sections
- presentation-only selected section

No fixed HP/MP, weapon/armor slot, class count, skill taxonomy or progression-track name is required.

## Project-owned profile

`CharacterScreenProfile` configures:
- section order / hidden sections
- stat labels
- resource labels and presentation roles
- equipment slot labels
- equipment labels
- ability labels
- progression labels

Defaults remain usable but do not encode gameplay rules.

## Navigation state

Section selection belongs to presentation only. Switching from Overview to Abilities/Equipment/etc. does not mutate canonical RPG state and is included in deterministic snapshot/restore.

## Boundary

Character Screen runtime never:
- equips/unequips items
- spends/restores resources
- learns/forgets abilities
- changes passives
- allocates progression
- changes class assignment
- mutates `ResolvedActorBuild`
