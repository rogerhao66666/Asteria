# Batch 136 — Asteria RPG Validation Project Assembly

Batch 136 turns the previously isolated validation labs into one coherent
reference-project flow.

The project now composes:
Character / Job / Progression
→ Equipment / Attachment / Growth
→ Inventory / Composition
→ Party / Formation
→ Battle Arena

The Character, Equipment, and Inventory labs share one `ReferenceActorScenario`.
This prevents the common integration bug where each screen mutates a different
copy of the actor.

When the project enters Battle Arena, it builds the combatant from the current
`ResolvedActorBuild`. Therefore job changes, progression unlocks, equipment,
attachments, and equipment growth performed before battle are reflected in the
battle member's stats and available authored battle abilities.

Battle remains isolated from persistent outside-battle state. Running a battle
does not silently mutate the project build, inventory, party organization, or
equipment state. Reward/application integration is intentionally left for the
next combined scenario batch rather than hidden inside battle construction.
