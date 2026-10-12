"""CMP-03: generic animated text in the running game - item gains, a full bag and authored SHOW_POPUP lines
rise and fade above field characters (AnimatedTextRuntime + AnimatedTextRenderComposer)."""

import pytest

pygame = pytest.importorskip("pygame")

from asteria.core import Transform  # noqa: E402
from asteria.events import EventInstruction, EventProgram  # noqa: E402
from asteria.rpg.items import InventoryRules  # noqa: E402


def _run(runtime, *instructions):
    runtime.game.project.event_programs.register("popup_test", EventProgram(tuple(instructions)))
    runtime.game.events.start("popup_test")


def _frames(runtime, count, dt=0.05):
    for _ in range(count):
        runtime._frame([], dt)


def test_item_gains_and_authored_popups_rise_and_fade_above_characters(runtime):
    runtime._ui_mode = "field"
    db = runtime.game.project.rpg_database
    item_id = sorted(db.items)[0]
    name = db.items[item_id].display_name
    _run(
        runtime,
        EventInstruction("WORLD", {"command": "GIVE_ITEM", "args": {"item_id": item_id, "quantity": 2}}),
        EventInstruction("WORLD", {"command": "SHOW_POPUP", "args": {"text": "!?", "entity": "Astral Tyrant"}}),
    )
    _frames(runtime, 2)
    texts = {r.text: r for r in runtime.popup_frame}
    assert f"+2 {name}" in texts and "!?" in texts
    assert texts["!?"].anchor_id == "Astral Tyrant"
    boss = next(e for e in runtime.game.scene.entities() if e.name == "Astral Tyrant").get(Transform)
    bx, by = runtime._popup_anchor("Astral Tyrant")
    assert (bx, by + 48 * runtime.field_camera.zoom) == pytest.approx(runtime._field_screen_xy(boss.x, boss.y))
    first = texts[f"+2 {name}"].transform.y
    _frames(runtime, 6)
    later = {r.text: r for r in runtime.popup_frame}[f"+2 {name}"].transform
    assert later.y < first and 0.0 < later.opacity <= 1.0  # rising, then fading
    runtime._draw_field(False)  # the popups are drawn with the field
    _frames(runtime, 30)
    assert not runtime.popup_frame  # gone when their time is up


def test_a_full_bag_says_so(runtime):
    runtime._ui_mode = "field"
    game = runtime.game
    db = game.project.rpg_database
    item_id = sorted(db.items)[0]
    game.save.rpg_state.inventory.configure(InventoryRules("bag", max_kinds=1), db.items.get)
    held = [i for i in sorted(db.items) if game.save.rpg_state.inventory.count(i)]
    other = next(i for i in sorted(db.items) if i not in held and i != item_id) if held else item_id
    if not held:
        game.save.rpg_state.inventory.add(item_id, 1)
        other = next(i for i in sorted(db.items) if i != item_id)
    _run(runtime, EventInstruction("WORLD", {"command": "GIVE_ITEM", "args": {"item_id": other, "quantity": 1}}))
    _frames(runtime, 2)
    assert any(r.text.startswith("No room for") for r in runtime.popup_frame)
