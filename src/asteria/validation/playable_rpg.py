from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import ModifierOperation, StatModifier
from asteria.presentation import (
    BattleActionEntry,
    BattleActionWorkflowDefinition,
    BattleWorkflowOption,
    BattleWorkflowStep,
)
from asteria.rpg import (
    ActorDefinition,
    AttachmentDefinition,
    ClassAssignment,
    ClassDefinition,
    EquipmentDefinition,
    EquipmentGrowthDefinition,
    EquipmentGrowthNodeDefinition,
    EquipmentGrowthReward,
    EquipmentGrowthRuntime,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    Inventory,
    ItemDefinition,
    PassiveDefinition,
    ProgressionAllocationRuntime,
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeReward,
    RpgActorRuntime,
    SocketDefinition,
    resolve_actor_build,
)


@dataclass(slots=True)
class ReferenceActorScenario:
    actor: RpgActorRuntime
    allocations: ProgressionAllocationRuntime
    loadout: EquipmentLoadout
    passives: dict[str, PassiveDefinition]
    inventory: Inventory
    item_catalog: tuple[ItemDefinition, ...]
    alchemy_workflow: BattleActionWorkflowDefinition

    def resolve(self):
        return resolve_actor_build(
            self.actor,
            allocations=self.allocations,
            loadout=self.loadout,
            passives=self.passives,
        )


@dataclass(frozen=True, slots=True)
class PlayableRpgValidationReport:
    actor_id: str
    class_assignment_ids: tuple[str, ...]
    equipment_instance_ids: tuple[str, ...]
    abilities: tuple[str, ...]
    ability_sources: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]
    resources: tuple[str, ...]
    capabilities: tuple[str, ...]
    inventory_counts: tuple[tuple[str, int], ...]
    action_entries: tuple[BattleActionEntry, ...]
    workflows: tuple[str, ...]

    def source_kinds(self, ability_id):
        table = dict(self.ability_sources)
        return tuple(x[0] for x in table[str(ability_id)])


def build_reference_actor_scenario():
    """Build one deliberately dense reference actor without project-specific engine code.

    The content names are reference-project data. The mechanisms are ordinary
    Asteria class, progression, equipment, attachment, passive and workflow APIs.
    """
    classes = {
        "vanguard": ClassDefinition(
            "vanguard",
            stat_bonuses={"power": 8, "guard": 5},
            resource_bonuses={"momentum": 2},
            granted_tags=("capability.weapon.blade",),
            granted_abilities=("power_strike", "guard_break"),
        ),
        "alchemist": ClassDefinition(
            "alchemist",
            stat_bonuses={"focus": 7},
            resource_bonuses={"reagent_charge": 3},
            granted_tags=("capability.alchemy",),
            granted_abilities=("quick_mix",),
        ),
    }
    actor = RpgActorRuntime(
        ActorDefinition(
            "validation_hero",
            "Validation Hero",
            class_assignments=(
                ClassAssignment("vanguard", assignment_id="job:vanguard", priority=0),
                ClassAssignment("alchemist", assignment_id="job:alchemist", priority=1),
            ),
            base_stats={"power": 20, "focus": 12, "speed": 10},
            base_resources={
                "vitality": 250,
                "technique": 40,
                "momentum": 3,
                "reagent_charge": 2,
            },
            tags=("actor.reference",),
            abilities=("basic_attack",),
        ),
        class_definitions=classes,
    )
    actor.ability_state.learn("field_mix")

    passive = PassiveDefinition(
        "counter_formula",
        "Counter Formula",
        tags=("passive.reference",),
        modifiers=(StatModifier("passive.focus", "focus", ModifierOperation.ADD, 3),),
        granted_abilities=("reactive_tonic",),
    )
    actor.ability_state.equip_passive(passive.passive_id)

    graph = ProgressionGraphDefinition(
        "hero_mastery",
        nodes=(
            ProgressionNodeDefinition(
                "double_strike_node",
                "Double Strike",
                rank_costs={"skill_point": 2},
                rewards=ProgressionNodeReward(
                    granted_abilities=("double_strike",),
                    granted_capabilities=("capability.combo",),
                ),
            ),
            ProgressionNodeDefinition(
                "deep_reserve",
                "Deep Reserve",
                rank_costs={"ability_point": 1},
                rewards=ProgressionNodeReward(
                    resource_bonuses={"technique": 10},
                    stat_bonuses={"focus": 2},
                ),
            ),
        ),
    )
    allocations = ProgressionAllocationRuntime(
        (graph,),
        balances={"skill_point": 4, "ability_point": 2},
    )
    allocations.allocate("hero_mastery", "double_strike_node")
    allocations.allocate("hero_mastery", "deep_reserve")

    growth_definition = EquipmentGrowthDefinition(
        "ember_blade_growth",
        nodes=(
            EquipmentGrowthNodeDefinition(
                "tempered",
                rank_requirements={"weapon_xp": 10},
                rewards=EquipmentGrowthReward(
                    modifiers=(
                        StatModifier(
                            "ember_blade.tempered",
                            "power",
                            ModifierOperation.ADD,
                            4,
                        ),
                    ),
                    granted_abilities=("tempered_arc",),
                    granted_capabilities=("capability.weapon.tempered",),
                ),
            ),
        ),
    )
    growth = EquipmentGrowthRuntime(growth_definition)
    growth.add_progress("weapon_xp", 10)

    blade = EquipmentDefinition(
        "ember_blade",
        "Ember Blade",
        slot="main_hand",
        tags=("weapon", "blade"),
        modifiers=(StatModifier("ember_blade.power", "power", ModifierOperation.ADD, 6),),
        granted_abilities=("flame_slash",),
        sockets=(SocketDefinition("rune", accepted_tags=("attachment.weapon",)),),
        growth_id="ember_blade_growth",
    )
    venom_rune = AttachmentDefinition(
        "venom_rune",
        "Venom Rune",
        tags=("attachment.weapon", "rune"),
        modifiers=(StatModifier("venom_rune.focus", "focus", ModifierOperation.ADD, 1),),
        granted_abilities=("venom_edge",),
    )
    blade_instance = EquippedItem(
        blade,
        instance_id="ember_blade:01",
        growth=growth,
    )
    blade_instance.attach("rune", venom_rune)

    charm = EquipmentDefinition(
        "echo_charm",
        "Echo Charm",
        slot="accessory",
        tags=("accessory",),
        granted_abilities=("echo_step",),
    )
    charm_instance = EquippedItem(charm, instance_id="echo_charm:01")

    loadout = EquipmentLoadout(
        (
            EquipmentSlotDefinition("main_hand", capacity=1),
            EquipmentSlotDefinition("accessory", capacity=2),
        )
    )
    loadout.equip("main_hand", blade_instance, validate_requirements=False)
    loadout.equip("accessory", charm_instance, validate_requirements=False)

    inventory = Inventory()
    inventory.add("red_herb", 4)
    inventory.add("spark_dust", 2)
    inventory.add("glass_vial", 3)
    item_catalog = (
        ItemDefinition("red_herb", "Red Herb", tags=("ingredient", "restorative")),
        ItemDefinition("spark_dust", "Spark Dust", tags=("ingredient", "volatile")),
        ItemDefinition("glass_vial", "Glass Vial", tags=("catalyst",)),
    )

    alchemy_workflow = BattleActionWorkflowDefinition(
        "field_concoction",
        "Field Concoction",
        (
            BattleWorkflowStep("base", "Choose Base"),
            BattleWorkflowStep("reagent", "Choose Reagent"),
            BattleWorkflowStep("catalyst", "Choose Catalyst", optional=True, minimum_selections=0),
        ),
        confirmation_label="Concoct",
    )

    return ReferenceActorScenario(
        actor=actor,
        allocations=allocations,
        loadout=loadout,
        passives={passive.passive_id: passive},
        inventory=inventory,
        item_catalog=item_catalog,
        alchemy_workflow=alchemy_workflow,
    )


class PlayableRpgValidationHarness:
    """Cross-system validation seam used by the Asteria reference project.

    It intentionally consumes public canonical APIs only. It does not add a new
    gameplay rules engine and it never mutates frozen Battle Core.
    """

    def __init__(self, scenario=None):
        self.scenario = scenario or build_reference_actor_scenario()

    def action_entries(self, build=None):
        build = build or self.scenario.resolve()
        entries = []
        for order, ability_id in enumerate(build.abilities):
            sources = build.ability_sources(ability_id)
            source_text = ", ".join(f"{source.source_kind}:{source.source_id}" for source in sources)
            entries.append(
                BattleActionEntry(
                    ability_id,
                    ability_id.replace("_", " ").title(),
                    category="resolved_abilities",
                    kind="ability",
                    detail=source_text,
                    order=order,
                    tags=tuple(dict.fromkeys(source.source_kind for source in sources)),
                )
            )
        entries.append(
            BattleActionEntry(
                self.scenario.alchemy_workflow.workflow_id,
                self.scenario.alchemy_workflow.label,
                category="composition",
                kind="workflow",
                detail="Multi-step controller-owned composition workflow",
                order=len(entries),
                tags=("workflow",),
            )
        )
        return tuple(entries)

    def alchemy_options(self):
        counts = self.scenario.inventory.to_data()["counts"]
        result = []
        for item in self.scenario.item_catalog:
            result.append(
                BattleWorkflowOption(
                    item.item_id,
                    item.display_name,
                    enabled=counts.get(item.item_id, 0) > 0,
                    detail=f"x{counts.get(item.item_id, 0)}",
                    tags=item.tags,
                    payload={"item_id": item.item_id},
                )
            )
        return tuple(result)

    def report(self):
        build = self.scenario.resolve()
        ability_sources = []
        for ability_id in build.abilities:
            ability_sources.append(
                (
                    ability_id,
                    tuple((source.source_kind, source.source_id) for source in build.ability_sources(ability_id)),
                )
            )
        resources = tuple(sorted(build.resources.to_data()["values"]))
        inventory = self.scenario.inventory.to_data()["counts"]
        return PlayableRpgValidationReport(
            actor_id=build.actor_id,
            class_assignment_ids=build.class_assignment_ids,
            equipment_instance_ids=build.equipment_instance_ids,
            abilities=build.abilities,
            ability_sources=tuple(ability_sources),
            resources=resources,
            capabilities=build.capabilities,
            inventory_counts=tuple(sorted(inventory.items())),
            action_entries=self.action_entries(build),
            workflows=(self.scenario.alchemy_workflow.workflow_id,),
        )
