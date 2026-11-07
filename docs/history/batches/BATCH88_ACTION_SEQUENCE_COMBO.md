# Batch 88 — Action Sequence / Combo / Cooperative Ability

Asteria now has one generic action-composition model for multi-hit attacks, ordered chains, finishers and N-person cooperative abilities.

## Contract

`ActionSequenceDefinition` owns authored sequence structure. `ActionSequenceStep` selects a participant by index, references an ordinary Ability, can repeat for multi-hit, carries a relative delay, and can require/emit arbitrary tags. `ActionSequenceRuntime` is a deterministic pure planner. `BattleRuntime.execute_sequence()` routes concrete steps back through the normal AbilityRuntime; there is no second damage/effect system.

Participant count is project data and `max_participants=None` means no engine cap. `participant_policy`, `interruption_policy`, `target_policy`, and tags are open project vocabulary. Common behavior can later be surfaced as presets; unusual behavior remains script/rule-extensible.

## Responsibility boundary

The engine guarantees valid deterministic planning/execution and rejects malformed references. It does not declare which game design is correct. Whether KO, stun, cost reservation, interruption, or a missing participant cancels/skips/substitutes a step is project policy. Current convenience execution supports cancel-remaining, skip/continue and raise behavior. Scheduler reservation and transactional cost semantics remain explicit closure seams for later battle transaction work rather than hidden assumptions.

## Examples

- Triple Slash: one step, repeat=3.
- Element chain: step A emits `element.fire`; step B requires it.
- Cooperative skill: participant 0 casts Fire, participant 1 casts Wind.
- 128-person authored sequence is accepted when the project chooses unlimited participants.
