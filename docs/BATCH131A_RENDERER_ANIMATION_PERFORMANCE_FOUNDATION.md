# Batch 131A — Renderer & Animation Performance Foundation

This batch adds concrete backend-neutral performance mechanisms for the battle
presentation layer.

Implemented:
- draw batching plans grouped by atlas/material/layer;
- visibility culling before batch submission;
- bounded reusable pools for transient VFX/popups;
- presentation-asset preload readiness tracking;
- target-FPS frame-time / dropped-frame metrics.

The representative stress case models:
- 12 party members;
- 1 boss;
- 4 adds;
- 1 summon;
- 300 transient VFX draws.

This layer does not claim GPU performance by itself. It prepares renderer
adapters so a concrete backend can avoid one-draw-per-object submission,
unbounded transient allocation, offscreen work, and first-use asset stalls.

Combined with Batch 129A:
- choreography timing is event-driven rather than virtual-substep scanning;
- gameplay and presentation clocks remain independent;
- animation roles are project-defined;
- sprite-sheet resolution is preloaded/cached.

Real 60 FPS acceptance remains gated on concrete renderer + representative
assets, but the engine now exposes the correct optimization and measurement
boundaries.
