# Batch 131 Closure Audit

Status: COMPLETE

Acceptance:
- default portrait party bodies hidden while HUD remains visible;
- battlefield members remain visible;
- member names do not influence role;
- opaque IDs supported;
- project may show party bodies without gameplay changes;
- battlefield visibility caps create presentation overflow only;
- duplicate membership rejected;
- HUD role and battlefield role are independent;
- default profile is distinct from side-view grammar;
- party size remains uncapped by default.

Verification:
- Focused: 10 passed.
- Full regression: 814 passed, 4 skipped, 0 failed.
- Compile: PASS.
- JSON: 78 files PASS.
- Frozen gameplay/RPG source diff vs Batch130 baseline: 0.
