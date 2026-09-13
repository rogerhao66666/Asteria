# Batch 149 — Enemy / Encounter / Reward Editor

Batch 149 closes the current canonical authoring surface for:
- Enemy definitions
- Stats / resources / tags / abilities
- Reward currencies / progression / loot
- Encounter composition
- Enemy counts / weights / tags
- Enemy AI decision rules
- Open AI conditions / target selectors / actions
- Boss phases
- Per-phase rule sets and actions-per-ready
- Enemy -> AI binding

## Canonical gap closed

Enemy AI definitions already existed, but reference/validation code manually knew
which AI belonged to which enemy. Batch 149 adds persistent
`EnemyBehaviorBinding`, so a project can save that relationship directly.

RpgDatabase schema advances from v22 to v23 and remains backward-readable.

## Information architecture

Boss complexity is not presented as one enormous form.

The workspace uses separate categories:
Enemies / Encounters / AI & Boss Phases / Rewards.

AI uses a rule/phase browser with a contextual detail inspector. Selecting a rule
focuses that rule; selecting a phase focuses that phase. Conditions, targets,
actions, phase hooks, priorities and weights are edited in focused groups instead
of being simultaneously expanded.

Enemy reward data remains logically attached to the enemy but is presented in its
own detail group to keep the primary enemy view readable.
