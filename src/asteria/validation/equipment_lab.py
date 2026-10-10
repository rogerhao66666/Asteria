from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import ModifierOperation, StatModifier
from asteria.rpg import (
    AttachmentDefinition,
    EquipmentDefinition,
    EquipmentGrowthRuntime,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
)

from .playable_rpg import ReferenceActorScenario, build_reference_actor_scenario


@dataclass(frozen=True, slots=True)
class EquipmentLabSnapshot:
    equipped: tuple[tuple[str, tuple[str, ...]], ...]
    attachments: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    growth_ranks: tuple[tuple[str, tuple[tuple[str, int], ...]], ...]
    abilities: tuple[str, ...]
    capabilities: tuple[str, ...]


class EquipmentLab:
    """Operable reference-project controller over canonical equipment APIs."""

    def __init__(self, scenario: ReferenceActorScenario | None = None):
        self.scenario = scenario or build_reference_actor_scenario()

        # Reuse canonical reference definitions, but start with a clean loadout.
        existing = {x.equipment.equipment_id: x for x in self.scenario.loadout.equipped()}
        blade = existing["ember_blade"].equipment
        charm = existing["echo_charm"].equipment
        growth_definition = existing["ember_blade"].growth.definition
        rune = existing["ember_blade"].attachments["rune"]

        self.equipment_catalog = {
            blade.equipment_id: blade,
            charm.equipment_id: charm,
            "frost_blade": EquipmentDefinition(
                "frost_blade",
                "Frost Blade",
                slot="main_hand",
                tags=("weapon", "blade"),
                modifiers=(StatModifier("frost_blade.power", "power", ModifierOperation.ADD, 4),),
                granted_abilities=("ice_arc",),
            ),
            "focus_charm": EquipmentDefinition(
                "focus_charm",
                "Focus Charm",
                slot="accessory",
                tags=("accessory",),
                modifiers=(StatModifier("focus_charm.focus", "focus", ModifierOperation.ADD, 2),),
                granted_abilities=("focus_step",),
            ),
        }
        self.attachment_catalog = {
            rune.attachment_id: rune,
            "echo_rune": AttachmentDefinition(
                "echo_rune",
                "Echo Rune",
                tags=("attachment.weapon", "rune"),
                granted_abilities=("echo_edge",),
            ),
        }
        self.growth_definitions = {
            growth_definition.growth_id: growth_definition,
        }
        self.instances = {
            "ember_blade:lab": EquippedItem(
                blade,
                instance_id="ember_blade:lab",
                growth=EquipmentGrowthRuntime(growth_definition),
            ),
            "frost_blade:lab": EquippedItem(
                self.equipment_catalog["frost_blade"],
                instance_id="frost_blade:lab",
            ),
            "echo_charm:lab": EquippedItem(
                charm,
                instance_id="echo_charm:lab",
            ),
            "focus_charm:lab": EquippedItem(
                self.equipment_catalog["focus_charm"],
                instance_id="focus_charm:lab",
            ),
        }
        self.scenario.loadout = EquipmentLoadout(
            (
                EquipmentSlotDefinition("main_hand", capacity=2),
                EquipmentSlotDefinition("accessory", capacity=2),
            )
        )

    def resolve(self):
        return self.scenario.resolve()

    def equip(self, slot_id, instance_id):
        item = self.instances[str(instance_id)]
        capabilities = self.scenario.actor.effective_capabilities(
            allocations=self.scenario.allocations,
            loadout=self.scenario.loadout,
            passives=self.scenario.passives,
        )
        return self.scenario.loadout.equip(str(slot_id), item, capabilities=capabilities, validate_requirements=True)

    def unequip(self, slot_id, index=0):
        return self.scenario.loadout.unequip(str(slot_id), index)

    def attach(self, instance_id, socket_id, attachment_id):
        item = self.instances[str(instance_id)]
        attachment = self.attachment_catalog[str(attachment_id)]
        item.attach(str(socket_id), attachment)
        return attachment

    def detach(self, instance_id, socket_id):
        return self.instances[str(instance_id)].detach(str(socket_id))

    def add_growth_progress(self, instance_id, counter_id, amount):
        item = self.instances[str(instance_id)]
        if item.growth is None:
            item.ensure_growth(self.growth_definitions)
        return item.growth.add_progress(counter_id, amount)

    def unlock_growth(self, instance_id, node_id):
        item = self.instances[str(instance_id)]
        if item.growth is None:
            item.ensure_growth(self.growth_definitions)
        return item.growth.unlock(node_id)

    def snapshot(self):
        equipped = []
        for slot_id in sorted(self.scenario.loadout._slots):
            equipped.append(
                (
                    slot_id,
                    tuple(x.instance_id for x in self.scenario.loadout.equipped(slot_id)),
                )
            )
        attachments = []
        growth = []
        for instance_id, item in sorted(self.instances.items()):
            attachments.append(
                (
                    instance_id,
                    tuple(sorted((sid, a.attachment_id) for sid, a in item.attachments.items())),
                )
            )
            if item.growth is not None:
                growth.append(
                    (
                        instance_id,
                        tuple(sorted((k, int(v)) for k, v in item.growth.ranks.items() if v)),
                    )
                )
        build = self.resolve()
        return EquipmentLabSnapshot(
            tuple(equipped),
            tuple(attachments),
            tuple(growth),
            tuple(build.abilities),
            tuple(build.capabilities),
        )
