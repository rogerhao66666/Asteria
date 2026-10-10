from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg import RewardRoll, RewardRuntime

from .playable_battle_mechanics import PlayableBattleMechanicsHarness
from .playable_battle_modes import PlayableBattleModeHarness
from .playable_battle_summons import PlayableBattleSummonHarness
from .rpg_validation_project import AsteriaRpgValidationProject


@dataclass(frozen=True, slots=True)
class EverythingCombinedReport:
    steps: tuple[str, ...]
    pre_battle_abilities: tuple[str, ...]
    crafted_item_count: int
    party_active_ids: tuple[str, ...]
    battle_damage_applied: bool
    status_exercised: bool
    transform_exercised: bool
    summon_exercised: bool
    reward_level_before: int
    reward_level_after: int
    reward_item_count: int
    reward_currency: float


class EverythingCombinedScenario:
    """Deterministic end-to-end validation across the already canonical systems.

    Specialized battle mechanics remain their existing generic harnesses. This
    scenario proves they can coexist in one project journey; it does not merge
    status/transform/summon into a new game-specific battle subsystem.
    """

    def __init__(self):
        self.project = AsteriaRpgValidationProject()
        self.steps = []
        self.currencies = {}

    def run(self):
        p = self.project

        # Build / multiclass / progression.
        p.character.unlock_job("alchemist")
        p.character.allocate_node("hero_mastery", "double_strike_node")
        p.character.allocate_node("hero_mastery", "deep_reserve")
        self.steps.append("build.progression")

        # Equipment + attachment + growth.
        p.equipment.equip("main_hand", "ember_blade:lab")
        p.equipment.equip("accessory", "echo_charm:lab")
        p.equipment.attach("ember_blade:lab", "rune", "venom_rune")
        p.equipment.add_growth_progress("ember_blade:lab", "weapon_xp", 10)
        self.steps.append("build.equipment")

        # Composition consumes real inventory and produces an item.
        craft = p.inventory
        craft.begin()
        craft.select("red_herb")
        craft.advance()
        craft.select("glass_vial")
        craft.advance()
        craft.advance()
        craft.craft()
        self.steps.append("inventory.composition")

        # Outside-battle party organization.
        p.party.swap_active_with_reserve("party_01", "party_08")
        p.party.move("party_08", "slot_0")
        self.steps.append("party.formation")

        build = p.resolve_build()
        expected = ("double_strike", "flame_slash", "venom_edge", "tempered_arc")
        if not all(x in build.abilities for x in expected):
            raise AssertionError("pre-battle build did not compose expected abilities")

        # Enter arena from current build and execute a progression-derived action.
        arena = p.build_battle_arena()
        enemy = arena.scenario.battle.member(arena.scenario.enemy_member_id)
        before = enemy.subject.resources.current("vitality")
        arena.player_action("double_strike")
        after = enemy.subject.resources.current("vitality")
        battle_damage = after < before
        self.steps.append("battle.current_build")

        # Exercise the already-generic specialized battle mechanics in the same
        # end-to-end validation run.
        mechanics = PlayableBattleMechanicsHarness()
        mechanics.apply_status("scorch")
        status_exercised = bool(mechanics.status_snapshot(mechanics.scenario.enemy_id))
        mechanics.apply_resolve_pressure()
        mechanics.double_flame()
        self.steps.append("battle.status.interaction.sequence")

        modes = PlayableBattleModeHarness()
        modes.enter_overdrive()
        transformed = modes.current_form() == "overdrive"
        modes.execute_current_action("overdrive_arc")
        modes.revert_mode()
        self.steps.append("battle.transform")

        summons = PlayableBattleSummonHarness()
        summons.summon_player_spirit()
        summons.summon_boss_add()
        summon_exercised = "spirit_echo" in summons.active_member_ids() and "ember_add" in summons.active_member_ids()
        summons.execute("spirit_echo", "spirit_bolt", summons.scenario.boss_id)
        self.steps.append("battle.summon.add")

        # Victory/reward application boundary: use canonical RewardRuntime to
        # update the persistent project after the battle scenario completes.
        level_before = p.character.level
        reward = RewardRoll(
            currencies={"gold": 125},
            experience={"character_level": 180},
            items={"spark_dust": 1},
        )
        reward_runtime = RewardRuntime(
            inventory=p.shared_scenario.inventory,
            progression=p.character.progression,
            currencies=self.currencies,
        )
        reward_runtime.apply(reward)
        level_after = p.character.level
        self.steps.append("postbattle.reward")

        return EverythingCombinedReport(
            tuple(self.steps),
            tuple(build.abilities),
            p.shared_scenario.inventory.count("healing_tonic"),
            p.party.active_ids(),
            battle_damage,
            status_exercised,
            transformed,
            summon_exercised,
            level_before,
            level_after,
            p.shared_scenario.inventory.count("spark_dust"),
            self.currencies["gold"],
        )
