# Batch 156 — Reference Saves

Batch 156 adds four real `GameRuntimeSave` files for the Batch155 Complex Reference RPG:

- `early`
- `mid`
- `endgame_complex`
- `boss_stress`

They are normal persistent save files, not Python fixtures.

The reference-save work exposed one real canonical gap: `RpgRuntimeState` did not
persist per-actor level/EXP or mutable job/class unlock/selection state. Batch156
therefore advances `RpgRuntimeState` from schema v3 to v4 and adds
`ActorProgressionState`.

`ActorProgressionState` persists:
- level
- experience
- generic progression point balances
- unlocked class/job ids
- active class/job ids

Old runtime-state schemas v1, v2 and v3 remain readable; pre-v4 saves restore with
an empty `actor_progression` map.

The reference saves also persist existing canonical state:
inventory, currencies, progression totals, per-actor skill-tree allocations,
learned abilities/passives, equipment instances, runes/attachments, equipment
growth, party roster, scene, player position/facing and event flags/variables/local state.
