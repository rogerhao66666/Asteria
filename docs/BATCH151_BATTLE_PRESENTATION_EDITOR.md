# Batch 151 — Complete Battle Presentation Editor

Batch 151 adds a canonical project-owned `BattlePresentationLibrary` and complete
Editor authoring coverage for current battle presentation profiles.

Authorable categories:
- Combatant visuals
- Feedback
- HUD
- UI layout / polish / theme
- Side-view templates
- Portrait-party templates
- Animation timing
- Motion sequences
- Presentation director
- Presentation layering
- Action menu
- Interaction layers
- Action workflows
- Result presentation
- Adaptive party layout

Project schema advances from v6 to v7. Pre-v7 projects remain readable and receive
an empty BattlePresentationLibrary.

## Information architecture

Presentation authoring is split into:
1. Combatants & Layout
2. Animation & Motion
3. VFX / Camera / Audio / Feedback
4. HUD & Interaction
5. Battle Result

Each section exposes category tabs, search/filter, a preview surface, and contextual
details for only the selected profile/child. The editor contract explicitly avoids
showing all categories or all details at the same time.

The presentation library remains presentation-only and does not alter battle
gameplay resolution.
