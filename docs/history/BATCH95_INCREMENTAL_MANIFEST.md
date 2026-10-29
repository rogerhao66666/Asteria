# Asteria Batch 95 Incremental Package

Base required: `Asteria_v0.94.0a94_FULL_CANONICAL_REVIEW_DOCS_CONSISTENCY.zip`

Apply this package as an overlay at the `Asteria/` root. It advances the
development version to `0.95.0a95` and contains only Batch 95 additions/active
document updates. It is **not** a standalone cumulative source archive.

Battle Core remains frozen at Batch 93 / v0.93.0a93.

Verification at closure:

- Full pytest: 531 passed, 4 skipped, 0 failed
- Batch 94 + 95 presentation tests: 13 passed
- Batch 95 headless reference demo: PASS
- JSON parsing: 41 files, 0 errors
- Python compileall: PASS
