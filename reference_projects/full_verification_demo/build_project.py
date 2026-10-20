"""Build the Full Verification demo: one hero against one boss, using the engine's systems
together.

A stress and showcase project, all ordinary project data (no engine code knows this game):
the hero fights as the Lucifer Warrior (Foozle, CC0) with three jobs, a deep
skill tree per job,
level-up stat points, job points, per-class growth, sockets (cards / gems), weapon growth and
+N refinement; the boss has phases, stances, summons, shields, statuses and counters.

Run: ``python reference_projects/full_verification_demo/build_project.py`` (writes this folder).
Play: ``.venv/bin/asteria-preview reference_projects/full_verification_demo/project.asteria.json``.
"""

from __future__ import annotations

import json
import shutil
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REFERENCE = REPO / "reference_projects" / "complex_reference_rpg"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "scripts"))

import trial_art as art  # noqa: E402
import trial_b11 as b11  # noqa: E402
import trial_b12 as b12  # noqa: E402
import trial_battle as battle_rules  # noqa: E402
import trial_brave as brave  # noqa: E402
import trial_cast as cast  # noqa: E402
import trial_classes as classes  # noqa: E402
import trial_content as content  # noqa: E402
import trial_extras as extras  # noqa: E402
import trial_gear as gear_plus  # noqa: E402
import trial_icons as icons  # noqa: E402
import trial_items as items  # noqa: E402
import trial_jobs as jobs  # noqa: E402
import trial_lucifer as lucifer  # noqa: E402
import trial_maps as maps  # noqa: E402
import trial_stage as stage  # noqa: E402
import trial_stats as stats  # noqa: E402
import trial_story as story  # noqa: E402
import trial_systems as systems  # noqa: E402
import trial_trees as trees  # noqa: E402
import trial_world as world_extras  # noqa: E402

from asteria.editor import EditorDocument  # noqa: E402
from asteria.project import Project  # noqa: E402


def main():
    import stable_ids

    stable_ids.install("asteria-boss-trial")
    target = HERE / "playable_assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(REFERENCE / "playable_assets", target)
    registry = EditorDocument().component_registry
    project = Project.load_json(REFERENCE / "project.asteria.json", registry)
    project.name = "Asteria Full Verification Demo"
    # its own id (it starts as a copy of the reference project, which has another one)
    project.id = str(uuid.uuid5(uuid.NAMESPACE_URL, "asteria://reference/full-verification-demo"))
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
    cast.party(context)
    classes.jobs(context)  # three-tier job lines and sub jobs for the companions
    brave.jobs(context)  # Aldric the Brave and Archmage: skills, passives, their trees
    trees.trees(context)  # the shared web, specs, runes and skill books
    cast.foes(context)
    gear_plus.forge(context)  # more gear, sets, gems, cards, refining, crafting
    brave.ring(context)  # the Demon Ring and its charms
    battle_rules.rules(context)  # every Battle category designed and used
    brave.foes(context)  # every foe far stronger; wind and earth weaknesses
    stage.abilities(context)  # input steps, slot-limited arts, field strikes
    world_extras.data(context)  # map areas, New Game Plus, translations, music room
    extras.systems(context)
    story.systems(context)
    maps.build_world(context, story.programs)
    art.hero_and_boss_art(context)
    art.effect_assets(context)
    art.prune_unused_art(context)
    content.presentation(context)
    stage.presentation(context)  # staging templates, command pages, input steps
    systems.fill(context)  # the editor's remaining sections, each used by the game
    brave.mechanics(context)  # weakness, crit, break, guard, dodge, states that are felt
    stats.stats(context)  # STR/DEX/INT/LUK, stat formulas, accuracy, elements, descriptions
    kept = art.weapon_icons(context)
    kept = (*kept, *lucifer.apply_icons(context))
    icons.apply_all(context)  # gear, items, gems, cards, jobs, passives, states
    icons.weapon_rarities(context)  # each weapon: the rarity its picture names
    brave.icons(context)  # the Demon Ring and the charms
    lucifer.apply_ui(context)
    lucifer.apply_music(context)
    import lucifer_reskin

    lucifer_reskin.paint_background("exterior", (960, 540), road=False, dim=0.45).save(
        HERE / "playable_assets" / "battle_background.png"
    )
    world_extras.backdrops(context)  # the bog, catacomb and throne battle backdrops
    content.finalize_names(context)
    content.game_start(context)
    path = HERE / "project.asteria.json"
    project.save_json(path)
    Project.load_json(path, registry)  # it must load back
    content.write_manifest(context)
    art.write_credits(HERE)
    from prune_orphan_assets import prune

    prune(HERE)  # the copied reference files this demo does not use
    from asteria.graphics.forged_icons import apply_to_project_file

    apply_to_project_file(path, replace=True, keep=kept)
    from center_cameras import center_file

    center_file(HERE)  # every scene's camera on the hero; the Player's place is the start
    db = project.rpg_database
    print(
        f"wrote {path.relative_to(REPO)}: {len(project.gameplay_library.abilities.ids())} "
        f"abilities, {len(db.classes)} jobs, {len(db.enemies)} enemies, "
        f"{sum(len(g.nodes) for g in db.progression_graphs.values())} tree nodes"
    )


if __name__ == "__main__":
    main()
    _ = json
