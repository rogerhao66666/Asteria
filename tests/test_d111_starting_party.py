"""D111: a character's page says whether they are in the starting party and changes it; the
party itself stays in Game Start ▸ Party, which the page opens. complex_reference_rpg has no
``actor.*`` / ``roster.*`` labels left either."""

import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

REPO = Path(__file__).resolve().parents[1]
COMPLEX = REPO / "reference_projects" / "complex_reference_rpg"
sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture(scope="module")
def app():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _line(family):
    return family.editor.starting_party


def _party(family):
    return family.document.project.game_start.rpg_state_data["party_actor_ids"]


def test_the_switch_shows_and_changes_the_starting_party(app):
    from test_d109_gear_wearers import _family

    family = _family("actors", "hero_04")  # Cael joins later
    line = _line(family)
    before = list(_party(family))
    assert "hero_04" not in before and not line.check.isChecked()
    line.check.setChecked(True)
    assert _party(family) == [*before, "hero_04"]  # at the end
    family.document.undo()
    assert _party(family) == before
    family.editor.set_record(family.editor.record(), family.editor._title,
                             optional=family.editor.optional)  # fmt: skip
    assert not line.check.isChecked()  # read again after the undo
    family.select_ids(["hero_01"])
    line = _line(family)
    assert line.check.isChecked()
    line.check.setChecked(False)  # Roger had a battle place: it goes with him
    assert "hero_01" not in _party(family) and not line.error.isVisibleTo(line)
    state = family.document.project.game_start.rpg_state_data
    assert "hero_01" not in state.get("party_placements", {})


def test_a_change_game_start_refuses_is_said_and_undone(app):
    from test_d109_gear_wearers import _family

    family = _family("actors", "hero_01")
    line = _line(family)
    controller_apply = "asteria.editor.rpg.game_start_authoring.GameStartAuthoringController"
    with pytest.MonkeyPatch.context() as patch:

        def refuse(self, data):
            raise ValueError("no")

        patch.setattr(f"{controller_apply}.apply", refuse)
        line.check.setChecked(False)
    assert line.check.isChecked() and "no" in line.error.text()


def test_other_pages_have_no_switch(app):
    from test_d109_gear_wearers import _family

    assert _family("equipment", "w_sunbrand").editor.starting_party is None


def test_the_button_opens_game_start_party(app):
    from test_d109_gear_wearers import _family

    line = _line(_family("actors", "hero_01"))
    opened = []
    line.window().navigate_to_problem = lambda problem: opened.append(problem.target)
    line.open_button.click()
    assert opened == [("game_start", "Party")]


def test_game_start_opens_a_card_it_is_sent_to(app):
    from test_d110_starting_equipment import _page

    page = _page()
    page.form.cards["Party"].set_open(False)
    assert page.show_card("Party") and page.form.cards["Party"].is_open()
    assert not page.show_card("Nowhere")


def test_the_switch_in_chinese(app):
    from asteria.editor.records.starting_party_line import HELP
    from asteria.editor.ui.i18n import set_language, translate

    set_language("zh_TW")
    try:
        assert translate("In the starting party") == "在初始隊伍"
        assert translate("Game Start ▸ Party") == "遊戲開始 ▸ 隊伍"
        assert translate(HELP).startswith("勾選")
    finally:
        set_language("en")


def test_complex_reference_rpg_has_no_actor_kind_or_roster_labels():
    found = []
    for path in sorted(COMPLEX.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        if '"actor.' in text or '"roster.' in text or "data.tag.actor." in text:
            found.append(path.relative_to(REPO).as_posix())
    assert not found
    db = json.loads((COMPLEX / "project.asteria.json").read_text(encoding="utf-8"))
    assert db["rpg_database"]["actors"]
