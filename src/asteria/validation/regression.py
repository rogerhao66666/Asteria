"""Regression snapshot (CB13): deterministic digests of behaviour that must not drift silently.

``regression_snapshot(repo)`` plays a scripted reference boss battle with
the canonical session (fixed seed), reloads every reference save, and
hashes the RPG database and the golden asset summary. The tests compare it
with ``tests/golden/baselines/regression.json``; updating follows the same
rules as the golden baseline (tests/golden/README.md).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _project(repo):
    from asteria.editor import EditorDocument
    from asteria.project import Project

    path = Path(repo) / "reference_projects" / "complex_reference_rpg" / "project.asteria.json"
    return Project.load_json(path, EditorDocument().component_registry)


def scripted_boss_battle(repo, *, limit=400):
    """Every hero uses its first ability on the first living enemy; enemies act by their AI."""
    from asteria.runtime.battle_presentation_adapters import entry_semantics
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.game_session import GameSessionRuntime

    project = _project(repo)
    root = Path(repo) / "reference_projects" / "complex_reference_rpg"
    save = GameRuntimeSave.load_json(root / "saves" / "boss_stress.asteria-save.json", project)
    game = GameSessionRuntime(project, save)
    game.start_encounter("boss_room")
    log = list(game.drain_battle_log())
    actions = 0
    winner = None
    while actions < limit:
        hero, _ = game.run_enemy_turns()
        log.extend(game.drain_battle_log())
        if not game.active_hero_ids():
            winner = "enemies"
            break
        if not game.active_enemy_ids():
            winner = "heroes"
            break
        ability = game.battle.member(hero).ability_ids[0]
        target = game.active_enemy_ids()[0]
        game.execute(hero, ability, (target,))
        game.end_turn()
        actions += 1
        log.extend(game.drain_battle_log())
        if not game.active_enemy_ids():
            winner = "heroes"
            break
    knockout = game.rules.knockout_resource_id
    final = {
        m.member_id: round(m.subject.resources.current(knockout), 4)
        for party in game.battle.parties.values()
        for m in party.members
    }
    semantics = [entry_semantics(e) for e in log]
    return {
        "winner": winner,
        "hero_actions": actions,
        "log_entries": len(log),
        "log_digest": _digest(semantics),
        "final_knockout_resource": final,
    }


def save_digests(repo):
    from asteria.runtime.game_save import GameRuntimeSave

    project = _project(repo)
    saves = Path(repo) / "reference_projects" / "complex_reference_rpg" / "saves"
    result = {}
    for path in sorted(saves.glob("*.asteria-save.json")):
        if path.name.startswith("playtest_"):
            continue  # player-written, not reference data
        result[path.name] = _digest(GameRuntimeSave.load_json(path, project).to_data())
    return result


def regression_snapshot(repo):
    from asteria.validation.golden import run_golden_suite

    repo = Path(repo)
    golden = run_golden_suite(repo / "tests" / "golden" / "assets")
    return {
        "boss_battle": scripted_boss_battle(repo),
        "reference_saves": save_digests(repo),
        "rpg_database": _digest(_project(repo).rpg_database.to_data()),
        "golden_summary": _digest(golden.summaries),
    }
