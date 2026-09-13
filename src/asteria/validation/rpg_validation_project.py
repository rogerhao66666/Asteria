from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import AbilityRegistry, AbilityRuntime
from asteria.rpg import AIDecisionRule, BattleRuntime, EnemyAIDefinition, Party, PartyMember

from .character_progression_lab import CharacterProgressionLab
from .equipment_lab import EquipmentLab
from .inventory_crafting_lab import InventoryCraftingLab
from .party_formation_lab import PartyFormationLab
from .playable_battle import (
    PlayableBattleScenario,
    PlayableBattleValidationHarness,
    _damage_ability,
    _reference_enemy_subject,
    _subject_from_resolved_build,
)
from .playable_rpg import build_reference_actor_scenario


@dataclass(frozen=True, slots=True)
class RpgValidationProjectSnapshot:
    actor_id: str
    level: int
    job_assignments: tuple[tuple[str, str], ...]
    abilities: tuple[str, ...]
    equipment_instance_ids: tuple[str, ...]
    inventory_counts: tuple[tuple[str, int], ...]
    party_active_ids: tuple[str, ...]
    party_reserve_ids: tuple[str, ...]


class AsteriaRpgValidationProject:
    """Coherent reference project that composes the previously isolated labs."""

    def __init__(self):
        shared=build_reference_actor_scenario()
        self.character=CharacterProgressionLab(shared)
        self.equipment=EquipmentLab(shared)
        self.inventory=InventoryCraftingLab(shared)
        self.party=PartyFormationLab()
        self.shared_scenario=shared

    def resolve_build(self):
        return self.shared_scenario.resolve()

    def build_battle_arena(self):
        build=self.resolve_build()

        authored_damage={
            "basic_attack":12,
            "power_strike":28,
            "guard_break":20,
            "quick_mix":14,
            "field_mix":18,
            "double_strike":18,
            "flame_slash":22,
            "venom_edge":16,
            "echo_edge":15,
            "focus_step":13,
            "ice_arc":21,
            "tempered_arc":30,
            "reactive_tonic":12,
            "enemy_claw":17,
            "enemy_crush":26,
        }
        registry=AbilityRegistry()
        for ability_id,amount in authored_damage.items():
            registry.register(_damage_ability(ability_id,amount))
        runtime=AbilityRuntime(registry)

        player_ability_ids=tuple(x for x in build.abilities if x in authored_damage)
        player=PartyMember(
            build.actor_id,
            "side.alpha",
            _subject_from_resolved_build(build),
            ability_ids=player_ability_ids,
            initiative=12,
        )
        enemy=PartyMember(
            "validation_boss",
            "side.omega",
            _reference_enemy_subject(),
            ability_ids=("enemy_claw","enemy_crush"),
            initiative=8,
        )
        ai=EnemyAIDefinition(
            "validation_boss_ai",
            rules=(
                AIDecisionRule(
                    "heavy","ability",
                    payload={"ability_id":"enemy_crush"},
                    target_selector="first_opponent",
                    priority=20,
                ),
                AIDecisionRule(
                    "light","ability",
                    payload={"ability_id":"enemy_claw"},
                    target_selector="first_opponent",
                    priority=10,
                ),
            ),
        )
        battle=BattleRuntime(
            (
                Party("side.alpha",(player,)),
                Party("side.omega",(enemy,)),
            ),
            runtime,
            enemy_ai_definitions=(ai,),
            rng_seed=136,
        )
        scenario=PlayableBattleScenario(
            battle,
            player.member_id,
            enemy.member_id,
            ai.ai_id,
            [],
        )
        return PlayableBattleValidationHarness(scenario)

    def snapshot(self):
        build=self.resolve_build()
        assignments=tuple(
            (x.role,x.class_id) for x in self.shared_scenario.actor.class_assignments
        )
        equipped=tuple(x.instance_id for x in self.shared_scenario.loadout.equipped())
        return RpgValidationProjectSnapshot(
            build.actor_id,
            self.character.level,
            assignments,
            tuple(build.abilities),
            tuple(equipped),
            tuple(sorted(self.shared_scenario.inventory._counts.items())),
            self.party.active_ids(),
            self.party.reserve_ids(),
        )
