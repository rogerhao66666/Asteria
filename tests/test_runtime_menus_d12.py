"""D12 runtime integration: recipe discovery + crafting, achievements, bestiary and settings
screens.

Every test drives PlayableTestRuntime frames with key events. Fixtures are
added to the reference project in memory only.
"""

import random

import pytest

pygame = pytest.importorskip("pygame")

from test_session_events import BOSS_PROGRAM, _replace_program, _session  # noqa: E402

from asteria.events import EventInstruction  # noqa: E402
from asteria.rpg import (  # noqa: E402
    AchievementDefinition,
    CompositionOutput,
    CompositionRecipeDefinition,
)
from asteria.runtime.game_menus import (
    CraftingScreen,
    GameSettings,
    achievement_rows,
    bestiary_rows,
)  # noqa: E402


def _secret_recipe():
    return CompositionRecipeDefinition(
        "star_tonic",
        "Star Tonic",
        selections=[{"step_id": "base", "item_ids": ["ether_leaf", "fire_dust"]}],
        outputs=[CompositionOutput("focus_stone")],
        station="alchemy_table",
        requires_discovery=True,
    )


def _press(rt, key):
    rt._frame([pygame.event.Event(pygame.KEYDOWN, key=key)], 0.016)
    rt._frame([pygame.event.Event(pygame.KEYUP, key=key)], 0.016)


def _open_pause(rt):
    rt._ui_mode = "field"
    _press(rt, pygame.K_ESCAPE)
    assert rt._ui_mode == "pause"


def _choose_pause(rt, label):
    from asteria.runtime.game_menus import PAUSE_OPTIONS

    index = [key for key, _ in PAUSE_OPTIONS].index(label)
    for _ in range((index - rt._pause_menu.index) % len(PAUSE_OPTIONS)):
        _press(rt, pygame.K_DOWN)
    _press(rt, pygame.K_RETURN)


def test_recipe_discovery_by_event_and_by_experiment():
    project, game = _session()
    project.rpg_database.add_composition_recipe(_secret_recipe())
    assert "star_tonic" not in [r.recipe_id for r in game.known_recipes()]
    inventory = game.save.rpg_state.inventory
    inventory.add("ether_leaf", 2)
    inventory.add("fire_dust", 2)
    result = game.craft(
        {"base": ["ether_leaf", "fire_dust"]}, station="alchemy_table", rng=random.Random(1)
    )
    assert result.recipe_id == "star_tonic" and game.recipe_known(
        "star_tonic"
    )  # experimenting discovers it
    assert game.save.event_context.get_switch("recipe.star_tonic.known")
    project2, game2 = _session()
    project2.rpg_database.add_composition_recipe(_secret_recipe())
    _replace_program(
        project2,
        BOSS_PROGRAM,
        [
            EventInstruction(
                "WORLD", {"command": "LEARN_RECIPE", "args": {"recipe_id": "star_tonic"}}
            ),
            EventInstruction(
                "WORLD", {"command": "OPEN_CRAFTING", "args": {"station": "alchemy_table"}}
            ),
            EventInstruction("END"),
        ],
    )
    game2.field_step({"interact": 1})
    assert game2.recipe_known("star_tonic") and game2.open_crafting_station == "alchemy_table"
    assert "star_tonic" in [r.recipe_id for r in game2.known_recipes("alchemy_table")]
    assert "star_tonic" not in [r.recipe_id for r in game2.known_recipes("forge")]


def test_crafting_screen_opened_by_event_crafts_in_the_runtime(runtime):
    game = runtime.game
    game.project.rpg_database.add_composition_recipe(_secret_recipe())
    screen = CraftingScreen(game, "alchemy_table")
    hidden_before = screen.undiscovered()
    assert hidden_before >= 1
    game.learn_recipe("star_tonic")
    game.save.rpg_state.inventory.add("ether_leaf", 1)
    game.save.rpg_state.inventory.add("fire_dust", 1)
    game.open_crafting_station = "alchemy_table"
    runtime._ui_mode = "field"
    runtime._frame([], 0.016)
    assert runtime._ui_mode == "crafting" and runtime._crafting_screen.station == "alchemy_table"
    names = [r.recipe_id for r in runtime._crafting_screen.rows()]
    assert "star_tonic" in names and runtime._crafting_screen.undiscovered() == hidden_before - 1
    runtime._crafting_screen.index = names.index("star_tonic")
    focus = game.save.rpg_state.inventory.count("focus_stone")
    _press(runtime, pygame.K_RETURN)
    assert game.save.rpg_state.inventory.count("focus_stone") == focus + 1
    assert runtime._crafting_screen.message.startswith("Crafted")
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "field" and game.open_crafting_station is None


def test_achievement_and_bestiary_screens_from_the_pause_menu(runtime):
    game = runtime.game
    db = game.project.rpg_database
    db.add_achievement(
        AchievementDefinition("first_blood", "First Blood", kind="defeated", target="mender_wisp")
    )
    db.add_achievement(
        AchievementDefinition(
            "secret", "Secret", kind="switch", target="secret.found", hidden=True
        )
    )
    game.world.note_enemy("mender_wisp", "seen", 2)
    game.world.note_enemy("mender_wisp", "defeated", 1)
    game.refresh_achievements()
    assert ("First Blood", "", True) in achievement_rows(game) and (
        "???",
        "Hidden achievement",
        False,
    ) in achievement_rows(game)
    rows = bestiary_rows(game)
    assert any(
        r[0] == db.enemies["mender_wisp"].display_name and r[1:4] == (2, 1, 0) for r in rows
    )
    assert any(r[0] == "???" for r in rows)
    _open_pause(runtime)
    _choose_pause(runtime, "achievements")
    assert runtime._ui_mode == "achievements"
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "pause"
    _choose_pause(runtime, "bestiary")
    assert runtime._ui_mode == "bestiary"
    _press(runtime, pygame.K_RETURN)
    assert runtime._ui_mode == "pause"


def test_settings_screen_changes_volume_applies_and_persists(runtime, resource_root):
    _open_pause(runtime)
    _choose_pause(runtime, "settings")
    assert runtime._ui_mode == "settings"
    start = runtime.settings.music_volume
    _press(runtime, pygame.K_LEFT)
    _press(runtime, pygame.K_LEFT)
    assert runtime.settings.music_volume == round(start - 0.2, 2)
    assert runtime.audio.volumes["bgm"] == runtime.settings.music_volume
    _press(runtime, pygame.K_DOWN)
    _press(runtime, pygame.K_RIGHT)  # effects capped at 1.0
    _press(runtime, pygame.K_DOWN)
    _press(runtime, pygame.K_RETURN)  # toggle battle messages
    assert runtime.settings.show_battle_log is False
    _press(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "pause"
    saved = GameSettings.load(resource_root / "saves" / "settings.json")
    assert saved == runtime.settings and saved.music_volume == round(start - 0.2, 2)
    assert GameSettings.load(resource_root / "missing.json") == GameSettings()
