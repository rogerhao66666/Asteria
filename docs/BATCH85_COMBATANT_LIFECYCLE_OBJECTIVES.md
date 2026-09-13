# Batch 85 — Combatant Lifecycle / Objectives / Escape

## Goal

Add battle-local participation semantics for incapacitation/revival, removal, summon, transformation, explicit battle objectives, and escape without defining HP=0, KO names, formation shapes, or victory rules as engine law.

## Combatant lifecycle

`CombatantLifecycleRuntime` owns a `CombatantLifecycleState` per battle member. A state records:

- open `state_id` project vocabulary
- present / can-act / targetable / defeated flags
- current form ID
- summon owner and generation provenance
- reason string

Convenience operations `incapacitate`, `revive`, and `remove` manipulate those generic flags. A project may call the state `ko`, `petrified`, `captured`, `banished`, or anything else.

The battle still accepts the caller-provided base `is_active` predicate. This preserves projects that define activity from HP, a custom resource, a tag, or another rule. Lifecycle participation and base activity are combined rather than replacing project semantics.

## Revival targeting

Incapacitated combatants can remain targetable while not active. Therefore a revive-like ability can use a normal targeting definition with `active_only=False`. Removed combatants are not targetable even under that mode.

## Summon

`BattleRuntime.summon()` adds a real `PartyMember` at runtime, records summon owner/generation provenance, updates targeting and future turn sources, and optionally places the summon into a formation slot.

The default is deliberately conservative: a summon joins the next round. `join_current_round=True` is an explicit caller policy.

Formation-slot validation occurs before mutation so a rejected summon does not partially alter the battle.

## Transform

`BattleRuntime.transform()` replaces a combatant's runtime `PartyMember` while preserving stable member ID and side. This allows form-specific subject data, abilities, and initiative without changing battle identity. Transformations are reversible and stack-safe.

The engine does not define what a dragon form, stance, vehicle, possession, or boss phase means.

## Objectives

`BattleObjectiveDefinition` composes generic conditions over battle facts:

- side active count
- member active state
- round index
- arbitrary objective flag

Success and failure conditions support ALL/ANY composition. Winner/defeated side IDs remain project-defined strings. Objectives also carry deterministic priority. Failure has explicit winner/defeated outputs (with a convenience inverse default), so multi-side or asymmetric objectives are not forced into a two-side assumption.

When explicit objectives are present they own battle completion. The legacy "one active side remains" rule is retained only for battles with no explicit objective definitions, preserving backward compatibility without overriding authored objectives such as survive, protect, or scripted encounters.

## Escape

`BattleEscapeRule` provides seeded, deterministic escape checks from:

- base chance
- optional project-defined source stat contribution
- optional project-defined opponent stat contribution
- min/max chance clamp

No `speed`, `agility`, or `luck` stat is hardcoded. Successful escape removes that side from battle participation and is represented in `BattleOutcome.escaped_sides`.

## Persistence

`RpgDatabase` schema is now v13 and owns:

- `battle_objectives`
- `escape_rules`

v1-v12 remain readable.

`CombatantLifecycleRuntime` also has a v1 snapshot seam. The final whole-battle snapshot remains intentionally deferred to the later Battle Snapshot batch.

## Developer harness

`demos/phase7b_batch85/run_battle_test_harness.py` extends the real-window sandbox with:

- KO/incapacitate
- revival
- summon
- transform/revert
- objective completion
- escape

It remains a developer interaction harness, not final Battle Presentation or RPG GUI.
