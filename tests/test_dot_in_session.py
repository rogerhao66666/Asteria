"""BTL-02 in the game session: damage over time is fixed damage, or - when its battle state policy
carries
interaction tags - goes through the battle's interaction rules (the author decides, per state)."""

import pytest
from test_session_events import _session

from asteria.gameplay import Effect, EffectOperation, EffectOperationKind
from asteria.gameplay.states import PeriodicEffect, StateDefinition
from asteria.rpg import BattleStatePolicy


def _boss_burn_tick(interaction_tags):
    project, _ = _session()
    project.gameplay_library.states.register(
        StateDefinition(
            "rm_burn",
            5,
            periodic=(
                PeriodicEffect(
                    1,
                    Effect(
                        "rm_burn.tick",
                        (EffectOperation(EffectOperationKind.RESOURCE_DELTA, "vitality", -40),),
                    ),
                ),
            ),
        )
    )
    project.rpg_database.battle_state_policies["rm_burn"] = BattleStatePolicy(
        "rm_burn", tick_trigger="rpg.battle.turn_ended", interaction_tags=interaction_tags
    )
    project, game = _session(project)
    game.start_encounter("boss_room")
    battle = game.battle
    boss = next(e for e in game.active_enemy_ids() if e.startswith("astral_tyrant"))
    hero = next(iter(game.active_hero_ids()))
    battle.apply_state("rm_burn", hero, boss)
    pool = battle.member(boss).subject.resources
    before = pool.current("vitality")
    battle.battle_states.apply_trigger("rpg.battle.turn_ended", (battle.member(boss),))
    return before - pool.current("vitality"), battle


def test_damage_over_time_is_fixed_unless_the_author_gives_it_interaction_tags():
    fixed, battle = _boss_burn_tick(())
    assert fixed == pytest.approx(40) and battle.periodic_interactions == []
    fire, battle = _boss_burn_tick(
        ("damage.fire",)
    )  # the boss is weak to fire (x1.5 rule weak_fire)
    assert fire == pytest.approx(60)
    assert [r.matched_rules for *_, r in battle.periodic_interactions] == [("weak_fire",)]
    other, _ = _boss_burn_tick(("damage.poison",))  # tags no rule matches: unchanged
    assert other == pytest.approx(40)
