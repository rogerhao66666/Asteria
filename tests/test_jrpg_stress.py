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
