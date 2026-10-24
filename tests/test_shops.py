"""The Full Verification demo's three new Hearthfold shops (D61 G3) and the engine change
behind them: a shop entry naming equipment sells into the equipment bag, at its rarity's
price; each keeper stands in Hearthfold with an event that opens their shop; a bought weapon
takes an orb in its socket and can be refined."""

import json
import random
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import trial_arsenal as arsenal  # noqa: E402
import trial_doll as doll  # noqa: E402
import trial_shops as shops  # noqa: E402
import trial_supplies as supplies  # noqa: E402


@pytest.fixture(scope="module")
def project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def _game(project):
    from asteria.runtime.game_session import GameSessionRuntime

    return GameSessionRuntime(project, project.game_start.instantiate(project))


def test_a_shop_runtime_sells_gear_into_the_equipment_bag():
    from asteria.rpg.economy import ShopDefinition, ShopEntry, ShopRuntime
    from asteria.rpg.items import Inventory

    shop = ShopDefinition(
        "s",
        "S",
        entries=(
            ShopEntry("sword", buy_prices={"gold": 100.0}),
            ShopEntry("potion", buy_prices={"gold": 10.0}),
        ),
    )
    received = []
    runtime = ShopRuntime(
        {"s": shop},
        inventory=Inventory(),
        currencies={"gold": 500.0},
        stock={},
        receive_equipment=lambda eid, qty: received.append((eid, qty)),
        equipment=("sword",),
    )
    runtime.buy("s", "sword", 2)
    runtime.buy("s", "potion", 1)
    assert received == [("sword", 2)]
    assert runtime.inventory.count("sword") == 0 and runtime.inventory.count("potion") == 1
    assert runtime.currencies["gold"] == 290.0


def test_the_three_shops_and_their_wares(project):
    db = project.rpg_database
    stocked = {sid: [e.item_id for e in db.shops[sid].entries] for sid in shops.SHOPS}
    assert stocked["arms_shop"] == list(arsenal.weapon_ids())
    assert stocked["armour_shop"] == [*supplies.all_equipment_ids(), *doll.equipment_ids()]
    remedies = set(stocked["remedy_shop"])
    assert set(shops.ITEM_PRICE) | set(supplies.MATERIALS) <= remedies
    assert {f"{e}_orb_item" for e in supplies.ORBS} <= remedies
    for entry in db.shops["arms_shop"].entries:
        rarity = db.equipment[entry.item_id].rarity or "common"
        assert entry.buy_prices == {"gold": float(shops.PRICE[rarity])}
        assert not entry.sell_prices  # gear is not bought back
    kinds = {db.equipment[i].tags[0] for i in stocked["arms_shop"]}
    assert len(kinds) >= 9
    assert shops.apply(project, DEMO) == 0  # applying again adds nothing


def test_each_keeper_stands_in_town_and_opens_their_shop(project):
    import trial_maps as maps

    scene = project.scene(maps.asset_id("scene", "town"))
    people = {e.name: e for e in scene.entities()}
    bindings = project.scene_event_bindings[scene.id]
    for shop_id, (_name, keeper, _xy, _look, _line) in shops.SHOPS.items():
        assert list(people).count(keeper) == 1
        (binding,) = bindings.for_entity(people[keeper].id)
        events = json.dumps(project.event_programs.get(binding.program_id).to_data())
        assert '"OPEN_SHOP"' in events and f'"{shop_id}"' in events, keeper
    table = dict(project.rpg_database.locale_tables["zh-TW"].entries)
    for shop_id in shops.SHOPS:
        assert table[f"data.shop.{shop_id}.name"]


def test_buying_socketing_and_refining_a_new_weapon(project):
    from asteria.events.world_commands import WorldCommand

    game = _game(project)
    state = game.save.rpg_state
    state.currencies["gold"] = 50000.0
    game.buy("w_knights_blade", 1, shop_id="arms_shop")
    assert "w_knights_blade" in {g.equipment.equipment_id for g in state.equipment_bag}
    assert state.inventory.count("w_knights_blade") == 0
    game.buy("fire_orb_item", 1, shop_id="remedy_shop")
    assert state.currencies["gold"] == 50000.0 - shops.PRICE["magic"] - shops.ORB_PRICE
    wear = {"actor_id": "hero_02", "equipment_id": "w_knights_blade", "slot_id": "weapon"}
    game.world_commands.dispatch(WorldCommand("EQUIP_ITEM", wear))
    blade = state.loadouts["hero_02"].equipped("weapon")[0]
    before = game.resolve_actor_build("hero_02").stats.get("fire_attack")
    game.socket_item("hero_02", blade.instance_id, "g1", "fire_orb_item")
    assert game.resolve_actor_build("hero_02").stats.get("fire_attack") == before + 15
    state.inventory.add("iron_ore", 1)
    ore = state.inventory.count("iron_ore")
    game.refine_rng = random.Random("test")
    game.refine_equipment("hero_02", blade.instance_id)
    assert state.inventory.count("iron_ore") == ore - 1  # the attempt spent its material
