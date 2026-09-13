# Batch 127 Closure Audit

Status: COMPLETE

Acceptance:
- battlefield/portrait/small portrait/icon are separate assets;
- common battle visual states are represented;
- unknown state safely falls back to idle;
- large boss scale/anchor/offset/z-order supported;
- battlefield body can be hidden while HUD remains visible;
- visibility changes do not alter gameplay identity/state;
- transform can replace visual profile for same member;
- player/enemy/boss/summon share one abstraction;
- duplicate visual registration rejected;
- idle fallback is required;
- snapshot records member visual state/profile/visibility.

Verification:
- Focused: 11 passed.
- Full regression: 769 passed, 4 skipped, 0 failed.
- Compile: PASS.
- JSON: 73 files PASS.
- Frozen gameplay/RPG source diff vs Batch126 baseline: 0.
