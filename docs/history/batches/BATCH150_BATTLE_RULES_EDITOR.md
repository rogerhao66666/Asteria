# Batch 150 — Battle Rules Editor

Batch 150 exposes the complete current canonical battle-rule surface through one
editor authoring layer:
- battle resources
- battle states/status policies
- interaction rules
- outcome checks
- targeting
- schedulers
- action timing
- action sequences
- gauge composition
- reactions
- battle objectives
- escape rules
- action transaction policies

Every mutation is undoable and edits the existing RpgDatabase mappings directly.
No second battle-rule data model was introduced.

## Information architecture

Battle authoring is intentionally two-level rather than one giant settings page.

Primary groups:
1. Combat Model
2. Turn Flow
3. Action Logic
4. Battle Flow
5. Execution / Costs

Each group exposes only its relevant rule-kind tabs. Inside one rule kind the
workspace uses search/filter, a selected definition, and contextual detail groups.

Sequences and gauge composition support child focus so an individual step, impact,
or threshold can be edited without expanding the entire definition at once.

## Reference integrity

The editor validates current cross-definition references that RpgDatabase itself
does not yet enforce globally:
- ability-linked targeting/timing/transaction/reaction/sequence rules
- gauge resource references
- gauge state references
- resource/state deletion protection while referenced by gauge definitions

No battle mechanics were redesigned in this batch.
