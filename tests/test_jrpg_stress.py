"""STR-01 (ASTERIA_SPEC §35): the JRPG stress test, demonstrated on the reference project's real game session."""

from pathlib import Path

from asteria.project_tools import load_project
from asteria.validation.jrpg_stress import ITEMS, run_jrpg_stress

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "complex_reference_rpg"


def test_every_jrpg_stress_item_is_demonstrated_in_one_playthrough():
    report, game = run_jrpg_stress(load_project(ROOT / "project.asteria.json"))
    assert report.missing == [], report.evidence
    assert set(report.evidence) == set(ITEMS)
    assert "broken=True" in report.evidence["break_mechanic"]  # the break applies the real battle state
    assert "->" in report.evidence["turn_order_manipulation"]
    phases = report.evidence["multi_phase_boss"]
    assert phases.count("phase_") >= 2
    assert report.outcome == "victory"
    assert not game.event_errors


def test_breaking_the_boss_applies_the_broken_state_and_delays_its_turn():
    """Regression: battle subjects had no StateRuntime, so a break raised instead of applying 'broken'."""
    from asteria.runtime.game_session import GameSessionRuntime

    project = load_project(ROOT / "project.asteria.json")
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    battle = game.start_encounter("boss_room")
    boss = next(x for x in game.active_enemy_ids() if x.startswith("astral_tyrant"))
    casters = [h for h in game.active_hero_ids() if "fire_arc" in game.resolve_actor_build(h).abilities]
    ready = {t.member_id: t.ready_time for t in battle.scheduler.pending()}[boss]
    for i in range(5):  # five fire-weakness hits empty the 5-point stagger shield
        game.use_ability(casters[i % len(casters)], "fire_arc", (boss,))
    assert battle.member(boss).subject.states.get("broken") is not None
    assert {t.member_id: t.ready_time for t in battle.scheduler.pending()}[boss] == ready + 1.5
    assert battle.battle_resources.current(boss, "stagger") == 5  # reset after the break


def test_haste_and_slow_change_speed_and_the_next_rounds_turn_order():
    """Regression: haste_song only added a tag nothing read; slow_hex had no effect at all."""
    from asteria.runtime.game_session import GameSessionRuntime

    project = load_project(ROOT / "project.asteria.json")
    game = GameSessionRuntime(project, project.game_start.instantiate(project))
    battle = game.start_encounter("boss_room")
    boss = next(x for x in game.active_enemy_ids() if x.startswith("astral_tyrant"))
    singer = next(h for h in game.active_hero_ids() if "haste_song" in game.resolve_actor_build(h).abilities)
    hexer = next(h for h in game.active_hero_ids() if "slow_hex" in game.resolve_actor_build(h).abilities)
    target = next(h for h in game.active_hero_ids() if h != singer)
    speed_before = battle.member(target).current_initiative
    boss_before = battle.member(boss).current_initiative
    build_speed = game.resolve_actor_build(target).stats.get("speed")
    game.use_ability(singer, "haste_song", (target,))
    game.use_ability(hexer, "slow_hex", (boss,))
    assert battle.member(target).current_initiative == speed_before + 20
    assert battle.member(boss).current_initiative == boss_before - 20
    # speed_timeline is a CONTINUOUS scheduler: the next ready time after a member's own turn uses its speed now
    acted = set()
    for _ in range(40):
        actor = game.current_turn_actor()
        if actor in (target, boss):
            acted.add(actor)
        if battle.member(actor).side == "heroes":
            game.use_ability(actor, "guard", (actor,))
            game.end_turn()
        else:
            game.enemy_act(actor)
            game.end_turn()
        if acted == {target, boss}:
            break
    scheduled = {t.member_id: t.speed for t in battle.scheduler.pending()}
    assert scheduled[target] == speed_before + 20 and scheduled[boss] == boss_before - 20
    assert game.resolve_actor_build(target).stats.get("speed") == build_speed  # a battle buff, not persistent
