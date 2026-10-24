"""Every menu screen of the Full Verification demo in Chinese draws no ids and no English (U1).

Each screen of ``trial_ui_tour`` is opened and drawn one frame with the player's language set
to zh-TW; every text the screen draws is caught on its way to ``runtime.text``. A drawn word
that is a database id (``hero_01``, ``fire_attack``, a socket's ``s1``, a quest objective's
``acolytes``) or an English word outside the few that stay (key names, the title) fails.
"""

import re
import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

# words a Chinese screen may still show: keys, units and the game's own title
KEPT = {
    "ASTERIA", "RPG", "Enter", "Esc", "Tab", "Shift", "Space", "Delete", "Backspace", "WASD",
    "Up", "Down", "Left", "Right", "Ctrl", "Alt", "Return", "Escape", "PageUp", "PageDown",
    "Lv", "HP", "MP", "SP", "AP", "JP", "EXP", "STR", "DEX", "INT", "LUK", "VIT", "Wheel",
}  # fmt: skip
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
FUNCTION_KEY = re.compile(r"^F\d{1,2}$")
SKIPPED = {"title", "backlog"}  # the game's own name; the log keeps lines as they were said
NAMES_ONLY = {"credits"}  # pack and tool names stay as written: only ids are looked for
COUNT = re.compile(r"^x\d+$")  # "x3" in a quantity column


def _ids(project):
    from asteria.editor.data_translation import stat_ids

    db = project.rpg_database
    ids = set(db.actors) | set(db.classes) | set(db.quests) | set(db.enemies)
    ids |= set(db.items) | set(db.equipment) | set(db.pet_species) | set(stat_ids(project))
    ids |= {o.objective_id for q in db.quests.values() for o in q.objectives}
    ids |= {s.socket_id for e in db.equipment.values() for s in e.sockets}
    ids |= {str(e.slot) for e in db.equipment.values()}
    return {i for i in ids if i}


@pytest.fixture
def host(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    yield runtime
    runtime.close()


def test_every_menu_screen_in_chinese_draws_no_ids_or_english(host):
    import trial_ui_tour

    game = host.game
    trial_ui_tour.prepare(game)
    game.set_locale("zh-TW")
    ids = _ids(host.project)
    drawn = []
    original = host.text

    def catch(value, *args, **kwargs):
        drawn.append((screen, str(value)))
        return original(value, *args, **kwargs)

    host.text = catch
    found = []
    for screen, setup in trial_ui_tour.screens(host):
        if screen in SKIPPED:
            continue
        setup()
        host._frame([], 0.016)
        for _ in range(3):
            host._frame([], 0.016)
        trial_ui_tour.reset(host)
    for screen, text in drawn:
        for word in WORD.findall(text):
            if FUNCTION_KEY.match(word) or COUNT.match(word) or word in KEPT and word not in ids:
                continue
            if screen in NAMES_ONLY and word not in ids:
                continue
            if word in ids or len(word) > 1:
                found.append((screen, word, text))
    found = sorted(set(found))
    assert not found, "\n".join(f"{s}: {w!r} in {t!r}" for s, w, t in found[:80])
