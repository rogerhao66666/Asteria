# Batch 87 Closure Audit

## Scope

Advanced action timing: startup, cast, recovery, priority, interrupt/cancel, timeline advance/delay, deterministic pending-action snapshot.

## Architecture checks

- Battle core remains renderer/editor independent.
- No fixed quick/heavy/cast spell enums.
- Timing metadata is canonical project data.
- Pending action runtime is mutation-free until `BattleRuntime` resolves the action.
- Continuous scheduler remains the source of actor readiness.
- Pending cast resolution uses deterministic `(resolve_at, -priority, sequence, actor_id)` ordering.
- Timeline advance cannot place readiness before current scheduler time.
- Existing scheduler definitions and v1-v14 RPG databases remain readable.
- Existing immediate `BattleRuntime.execute()` API remains available for low-level callers and tests.

## Validation

- Full pytest regression: 466 passed, 4 skipped.
- Batch 87 deterministic demo: PASS.
- `compileall`: PASS.
- Backend AST dependency audit for PySide6/pygame in `src/asteria/{core,gameplay,rpg,events}`: 0 / 0.

## Deliberate deferrals

- Cost reservation/pay/refund policy is deferred to the Battle Transaction layer.
- Cooperative/multi-participant timing policy is Batch 88.
- Reaction queue/preemption is later Battle Core work.
- Final animation/VFX/UI presentation remains after Battle Core closure.
