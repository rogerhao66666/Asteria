"""Real-window check of the Lucifer-dressed party demos: a battle at the hero's turn in a real
window (Cocoa on a Mac), a screenshot of it and of the field.

    python scripts/reskin_live_check.py OUT_DIR
"""

import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from asteria.editor import EditorDocument  # noqa: E402
from asteria.editor.project_templates import create_from_template  # noqa: E402
from asteria.project import Project  # noqa: E402
from asteria.runtime.playable_test_runtime import PlayableTestRuntime  # noqa: E402


def shoot(root, encounter, out, name):
    project = Project.load_json(root / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=960, height=540
    )
    runtime.open()
    pg = runtime.pg
    runtime._ui_mode = "field"
    for _ in range(90):
        runtime._frame(pg.event.get(), 1 / 60)
        runtime.present()
    pg.image.save(pg.display.get_surface(), str(out / f"{name}_field.png"))
    runtime.game.start_encounter(encounter)
    runtime._battle_presentation.begin()
    runtime._advance_to_hero_turn()
    for _ in range(420):
        runtime._frame(pg.event.get(), 1 / 60)
        runtime.present()
    pg.image.save(pg.display.get_surface(), str(out / f"{name}_battle.png"))
    driver = pg.display.get_driver()
    runtime.close()
    return driver


def main(argv):
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    demos = REPO / "reference_projects"
    drivers = {
        "octopath": shoot(demos / "octopath_demo", "boss_room", out, "octopath"),
        "reference": shoot(demos / "complex_reference_rpg", "boss_room", out, "reference"),
    }
    basic = create_from_template("basic_rpg", "Basic", Path(tempfile.mkdtemp()) / "basic")
    drivers["basic"] = shoot(basic.parent, "old_crypt", out, "basic")
    print(drivers)


if __name__ == "__main__":
    main(sys.argv)
