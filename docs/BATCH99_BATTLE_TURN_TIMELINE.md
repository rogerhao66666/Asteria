# Batch 99 — Battle Turn / Timeline Presentation

Batch 99 adds a backend-neutral, read-only projection of the frozen Battle Core scheduler and action-timing queues.

`BattleTurnTimelineRuntime.sync()` mirrors `BattleScheduler.pending()` and optional `BattleActionTimingRuntime.pending()` into presentation view-state. It exposes scheduler mode, round/time, upcoming turn entries, optional caller-supplied current actor marking, and pending cast/action progress.

The presentation layer does not pop or shift scheduler entries, resolve abilities, interrupt/cancel casts, validate targets, or infer turn ownership. `max_turns` is presentation policy only. Cast progress is calculated only as a visual ratio from canonical `started_at` / `resolve_at` / scheduler `current_time`; it has no gameplay effect.

Actual typography, portraits/icons and final UI layout remain renderer/UI-adapter work.
