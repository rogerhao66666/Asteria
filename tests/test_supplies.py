"""The Full Verification demo's armour, accessories and supplies (D61 G2): what each kind is,
that the battle items work (a potion heals, a cure removes its state, a bomb hurts and leaves a
state), that an orb sockets like a gem and gives its element, and the fixed "removes" words."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import trial_supplies as supplies  # noqa: E402


@pytest.fixture(scope="module")
def project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def _game(project):
    from asteria.runtime.game_session import GameSessionRuntime

    return GameSessionRuntime(project, project.game_start.instantiate(project))


def _active(states, state_id):
    return state_id in [s.state_id for s in states.active_states()]


def test_every_record_is_in_the_demo_with_its_picture(project):
    db = project.rpg_database
    for eid in supplies.all_equipment_ids():
        record = db.equipment[eid]
        assert record.icon_id.startswith("playable_assets/icons_7soul/")
        assert (DEMO / record.icon_id).is_file()
    for item_id in supplies.all_item_ids():
        assert (DEMO / db.items[item_id].icon_id).is_file(), item_id
    armour = [e for e in db.equipment.values() if e.slot == "armor"]
    accessories = [e for e in db.equipment.values() if e.slot == "accessory"]
    assert len(armour) >= 18 and len(accessories) >= 19
    for eid, (_name, rarity, *_rest) in supplies.ARMOUR.items():
        sockets = [s.socket_id for s in db.equipment[eid].sockets]
        assert sockets == (["c1"] if supplies.TIERS[rarity][4] else [])
    assert supplies.apply(project, DEMO) == 0  # applying again adds nothing


def test_the_item_kinds(project):
    db = project.rpg_database
    by_tag = {}
    for item in db.items.values():
        for tag in item.tags:
            by_tag.setdefault(tag, set()).add(item.item_id)
    assert {"potion", "hi_potion", "mega_potion", "ether", "hi_ether", "elixir"} <= by_tag[
        "potion"
    ]
    assert {"antidote", "eye_drops", "echo_herb", "remedy"} <= by_tag["cure"]
    assert set(supplies.THROWN) <= by_tag["throwable"]
    assert set(supplies.MATERIALS) <= by_tag["material"]
    for element in supplies.ORBS:
        orb = db.attachments[f"{element}_orb"]
        assert {"gem", "orb"} <= set(orb.tags)  # it fits a gem socket
        assert db.items[f"{element}_orb_item"].attachment_id == f"{element}_orb"
    for card in supplies.CARDS:
        assert "card" in db.attachments[card].tags
        assert db.items[f"{card}_item"].destroyed_on_removal


def test_potions_cures_and_bombs_work_in_battle(project):
    game = _game(project)
    inventory = game.save.rpg_state.inventory
    for item_id in ("potion", "antidote", "remedy", "thunder_bomb", "iron_ball"):
        inventory.add(item_id, 2)
    game.start_encounter("woods_patrol")
    hero, foe = "hero_01", game.active_enemy_ids()[0]
    me = game.battle.member(hero).subject
    me.resources.set_current("vitality", 100.0)
    game.use_battle_item(hero, "potion", (hero,))
    assert me.resources.current("vitality") == 600.0 and inventory.count("potion") == 1
    me.states.apply("poison")
    game.use_battle_item(hero, "antidote", (hero,))
    assert not _active(me.states, "poison")
    me.states.apply("blind")
    me.states.apply("silence")
    game.use_battle_item(hero, "remedy", (hero,))
    assert not _active(me.states, "blind") and not _active(me.states, "silence")
    them = game.battle.member(foe).subject
    start = them.resources.current("vitality")
    game.use_battle_item(hero, "thunder_bomb", (foe,))
    assert them.resources.current("vitality") < start
    assert _active(them.states, "stun")
    bomb = project.gameplay_library.abilities.require("throw_thunder_bomb")
    assert "damage.lightning" in bomb.tags  # the foes' lightning weakness reads it


def test_an_orb_sockets_into_a_weapon_and_gives_its_element(project):
    from asteria.events.world_commands import WorldCommand

    game = _game(project)
    game.save.rpg_state.inventory.add("ice_orb_item", 1)
    for name, args in (
        ("GIVE_EQUIPMENT", {"equipment_id": "w_bloodreaver"}),
        (
            "EQUIP_ITEM",
            {"actor_id": "hero_01", "equipment_id": "w_bloodreaver", "slot_id": "weapon"},
        ),
    ):
        game.world_commands.dispatch(WorldCommand(name, args))
    weapon = game.save.rpg_state.loadouts["hero_01"].equipped("weapon")[0]
    before = game.resolve_actor_build("hero_01").stats.get("ice_attack")
    game.socket_item("hero_01", weapon.instance_id, "g1", "ice_orb_item")
    assert weapon.attachments["g1"].attachment_id == "ice_orb"
    assert game.resolve_actor_build("hero_01").stats.get("ice_attack") == before + 15
    assert game.save.rpg_state.inventory.count("ice_orb_item") == 0


def test_a_skill_that_removes_states_says_so(project):
    abilities = project.gameplay_library.abilities
    purify = abilities.require("purify")
    assert purify.description.startswith("Support: removes Poison, Burn")
    assert "user gains" not in purify.description
    table = dict(project.rpg_database.locale_tables["zh-TW"].entries)
    assert table["data.ability.purify.description"].startswith("輔助：解除中毒、燃燒")
    for ability_id in abilities.ids():
        definition = abilities.require(ability_id)
        if any(s.get("remove") for s in definition.apply_states):
            assert "removes " in definition.description, ability_id
