# Asteria Phase 7B Batch 78 — Flexible Equipment / Capability Rules

Version: `v0.78.0a78`

## Goal

Make equipment layout and equipment permission fully project-defined rather than hardcoding RPG conventions such as one weapon, one armor piece, two accessories, or fixed weapon proficiency enums.

## Delivered

- Arbitrary equipment slots and capacities remain canonical project/runtime data.
- `capacity=None` means unlimited; there is no engine-wide collection cap.
- Multiple weapon, armor, accessory, or custom-slot items may be equipped simultaneously.
- `EquipmentDefinition` schema v2 adds generic permission rules:
  - `required_capabilities`: all required.
  - `any_capabilities`: at least one required.
  - `forbidden_capabilities`: none may be present.
- `EquipmentEligibility` provides explainable allow/reject results.
- `EquipmentLoadout.check_equip(...)` supports non-mutating preview/validation.
- `RpgActorRuntime.effective_capabilities(...)`, `equipment_eligibility(...)`, and `equip_item(...)` compose actor/class/progression/passive/current-equipment contributions automatically.
- Capabilities intentionally use the canonical tag vocabulary rather than a weapon enum. A project may define `capability.weapon.sword`, `license.mech`, `species.dragon`, `story.king`, or any other permission concept.
- Existing class tags, passive tags, progression graph capability grants, actor tags, and equipped-item tags can grant equipment permissions.
- Equipment can therefore unlock later equipment without a bespoke engine subsystem.
- Requirement rejection emits `rpg.equipment.equip_rejected`, preserving the universal lifecycle/Event VM seam.
- Equipment schema v1 remains readable.
- Modifier IDs are scoped by stable equipment instance identity, so multiple copies of the same equipment definition stack correctly instead of colliding.
- Loadout restoration is structural and does not require actor context to exist during deserialization; current eligibility can be audited after actor resolution.

## Important design rule

Asteria does **not** define concepts such as SwordUser, HeavyArmorUser, TwoHanded, or AccessorySlot as engine enums. Those are project rules expressed through slots, tags/capabilities, conditions, and later resolved-build validation.

## Demonstration

`AsteriaPhase7B_EquipmentCapabilityDemo.asteria.json`

Companion save:

`reference_data/phase7b_batch78_equipment_capability_demo.save.json`

The demo actor Aria has Warrior, Scholar, and Hunter class layers and therefore receives sword, staff, and bow capabilities. Three different weapon types can be equipped simultaneously. Titan Blade initially fails because the actor lacks `capability.weapon.greatblade`; equipping a generic Mastery Badge contributes that capability and makes Titan Blade legal.

The saved demo layout uses:

- weapon capacity: 8
- armor capacity: 12
- accessory capacity: unlimited
- four simultaneous weapons
- two armor instances
- four accessories

Stress tests additionally equip 128 accessories to prove there is no arbitrary engine cap.

Verification:

```bash
PYTHONPATH=src python demos/phase7b_batch78/verify_equipment_capability_demo.py
```
