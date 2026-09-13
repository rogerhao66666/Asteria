# Batch 152 — Runtime RPG UI Editor

Batch 152 makes all current runtime RPG screen presentation profiles project-owned
and authorable through the Editor:
- Character
- Equipment / accessories / sockets / growth
- Abilities / passives
- Progression / skill trees
- Party / formation
- Inventory

These are presentation policies, not save-state editors. The Editor defines how
runtime state is organized and displayed; the actual player level, EXP, learned
skills, equipment instances, AP allocations, party membership and inventory remain
runtime/save data.

## Information architecture

The workspace deliberately does not expose every RPG system on one page.

Primary sections:
1. Character
2. Build & Progression
3. Party & Formation
4. Inventory

Build & Progression uses secondary tabs for Equipment, Abilities/Passives and
Progression. Each profile has a preview plus contextual detail. Preview density can
be switched among screen, compact, wide and overflow scenarios so large rosters,
many skills and large inventories can be tested without imposing gameplay caps.
