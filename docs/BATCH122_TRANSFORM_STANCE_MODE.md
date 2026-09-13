# Batch 122 — Transform / Stance / Mode Integration

Batch 122 validates project-authored combat modes over the canonical
`BattleRuntime.transform()` / `revert_transform()` mechanism.

The reference scenario uses:
- normal form -> `steady_strike`
- guard stance -> `guard_counter`
- overdrive stacked on guard stance -> `overdrive_arc`

Each mode can replace stats, resources, tags, initiative and available abilities.
Nested form stacks revert deterministically. Snapshot/restore preserves the
active form and prior forms, so restored battles can continue reverting.

No GuardStanceSystem or OverdriveSystem was added. The reference names are
project vocabulary; the engine mechanism is generic member replacement plus
canonical combatant form state.

Presentation requirement:
the action UI must project the current form's action surface only. Inactive
normal/stance/transformed actions must not be dumped together into one menu.
