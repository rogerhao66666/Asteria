# Asteria Direct-Use Reference Projects

These are original Asteria validation/reference presets intended for immediate
local testing. They contain no third-party game assets or copyrighted content.

From the repository root:

```bash
PYTHONPATH=src python reference_projects/run_reference_smoke.py
```

Files:
- `sideview_jrpg_reference.json`: job/equipment/progression + side-view JRPG data.
- `portrait_dungeon_reference.json`: portrait-party/dungeon visual grammar.
- `large_party_stress_reference.json`: large party + renderer/UI stress profile.
- `non_octopath_generality_reference.json`: deliberately different RPG shapes.
- `run_reference_smoke.py`: executable smoke validation against the actual
  Asteria validation APIs.

JSON files are reference project data/presets, not proprietary third-party game
files. Concrete editor/import UX will be part of the Editor GUI phase.
