# Phase 7B Batch 81 — Battle Resources / Gauges Demo

Loads `AsteriaPhase7B_BattleResourcesDemo.asteria.json`, whose canonical RPG database owns five example resource policies: bound `mp`, plus combat-scoped `rage`, `boost`, `stagger`, and `combo` gauges.

```bash
PYTHONPATH=src python demos/phase7b_batch81/verify_battle_resources_demo.py
```

The demo validates start/end policy, BattleRuntime lifecycle-driven gain/decay, custom string triggers, overflow-ready combat gauges, and snapshot data. This remains backend verification; the integrated playable battle GUI is intentionally deferred until Battle Core + presentation are complete.
