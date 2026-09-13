# Batch 107 — Multi-step Action Workflow / Composition

Batch 107 adds a generic workflow presentation/controller layer for battle commands that require multiple user decisions before canonical action execution.

## Generic mechanism

`BattleActionWorkflowDefinition` is not an alchemy system. It describes ordered input steps. Each step can use single or multiple selection, minimum/maximum selection counts, optional selection, and back navigation.

This supports project systems such as:

- concoction / alchemy,
- rune or card combinations,
- ammunition preparation,
- summon configuration,
- transformation choices,
- stance chains,
- multi-part skills,
- project-defined composite actions.

## Runtime boundary

`BattleActionWorkflowRuntime` owns only transient interaction state:

- current step,
- supplied options,
- user selections,
- back/advance,
- completion,
- deterministic snapshot/restore.

The canonical controller supplies current options and their already-resolved enabled/disabled metadata. The workflow never evaluates a recipe, consumes ingredients, changes inventory/resources, validates battle targets, determines result abilities, or executes an action.

After completion, `selection_payload()` returns opaque selections to the canonical controller for interpretation.

## UI

`BattleUiComposer` renders an active workflow as its own interaction surface and suppresses the ordinary action menu while the workflow is active. This keeps nested action flows readable without imposing project-specific semantics.
