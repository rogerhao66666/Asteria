# Batch 135 Closure Audit

Status: COMPLETE

Acceptance:
- 12-member roster with 4 active / 8 reserve default reference policy;
- active members are placed in canonical formation slots;
- active/reserve swap preserves roster and formation slot;
- invalid swap roles are rejected;
- active members can exchange occupied formation slots;
- reserve members cannot bypass active policy and occupy slots directly;
- active set can be rebuilt from explicit project-owned selection;
- active capacity can be 6, proving no engine-fixed 4-person cap;
- controller-policy overflow is rejected without shrinking canonical roster;
- roster order can change independently from active membership;
- reserve and active member removal update canonical party/formation correctly;
- snapshot reports operated party state.

Verification:
- Focused: 13 passed.
- Full regression: 873 passed, 4 skipped, 0 failed.
- Compile: PASS.
- JSON: 83 files PASS.
- Frozen gameplay/RPG source diff vs Batch134 baseline: 0.
