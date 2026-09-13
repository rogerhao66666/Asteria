from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import ModifierOperation, StatModifier
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
    PassiveDefinition,
    ProgressionAllocationRuntime,
    ProgressionGraphDefinition,
    ProgressionNodeDefinition,
    ProgressionNodeReward,
    RpgActorRuntime,
    SocketDefinition,
    resolve_actor_build,
)


@dataclass(frozen=True, slots=True)
class PreBattleCharacterSnapshot:
    actor_id: str
    level: int
    main_job: str
    secondary_job: str
    stats: tuple[tuple[str, float], ...]
    resources: tuple[str, ...]
    abilities: tuple[str, ...]
    active_passives: tuple[str, ...]
    equipment_instance_ids: tuple[str, ...]
    attachment_ids: tuple[str, ...]
    capability_count: int


@dataclass(frozen=True, slots=True)
class PreBattleStressReport:
    characters: tuple[PreBattleCharacterSnapshot, ...]
    active_ids: tuple[str, ...]
    reserve_ids: tuple[str, ...]
    inventory_unique_items: int
    inventory_total_items: int
    recipe_count: int
    job_ids: tuple[str, ...]
    max_ability_count: int
    min_ability_count: int


class ComplexPreBattleStressHarness:
    """Dense pre-battle RPG state using only canonical RPG mechanisms."""

    JOB_IDS=(
        "vanguard","scholar","alchemist","warden",
        "ranger","oracle","duelist","mystic",
    )

    def __init__(self, roster_size=12, active_count=4):
        self.roster_size=int(roster_size)
        self.active_count=int(active_count)
        if self.roster_size < 8:
            raise ValueError("stress roster_size must be >= 8")
        if not 1 <= self.active_count <= self.roster_size:
            raise ValueError("invalid active_count")
        self.classes=self._classes()
        self.passives=self._passives()
        self.characters=[]
        self.inventory=self._inventory()
        self.recipe_count=16
        self._build_roster()

    def _classes(self):
        result={}
        for i,jid in enumerate(self.JOB_IDS):
            result[jid]=ClassDefinition(
                jid,
                stat_bonuses={
                    "power": 2+(i%4)*2,
                    "guard": 1+(i%3),
                    "focus": 1+((i+2)%4),
                    "speed": 1+((i+1)%5),
                },
                resource_bonuses={f"{jid}_charge": 2+(i%3)},
                granted_tags=(f"capability.job.{jid}",f"weapon_family.{i%4}"),
                granted_abilities=(f"{jid}_skill_1",f"{jid}_skill_2",f"{jid}_skill_3"),
            )
        return result

    def _passives(self):
        result={}
        for i in range(16):
            pid=f"passive_{i:02d}"
            result[pid]=PassiveDefinition(
                pid,
                f"Passive {i:02d}",
                tags=("passive.stress",f"passive.group.{i%4}"),
                modifiers=(
                    StatModifier(pid+".stat","focus" if i%2 else "power",
                                 ModifierOperation.ADD,1+(i%3)),
                ),
                granted_abilities=(f"passive_ability_{i:02d}",),
            )
        return result

    def _inventory(self):
        inv=Inventory()
        # 64 unique items, deliberately varied counts.
        for i in range(64):
            inv.add(f"item_{i:03d}",1+(i%9))
        return inv

    def _graph(self, actor_index):
        nodes=[]
        for i in range(6):
            nodes.append(ProgressionNodeDefinition(
                f"node_{i}",
                f"Node {i}",
                rank_costs={"skill_point":1+(i%2)},
                rewards=ProgressionNodeReward(
                    stat_bonuses={"power" if i%2==0 else "focus":1+i},
                    resource_bonuses={f"personal_gauge_{actor_index%3}":1+(i%2)},
                    granted_abilities=(f"actor_{actor_index:02d}_tree_skill_{i}",),
                    granted_capabilities=(f"capability.tree.{i}",),
                ),
            ))
        return ProgressionGraphDefinition(f"graph_actor_{actor_index:02d}",nodes=tuple(nodes))

    def _equipment(self, actor_index):
        growth_def=EquipmentGrowthDefinition(
            f"weapon_growth_{actor_index:02d}",
            nodes=(
                EquipmentGrowthNodeDefinition(
                    "tempered",
                    rank_requirements={"weapon_xp":10},
                    rewards=EquipmentGrowthReward(
                        modifiers=(StatModifier(
                            f"weapon_{actor_index:02d}.growth","power",
                            ModifierOperation.ADD,3,
                        ),),
                        granted_abilities=(f"weapon_growth_skill_{actor_index:02d}",),
                        granted_capabilities=("capability.weapon.grown",),
                    ),
                ),
            ),
        )
        growth=EquipmentGrowthRuntime(growth_def)
        growth.add_progress("weapon_xp",10)

        weapon=EquipmentDefinition(
            f"weapon_{actor_index:02d}",
            f"Weapon {actor_index:02d}",
            slot="main_hand",
            tags=("weapon",f"weapon.family.{actor_index%4}"),
            modifiers=(StatModifier(
                f"weapon_{actor_index:02d}.power","power",
                ModifierOperation.ADD,4+(actor_index%5),
            ),),
            granted_abilities=(f"weapon_skill_{actor_index:02d}",),
            sockets=(SocketDefinition("rune",accepted_tags=("attachment.weapon",)),),
            growth_id=growth_def.growth_id,
        )
        rune=AttachmentDefinition(
            f"rune_{actor_index:02d}",
            f"Rune {actor_index:02d}",
            tags=("attachment.weapon","rune"),
            modifiers=(StatModifier(
                f"rune_{actor_index:02d}.focus","focus",
                ModifierOperation.ADD,1+(actor_index%2),
            ),),
            granted_abilities=(f"rune_skill_{actor_index:02d}",),
        )
        weapon_item=EquippedItem(
            weapon,instance_id=f"weapon_{actor_index:02d}:instance",growth=growth
        )
        weapon_item.attach("rune",rune)

        accessories=[]
        for slot_index in range(2):
            eq=EquipmentDefinition(
                f"accessory_{actor_index:02d}_{slot_index}",
                f"Accessory {actor_index:02d}-{slot_index}",
                slot="accessory",
                tags=("accessory",f"accessory.group.{slot_index}"),
                modifiers=(StatModifier(
                    f"accessory_{actor_index:02d}_{slot_index}.stat",
                    "guard" if slot_index==0 else "speed",
                    ModifierOperation.ADD,2+slot_index,
                ),),
                granted_abilities=(f"accessory_skill_{actor_index:02d}_{slot_index}",),
            )
            accessories.append(EquippedItem(
                eq,instance_id=f"accessory_{actor_index:02d}_{slot_index}:instance"
            ))

        loadout=EquipmentLoadout((
            EquipmentSlotDefinition("main_hand",capacity=1),
            EquipmentSlotDefinition("accessory",capacity=2),
        ))
        loadout.equip("main_hand",weapon_item,validate_requirements=False)
        for item in accessories:
            loadout.equip("accessory",item,validate_requirements=False)
        return loadout,rune

    def _build_character(self, i):
        main=self.JOB_IDS[i%len(self.JOB_IDS)]
        secondary=self.JOB_IDS[(i+3)%len(self.JOB_IDS)]
        actor=RpgActorRuntime(
            ActorDefinition(
                f"stress_actor_{i:02d}",
                f"Stress Actor {i:02d}",
                class_assignments=(
                    ClassAssignment(main,assignment_id=f"main:{main}",role="primary",priority=0),
                    ClassAssignment(secondary,assignment_id=f"secondary:{secondary}",role="secondary",priority=1),
                ),
                base_stats={
                    "power":18+i,"guard":12+(i%6),"focus":14+(i%8),"speed":10+(i%7)
                },
                base_resources={
                    "vitality":260+i*25,
                    "technique":50+(i%5)*10,
                    "boost_like":3+(i%3),
                    f"unique_resource_{i:02d}":5+i,
                },
                tags=("actor.prebattle_stress",f"roster.index.{i}"),
                abilities=(f"basic_{i:02d}",f"utility_{i:02d}"),
            ),
            class_definitions=self.classes,
        )
        # learned skill + two active passives, varied by member
        actor.ability_state.learn(f"learned_skill_{i:02d}")
        p1=f"passive_{(i*2)%16:02d}"
        p2=f"passive_{(i*2+1)%16:02d}"
        actor.ability_state.equip_passive(p1)
        actor.ability_state.equip_passive(p2,capacity=3)

        graph=self._graph(i)
        allocations=ProgressionAllocationRuntime(
            (graph,),balances={"skill_point":30}
        )
        # Different depth by character, minimum 3 allocated nodes.
        for n in range(3+(i%4)):
            allocations.allocate(graph.graph_id,f"node_{n}")

        loadout,rune=self._equipment(i)
        build=resolve_actor_build(
            actor,allocations=allocations,loadout=loadout,passives=self.passives
        )
        level=12+i*4
        return actor,allocations,loadout,build,level,rune.attachment_id

    def _build_roster(self):
        self.characters=[self._build_character(i) for i in range(self.roster_size)]

    @property
    def active_ids(self):
        return tuple(x[0].definition.actor_id for x in self.characters[:self.active_count])

    @property
    def reserve_ids(self):
        return tuple(x[0].definition.actor_id for x in self.characters[self.active_count:])

    def report(self):
        snapshots=[]
        ability_counts=[]
        for actor,allocations,loadout,build,level,rune_id in self.characters:
            assignments=actor.class_assignments
            stats=tuple(sorted((k,float(v)) for k,v in build.stats.to_data()["values"].items()))
            resources=tuple(sorted(build.resources.to_data()["values"]))
            abilities=tuple(build.abilities)
            ability_counts.append(len(abilities))
            snapshots.append(PreBattleCharacterSnapshot(
                build.actor_id,
                level,
                assignments[0].class_id,
                assignments[1].class_id,
                stats,
                resources,
                abilities,
                tuple(actor.ability_state.active_passives),
                tuple(build.equipment_instance_ids),
                (rune_id,),
                len(build.capabilities),
            ))
        counts=self.inventory.to_data()["counts"]
        return PreBattleStressReport(
            tuple(snapshots),
            self.active_ids,
            self.reserve_ids,
            len(counts),
            sum(counts.values()),
            self.recipe_count,
            tuple(self.JOB_IDS),
            max(ability_counts),
            min(ability_counts),
        )
