# Batch 131 — Dungeon / Portrait Party Template

Batch 131 adds a second battle presentation grammar using the same canonical
gameplay.

Default behavior:
- party members are represented through portrait/HUD;
- their battlefield bodies are hidden;
- opponents/bosses/adds remain visible in a battlefield zone.

The project/controller explicitly supplies which members belong to the
portrait-party role and which belong to the battlefield role. No player/enemy
semantics are inferred from IDs.

Battlefield visibility and HUD visibility are independent. A project may choose
to show party bodies again without changing gameplay. Battlefield visibility
caps produce presentation overflow only and do not remove canonical members.

This proves that Asteria's battle systems do not depend on side-view player
bodies. The same gameplay can use substantially different presentation grammar.
