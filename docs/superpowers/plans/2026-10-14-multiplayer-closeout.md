# Multiplayer Closeout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the generic multiplayer prototype with a server-authoritative cooperative boss example, reliable client/session behavior, and evidence from automated plus native GUI testing.

**Architecture:** Keep TCP sessions and the adapter API game-agnostic. The boss encounter stays in a separate sample adapter that owns its rules and publishes serializable snapshots/events. The copied Diablo project opts into a small runtime bridge; normal projects without an enabled multiplayer profile remain offline and do not connect.

**Tech Stack:** Python 3.13, socketserver/TCP JSON Lines, pytest, PySide6 editor, macOS Cocoa GUI.

**Spec:** `docs/audits/MULTIPLAYER_DESIGN.md`

## Global Constraints

- The server owns command validation, simulation, boss health, player health, phase changes, and rewards.
- Game adapters remain optional; existing offline project/runtime flows must continue to work.
- Preserve the existing Multiplayer UI style and profile behavior.
- The first playable network target is 2–4 clients on a trusted local/LAN server; public hosting security is not claimed.

## Review Focus

- Two clients must receive the same increasing authoritative revisions after inputs and ticks.
- A client may only control its server-assigned player; invalid or oversized input is rejected without stopping the server.
- Adapter errors, a full lobby, and a dropped connection must leave other clients usable.
- Boss phase/death/reward transitions must happen once even with repeated attack input.
- Editor sample selection and launching must not affect existing project settings or offline play.

### Task 1: Lock down the network session contract

**Files:**
- Create: `tests/test_multiplayer.py`
- Modify only when a failing test proves it necessary: `src/asteria/multiplayer/server.py`, `client.py`, `protocol.py`

- [x] Test two real clients sharing a loopback server, independent player identities, ordered command/state revisions, input acknowledgements, duplicate input rejection, disconnect membership, and server survival after adapter rejection.
- [x] Run the focused tests for the session contract.
- [x] Implement server/client session behavior and validation.
- [x] Run focused networking tests; the full regression is recorded under Task 4.

### Task 2: Add the authoritative cooperative boss adapter

**Files:**
- Create: `src/asteria/multiplayer/boss_demo.py`
- Create or extend: `tests/test_multiplayer.py`
- Modify: `src/asteria/multiplayer/__init__.py`

- [x] Specify behavior in tests for per-player movement/attack ownership, bounded input, boss threat targeting, phase thresholds, player defeat/revive, one-time boss death, and one-time per-player rewards.
- [x] Run the Boss tests against the specified behaviors.
- [x] Implement `build_boss_adapter()` as a `TickableGameNetworkAdapter` plus `InputGameNetworkAdapter`, with a 20 Hz authoritative tick and JSON-safe snapshots/events.
- [x] Run adapter and two-client integration tests.

### Task 3: Expose the boss sample in the editor

**Files:**
- Modify: `src/asteria/editor/multiplayer_workspace.py`
- Modify: relevant editor tests under `tests/`

- [x] Add a styled “Use Boss Co-op Demo” selector and usable default input state without moving or removing existing controls.
- [x] Add GUI-level tests for selector wiring, state preview updates, and existing Counter/Movement/profile behavior.
- [ ] Native Cocoa page interaction remains unverified: the visible editor stayed on Scene and `cua_repl` input returned `noWindowsAvailableWindow`. Qt/offscreen editor tests are not counted as native visual acceptance.

### Task 4: Document author and native test workflows

**Files:**
- Modify: `docs/audits/MULTIPLAYER_DESIGN.md`, `README.md`, `docs/ENGINE_HANDBOOK.md`, and `ASTERIA_PROGRESS.md` only where multiplayer status is already recorded.
- [x] Document sample factory, controls, local two-client test, server-authoritative adapter boundaries, runtime map preview, XP rule, and trusted-LAN boundary.
- [x] Run the full headless-safe suite (2266 passed), then run the editor Multiplayer tests from VS Code's integrated terminal with `QT_QPA_PLATFORM=cocoa` (`platform=cocoa`, 6 passed) and the real server/runtime bridge integration test with pygame dummy display.
- [x] Record the exact regression result, native UI limitation, and remaining runtime/security gaps; do not claim public-Internet readiness.

## User-approved follow-on: persistent reward rules and playable demo

The user approved server-side SQLite persistence, editable project-owned reward templates,
preserving the offline `diablo_demo`, and a separate connected copy. For the boss template,
"touched" means the server accepted positive damage: every such player gets the full configured
XP amount (100 by default), and each configured boss drop is independently assigned to a random
damaging participant. XP is not divided into a shared pool. Custom adapters remain free to
implement different rules.

### Task 5: Apply the boss participation reward semantics

**Files:**
- Modify: `src/asteria/multiplayer/boss_demo.py`
- Modify: `tests/test_multiplayer.py`

- [x] Pin the default to 100 XP per damaging participant, exclude players who did no damage,
  independently assign configured drops only to damaging participants, and assert awards happen
  only once.
- [x] Run the focused test red before implementation, then run the Boss adapter and two-client
  regressions green.

### Task 6: Add durable SQLite state primitives

**Files:**
- Create: `src/asteria/multiplayer/persistence.py`
- Create: `tests/test_multiplayer_persistence.py`
- Modify: `src/asteria/multiplayer/__init__.py`

- [x] Define a versioned SQLite schema for persistent player state, inventory, encounter damage
  contribution, reward grants, world-drop claims, and processed operation IDs.
- [x] Expose transaction-safe APIs that let any server adapter save arbitrary JSON game state,
  record authoritative encounter contributions, grant XP/items once, and atomically claim a
  contested world drop.
- [x] Test reopen persistence, duplicate operation/reward IDs, simultaneous claims, invalid JSON,
  and transaction rollback.

### Task 7: Connect stable guest identity and the server adapter

**Files:**
- Modify: `src/asteria/multiplayer/client.py`, `server.py`, `protocol.py`
- Modify: `src/asteria/editor/multiplayer_workspace.py`
- Modify: `tests/test_multiplayer.py`, `tests/test_editor_multiplayer.py`

- [x] Give each client a persistent, non-authenticating guest ID so SQLite can restore the same
  player's state after reconnect; keep the server-assigned session membership and display name
  separate from authentication (not included in this demo).
- [x] Let a headless server select its SQLite path and expose the store to adapters while preserving
  existing adapters that do not use persistence.
- [x] Persist the multiplayer workspace's client ID locally and expose a regenerate/edit control
  so two local demo clients can use distinct IDs.
- [x] Verify duplicate active guest IDs are rejected safely, disconnected IDs can reconnect, and
  old clients that omit an ID still work as ephemeral guests.

### Task 8: Add project-owned reward templates

**Files:**
- Create: `src/asteria/multiplayer/rules.py`
- Modify: `src/asteria/editor/multiplayer_workspace.py`
- Modify: `tests/test_editor_multiplayer.py`, `tests/test_multiplayer.py`

- [x] Define a versioned project rule file separate from the multiplayer connection profile and
  server SQLite file.
- [x] Provide editable eligibility, XP, boss-drop, and world-pickup policies; the Boss preset grants
  the full configured XP amount independently to each eligible participant and randomly assigns drops.
- [x] Add a Multiplayer rules card using existing Asteria styles and icons; validate values before
  saving and leave custom adapter code unrestricted by built-in presets.

### Task 9: Connect a separate Diablo demo copy and document the boundary

**Files:**
- Create: `reference_projects/diablo_multiplayer_demo/` from the existing offline demo
- Modify: `docs/audits/MULTIPLAYER_DESIGN.md`, `README.md`, `docs/ENGINE_HANDBOOK.md` only where
  multiplayer is already discussed
- Add integration tests under `tests/`

- [x] Keep `reference_projects/diablo_demo` unchanged and make the connected project a separate copy.
- [x] Replace the preliminary Boss overlay with the project-backed authoritative ECS adapter.
- [x] Synchronize original skills, monsters, collision, inventory, equipment, NPCs and saves.
- [x] Four separate Cocoa clients defeat the original Cyclops, receive full per-player XP,
  claim original rolled gear, equip it and restore durable SQLite data. Full regression 2307 passed.
- Native automated widget controls and native game input are distinguished from human playtesting.
  Final acceptance is recorded in `2026-10-15-multiplayer-ecs-closeout.md`.
