# Batch 132 — Character / Job / Progression Lab

Batch 132 turns the outside-battle character-growth validation into an operable
reference-project controller.

The lab can now perform real state changes through existing canonical RPG APIs:
- award EXP and increase a generic progression rank;
- unlock jobs as reference-project policy;
- change primary job;
- add/remove a secondary job;
- resolve multiclass contributions;
- spend Skill Point and Ability Point currencies;
- allocate/refund progression graph nodes;
- equip/unequip passives with capacity checks.

No JobSystem, SkillPointSystem, AbilityPointSystem, or project-specific RPG
engine subsystem was introduced.

Job slots and unlock rules are controller/project policy. Job contributions are
rebuilt using canonical ActorDefinition + ClassAssignment + RpgActorRuntime.
Progression uses the existing generic ProgressionRuntime and
ProgressionAllocationRuntime. Passive loadout uses ActorAbilityState.

Every operation can be followed by `resolve()` to produce the ordinary
ResolvedActorBuild consumed by the rest of Asteria.
