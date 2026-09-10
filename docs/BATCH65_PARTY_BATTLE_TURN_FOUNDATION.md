# Phase 7 Batch 65 — Party / Battle / Turn Foundation

Version: `v0.65.0a65`

Added:

- `PartyMember`
- `Party`
- deterministic `TurnQueue`
- `BattleAction`
- `BattleRuntime`

`BattleRuntime` is deliberately thin. It coordinates party membership, actor
selection and turn order while delegating actual ability meaning to the frozen
Phase 6 `AbilityRuntime`.

There is no RPG-specific damage calculator here. A battle action simply resolves
an actor and targets into Phase 6 `AbilityTarget` values and executes the
canonical ability.

Party side names are project-defined strings. `player` and `enemy` are
conventions only.

Current turn policy is deterministic fixed initiative:
higher initiative acts first, with stable member ID tie-breaking. The queue is
snapshot/restorable for future save/resume support.

This batch is a foundation, not the final JRPG battle controller. Later Phase 7
batches may add command selection, victory/defeat resolution, reward handoff,
and battle state orchestration without changing Phase 6.

Next Batch 66: battle outcome + reward/progression handoff.
