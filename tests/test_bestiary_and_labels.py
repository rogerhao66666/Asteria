"""The bestiary unlocks an enemy's weaknesses and health once one is defeated and lists only the
drops that really fell; overhead enemy names never cover another combatant or another name; an
NPC can start hidden until an event shows it."""

from pathlib import Path

import pytest

from asteria.editor import EditorDocument
from asteria.project import Project
from asteria.runtime.game_menus import bestiary_rows
from asteria.runtime.game_session import GameSessionRuntime

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _session():
    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _row(game, enemy_id):
    name = game.project.rpg_database.enemies[enemy_id].display_name
    return next(r for r in bestiary_rows(game) if r[0] == name)


def test_weaknesses_and_health_unlock_with_the_first_defeat():
    game = _session()
    game.world.note_enemy("goblin_slinger", "seen")
    row = _row(game, "goblin_slinger")
    assert row[1] == 1 and row[4] == () and row[5] == () and row[6] == ()  # seen, nothing known
    game.world.note_enemy("goblin_slinger", "defeated")
    row = _row(game, "goblin_slinger")
    assert "weak.sword" in row[4] and dict(row[5])["vitality"] > 0


def test_a_battle_won_records_only_what_really_dropped():
    game = _session()
    game.start_encounter("woods_patrol")
    for member_id in game.active_enemy_ids():
        game.battle.member(member_id).subject.resources.set_current("vitality", 0.0)
    assert not game.active_enemy_ids()
    applied = game.finish_victory()
    entry = game.world.bestiary["goblin_slinger"]
    fell = {}
    for reward in applied:
        for item_id, amount in reward.items.items():
            fell[item_id] = fell.get(item_id, 0) + amount
    noted = {k[5:]: v for k, v in entry.items() if k.startswith("drop:")}
    gear = {k: v for k, v in noted.items() if k in game.project.rpg_database.equipment}
    assert {k: v for k, v in noted.items() if k not in gear} == fell
    names = dict(_row(game, "goblin_slinger")[6])
    assert len(names) == len(noted)


def test_overhead_names_never_cover_a_combatant_or_each_other(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.runtime.camera import Camera2D
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    runtime.open()
    try:
        runtime._ui_mode = "field"
        runtime.game.start_encounter("woods_boss")  # a big boss and two slingers close together
        runtime._battle_presentation.begin()
        runtime._advance_to_hero_turn()
        adapter = runtime._battle_presentation
        # names wait while the boss intro and queued actions play: check them once shown
        for _ in range(900):
            runtime._frame([], 1 / 60)
            if not adapter.busy() and not adapter.screen.overhead_hidden:
                break
        screen = adapter.screen
        layout = screen.composer.layout
        assert not layout.overhead_bars  # health stays hidden
        frame = screen.build_frame(
            Camera2D(width=layout.virtual_width, height=layout.virtual_height)
        )
        assert not any(g.member_id in screen.composer.overhead_labels for g in frame.gauges)
        labels = screen.composer.overhead_labels
        boxes = screen.composer._combatant_boxes()
        assert set(labels) == set(runtime.game.active_enemy_ids())

        def apart(a, b):
            return (
                a[0] + a[2] <= b[0]
                or b[0] + b[2] <= a[0]
                or a[1] + a[3] <= b[1]
                or b[1] + b[3] <= a[1]
            )

        items = list(labels.items())
        for index, (member_id, rect) in enumerate(items):
            for other, box in boxes.items():
                if other != member_id:
                    assert apart(rect, box), (member_id, other)
            for _other, rect2 in items[index + 1 :]:
                assert apart(rect, rect2)
    finally:
        runtime.close()


def test_a_companion_waits_hidden_at_the_guild_until_met():
    game = _session()
    from asteria.runtime.npc_state import apply_npc_states

    town = game.scene
    by_name = {e.name: e for e in town.entities()}
    apply_npc_states(town, game.world)
    assert by_name["Mira"].enabled and not by_name["Vesper"].enabled
    game.world.npc("vesper_guild")["visible"] = True
    apply_npc_states(town, game.world)
    assert by_name["Vesper"].enabled
    _ = pytest


def test_top_level_commands_show_no_numbers_unless_the_layout_asks():
    from dataclasses import replace

    from asteria.presentation.battle_action_menu import BattleActionEntry, BattleActionMenuView
    from asteria.presentation.battle_ui import BattleUiLayoutProfile

    assert BattleUiLayoutProfile().command_counts is False  # the default: names alone
    entries = (
        BattleActionEntry("root:Attack", "Attack", category="Command", cost_text="3"),
        BattleActionEntry("fire", "Fire", category="Skills", cost_text="4 SP"),
    )
    menu = BattleActionMenuView(("Command",), "Command", "", entries, 0, 1, 2, 0, 0)
    from asteria.presentation.battle import BattlePresentationScene
    from asteria.presentation.battle_ui import BattleUiComposer

    composer = BattleUiComposer(BattlePresentationScene("s", "bg"))
    _p, texts, _i = composer._action_menu_commands(menu)
    shown = [t.text for t in texts]
    assert "3" not in shown and "4 SP" in shown  # a skill's cost stays
    composer.layout = replace(composer.layout, command_counts=True)
    _p, texts, _i = composer._action_menu_commands(menu)
    assert "3" in [t.text for t in texts]
