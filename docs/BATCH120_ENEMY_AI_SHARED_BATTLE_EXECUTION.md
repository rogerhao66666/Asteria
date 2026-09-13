# Batch 120 — Enemy AI + Shared Battle Execution Integration

Batch 120 connects the Batch 119 complex resolved actor to the frozen canonical
BattleRuntime. A reference enemy uses EnemyAIRuntime to choose actions, while
both player and enemy abilities execute through the same AbilityRegistry,
AbilityRuntime and BattleRuntime.

The test deliberately uses opaque side IDs (`side.alpha`, `side.omega`) so no
player/enemy naming convention can become gameplay semantics.

Player abilities originating from progression, equipment and attachments are
executed exactly like any other canonical ability. Enemy AI is a decision layer,
not an EnemySkillSystem.

Presentation requirement carried forward: arbitrary capability must not result
in arbitrary visual clutter. Action/resource visibility will be organized by
presentation policy, context, hierarchy and adaptive layouts in the playable
visual template.
