# Asteria Next Phase Plan

Canonical baseline:
`Asteria_Phase1_4_Canonical_v0.34.0a34.zip`

## Phase 5 — Event VM + Dialogue

Goal: turn the walkable 2D world into an actual RPG world with behavior.

Recommended first batches:

1. Event VM core
   - instruction format
   - program counter
   - wait/resume
   - deterministic state
   - save/load/resume seam

2. Event context/state
   - switches
   - variables
   - local/self state
   - conditions

3. Interaction
   - Interaction component
   - proximity/facing checks
   - action button
   - NPC/chest/door event start

4. Dialogue
   - dialogue command
   - choice command
   - dialogue UI boundary
   - variable/switch consequences

5. World commands
   - transfer scene/map position
   - give/remove item placeholder API
   - play animation/audio/screen effect boundaries

6. Common/parallel/autorun events
   - scheduling
   - cancellation
   - debugger hooks

7. Reference World RPG slice
   - NPC
   - dialogue
   - choice
   - chest
   - door/transfer
   - simple cutscene

Do not hardcode game-specific quest/battle mechanics in Phase 5.
