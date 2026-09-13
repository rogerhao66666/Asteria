# Playable Test Content Pack

This patch closes a practical acceptance gap discovered during Codex real-machine
testing: the frozen RPG/runtime architecture was testable headlessly but the
Complex Reference RPG did not include enough rendered content to be played by a
human.

Added direct-use visual test content:

- field map/background
- animated four-direction player sprite sheet
- field Boss sprite
- six party battle sprites
- Astral Tyrant battle sprite
- Mender Wisp battle sprite
- battle background
- 16-frame Strike VFX
- 16-frame Fire VFX
- 16-frame Heal VFX
- 16-frame Meteor VFX
- HUD/action menu rendered by the playable test adapter
- interaction/victory/save feedback

`Runtime Preview` detects `playable_test_manifest.json` and routes this reference
project to a human-operable pygame adapter while keeping game rules in canonical
Project + GameRuntimeSave + GameSessionRuntime.

The assets are original functional test art. They are deliberately not presented
as final production visuals.
