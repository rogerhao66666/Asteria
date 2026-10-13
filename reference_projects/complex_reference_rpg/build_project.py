from __future__ import annotations

from pathlib import Path

from asteria.core import Entity, Scene, Transform
from asteria.events import (
    EventBinding,
    EventInstruction,
    EventProgram,
    EventTriggerKind,
    SceneEventBindings,
)
from asteria.gameplay import (
    AbilityCost,
    AbilityDefinition,
    AbilityEffect,
    AbilityTargetMode,
    Effect,
    EffectOperation,
    EffectOperationKind,
    TargetingRule,
)
from asteria.presentation import (
    AbilityScreenProfile,
    BattleActionMenuPolicy,
    BattleFeedbackProfile,
    BattleHudProfile,
    BattlePartyLayoutPolicy,
    BattleResultProfile,
    BattleUiLayoutProfile,
    BattleUiPolishProfile,
    BattleUiTheme,
    CharacterScreenProfile,
    EquipmentScreenProfile,
    InventoryScreenProfile,
    PartyScreenProfile,
    ProgressionScreenProfile,
)
from asteria.project import Project
from asteria.rpg import (
    ActionSequenceDefinition,
    ActionSequenceStep,
    ActionTimingDefinition,
    ActionTransactionPolicy,
    ActorDefinition,
    AICondition,
    AIDecisionRule,
    AttachmentDefinition,
    BattleEscapeRule,
    BattleObjectiveCondition,
    BattleObjectiveDefinition,
    BattleResourceDefinition,
    BattleResourceRule,
    BattleSchedulerDefinition,
    BattleSessionRules,
    BattleStatePolicy,
    BattleTargetingDefinition,
    BossPhaseDefinition,
    ClassAssignment,
    ClassDefinition,
    CompositionOutput,
    CompositionRecipeDefinition,
    CompositionSelection,
    EncounterDefinition,
    EncounterMember,
    EnemyAIDefinition,
    EnemyBehaviorBinding,
    EnemyDefinition,
    EquipmentDefinition,
    EquipmentGrowthDefinition,
    EquipmentGrowthNodeDefinition,
    EquipmentGrowthReward,
    FormationDefinition,
    FormationSlotDefinition,
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
    InteractionRule,
    ItemDefinition,
    LootEntry,
    OutcomeCheckDefinition,
    PartyPlacementDefinition,
    PartyPresentationPolicyDefinition,
    PartySetupDefinition,
    PassiveDefinition,
    ProgressionGraphDefinition,
    ProgressionMilestone,
    ProgressionNodeDefinition,
    ProgressionNodeRequirement,
    ProgressionNodeReward,
    ProgressionTrackDefinition,
    ReactionDefinition,
    RewardDefinition,
    SocketDefinition,
)
from asteria.runtime import Interaction2DComponent

ABILITY_IDS = (
    "strike",
    "guard",
    "fire_arc",
    "ice_lance",
    "storm_chain",
    "heal",
    "revive",
    "double_cut",
    "armor_break",
    "poison_edge",
    "haste_song",
    "slow_hex",
    "party_barrier",
    "focus_charge",
    "burst_release",
    "counter_stance",
    "summon_wisp",
    "dispel",
    "meteor",
    "boss_cleave",
    "boss_roar",
    "boss_nova",
    "add_bite",
    "add_mend",
)

JOBS = (
    ("vanguard", "Vanguard"),
    ("arcanist", "Arcanist"),
    ("alchemist", "Alchemist"),
    ("warden", "Warden"),
    ("ranger", "Ranger"),
    ("oracle", "Oracle"),
    ("duelist", "Duelist"),
    ("mystic", "Mystic"),
)

ACTORS = tuple((f"hero_{i:02d}", f"Hero {i:02d}") for i in range(1, 13))


def build_project():
    project = Project("Asteria Complex Reference RPG")
    db = project.rpg_database

    # --- Gameplay abilities ---
    costs = {
        "fire_arc": ("technique", 8),
        "ice_lance": ("technique", 8),
        "storm_chain": ("technique", 12),
        "heal": ("technique", 7),
        "revive": ("technique", 18),
        "double_cut": ("technique", 9),
        "armor_break": ("technique", 10),
        "poison_edge": ("technique", 8),
        "haste_song": ("technique", 10),
        "slow_hex": ("technique", 10),
        "party_barrier": ("technique", 14),
        "focus_charge": ("technique", 4),
        "burst_release": ("focus", 2),
        "counter_stance": ("technique", 8),
        "summon_wisp": ("technique", 16),
        "dispel": ("technique", 7),
        "meteor": ("technique", 24),
        "boss_nova": ("rage", 30),
        "add_mend": ("technique", 5),
    }
    for aid in ABILITY_IDS:
        relation = (
            "self"
            if aid in {"guard", "focus_charge", "counter_stance"}
            else "ally"
            if aid in {"heal", "revive", "party_barrier", "haste_song", "add_mend"}
            else "opponent"
        )
        tags = ["ability"]
        if aid in {"fire_arc", "meteor", "boss_nova"}:
            tags += ["damage.fire", "magic"]
        elif aid == "ice_lance":
            tags += ["damage.ice", "magic"]
        elif aid == "storm_chain":
            tags += ["damage.lightning", "magic"]
        elif aid in {"heal", "revive", "add_mend"}:
            tags += ["healing"]
        elif aid in {"guard", "party_barrier", "counter_stance"}:
            tags += ["defense"]
        else:
            tags += ["physical"]
        maximum = 6 if aid in {"party_barrier", "haste_song", "boss_nova", "boss_roar"} else 1
        damage_values = {
            "strike": 900,
            "fire_arc": 1150,
            "ice_lance": 1150,
            "storm_chain": 980,
            "double_cut": 780,
            "armor_break": 820,
            "poison_edge": 760,
            "burst_release": 1700,
            "meteor": 2200,
            "boss_cleave": 220,
            "boss_roar": 120,
            "boss_nova": 350,
            "add_bite": 80,
        }
        heal_values = {"heal": 800, "revive": 1000, "add_mend": 180}
        effects = ()
        if aid in damage_values:
            ops = [
                EffectOperation(
                    EffectOperationKind.RESOURCE_DELTA, "vitality", -float(damage_values[aid])
                )
            ]
            tag_effects = {
                "poison_edge": "status.poison",
                "armor_break": "debuff.armor_down",
                "boss_roar": "debuff.fear",
            }
            if aid in tag_effects:
                ops.append(EffectOperation(EffectOperationKind.TAG_ADD, tag_effects[aid]))
            effects = (
                AbilityEffect(AbilityTargetMode.SELECTED, Effect(f"{aid}.effect", tuple(ops))),
            )
        elif aid in heal_values:
            effects = (
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        f"{aid}.effect",
                        (
                            EffectOperation(
                                EffectOperationKind.RESOURCE_DELTA,
                                "vitality",
                                float(heal_values[aid]),
                            ),
                        ),
                    ),
                ),
            )
        elif aid in {"haste_song", "party_barrier", "counter_stance", "guard", "focus_charge"}:
            tag = {
                "haste_song": "buff.haste",
                "party_barrier": "buff.barrier",
                "counter_stance": "state.counter",
                "guard": "buff.guard",
                "focus_charge": "buff.focus",
            }[aid]
            ops = [EffectOperation(EffectOperationKind.TAG_ADD, tag)]
            if (
                aid == "haste_song"
            ):  # turn-order manipulation: faster allies act sooner (speed feeds the scheduler)
                ops.append(EffectOperation(EffectOperationKind.STAT_DELTA, "speed", 20.0))
            effects = (
                AbilityEffect(AbilityTargetMode.SELECTED, Effect(f"{aid}.effect", tuple(ops))),
            )
        elif aid == "slow_hex":  # and a slowed enemy acts later
            effects = (
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        f"{aid}.effect",
                        (
                            EffectOperation(EffectOperationKind.TAG_ADD, "debuff.slow"),
                            EffectOperation(EffectOperationKind.STAT_DELTA, "speed", -20.0),
                        ),
                    ),
                ),
            )
        ability = AbilityDefinition(
            aid,
            targeting=TargetingRule(
                minimum_targets=1, maximum_targets=maximum, allow_self=relation != "opponent"
            ),
            costs=((AbilityCost(*costs[aid]),) if aid in costs else ()),
            effects=effects,
            tags=tags,
        )
        project.gameplay_library.add_ability(ability)

    # --- Jobs + progression ---
    job_abilities = {
        "vanguard": ("strike", "guard", "armor_break", "party_barrier"),
        "arcanist": ("fire_arc", "ice_lance", "storm_chain", "meteor"),
        "alchemist": ("heal", "revive", "dispel", "poison_edge"),
        "warden": ("guard", "party_barrier", "counter_stance", "armor_break"),
        "ranger": ("strike", "double_cut", "poison_edge", "haste_song"),
        "oracle": ("heal", "revive", "haste_song", "slow_hex"),
        "duelist": ("strike", "double_cut", "counter_stance", "burst_release"),
        "mystic": ("fire_arc", "summon_wisp", "focus_charge", "burst_release"),
    }
    for index, (jid, name) in enumerate(JOBS):
        track_id = f"{jid}_mastery"
        db.add_progression_track(
            ProgressionTrackDefinition(
                track_id,
                f"{name} Mastery",
                milestones=(
                    ProgressionMilestone(1, 0, granted_abilities=job_abilities[jid][:1]),
                    ProgressionMilestone(
                        2,
                        100,
                        stat_bonuses={"power": 4 + index},
                        granted_abilities=job_abilities[jid][1:2],
                    ),
                    ProgressionMilestone(
                        3,
                        300,
                        stat_bonuses={"speed": 2 + index % 3},
                        granted_abilities=job_abilities[jid][2:3],
                    ),
                    ProgressionMilestone(4, 700, granted_abilities=job_abilities[jid][3:]),
                ),
            )
        )
        db.add_class(
            ClassDefinition(
                jid,
                name,
                stat_bonuses={
                    "power": 8 + index * 2,
                    "defense": 5 + index,
                    "speed": 4 + (index % 4) * 2,
                },
                resource_bonuses={"vitality": 40 + index * 5, "technique": 15 + index * 2},
                granted_tags=(f"job.{jid}",),
                granted_abilities=job_abilities[jid][:2],
            )
        )
        nodes = []
        branching = index % 2 == 0
        for n in range(6):
            nid = f"{jid}_node_{n + 1}"
            if not branching:
                prereq = () if n == 0 else (ProgressionNodeRequirement(f"{jid}_node_{n}"),)
            else:
                deps = ((), (1,), (1,), (2,), (3,), (4, 5))[n]
                prereq = tuple(ProgressionNodeRequirement(f"{jid}_node_{d}") for d in deps)
            reward = ProgressionNodeReward(
                stat_bonuses={"power": 2 + n, "defense": 1 + n // 2},
                granted_abilities=(job_abilities[jid][min(n, len(job_abilities[jid]) - 1)],)
                if n in {1, 3, 5}
                else (),
                granted_tags=(f"mastery.{jid}.{n + 1}",),
            )
            nodes.append(
                ProgressionNodeDefinition(
                    nid,
                    f"{name} Node {n + 1}",
                    max_rank=2 if n in {2, 4} else 1,
                    rank_costs=({"ap": 1}, {"ap": 2}) if n in {2, 4} else ({"ap": 1},),
                    rewards=(reward, reward) if n in {2, 4} else (reward,),
                    prerequisites=prereq,
                    tags=(f"tree.{jid}",),
                )
            )
        positions = {}
        if branching:
            coords = ((0, 90), (190, 20), (190, 160), (380, 20), (380, 160), (570, 90))
            positions = {node.node_id: coords[i] for i, node in enumerate(nodes)}
        db.add_progression_graph(
            ProgressionGraphDefinition(
                f"{jid}_tree",
                f"{name} Skill Tree",
                nodes=nodes,
                tags=("skill_tree", f"job.{jid}"),
                editor_view="graph" if branching else "list",
                node_positions=positions,
            )
        )

    # --- Passives ---
    for i in range(16):
        pid = f"passive_{i + 1:02d}"
        granted = (ABILITY_IDS[(i + 5) % 12],) if i % 4 == 0 else ()
        db.add_passive(
            PassiveDefinition(
                pid,
                f"Passive {i + 1:02d}",
                tags=(f"passive.family.{i % 4}",),
                granted_abilities=granted,
            )
        )

    # --- Actors: 12 roster, each dual job ---
    for i, (aid, name) in enumerate(ACTORS):
        primary = JOBS[i % 8][0]
        secondary = JOBS[(i + 3) % 8][0]
        db.add_actor(
            ActorDefinition(
                aid,
                name,
                class_assignments=(
                    ClassAssignment(
                        primary,
                        assignment_id=f"{aid}.main",
                        role="main",
                        priority=10,
                        progression_track_ids=(f"{primary}_mastery",),
                    ),
                    ClassAssignment(
                        secondary,
                        assignment_id=f"{aid}.sub",
                        role="secondary",
                        priority=5,
                        progression_track_ids=(f"{secondary}_mastery",),
                    ),
                ),
                base_stats={
                    "power": 40 + i * 3,
                    "defense": 34 + i * 2,
                    "speed": 30 + (i % 6) * 4,
                    "magic": 35 + (i % 5) * 5,
                },
                base_resources={"vitality": 1500 + i * 80, "technique": 140 + i * 4, "focus": 3},
                tags=("actor.playable", f"roster.{i + 1:02d}"),
                abilities=("strike", "guard"),
            )
        )

    # --- Items / equipment / attachments / growth / crafting ---
    item_names = (
        "healing_herb",
        "ether_leaf",
        "phoenix_seed",
        "fire_dust",
        "ice_crystal",
        "storm_core",
        "iron_ore",
        "silver_ore",
        "moon_shard",
        "venom_sac",
        "guardian_scale",
        "ancient_thread",
        "boss_emblem",
        "wisp_essence",
        "alchemy_salt",
        "focus_stone",
    )
    for iid in item_names:
        db.add_item(
            ItemDefinition(
                iid,
                iid.replace("_", " ").title(),
                tags=("material",)
                if iid not in {"healing_herb", "ether_leaf", "phoenix_seed"}
                else ("consumable",),
            )
        )

    growth_nodes = (
        EquipmentGrowthNodeDefinition(
            "temper_1",
            "Temper I",
            auto_unlock=False,
            rewards=(EquipmentGrowthReward(granted_tags=("weapon.tempered",)),),
        ),
        EquipmentGrowthNodeDefinition(
            "temper_2",
            "Temper II",
            auto_unlock=False,
            prerequisites=("temper_1",),
            rewards=(EquipmentGrowthReward(granted_abilities=("double_cut",)),),
        ),
        EquipmentGrowthNodeDefinition(
            "awaken",
            "Awaken",
            auto_unlock=False,
            prerequisites=("temper_2",),
            rewards=(EquipmentGrowthReward(granted_capabilities=("weapon.awakened",)),),
        ),
    )
    db.add_equipment_growth(
        EquipmentGrowthDefinition(
            "weapon_growth", "Weapon Growth", nodes=growth_nodes, tags=("growth.weapon",)
        )
    )

    for i in range(12):
        eid = f"weapon_{i + 1:02d}"
        db.add_equipment(
            EquipmentDefinition(
                eid,
                f"Weapon {i + 1:02d}",
                slot="weapon",
                tags=("weapon", f"weapon.family.{i % 4}"),
                granted_abilities=(ABILITY_IDS[2 + (i % 10)],),
                sockets=(SocketDefinition("rune", accepted_tags=("rune",)),),
                growth_id="weapon_growth",
            )
        )
    for i in range(8):
        db.add_equipment(
            EquipmentDefinition(
                f"accessory_{i + 1:02d}",
                f"Accessory {i + 1:02d}",
                slot="accessory",
                tags=("accessory", f"accessory.family.{i % 3}"),
                granted_abilities=(ABILITY_IDS[5 + (i % 6)],) if i % 2 == 0 else (),
            )
        )
    for i in range(6):
        db.add_attachment(
            AttachmentDefinition(
                f"rune_{i + 1:02d}",
                f"Rune {i + 1:02d}",
                tags=("rune", f"element.{i % 3}"),
                granted_abilities=(ABILITY_IDS[2 + (i % 3)],),
            )
        )

    for i, (rid, out, mat) in enumerate(
        (
            ("healing_tonic", "healing_herb", "alchemy_salt"),
            ("revival_draught", "phoenix_seed", "moon_shard"),
            ("storm_bomb", "storm_core", "alchemy_salt"),
            ("focus_elixir", "focus_stone", "wisp_essence"),
        )
    ):
        db.add_composition_recipe(
            CompositionRecipeDefinition(
                rid,
                rid.replace("_", " ").title(),
                selections=(
                    CompositionSelection("base", (out,)),
                    CompositionSelection("catalyst", (mat,)),
                ),
                outputs=(CompositionOutput(out, 2),),
                tags=("alchemy", f"tier.{1 + i // 2}"),
            )
        )

    # --- Formation / party ---
    slots = tuple(
        FormationSlotDefinition(
            f"slot_{i + 1}",
            x=float((i % 3) * 44),
            y=float((i // 3) * 36),
            tags=("front",) if i < 3 else ("back",),
        )
        for i in range(6)
    )
    db.add_formation(FormationDefinition("standard_six", slots))
    db.add_party_setup(
        PartySetupDefinition(
            "main_party",
            "Main Party",
            roster_actor_ids=tuple(a for a, _ in ACTORS),
            active_actor_ids=tuple(a for a, _ in ACTORS[:4]),
            active_capacity=6,
            formation_id="standard_six",
            placements=tuple(
                PartyPlacementDefinition(ACTORS[i][0], f"slot_{i + 1}") for i in range(4)
            ),
            allow_reserve=True,
            allow_swap=True,
            allow_reorder=True,
            tags=("reference.party",),
        )
    )
    db.add_party_presentation_policy(
        PartyPresentationPolicyDefinition(
            "adaptive_party",
            visible_limits={"active": 6, "reserve": 8},
            group_labels={"active": "Active", "reserve": "Reserve"},
        )
    )

    # --- Enemies / Boss / rewards ---
    db.add_enemy(
        EnemyDefinition(
            "ember_hound",
            "Ember Hound",
            stats={"power": 55, "defense": 40, "speed": 50},
            resources={"vitality": 900, "technique": 30},
            tags=("enemy", "weak.ice"),
            abilities=("add_bite", "fire_arc"),
            reward=RewardDefinition(
                currencies={"gold": 120},
                experience={"vanguard_mastery": 40},
                loot=(LootEntry("fire_dust", chance=0.7),),
            ),
        )
    )
    db.add_enemy(
        EnemyDefinition(
            "mender_wisp",
            "Mender Wisp",
            stats={"power": 30, "defense": 35, "speed": 42},
            resources={"vitality": 700, "technique": 80},
            tags=("enemy", "weak.lightning"),
            abilities=("add_mend", "fire_arc"),
            reward=RewardDefinition(
                currencies={"gold": 100},
                experience={"mystic_mastery": 35},
                loot=(LootEntry("wisp_essence", chance=0.8),),
            ),
        )
    )
    db.add_enemy(
        EnemyDefinition(
            "iron_guard",
            "Iron Guard",
            stats={"power": 65, "defense": 75, "speed": 28},
            resources={"vitality": 1200, "technique": 25},
            tags=("enemy", "weak.fire"),
            abilities=("strike", "armor_break"),
            reward=RewardDefinition(
                currencies={"gold": 180},
                experience={"warden_mastery": 50},
                loot=(LootEntry("iron_ore", chance=1.0, minimum=2, maximum=4),),
            ),
        )
    )
    boss_reward = RewardDefinition(
        currencies={"gold": 2500, "renown": 1},
        experience={f"{jid}_mastery": 220 for jid, _ in JOBS},
        loot=(
            LootEntry("boss_emblem", chance=1.0),
            LootEntry("moon_shard", chance=1.0, minimum=3, maximum=5),
        ),
    )
    db.add_enemy(
        EnemyDefinition(
            "astral_tyrant",
            "Astral Tyrant",
            stats={"power": 125, "defense": 105, "speed": 72, "magic": 135},
            resources={"vitality": 9000, "technique": 999, "rage": 0, "stagger": 5},
            tags=("enemy", "boss", "weak.fire", "weak.ice", "weak.lightning"),
            abilities=("boss_cleave", "boss_roar", "boss_nova", "summon_wisp", "meteor"),
            reward=boss_reward,
        )
    )
    db.add_encounter(
        EncounterDefinition(
            "boss_room",
            members=(EncounterMember("astral_tyrant"), EncounterMember("mender_wisp", count=2)),
            tags=("boss", "multi_phase", "adds"),
        )
    )

    rules = (
        AIDecisionRule(
            "cleave",
            "ability",
            payload={"ability_id": "boss_cleave"},
            target_selector="first_opponent",
            priority=5,
        ),
        AIDecisionRule(
            "roar",
            "ability",
            payload={"ability_id": "boss_roar"},
            target_selector="all_opponents",
            priority=4,
        ),
        AIDecisionRule(
            "nova",
            "ability",
            payload={"ability_id": "boss_nova"},
            target_selector="all_opponents",
            priority=10,
            conditions=(
                AICondition("resource", params={"resource_id": "rage", "op": ">=", "value": 30}),
            ),
        ),
        AIDecisionRule(
            "meteor",
            "ability",
            payload={"ability_id": "meteor"},
            target_selector="first_opponent",
            priority=7,
        ),
    )
    phases = (
        BossPhaseDefinition("phase_1", decision_rule_ids=("cleave", "roar"), priority=1),
        BossPhaseDefinition(
            "phase_2",
            conditions=(
                AICondition(
                    "resource_ratio", params={"resource_id": "vitality", "op": "<=", "value": 0.65}
                ),
            ),
            decision_rule_ids=("cleave", "meteor", "roar"),
            priority=5,
            actions_per_ready=2,
        ),
        BossPhaseDefinition(
            "phase_3",
            conditions=(
                AICondition(
                    "resource_ratio", params={"resource_id": "vitality", "op": "<=", "value": 0.3}
                ),
            ),
            decision_rule_ids=("nova", "meteor", "cleave"),
            priority=10,
            actions_per_ready=3,
        ),
    )
    db.add_enemy_ai(
        EnemyAIDefinition(
            "astral_tyrant_ai", rules=rules, phases=phases, initial_phase_id="phase_1"
        )
    )
    db.add_enemy_behavior_binding(EnemyBehaviorBinding("astral_tyrant", "astral_tyrant_ai"))

    # --- Battle rules: generic equivalents, never game-specific engine assumptions ---
    db.add_battle_resource(
        BattleResourceDefinition(
            "stagger", minimum=0, maximum=5, start_mode="maximum", end_mode="persist"
        )
    )
    db.add_battle_resource(
        BattleResourceDefinition(
            "rage",
            minimum=0,
            maximum=100,
            start_mode="fixed",
            start_value=0,
            end_mode="reset_to_start",
        )
    )
    # Generic boost-like resource. The reference game calls it Momentum; the engine
    # attaches no BP-specific meaning to the resource name or lifecycle.
    db.add_battle_resource(
        BattleResourceDefinition(
            "momentum",
            minimum=0,
            maximum=5,
            start_mode="fixed",
            start_value=1,
            end_mode="reset_to_start",
            rules=(BattleResourceRule("rpg.battle.turn_ready", 1),),
        )
    )
    db.add_battle_state_policy(
        BattleStatePolicy(
            "broken", prevent_action=True, duration_multiplier=1.0, remove_triggers=("round.end",)
        )
    )
    from asteria.gameplay.states import StateDefinition

    project.gameplay_library.add_state(
        StateDefinition("broken", 1.0)
    )  # the state the break threshold applies
    for element in ("fire", "ice", "lightning"):
        db.add_interaction_rule(
            InteractionRule(
                f"weak_{element}",
                source_tags_all=(f"damage.{element}",),
                target_tags_all=(f"weak.{element}",),
                multiplier=1.5,
                outcome_tags=("outcome.weak", "outcome.stagger"),
                priority=10,
            )
        )
    db.add_outcome_check(
        OutcomeCheckDefinition(
            "critical", 0.08, source_stat_terms={"speed": 0.001}, success_tags=("outcome.crit",)
        )
    )
    for aid in ABILITY_IDS:
        relation = (
            "ally"
            if aid in {"heal", "revive", "party_barrier", "haste_song", "add_mend"}
            else "self"
            if aid in {"guard", "focus_charge", "counter_stance"}
            else "opponent"
        )
        maximum = 6 if aid in {"party_barrier", "haste_song", "boss_nova", "boss_roar"} else 1
        db.add_battle_targeting(
            BattleTargetingDefinition(
                aid, relation=relation, minimum_targets=1, maximum_targets=maximum
            )
        )
        db.add_action_timing(
            ActionTimingDefinition(
                aid,
                startup=0.1,
                cast_time=0.25 if aid in {"meteor", "boss_nova", "revive"} else 0.0,
                recovery=0.15,
                priority=5 if aid == "heal" else 0,
            )
        )
        db.add_action_transaction(
            ActionTransactionPolicy(aid, cost_commit="resolution", interrupt_cost="refund")
        )
    db.add_battle_scheduler(
        BattleSchedulerDefinition("speed_timeline", mode="continuous", timeline_scale=100)
    )
    db.add_action_sequence(
        ActionSequenceDefinition("double_cut_sequence", (ActionSequenceStep("strike", repeat=2),))
    )
    db.add_gauge_composition(
        GaugeCompositionDefinition(
            "stagger_system",
            impacts=(
                GaugeImpactRule(
                    "weak_hit",
                    "stagger",
                    "battle.hit",
                    delta=-1,
                    required_outcome_tags_all=("outcome.weak",),
                ),
            ),
            thresholds=(
                GaugeThresholdRule(
                    "break",
                    "stagger",
                    "at_or_below",
                    0,
                    state_id="broken",
                    reset_to=5,
                    emit_trigger="battle.break",
                    timeline_shift=1.5,
                ),
            ),
        )
    )
    db.add_reaction(
        ReactionDefinition(
            "counter_reaction",
            "battle.after_action",
            "event_targets",
            target_selector="event_source",
            ability_id="strike",
            required_tags=("state.counter",),
        )
    )
    db.add_battle_objective(
        BattleObjectiveDefinition(
            "standard_victory",
            success_conditions=(
                BattleObjectiveCondition("side_active_count", "enemies", "==", 0),
            ),
            failure_conditions=(BattleObjectiveCondition("side_active_count", "heroes", "==", 0),),
            winning_sides=("heroes",),
            defeated_sides=("enemies",),
        )
    )
    db.add_escape_rule(
        BattleEscapeRule(
            "standard_escape", "heroes", base_chance=0.45, source_stat="speed", source_scale=0.002
        )
    )
    db.add_battle_session_rules(
        BattleSessionRules(
            "reference_session",
            knockout_resource_id="vitality",
            hit_trigger="battle.hit",
            boost_resource_id="momentum",
            boost_cost_per_level=1,
            boost_max_level=3,
        )
    )

    # --- Presentation profiles, project-owned ---
    lib = project.battle_presentation_library
    lib.add("feedback", "premium", BattleFeedbackProfile())
    lib.add("hud", "adaptive", BattleHudProfile())
    lib.add("ui_layout", "adaptive", BattleUiLayoutProfile(virtual_width=480, virtual_height=270))
    lib.add("ui_polish", "premium", BattleUiPolishProfile())
    lib.add("action_menu", "default", BattleActionMenuPolicy())
    lib.add("results", "default", BattleResultProfile())
    lib.add("party_layout", "adaptive", BattlePartyLayoutPolicy())
    lib.add("ui_theme", "reference", BattleUiTheme())
    lib.add("rpg_character_screen", "default", CharacterScreenProfile())
    lib.add("rpg_equipment_screen", "default", EquipmentScreenProfile(page_size=12))
    lib.add(
        "rpg_ability_screen",
        "default",
        AbilityScreenProfile(visible_limits={"abilities": 12, "passives": 8}),
    )
    lib.add(
        "rpg_progression_screen",
        "default",
        ProgressionScreenProfile(visible_limits={f"{jid}_tree": 10 for jid, _ in JOBS}),
    )
    lib.add(
        "rpg_inventory_screen", "default", InventoryScreenProfile(visible_limits={"items": 24})
    )
    lib.add(
        "rpg_party_screen",
        "default",
        PartyScreenProfile(visible_limits={"active": 6, "reserve": 8}),
    )

    # --- Field scene + Boss interaction ---
    scene = Scene("Astral Gate")
    player = Entity("Player")
    pt = player.add_component(Transform())
    pt.x = 0.0
    pt.y = 0.0
    scene.add_entity(player)
    boss = Entity("Astral Tyrant")
    bt = boss.add_component(Transform())
    bt.x = 48.0
    bt.y = 0.0
    interact = boss.add_component(Interaction2DComponent())
    interact.range = 28.0
    interact.require_facing = True
    scene.add_entity(boss)
    project.add_scene(scene)

    event_id = "boss_interaction_event"
    binding_id = "boss_interaction"
    program = EventProgram(
        (
            # Boss camera (CAM-02): pan and zoom onto the boss while it speaks, cut back as the
            # fight starts.
            EventInstruction(
                "WORLD",
                {
                    "command": "CAMERA_FOCUS",
                    "args": {"entity": "Astral Tyrant", "zoom": 1.6, "blend": 0.8},
                },
            ),
            EventInstruction(
                "DIALOGUE",
                {"speaker": "Astral Tyrant", "text": "The gate yields only to those who endure."},
            ),
            EventInstruction(
                "WORLD", {"command": "CAMERA_RELEASE", "args": {"blend": 0.0, "ease": "cut"}}
            ),
            EventInstruction(
                "WORLD", {"command": "START_ENCOUNTER", "args": {"encounter_id": "boss_room"}}
            ),
            EventInstruction("END"),
        ),
        name="Astral Tyrant Encounter",
    )
    project.event_programs.register(event_id, program)
    bindings = SceneEventBindings()
    bindings.add(
        EventBinding(
            binding_id,
            boss.id,
            event_id,
            trigger=EventTriggerKind.ACTION,
            local_scope_id="astral_tyrant",
        )
    )
    project.scene_event_bindings[scene.id] = bindings
    interact.event_binding_id = binding_id
    interact.event_program_id = event_id
    interact.local_scope_id = "astral_tyrant"

    project.validate()
    return project, player.id, boss.id


def write_project(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    project, player_id, boss_id = build_project()
    # Canonical New Game state belongs to the Project, not a developer/player save.
    try:
        from .build_saves import build_save
    except ImportError:
        from build_saves import build_save
    from asteria.runtime.game_start import GameStartDefinition

    project.game_start = GameStartDefinition.from_runtime_save(build_save(project, "early"))
    project.game_start.event_context_data["variables"]["reference_profile"] = "new_game"
    project.validate()
    path = output_dir / "project.asteria.json"
    project.save_json(path)
    (output_dir / "reference_ids.json").write_text(
        __import__("json").dumps(
            {
                "project_id": project.id,
                "startup_scene_id": project.startup_scene_id,
                "player_entity_id": player_id,
                "boss_entity_id": boss_id,
                "party_id": "main_party",
                "encounter_id": "boss_room",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    write_project(Path(__file__).resolve().parent)
