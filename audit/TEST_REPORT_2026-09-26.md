# Integrated Test Report

Date: 2026-09-26

Fresh integration checks:

```text
QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
1746 passed, 0 failed

.venv/bin/python -m compileall -q src tests
PASS
```

Reference validation:

- `reference_projects/run_reference_smoke.py` — PASS
- `reference_projects/complex_reference_rpg/run_project_smoke.py` — PASS
- `reference_projects/complex_reference_rpg/run_full_playable_validation.py` — PASS; save/reload exact

The canonical ZIP's historical `1734 passed, 8 skipped` report was not reused as the result; the counts above are from this fresh integration environment.
