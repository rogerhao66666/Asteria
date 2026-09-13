# Batch 86 — Speed / Turn / Continuous Timeline Scheduler

## Goal
Provide a backend-neutral scheduling layer that can represent classic rounds, one-turn-per-round speed ordering, and true continuous timelines without hardcoding a particular JRPG battle model.

## Canonical types
- `BattleSchedulerMode`: `round`, `speed_ordered`, `continuous`
- `BattleSchedulerDefinition`: project-owned scheduler policy
- `BattleScheduler`: deterministic runtime
- `ScheduledTurn`: immutable ready entry

## Modes
### Round
Every registered combatant receives one turn per round in deterministic project identity order. Speed does not affect ordering.

### Speed ordered
Every registered combatant receives one turn per round, ordered by descending speed (`PartyMember.initiative`). Stable member ID breaks ties.

### Continuous
Each combatant receives a next-ready time:

`next_ready = current_time + timeline_scale / speed`

A faster combatant can therefore act multiple times before a slower combatant. Ties remain deterministic by member ID.

## Battle integration
`BattleRuntime` accepts an optional `scheduler_definition`. Existing projects that omit it keep the legacy fixed-initiative queue, preserving compatibility.

Summons can be scheduled from current timeline time. Transformations preserve an already-earned ready time; their new speed applies on the next scheduling cycle. Removed combatants are removed from the scheduler.

A `BattleStatePolicy(prevent_action=True)` is now scheduler-visible: a blocked turn is consumed, `turn_ended` lifecycle processing still runs, and finite states can naturally expire rather than deadlocking the timeline.

## Snapshot seam
`BattleScheduler.to_data()/from_data()` preserves:
- scheduler definition
- virtual timeline time
- logical round index
- deterministic sequence counter
- current round participation
- pending ready entries

This is a scheduler-local snapshot seam; complete Battle Snapshot integration remains scheduled for the later battle closure batch.

## Data model
`RpgDatabase` schema v14 owns `battle_schedulers`. Older v1–v13 databases remain readable and do not receive invented scheduler definitions.

## Non-goals
Batch 86 intentionally does not implement cast time, recovery, action delay, priority, interrupt, timeline advance/delay, or queued casts. Those belong to Batch 87 and build on this scheduler.
