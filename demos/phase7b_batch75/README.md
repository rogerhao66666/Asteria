# Phase 7B Batch 75 Multi-Class Demo

This demo is intentionally built from ordinary canonical Asteria project/RPG data.
It is not a special engine-only test fixture.

## Playable project

Open `AsteriaPhase7B_MultiClassDemo.asteria.json` in the Asteria Editor and use
Play. It reuses the Mac-verified reference world so movement/collision/camera
remain directly testable while the same project now contains the Batch 75 RPG data.

## Companion RPG save

`reference_data/phase7b_batch75_multiclass_demo.save.json` contains the runtime
progression/save state for Aria's three simultaneous job assignments:
Warrior (primary), Scholar (secondary), and Hunter (special).

## Functional verification

From repository root:

```bash
PYTHONPATH=src python demos/phase7b_batch75/verify_multiclass_demo.py
```

Expected result is PASS and a resolved build showing contributions from all three
jobs plus only their explicitly assigned job progression tracks.

This is the first Phase 7B demo-save convention. Future batches should add a
playable project/save or executable reference scenario whenever the feature can
be meaningfully demonstrated at that stage.
