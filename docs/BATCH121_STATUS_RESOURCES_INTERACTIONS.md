# Batch 121 — Status / Resources / Interaction Integration

Batch 121 expands the playable validation harness with real battle-state and
interaction behavior.

Validated:
- duration-bearing states with source provenance;
- turn-triggered duration decrement and expiry;
- periodic effects;
- buff modifiers;
- arbitrary battle-only gauges;
- tag-driven weakness-like interaction;
- outcome-tag-driven gauge pressure;
- threshold-triggered stagger-like state;
- multi-hit action sequence;
- healing through ordinary resource delta;
- revive through canonical combatant lifecycle.

The reference names (`scorch`, `focus_up`, `resolve_guard`, etc.) are project
content only. No PoisonSystem, BuffSystem, WeaknessSystem or BreakSystem was
added.

Presentation follow-up:
status views must expose remaining duration/stacks/source cleanly, while dense
status/resource configurations must remain grouped and readable rather than
being dumped onto the HUD.
