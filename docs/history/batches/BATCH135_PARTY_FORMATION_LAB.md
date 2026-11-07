# Batch 135 — Party / Formation Lab

Batch 135 makes outside-battle party organization operable.

Reference behavior:
- 12-member canonical roster;
- default 4 active + 8 reserve;
- active/reserve swap;
- direct active-set editing;
- logical formation placement and occupied-slot swap;
- roster reordering;
- member add/remove.

Architecture remains generic:
- canonical `Party` owns the roster;
- canonical `BattleFormationRuntime` owns slot placement;
- active/reserve grouping is controller/project policy;
- the default active capacity of 4 is reference-project policy only;
- tests explicitly validate a 6-active configuration without changing engine
  code.

No fixed front/back meaning is assigned to formation slot tags and no permanent
4-character party cap is introduced.
