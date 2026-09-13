# Batch 76 Ability / Passive Demo

Open `AsteriaPhase7B_AbilityPassiveDemo.asteria.json` in Asteria Editor and Play it as the normal reference world.

The companion RPG save is `reference_data/phase7b_batch76_ability_passive_demo.save.json`.
It demonstrates:
- a learned `heal` ability that is runtime-owned rather than job-owned;
- equipped passive `battle_instinct` adding Attack, a tag and `counter_stance`;
- Scholar rank 3 evolving `fireball` into `firestorm`;
- provenance for intrinsic/class/learned/passive/evolution grants.

Functional verification:

```bash
PYTHONPATH=src python demos/phase7b_batch76/verify_ability_passive_demo.py
```
