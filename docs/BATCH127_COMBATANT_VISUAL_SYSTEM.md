# Batch 127 — Combatant Visual System

Batch 127 separates a combatant's battlefield body from portrait, small portrait,
and icon assets. This is required because different battle grammars need different
representations of the same canonical member.

Supported presentation states:
- idle
- attack
- cast
- hit
- guard
- ko
- revive
- status
- transform

Profiles also carry presentation-only transform metadata:
scale, anchor, offset, and z-order. This allows large bosses, small summons, and
different sprite proportions without introducing gameplay semantics.

Player, enemy, boss, summon, and temporary combatant visuals all use the same
profile/runtime abstraction. A dungeon/portrait-party template may hide the
player battlefield body while keeping portrait/HUD representation visible.

Transform presentation can replace the visual profile for the same member ID,
matching the canonical gameplay rule that form changes preserve combatant identity.

This batch does not resolve animation timing or gameplay state. It only maps
already-known presentation state to visual assets and layout metadata.
