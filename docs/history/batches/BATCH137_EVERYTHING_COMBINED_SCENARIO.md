# Batch 137 — Everything Combined Scenario

Batch 137 executes one deterministic end-to-end validation journey rather than
testing only isolated subsystems.

Sequence:
1. multiclass-capable character + skill-tree allocations;
2. equipment, attachment and equipment-growth rewards;
3. real inventory composition;
4. outside-battle party/formation swap;
5. Battle Arena constructed from the current ResolvedActorBuild;
6. status, interaction/gauge pressure and multi-hit sequence;
7. generic transform/overdrive;
8. player summon plus boss add;
9. canonical post-battle RewardRuntime application.

The specialized status/mode/summon harnesses are intentionally reused rather
than merged into a new validation-only battle engine. Their presence in the
same deterministic project journey proves coexistence while preserving generic
mechanism boundaries.

Post-battle persistent mutation is explicit: RewardRuntime updates the project
ProgressionRuntime, Inventory and caller-owned arbitrary currency mapping.
