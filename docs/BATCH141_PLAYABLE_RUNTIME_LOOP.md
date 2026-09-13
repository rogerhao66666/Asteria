# Batch 141 — Character Setup → Field Interaction → Battle Loop

Batch 141 begins the real playable-runtime validation layer after the systems
closure.

The validation loop is intentionally simple and explicit:

`Character Setup → Field → face monster → Interact → Encounter → Battle → Field`

Character setup exercises the same shared project state used by battle:
- level / EXP progression
- main/secondary job assignment
- skill-tree allocation
- active passive APIs
- weapon/accessory equipment
- attachments
- equipment growth
- inventory/composition
- party/formation

The field encounter uses canonical `Scene`, `Entity`, `Transform`,
`Interaction2DComponent`, `InputSnapshot` and `InteractionController`. Core
entity IDs remain UUIDs. Human-readable encounter semantics remain project data
through `event_program_id` and `local_scope_id`.

The battle arena is constructed only when the encounter starts, from the current
`ResolvedActorBuild`; therefore edits made before walking to the monster are
present in the battle actor.

This batch is a headless/playable-runtime integration foundation. Concrete
visual field/battle rendering and input UI remain subsequent batches.
