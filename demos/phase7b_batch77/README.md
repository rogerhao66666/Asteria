# Batch 77 Progression Allocation Demo

Open `AsteriaPhase7B_ProgressionAllocationDemo.asteria.json` in the normal Asteria Editor and press Play to exercise the same Reference World runtime used by the Mac-verified baseline.

The project also contains the canonical Phase 7B progression graph. The companion save is `reference_data/phase7b_batch77_progression_allocation_demo.save.json`.

Verify the RPG allocation state with:

```bash
PYTHONPATH=src python demos/phase7b_batch77/verify_progression_allocation_demo.py
```

The save demonstrates rankable stat allocation, multiple point currencies, prerequisites, a granted skill, an unlocked passive, an exclusive branch and save/load persistence.
