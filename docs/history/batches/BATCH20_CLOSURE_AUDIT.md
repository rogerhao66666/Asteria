# Phase 3 / Batch 20 Closure Audit

## Added
- formal `ComponentRegistry.registrations()` discovery API
- registry-driven Component Picker
- generic Add Component UI
- serialized Entity clipboard snapshot
- Duplicate Entity
- Paste Entity
- fresh persistent UUIDs on clone/paste
- component deep copy through canonical serializer
- atomic `CommandTransaction`
- rollback on partial transaction failure

## Decisions
1. Editor component discovery depends only on a public registry seam.
2. The picker is not hard-coded to Transform.
3. Copy/paste stores canonical data, not live object pointers.
4. Duplicate/paste create new persistent identity.
5. Transactions make compound editor operations one undo step.
6. Qt remains an adapter over pure Python editor services.

## Deferred
- component categories/icons
- constructor wizard
- component clipboard
- cut
- multi-selection
- hierarchy drag/drop
- command coalescing
- cross-project asset dependency remapping

## Closure
Batch 20: PASS.
