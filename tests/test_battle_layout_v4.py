"""UI_PLAN_2 V4: the battle screen as layout data (``battle``): each group the composer lays
out - party cards, overhead names, command menu, help, step lists, timeline, numbers, result,
target cursor - moved, sized, restyled or hidden as one, plus the author's own pieces; and
without a layout, the very frame the composer made."""

from pathlib import Path

import pytest

from asteria.presentation.battle_layout import BattleScreenLayout
from asteria.presentation.battle_ui import BattleUiPanel, BattleUiText
from asteria.presentation.menu_layout import MenuElement, MenuLayout

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "octopath_demo"
PURPLE, GOLD = (30, 0, 60, 255), (200, 160, 0, 255)


# --- the data step alone ---------------------------------------------------------------------
def _lists(*panels, texts=()):
    lists = {k: [] for k in ("panel", "text", "gauge", "icon", "portrait", "marker")}
    lists["panel"] = [p for p, _g in panels]
    lists["text"] = [t for t, _g in texts]
    tags = {k: [] for k in lists}
    tags["panel"] = [g for _p, g in panels]
    tags["text"] = [g for _t, g in texts]
    return lists, tags


def test_a_group_moves_and_scales_as_one_and_its_words_follow():
    lists, tags = _lists(
        (BattleUiPanel("menu", 200, 100, 80, 60, "interaction:menu"), "menu"),
        (BattleUiPanel("button:0", 204, 110, 72, 10, "button:selected"), "menu"),
        texts=[(BattleUiText("Attack", 210, 112), "menu")],
    )
    layout = MenuLayout(
        "battle",
        (MenuElement("menu", "list", rect=(10, 20, 160, 0), fill=PURPLE, selection_fill=GOLD),),
    )
    screen = BattleScreenLayout(layout, (320, 180))
    out = screen.apply(lists, tags)
    frame, row = out["panel"]
    assert (frame.x, frame.y, frame.width, frame.height) == (10, 20, 160, 60)  # 2x wide
    assert frame.fill == PURPLE and frame.skin is False  # the author's colour, no theme picture
    assert (row.x, row.width, row.fill) == (18, 144, GOLD)  # the chosen row's own look
    assert (out["text"][0].x, out["text"][0].y) == (30, 32)
    assert screen.boxes["menu"] == (10, 20, 160, 60)


def test_one_party_card_is_placed_on_its_own_after_its_group():
    lists, tags = _lists(
        (BattleUiPanel("hud:a", 240, 30, 70, 40, "hud", "hana"), "party_hud"),
        (BattleUiPanel("hud:b", 240, 80, 70, 40, "hud", "ren"), "party_hud"),
        (BattleUiPanel("hud:c", 240, 130, 70, 40, "hud", "sol"), "party_hud"),
        texts=[
            (BattleUiText("Hana", 244, 34, member_id="hana"), "party_hud"),
            (BattleUiText("Ren", 244, 84, member_id="ren"), "party_hud"),
        ],
    )
    layout = MenuLayout(
        "battle",
        (
            MenuElement("party_hud", "panel", rect=(200, 30, 0, 0)),  # all 40 to the left
            MenuElement("party_hud.2", "panel", rect=(10, 10, 140, 0), fill=PURPLE),
            MenuElement("party_hud.3", "panel", visible=False),
        ),
    )
    screen = BattleScreenLayout(layout, (320, 180))
    out = screen.apply(lists, tags)
    first, second = out["panel"]  # the third card is hidden
    assert (first.x, first.y) == (200, 30)  # moved with its group
    assert (second.x, second.y, second.width, second.height) == (10, 10, 140, 40)
    assert second.fill == PURPLE  # its own look
    assert [(t.text, t.x, t.y) for t in out["text"]] == [("Hana", 204, 34), ("Ren", 18, 14)]
    assert screen.boxes["party_hud.1"] == (200, 30, 70, 40)  # outlined for the editor
    assert screen.boxes["party_hud.2"] == (10, 10, 140, 40)


def test_without_card_elements_the_cards_stay_as_their_group_left_them():
    lists, tags = _lists(
        (BattleUiPanel("hud:a", 240, 30, 70, 40, "hud", "hana"), "party_hud"),
        (BattleUiPanel("hud:b", 240, 80, 70, 40, "hud", "ren"), "party_hud"),
    )
    layout = MenuLayout("battle", (MenuElement("party_hud", "panel", rect=(200, 30, 0, 0)),))
    out = BattleScreenLayout(layout, (320, 180)).apply(lists, tags)
    assert [(p.x, p.y) for p in out["panel"]] == [(200, 30), (200, 80)]


def test_hidden_groups_go_and_the_authors_pieces_come():
    lists, tags = _lists(
        (BattleUiPanel("turn:0", 100, 4, 120, 16, "timeline"), "timeline"),
        (BattleUiPanel("card", 240, 30, 70, 40, "hud"), "party_hud"),
    )
    layout = MenuLayout(
        "battle",
        (
            MenuElement("timeline", "panel", visible=False),
            MenuElement(
                "extra.title",
                "text",
                rect=(0, 2, 320, 12),
                text="key:boss.title|Boss",
                align="center",
                color=(255, 0, 0),
                size=14,
            ),
            MenuElement("extra.back", "panel", rect=(0, 0, 320, 20), fill=PURPLE, layer=-1),
        ),
    )
    words = BattleScreenLayout(layout, (320, 180), lambda key, english: f"<{english}>")
    out = words.apply(lists, tags)
    assert [p.panel_id for p in out["panel"]] == ["extra.back", "card"]  # under the rest
    title = out["text"][-1]
    assert (title.text, title.x, title.align, title.color, title.size) == (
        "<Boss>", 160, "center", (255, 0, 0), 14,
    )  # fmt: skip


# --- the real battle -------------------------------------------------------------------------
@pytest.fixture(scope="module")
def battle():
    pytest.importorskip("pygame")
    mp = pytest.MonkeyPatch()
    for name, value in (("SDL_VIDEODRIVER", "dummy"), ("SDL_AUDIODRIVER", "dummy"),
                        ("ASTERIA_MUTE", "1")):  # fmt: skip
        mp.setenv(name, value)
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    rt.game.start_encounter("boss_room")
    rt._battle_presentation.begin()
    rt._advance_to_hero_turn()
    for _ in range(260):
        rt._frame([], 1 / 60)
    yield rt
    rt.close()
    mp.undo()


def _frame(rt):
    """The UI frame the battle draws next, and its pixels."""
    adapter = rt._battle_presentation
    seen = []
    renderer = adapter.renderer
    original = renderer.render
    renderer.render = lambda frame: seen.append(frame) or original(frame)
    try:
        rt.screen.fill((0, 0, 0))
        adapter.draw()
    finally:
        renderer.render = original
    return seen[-1], rt.pg.image.tobytes(rt.screen, "RGB")


def _layout(rt, layout):
    rt.project.battle_presentation_library.set("menu_layout", "battle", layout)


def test_without_a_layout_the_frame_is_the_composers(battle):
    battle.project.battle_presentation_library._records.get("menu_layout", {}).pop("battle", 0)
    first, pixels = _frame(battle)
    composer = battle._battle_presentation.screen.composer
    assert composer.screen_layout is None and composer.layout_boxes == {}
    again, same = _frame(battle)
    assert again == first and same == pixels
    # an empty layout (the editor's preview) says where the groups are and changes nothing
    _layout(battle, MenuLayout("battle", ()))
    laid, laid_pixels = _frame(battle)
    assert laid == first and laid_pixels == pixels
    assert {"party_hud", "menu", "timeline"} <= set(composer.layout_boxes)


def test_the_layout_moves_restyles_and_hides_the_battles_groups(battle):
    _layout(
        battle,
        MenuLayout(
            "battle",
            (
                MenuElement("menu", "list", rect=(10, 10, 0, 0), fill=PURPLE, selection_fill=GOLD),
                MenuElement("timeline", "panel", visible=False),
                MenuElement(
                    "extra.title",
                    "text",
                    rect=(100, 4, 120, 12),
                    text="Boss fight",
                    color=(255, 80, 80),
                    size=14,
                ),
            ),
        ),
    )
    frame, _pixels = _frame(battle)
    composer = battle._battle_presentation.screen.composer
    assert composer.layout_boxes["menu"][:2] == (10, 10)
    assert not any(p.panel_id.startswith("turn:") for p in frame.panels)
    assert any(p.fill == PURPLE for p in frame.panels)
    assert any(t.text == "Boss fight" and t.size == 14 for t in frame.texts)
    unit = battle._menu_units["battle"]  # 960 / 480 (the demo's battle size): two pixels
    assert unit == pytest.approx(960 / composer.layout.virtual_width)
    assert battle._menu_boxes["battle"]["menu"][:2] == (round(10 * unit), round(10 * unit))
    assert battle.screen.get_at((round(14 * unit), round(40 * unit)))[:3] == PURPLE[:3]
    battle.project.battle_presentation_library._records["menu_layout"].pop("battle")


def test_the_editor_preview_opens_a_battle_and_measures_it_in_battle_units():
    pytest.importorskip("pygame")
    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.menu_preview import MenuPreview

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    preview = MenuPreview(project, ROOT, size=(960, 540))
    try:
        surface, boxes = preview.render("battle", "en")
        assert surface.get_size() == (960, 540) and preview.unit == pytest.approx(2.0)
        assert {"party_hud", "menu"} <= set(boxes)
        _surface, after = preview.render("pause", "en")  # the preview's fight is left behind
        assert preview.runtime.game.mode == "field" and "options" in after
    finally:
        preview.close()
