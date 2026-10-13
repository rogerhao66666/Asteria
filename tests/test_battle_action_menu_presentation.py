from asteria.presentation import (
    BattleActionEntry,
    BattleActionMenuPolicy,
    BattleActionMenuRuntime,
    BattlePresentationFrame,
    BattlePresentationScene,
    BattleUiComposer,
)
from asteria.runtime import Camera2D


def _entries():
    return (
        BattleActionEntry(
            "slash", "Slash", category="weapon", kind="ability", order=10, cost_text="3 SP"
        ),
        BattleActionEntry("guard", "Guard", category="stance", kind="command", order=20),
        BattleActionEntry(
            "fire",
            "Fire",
            category="magic",
            kind="ability",
            order=30,
            cost_text="8 MP",
            tags=("fire",),
        ),
        BattleActionEntry(
            "heal", "Heal", category="magic", kind="ability", order=40, cost_text="6 MP"
        ),
        BattleActionEntry(
            "mix",
            "Concoct",
            category="craft",
            kind="workflow",
            order=50,
            detail="Combine ingredients",
        ),
        BattleActionEntry("summon", "Summon", category="special", kind="workflow", order=60),
        BattleActionEntry(
            "locked",
            "Forbidden Art",
            category="special",
            kind="ability",
            order=70,
            enabled=False,
            disabled_reason="Requires Overdrive",
        ),
        BattleActionEntry(
            "bomb", "Bomb", category="item", kind="item", order=80, search_terms=("explosive",)
        ),
    )


def test_menu_is_generic_and_has_no_hardcoded_command_set():
    runtime = BattleActionMenuRuntime(BattleActionMenuPolicy(page_size=4))
    view = runtime.set_entries(_entries())
    assert view.total_count == 8
    assert {x.kind for x in _entries()} >= {"ability", "command", "workflow", "item"}
    assert "Attack" not in [x.label for x in _entries()]
    assert view.categories[0] == "all"


def test_large_action_collection_supports_categories_pages_and_search():
    runtime = BattleActionMenuRuntime(BattleActionMenuPolicy(page_size=3))
    runtime.set_entries(_entries())
    assert runtime.view.page_count == 3
    assert [x.action_id for x in runtime.view.entries] == ["slash", "guard", "fire"]

    runtime.set_page(1)
    assert [x.action_id for x in runtime.view.entries] == ["heal", "mix", "summon"]

    runtime.set_category("magic")
    assert [x.action_id for x in runtime.view.entries] == ["fire", "heal"]
    assert runtime.view.page_count == 1

    runtime.set_query("heal")
    assert [x.action_id for x in runtime.view.entries] == ["heal"]

    runtime.set_category("all")
    runtime.set_query("explosive")
    assert [x.action_id for x in runtime.view.entries] == ["bomb"]


def test_disabled_state_is_supplied_presentation_metadata_not_recomputed():
    runtime = BattleActionMenuRuntime()
    runtime.set_entries(_entries())
    runtime.set_category("special")
    locked = next(x for x in runtime.view.entries if x.action_id == "locked")
    assert locked.enabled is False
    assert locked.disabled_reason == "Requires Overdrive"


def test_cursor_navigation_only_selects_opaque_action_id():
    runtime = BattleActionMenuRuntime(BattleActionMenuPolicy(page_size=4, wrap_cursor=True))
    runtime.set_entries(_entries())
    assert runtime.selected_action_id() == "slash"
    runtime.move_cursor(1)
    assert runtime.selected_action_id() == "guard"
    runtime.move_cursor(-2)
    assert runtime.selected_action_id() == "heal"
    # Cursor navigation never executes or resolves the opaque action.


def test_composer_renders_generic_action_view_without_gameplay_resolution():
    runtime = BattleActionMenuRuntime(BattleActionMenuPolicy(page_size=4))
    runtime.set_entries(_entries())
    runtime.set_category("special")
    # Put disabled entry under cursor.
    runtime.move_cursor(1)

    scene = BattlePresentationScene("action.menu", "bg", ())
    frame = BattleUiComposer(scene).compose(
        Camera2D(),
        BattlePresentationFrame("action.menu", "bg", ()),
        action_menu=runtime.view,
    )
    assert any(x.panel_id == "action_menu" for x in frame.panels)
    assert any(x.text.startswith("▶ ") for x in frame.texts)
    assert any(
        x.text == "Requires Overdrive" and x.role == "action_disabled_reason" for x in frame.texts
    )


def test_policy_and_runtime_snapshot_roundtrip_preserve_view_state():
    policy = BattleActionMenuPolicy(page_size=2, sort_mode="priority", wrap_cursor=False)
    runtime = BattleActionMenuRuntime(policy)
    runtime.set_entries(_entries())
    runtime.set_category("magic")
    runtime.set_page(0)
    runtime.move_cursor(1)
    snapshot = runtime.snapshot()

    restored = BattleActionMenuRuntime(policy)
    restored.restore(snapshot)
    assert restored.snapshot() == snapshot
    assert restored.view.active_category == "magic"
    assert restored.selected_action_id() == runtime.selected_action_id()


def test_duplicate_action_ids_are_rejected():
    runtime = BattleActionMenuRuntime()
    import pytest

    with pytest.raises(ValueError):
        runtime.set_entries((BattleActionEntry("x"), BattleActionEntry("x")))
