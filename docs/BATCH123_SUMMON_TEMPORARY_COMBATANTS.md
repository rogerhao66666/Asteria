# Batch 123 — Summon / Temporary Combatants / Boss Adds

Batch 123 validates both player summons and boss adds through the same canonical
combatant lifecycle.

Validated:
- player-owned summon registration;
- boss-owned add registration;
- summon owner and summon generation provenance;
- summoned combatants execute ordinary `BattleAction`;
- player summon + multiple boss adds coexist;
- temporary combatant removal makes the member non-present/non-actionable;
- duplicate IDs and unknown owners are rejected;
- snapshot/restore preserves summoned topology, owner provenance, and removed state.

No `SummonSystem`, `BossAddSystem`, or side-specific execution path was added.

Presentation consequence:
default battle UI/layout must adapt to temporary combatants dynamically rather
than assuming a fixed player/enemy count.
