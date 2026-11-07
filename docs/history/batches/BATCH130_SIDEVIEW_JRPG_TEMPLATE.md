# Batch 130 — Side-view JRPG Template

Batch 130 adds Asteria's first concrete battle presentation grammar.

Default visual preset:
- left-side combatants stand on the left and face right;
- right-side combatants stand on the right and face left;
- both therefore face toward the visual center.

This is strictly presentation policy. The project/controller explicitly assigns
opaque members to left/right visual zones. Asteria never infers player, enemy,
boss, summon, ally, or foe semantics from IDs.

The template emits:
- battlefield zone placement;
- x/y/depth/facing metadata;
- HUD-zone mapping;
- optional presentation overflow.

The default preset has no member cap. A project may author a visibility cap for
a crowded battlefield, but all canonical members remain represented in the
result and overflow is presentation-only.

The template can be reversed or completely replaced without any Battle Core
change. Batch 131 will prove this further with a dungeon/portrait-party grammar
where player battlefield bodies may be hidden while HUD portraits remain.
