"""D89: a stat window in the manner of MapleStory's - the Status page's stat table (rank, total,
base, points, gear, each +), its detail table of groups and lines (number, percent, range,
chance), penetration, and Game Systems ▸ Menu Pages' detail table fields."""

import sys
from pathlib import Path

import pytest
from test_session_events import _project

from asteria.editor import EditorDocument
from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
from asteria.gameplay.formulas import FormulaContext, FormulaTerm, ValueFormula
from asteria.gameplay.stats import ResourcePool, StatBlock
from asteria.gameplay.tags import TagSet
from asteria.rpg.interactions import OutcomeCheckDefinition
from asteria.rpg.menu_rules import MenuRules, StatGroup, StatLine

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
RULES = MenuRules(
    "pages",
    "Pages",
    stat_groups=(StatGroup("attack", "Attack"), StatGroup("battle", "Battle")),
    stat_lines=(
        StatLine("power", "attack", "range", 10.0),
        StatLine("crit", "attack", "chance", check="crit"),
        StatLine("speed", "battle", label="Action Speed"),
    ),
)


def test_a_stat_line_writes_numbers_percents_ranges_and_chances():
    assert StatLine("defense").text(299.0) == "299"
    assert StatLine("boss_damage", format="percent").text(12.5) == "12.5%"
    assert StatLine("power", format="range", spread=10.0).text(200.0) == "180 ~ 220"
    crit = OutcomeCheckDefinition(
        "crit", 0.05, source_stat_terms={"crit": 0.003}, maximum_chance=0.65
    )
    line = StatLine("crit", format="chance", check="crit")
    assert line.text(50.0, crit) == "20%"  # 5% + 50 x 0.3%
    assert line.text(500.0, crit) == "65%"  # never past the check's highest chance
    evade = OutcomeCheckDefinition("land", 0.95, target_stat_terms={"evade": -0.003})
    assert StatLine("evade", format="chance", check="land").text(100.0, evade) == "30%"
    with pytest.raises(ValueError, match="outcome check"):
        StatLine("crit", format="chance")
    with pytest.raises(ValueError, match="format"):
        StatLine("crit", format="stars")
    with pytest.raises(ValueError, match="spread"):
        StatLine("power", format="range", spread=100.0)


def test_menu_pages_keep_their_groups_and_lines():
    assert MenuRules.from_data(RULES.to_data()) == RULES
    assert RULES.stat_groups[0].display_name == "Attack"
    assert StatGroup("misc").display_name == "misc"  # no name: its id


def _page():
    """D96: the detail table is a Stat Details block of a menu page."""
    from asteria.rpg.menu_pages import MenuBlock, MenuPage

    block = MenuBlock(
        "stat_details", "right", stat_groups=RULES.stat_groups, stat_lines=RULES.stat_lines
    )
    return MenuPage("pages", "Pages", blocks=(block,))


def test_the_detail_table_survives_the_editor_form():
    document = EditorDocument(_project())
    api = GameSystemsAuthoringController(document)
    api.create("menu_pages", _page())
    data = api.form_data("menu_pages", "pages")
    lines = data["blocks"][0]["stat_lines"]
    assert lines[0]["format"] == "range" and lines[2]["check"] == ""
    api.edit("menu_pages", "pages", data)
    assert api.get("menu_pages", "pages") == _page()


def test_the_editor_words_the_detail_table_in_chinese():
    import json

    from asteria.editor.game_systems_authoring import _MENU_BLOCK

    path = Path(__file__).resolve().parents[1] / "src/asteria/editor/translations/zh_TW.json"
    words = json.loads(path.read_text(encoding="utf-8"))["exact"]
    fields = {f.key: f for f in _MENU_BLOCK}
    labels = [fields["stat_groups"].label, fields["stat_lines"].label, "Penetration Stat"]
    for key in ("stat_groups", "stat_lines"):
        labels += [f.label for f in fields[key].fields]
    assert [w for w in labels if w not in words] == []


def _context(defense, scale):
    return FormulaContext(
        StatBlock({"power": 100.0}),
        ResourcePool(),
        TagSet(),
        StatBlock({"defense": defense}),
        ResourcePool(),
        TagSet(),
        target_stat_scale=scale,
    )


def test_penetration_takes_its_share_off_the_targets_stats():
    from asteria.gameplay.abilities import _formula_context
    from asteria.gameplay.conditions import GameplaySubject

    damage = ValueFormula(
        (FormulaTerm("source_stat", "power", 3.0), FormulaTerm("target_stat", "defense", -1.0))
    )
    assert damage.evaluate(_context(100.0, 1.0)) == 200.0
    assert damage.evaluate(_context(100.0, 0.7)) == 230.0  # 30% of the defence ignored
    source = GameplaySubject(StatBlock({"penetration": 30.0}), ResourcePool(), TagSet())
    target = GameplaySubject(StatBlock({"defense": 50.0}), ResourcePool(), TagSet())
    assert _formula_context(source, target, penetration="penetration").target_stat_scale == 0.7
    assert _formula_context(source, target).target_stat_scale == 1.0  # no penetration stat
    over = GameplaySubject(StatBlock({"penetration": 250.0}), ResourcePool(), TagSet())
    assert _formula_context(over, target, penetration="penetration").target_stat_scale == 0.0
    assert _formula_context(source, source, penetration="penetration").target_stat_scale == 1.0


def test_battle_rules_name_the_penetration_stat():
    from asteria.rpg.battle_session_rules import BattleSessionRules

    rules = BattleSessionRules("r", penetration_stat="penetration")
    assert rules.to_data()["penetration_stat"] == "penetration"
    assert BattleSessionRules.from_data(rules.to_data()) == rules
    assert "penetration_stat" not in BattleSessionRules("r").to_data()


# -- the Full Verification demo's stat window -------------------------------------------------
@pytest.fixture
def host(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    sys.path.insert(0, str(DEMO))
    import trial_ui_tour

    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=960, height=540
    )
    runtime.open()
    trial_ui_tour.prepare(runtime.game)
    yield runtime
    runtime.close()


def test_the_stat_table_splits_each_stat_by_where_it_comes_from(host):
    host._open_pause_page("status")
    menu = host.status_menu
    rows = {r.stat_id: r for r in menu.stat_rows()}
    for row in rows.values():
        assert row.value == pytest.approx(row.base + row.points + row.gear), row.stat_id
    assert rows["vitality"].gain == 100.0 and rows["technique"].gain == 30.0  # HP / MP points
    assert rows["vit"].gain == 1.0
    hp = rows["vitality"].value
    menu.row = list(rows).index("vitality")
    assert menu.activate() is True
    assert {r.stat_id: r for r in menu.stat_rows()}["vitality"].value == hp + 100.0


def test_the_detail_table_has_its_groups_and_writes_each_line_its_way(host):
    host._open_pause_page("status")
    groups = dict(host.status_menu.detail_groups())
    assert list(groups) == ["Attack", "Defence", "Battle", "Element Attack", "Element Resistance"]
    attack = {line.stat_id: line for line in groups["Attack"]}
    assert " ~ " in attack["power"].text  # attack floats 10% either way: a range
    assert attack["crit"].text.endswith("%") and attack["penetration"].text.endswith("%")
    assert not attack["penetration"].label.endswith("%")  # the value carries the %
    battle = {line.stat_id: line for line in groups["Battle"]}
    assert battle["bp_power"].text.startswith("1")  # 100% a BP and up
    gear = [line for lines in groups.values() for line in lines if line.gear]
    assert gear  # the worn pieces add penetration, damage, VIT...


def test_the_status_page_draws_the_two_tables_in_chinese(host):
    host.game.set_locale("zh-TW")
    host._open_pause_page("status")
    drawn = []
    original = host.text

    def catch(value, *args, **kwargs):
        drawn.append(str(value))
        return original(value, *args, **kwargs)

    host.text = catch
    with host.menu_fit():
        host._draw_status_menu()
    words = " ".join(drawn)
    for word in ("總計", "基礎", "加點", "裝備", "攻擊", "屬性抗性", "穿透", "每 BP 技能強化"):
        assert word in words, word


@pytest.fixture
def window():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow

    app = QApplication.instance() or QApplication([])
    value = AsteriaEditorWindow(_project())
    yield value
    value.document.mark_saved()
    value.close()
    app.processEvents()


def test_the_menu_pages_form_edits_the_detail_table(window):
    editor = window.game_systems_editor
    api = editor.controller
    api.create("menu_pages", _page())
    editor.set_kind("pause_menu")  # D97: a page is a row of the Pause Menu
    editor.refresh("page:pages")
    assert editor.apply(), editor.status.text()
    assert api.get("menu_pages", "pages") == _page()
    blocks = editor.pause.form.widgets["blocks"]
    lines = blocks.detail.widgets["stat_lines"]
    row = {"stat_id": "defense", "group": "battle", "format": "percent", "spread": 0.0}
    lines.set_rows([*lines.values(), {**row, "label": "Guard", "check": ""}])
    assert editor.apply(), editor.status.text()
    added = api.get("menu_pages", "pages").blocks[0].stat_lines[-1]
    assert (added.stat_id, added.group, added.format, added.label) == (
        "defense",
        "battle",
        "percent",
        "Guard",
    )


def test_the_stat_table_shows_the_columns_menu_pages_tick():
    from asteria.runtime.playtest.menu_pages import MenuPagesMixin

    assert MenuRules("m").columns() == ("rank", "total", "base", "points", "gear", "gain")
    rules = MenuRules("m", stat_columns=("total", "gain"))
    assert MenuRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError, match="unknown stat table columns"):
        MenuRules("m", stat_columns=("stars",))

    class Menu:
        pass

    menu = Menu()
    menu.rules = rules
    assert MenuPagesMixin._stat_columns(menu) == [("total", 108), ("gain", 54)]  # no gap


def test_the_demo_hides_the_rank_column(host):
    host._open_pause_page("status")
    host.pointer.drawn.clear()
    drawn = []
    original = host.text

    def catch(value, *args, **kwargs):
        drawn.append(str(value))
        return original(value, *args, **kwargs)

    host.text = catch
    with host.menu_fit():
        host._draw_status_menu()
    assert "Rank" not in drawn and "Total" in drawn
    assert "Each +" not in drawn  # D98: the demo hides the gain column too
