# Real Environment Validation

## PASS

- Python compile check.
- Fresh full headless regression suite.
- Canonical reference-world smoke.
- Complex Reference RPG project smoke.
- Full playable validation, including exact save/reload comparison.
- PySide6-dependent tests under `QT_QPA_PLATFORM=offscreen`.

## NOT VERIFIED

- Interactive macOS PySide6 editor behavior and visual inspection.
- Real ModernGL/Pygame GPU shader/material/lighting output.
- Audio-device latency and mixer behavior.
- Hardware performance profiling with production assets.
- RPG Maker MV fixture import and real asset playback; no fixture was available.
- Final production Starter art and vertical-slice art/motion review.
