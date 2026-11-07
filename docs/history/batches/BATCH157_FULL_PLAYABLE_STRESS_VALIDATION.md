# Batch 157 — Full Playable Stress Validation

Batch157 validates the real path:

`Load Project + Load Save -> modify runtime build -> project runtime UI projection ->
field interaction -> encounter -> BattleRuntime + EnemyAIRuntime -> victory ->
reward write-back -> save -> close/reload exact state`.

## Gaps found and closed

1. The Batch155 reference abilities had authoring metadata but insufficient
   AbilityEffect payloads for a genuine battle. The reference project now authors
   real generic vitality delta effects.

2. Runtime save stored roster IDs but not active/reserve selection or formation
   placement. `RpgRuntimeState` advances from v4 to v5 with:
   - `party_active_actor_ids`
   - `party_placements`

   v1-v4 remain readable. v4 defaults active party to the roster and placements
   to empty.

3. Battle actor resource state previously did not write back to save snapshots.
   `GameSessionRuntime.finish_victory()` now persists hero battle resources/stats/
   tags before applying rewards.

## Generic runtime seam

`asteria.runtime.GameSessionRuntime` is project-agnostic. It knows no reference
actor/job/boss/resource names. It consumes canonical Project definitions and
GameRuntimeSave state, resolves current saved builds, processes Interaction2D
event programs, constructs BattleRuntime, executes AI/actions, applies rewards,
and synchronizes world/save state.
