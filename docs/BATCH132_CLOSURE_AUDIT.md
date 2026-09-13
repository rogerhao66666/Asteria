# Batch 132 Closure Audit

Status: COMPLETE

Acceptance:
- clean operable skill-tree allocation state;
- EXP advances canonical generic rank;
- locked job cannot be selected until project policy unlocks it;
- primary job switch changes resolved contributions;
- primary + secondary multiclass contributions combine;
- Skill Point allocation grants ability/capability;
- Ability Point allocation changes stat/resource contribution;
- refunds reverse progression contribution and restore currency;
- passive equip/unequip is operable;
- passive capacity is enforced by canonical ActorAbilityState;
- job change preserves learned ability/passive state;
- snapshot reports actual operated lab state.

Verification:
- Focused: 12 passed.
- Full regression: 835 passed, 4 skipped, 0 failed.
- Compile: PASS.
- JSON: 80 files PASS.
- Frozen gameplay/RPG source diff vs Batch131A baseline: 0.
