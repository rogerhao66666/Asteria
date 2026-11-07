# Batch 154 — Save / Runtime State / Run Integration

Batch 154 establishes the canonical boundary between Project definitions and
mutable game state.

`GameRuntimeSave` stores:
- project identity
- current scene
- player entity
- player facing
- player position
- `RpgRuntimeState`
- serializable `EventContext`

The Project remains the source of definitions. Saves contain runtime state only.

Editor `RuntimeStateIntegrationController` now supports:
- New Save
- Load Save
- Save / Save As
- Run with a loaded save
- Capture runtime save changes back from a play session

Play mode still clones the Project before Run. Runtime mutation cannot mutate
Editor project definitions.

The runtime launcher and preview accept a save snapshot. The preview selects the
saved scene and restores the saved player transform before entering runtime.

This is the boundary required for the next phase:
`Load Project + Load Save -> Run -> modify runtime state -> field -> encounter ->
battle -> rewards -> save -> close/reload`.
