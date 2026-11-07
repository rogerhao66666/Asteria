# Batch 133 — Equipment / Accessory / Attachment Lab

Batch 133 makes equipment manipulation operable through existing canonical RPG
equipment APIs.

Validated operations:
- equip / unequip;
- multiple equipped weapons in a project-authored slot;
- accessories using the same generic loadout mechanism;
- socket attachment / detachment;
- equipment growth progress;
- growth node auto-unlock;
- immediate ResolvedActorBuild changes for stats, abilities and capabilities.

The lab deliberately does not introduce weapon-type or accessory-type engine
enums. `main_hand` and `accessory` are reference-project slot IDs.

A useful integration finding was confirmed: the reference `tempered` growth node
is authored as auto-unlock. Therefore adding enough `weapon_xp` canonically
unlocks the node during `add_progress()`. The lab/test follows that behavior
rather than adding a second project-specific unlock rule.

All equipment effects continue to flow through EquipmentLoadout, EquippedItem,
AttachmentDefinition, EquipmentGrowthRuntime and ResolvedActorBuild.
