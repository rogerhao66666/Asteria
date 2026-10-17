"""Build the Boss Trial demo: one hero against one boss, using the engine's systems together.

A stress and showcase project, all ordinary project data (no engine code knows this game):
the hero fights as the animated NinjaGreen (Ninja Adventure, CC0) with three jobs, a deep
skill tree per job,
level-up stat points, job points, per-class growth, sockets (cards / gems), weapon growth and
+N refinement; the boss has phases, stances, summons, shields, statuses and counters.

Run: ``python reference_projects/boss_trial_demo/build_project.py`` (writes this folder).
Play: ``.venv/bin/asteria-preview reference_projects/boss_trial_demo/project.asteria.json``.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REFERENCE = REPO / "reference_projects" / "complex_reference_rpg"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))

import trial_art as art  # noqa: E402
import trial_b11 as b11  # noqa: E402
import trial_b12 as b12  # noqa: E402
import trial_content as content  # noqa: E402
import trial_items as items  # noqa: E402
import trial_jobs as jobs  # noqa: E402

from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402


def main():
    target = HERE / "playable_assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(REFERENCE / "playable_assets", target)
    registry = EditorDocument().component_registry
    project = Project.load_json(REFERENCE / "project.asteria.json", registry)
    project.name = "Asteria Boss Trial Demo"
    context = content.Context(project, HERE)
    content.strip_reference(context)
    content.rules_and_statuses(context)
    content.gear(context)
    content.hero_jobs_and_trees(context)
    content.hero_skills(context)
    jobs.advanced_jobs(context)
    content.boss(context)
    b11.companion(context)
    items.items_and_alchemy(context)
    items.counters(context)
    b12.systems(context)
    content.world(context)
    art.hero_and_boss_art(context)
    art.effect_assets(context)
    art.prune_unused_art(context)
    content.presentation(context)
    kept = art.weapon_icons(context)
    content.finalize_names(context)
    content.game_start(context)
    path = HERE / "project.asteria.json"
    project.save_json(path)
    Project.load_json(path, registry)  # it must load back
    content.write_manifest(context)
    art.write_credits(HERE)
    from asteria.graphics.forged_icons import apply_to_project_file

    apply_to_project_file(path, replace=True, keep=kept)
    db = project.rpg_database
    print(
        f"wrote {path.relative_to(REPO)}: {len(project.gameplay_library.abilities.ids())} "
        f"abilities, {len(db.classes)} jobs, {len(db.enemies)} enemies, "
        f"{sum(len(g.nodes) for g in db.progression_graphs.values())} tree nodes"
    )


if __name__ == "__main__":
    main()
    _ = json
