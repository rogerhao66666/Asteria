# Batch 100 — Battle Result / Reward Presentation

Batch 100 adds a backend-neutral result/reward projection over canonical resolved battle and reward data.

`BattleResultPresentationRuntime.present()` accepts a `BattleOutcome` plus an optional `RewardApplicationResult`. It mirrors winning/defeated/escaped sides, objective ids, applied currencies/items, and canonical progression advance results including rank crossings and milestone-granted abilities/tags.

Presentation never rolls loot, applies currency/items, adds progression, resolves battle outcome, or decides victory/defeat criteria. Labels are project-owned through `BattleResultProfile`.
