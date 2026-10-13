"""RPG-04: weighted / guaranteed / pity drop tables, rolled by enemy rewards on victory."""

import random
from collections import Counter
from dataclasses import replace

import pytest

from asteria.rpg.drop_tables import DropEntry, DropTable, PityRule, roll_drop_table


def test_weighted_picks_follow_their_weights_and_no_drop():
    table = DropTable(
        "slime",
        rolls=1,
        nothing_weight=2.0,
        entries=(DropEntry("gel", weight=6.0), DropEntry("core", weight=2.0, rarity="rare")),
    )
    rng = random.Random(1)
    counts = Counter()
    for _ in range(10_000):
        counts.update(roll_drop_table(table, rng).keys() or ["nothing"])
    assert counts["gel"] / 10_000 == pytest.approx(0.6, abs=0.02)
    assert counts["core"] / 10_000 == pytest.approx(0.2, abs=0.02)
    assert counts["nothing"] / 10_000 == pytest.approx(0.2, abs=0.02)


def test_guaranteed_drops_switch_gates_and_quantities():
    table = DropTable(
        "boss",
        rolls=0,
        guaranteed=(
            DropEntry("emblem", minimum=2, maximum=2),
            DropEntry("key", required_switch="act2"),
        ),
    )
    rng = random.Random(0)
    assert roll_drop_table(table, rng) == {"emblem": 2}
    assert roll_drop_table(table, rng, switches=lambda s: s == "act2") == {"emblem": 2, "key": 1}


def test_pity_guarantees_the_item_after_misses_and_resets():
    table = DropTable(
        "chest",
        rolls=1,
        nothing_weight=1.0,
        entries=(DropEntry("relic", weight=0.0, rarity="legendary"),),
        pity=(PityRule("relic", after_misses=3),),
    )
    counters = {}
    rng = random.Random(0)
    results = [roll_drop_table(table, rng, counters=counters) for _ in range(7)]
    assert [bool(r) for r in results] == [False, False, True, False, False, True, False]
    assert counters["pity:chest:relic"] == 1.0


def test_luck_raises_only_non_common_weights():
    table = DropTable(
        "t",
        entries=(
            DropEntry("common_item", weight=1.0),
            DropEntry("rare_item", weight=1.0, rarity="rare"),
        ),
        luck_weight_bonus=1.0,
    )
    rng = random.Random(3)
    counts = Counter()
    for _ in range(6000):
        counts.update(roll_drop_table(table, rng, luck=2.0))
    assert counts["rare_item"] / 6000 == pytest.approx(0.75, abs=0.03)  # weight 1 * (1 + 2) vs 1


def test_victory_rolls_the_enemy_drop_table_and_pity_survives_save_and_load(runtime):
    from asteria.runtime.game_save import GameRuntimeSave

    game = runtime.game
    db = game.project.rpg_database
    db.add_drop_table(
        DropTable(
            "wisp_drops",
            rolls=1,
            nothing_weight=1.0,
            entries=(DropEntry("focus_stone", weight=0.0, rarity="epic"),),
            pity=(PityRule("focus_stone", after_misses=2),),
            guaranteed=(DropEntry("ether_leaf"),),
        )
    )
    wisp = db.enemies["mender_wisp"]
    db.enemies["mender_wisp"] = replace(
        wisp, reward=replace(wisp.reward, drop_table_id="wisp_drops")
    )
    game.project.validate()
    inventory = game.save.rpg_state.inventory

    def win():
        game.start_encounter("boss_room")
        for member_id in tuple(game.active_enemy_ids()):
            member = game.battle.member(member_id)
            member.subject.resources.set_current(game.rules.knockout_resource_id, 0)
        game.finish_victory()

    leaf, stone = inventory.count("ether_leaf"), inventory.count("focus_stone")
    win()  # two wisps: first misses (1), second misses (2 -> guaranteed)
    assert inventory.count("ether_leaf") == leaf + 2  # guaranteed per wisp
    assert inventory.count("focus_stone") == stone + 1  # pity after two misses
    win()
    game.sync_world_state()
    data = game.save.to_data()
    restored = GameRuntimeSave.from_data(data, game.project)
    assert (
        restored.rpg_state.world.counters["pity:wisp_drops:focus_stone"]
        == game.world.counters["pity:wisp_drops:focus_stone"]
    )


def test_drop_tables_are_edited_in_the_game_systems_forms_and_validated():
    from pathlib import Path

    from asteria.editor import EditorDocument
    from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
    from asteria.project import Project

    ref = (
        Path(__file__).parents[1] / "reference_projects/complex_reference_rpg/project.asteria.json"
    )
    document = EditorDocument()
    document.set_project(Project.load_json(ref, document.component_registry), file_path=ref)
    api = GameSystemsAuthoringController(document)
    api.create_new("drop_tables", "slime_drops")
    data = api.form_data("drop_tables", "slime_drops")
    data["entries"] = [
        {
            "item_id": "fire_dust",
            "weight": 3,
            "minimum": 1,
            "maximum": 2,
            "rarity": "common",
            "required_switch": "",
        }
    ]
    data["pity"] = [{"item_id": "focus_stone", "after_misses": 5}]
    api.edit("drop_tables", "slime_drops", api.decode("drop_tables", data))
    table = document.project.rpg_database.drop_tables["slime_drops"]
    assert table.entries[0].weight == 3 and table.pity[0].after_misses == 5
    assert (
        Project.from_data(
            document.project.to_data(), document.component_registry
        ).rpg_database.drop_tables["slime_drops"]
        == table
    )
    data["entries"][0]["item_id"] = "missing_item"
    with pytest.raises(Exception):
        api.edit("drop_tables", "slime_drops", api.decode("drop_tables", data))
        document.project.validate()
