# Phase 7B Batch 79 Equipment Growth Demo

Open `AsteriaPhase7B_EquipmentGrowthDemo.asteria.json` in Asteria to verify that the project remains a normal engine-loadable Reference World project.

The RPG save `reference_data/phase7b_batch79_equipment_growth_demo.save.json` contains a unique Blood Blade equipment instance with its own growth state: XP-based weapon ranks, a growth-unlocked socket, an attached ruby, a manually selected awakening branch, and an equipment evolution target.

Functional verification:

```bash
PYTHONPATH=src python demos/phase7b_batch79/verify_equipment_growth_demo.py
```

This is backend/runtime verification. The RPG interactive GUI remains intentionally deferred until the Phase 7B backend contract is complete.
