"""Names over heads stay by their owner and never cover a figure (its own included), they wait
while the camera is zoomed in, a menu's category row stays inside the menu, and every menu
cursor is drawn level with the text of its row."""

import pytest

from asteria.presentation import (
    BattleCombatantVisual,
    BattleHudGauge,
    BattleHudMember,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
    BattleUiLayoutProfile,
    BattleVisualAnchor,
)
from asteria.presentation.battle_ui import _category_strip
from asteria.runtime import Camera2D


def _scene(*anchors):
    return BattlePresentationScene(
        "battle.labels",
        "bg.arena",
        tuple(
            BattleCombatantVisual(name, f"{name}.sheet", f"{name}.clips", BattleVisualAnchor(x, y))
            for name, x, y in anchors
        ),
    )


def _members(*names):
    gauge = BattleHudGauge("hp", "HP", 50, 0, 100, 0, 0.5, False, None, 0)
    return tuple(BattleHudMember(name, (gauge,), ()) for name in names)


def _compose(scene, camera=None, **kw):
    composer = BattleUiComposer(scene, BattleUiLayoutProfile(overhead_zones=("left",)))
    names = [v.member_id for v in scene.combatants]
    composer.compose(
        camera or Camera2D(width=320, height=180),
        BattlePresentationFrame(scene.scene_id, "bg.arena", ()),
        hud_members=_members(*names),
        placement_by_member=dict.fromkeys(names, "left"),
        **kw,
    )
    return composer


def _clear(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay


def test_a_name_sits_just_over_its_figure_and_covers_no_figure():
    scene = _scene(("boss", 100, 140), ("imp", 200, 140))
    # the boss's visible pixels reach well above its listed height (a raised axe)
    extents = {"boss": (-30.0, -90.0, 30.0, 0.0), "imp": (-8.0, -20.0, 8.0, 0.0)}
    composer = _compose(scene, member_heights={"boss": 50.0, "imp": 20.0}, member_extents=extents)
    boxes = composer._combatant_boxes()
    for label in composer.overhead_labels.values():
        assert all(_clear(label, box) for box in boxes.values())
    x, y, w, h = composer.overhead_labels["boss"]
    _, top, _, tall = boxes["boss"]
    over = top - 16 <= y + h <= top  # just over the raised axe ...
    under = top + tall <= y <= top + tall + 12  # ... else just under the feet row
    assert over or under, (y, h, top, tall)
    assert abs(x + w / 2 - 100) <= w / 2 + 12  # by its owner, not off to one side


def test_a_name_with_no_clear_place_by_its_owner_is_not_shown():
    # a towering figure right under the turn bar, hemmed in below by another: nowhere near
    scene = _scene(("boss", 100, 150), ("wall", 100, 178))
    extents = {"boss": (-40.0, -140.0, 40.0, 0.0), "wall": (-60.0, -20.0, 60.0, 0.0)}
    composer = _compose(scene, member_extents=extents)
    assert "boss" not in composer.overhead_labels  # no name rather than one far away


def test_names_wait_while_the_camera_is_zoomed_in():
    scene = _scene(("boss", 100, 140))
    composer = _compose(scene, overhead_hidden=True)
    assert composer.overhead_labels == {}
    composer = _compose(scene, overhead_hidden=False)
    assert "boss" in composer.overhead_labels


def test_a_zoomed_camera_grows_the_figures_a_name_keeps_clear_of():
    scene = _scene(("boss", 160, 120))
    extents = {"boss": (-20.0, -40.0, 20.0, 0.0)}
    flat = _compose(scene, member_extents=extents)._combatant_boxes()["boss"]
    zoomed = _compose(
        scene, camera=Camera2D(x=80, y=45, width=320, height=180, zoom=1.5), member_extents=extents
    )._combatant_boxes()["boss"]
    assert zoomed[2] == pytest.approx(flat[2] * 1.5) and zoomed[3] > flat[3]


def test_the_category_row_keeps_inside_the_menu():
    names = ["Attack", "Skills", "Combo", "Limit"]
    for active in names:
        row = _category_strip(names, active, 90.0)
        assert len(row) * 3.8 <= 90.0 and f"[{active}]" in row
    assert _category_strip(names, "Combo", 400.0) == "Attack  Skills  [Combo]  Limit"
    assert _category_strip(names, "Combo", 90.0).startswith("< ")


def test_field_menu_cursors_sit_level_with_their_row(monkeypatch):
    pygame = pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    pygame.init()
    runtime = PlayableTestRuntime.__new__(PlayableTestRuntime)
    runtime.pg = pygame
    runtime._fonts, runtime._cjk_fonts, runtime._glyphs = {}, {}, {}
    for size in (21, 24, 30):
        runtime.screen = pygame.Surface((400, 120))
        runtime.menu_row("HUGE", 20, 30, selected=True, size=size, color=(255, 0, 0))

        def rows(x0, x1):
            return [
                y
                for y in range(120)
                if any(runtime.screen.get_at((x, y))[:3] == (255, 0, 0) for x in range(x0, x1))
            ]

        room = runtime.menu_mark_room(size)
        mark, text = rows(20, 20 + room - 2), rows(20 + room, 400)
        assert abs((mark[0] + mark[-1]) / 2 - (text[0] + text[-1]) / 2) <= 1.0, size
