# Multiplayer ECS closeout

The user requests a loadable, separately copied ARPG project with the original gameplay
running authoritatively on the server. All supplied multiplayer rules remain editable examples.
Preserve the offline project's data/assets, original editor appearance, and non-network behavior.

## Acceptance

- [x] One server simulates each authored scene once, including original AI, physics/collision,
  timelines, hitboxes, projectiles, statuses, skills and monster deaths.
- [x] Four independent player entities receive independent movement/action inputs and RPG saves.
- [x] Client ECS visuals receive server snapshots; clients do not independently resolve combat.
- [x] Original inventory/equipment/progression UI routes commands to the server and displays
  the accepted authoritative state.
- [x] Original NPC interactions, scene transitions, vendors and crafting remain playable online.
- [x] Damage/kill/loot/XP eligibility ordering is owned by the server. Boss default: every positive
  damage contributor gets full configured XP; each configured drop goes to a random contributor.
- [x] SQLite preserves player RPG saves, equipment, XP and claimed loot across disconnect/restart.
- [x] Native four-process integration exercises original ECS monsters, gameplay commands,
  rendering, pickup/reward ownership and persistence, followed by full regression checks.
- [x] Demo profile selects the project-backed adapter; load instructions and customization examples
  describe the final implementation. No completion claim while required work remains.

## Verified evidence

- Full suite: 2307 passed in 154.86s.
- Four Cocoa processes: `/private/tmp/asteria-project-native-to1iiyj_/result.json`.
- Reviewed fixes: interaction facing, side-view mode, entry-position respawn; server adapter 24 tests.
- Runtime bridge 16 tests; original offline project/assets preserved by copy-integrity tests.
- Persistence covers character state and completed claims; session world is intentionally fresh
  after server restart. Deployment authentication and WAN quality are outside this LAN template.

Native editor acceptance: `/private/tmp/asteria-gui-network-762t5nko/result.json`
reports Cocoa Host/Join/Ping/Leave/Stop, profile save and button centering passed.
Controls were invoked by the test harness inside a visible native editor.

Final isolated regression after formatting: 2307 passed in 154.86s. A simultaneous native-game
run caused the existing strict frame-limiter timing test to exceed its wall-clock budget;
the isolated complete rerun passed without weakening the assertion or changing its implementation.
Ruff check, format check (29 files), git diff whitespace check and offline-demo unchanged check passed.
