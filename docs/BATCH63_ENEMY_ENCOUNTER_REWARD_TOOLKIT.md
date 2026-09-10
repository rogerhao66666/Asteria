# Phase 7 Batch 63 — Enemy / Encounter / Loot-Reward Toolkit

Version: `v0.63.0a63`

Added EnemyDefinition/Runtime, EncounterDefinition/Member, RewardDefinition,
LootEntry and deterministic/seedable reward rolling.

Enemies instantiate the same generic Phase 6 StatBlock, ResourcePool and
TagSet used elsewhere. `hp`, `gold`, and `level` in the Simple RPG preset are
template keys only; projects may use any resource, currency, or progression
track names.

Encounter definitions describe composition, not a turn-based battle engine.
This keeps the data reusable by future JRPG and ARPG controllers.

RpgDatabase is schema v3 with v1/v2 backward reading.

Simple RPG now includes a Slime and a two-Slime field encounter with editable
gold/experience/loot defaults.

Next Batch 64: progression / level / experience toolkit.
