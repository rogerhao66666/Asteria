# Batch 125 — Battle Interaction Architecture

Batch 125 adds a presentation-only interaction router over the existing generic
action menu and multi-step workflow runtimes.

The default grammar is layered rather than flat:

`Root -> Action/Category -> Optional Workflow/Modifier -> Target -> Confirm`

Project-defined root layers may represent weapon selection, skill groups, items,
composition, special actions, swap, stance, or entirely different concepts.
Contextual controls such as boost-like modifiers stay hidden until the selected
action actually needs them.

Stress validation includes four weapon choices and eighty abilities. The eighty
abilities remain available without becoming eighty simultaneous buttons: the
menu groups by project category and pages at eight entries per view. Excess
root-level categories move into overflow rather than shrinking the entire UI.

Transform, summon, swap, composition and stance remain ordinary project actions
or workflows. The router never evaluates costs, target legality, resource
requirements, recipes, or gameplay results. Those remain controller/canonical
runtime responsibilities.

Product rule: gameplay complexity may be high; visual interaction complexity
must be layered and contextual.
