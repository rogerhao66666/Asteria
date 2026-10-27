"""The equipment and enhance screens of the playtest host (U3; they replace the workshop).

The paper doll shows every slot of the member (one place per piece a slot holds), lists the bag
pieces that fit the chosen place, wears one and takes it off; the enhance screen refines,
sockets and takes out, lists card sockets apart and unlocks growth stages, each by key presses.
The build-test menu opens only with Settings ▸ Developer Menu on.
"""

import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))


@pytest.fixture
def host(monkeypatch):
    import real_window

    from asteria.editor import EditorDocument
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    runtime = PlayableTestRuntime(
        project, project.game_start.instantiate(project), DEMO, width=1280, height=720
    )
    runtime.open()
    yield runtime
    runtime.close()


def _key(host, key, frames=2):
    pg = host.pg
    for kind in (pg.KEYDOWN, pg.KEYUP):
        pg.event.post(pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0))
        host._frame(pg.event.get(), 1 / 60)
    for _ in range(frames):
        host._frame([], 1 / 60)


def _worn(host, slot_id, actor="hero_01"):
    loadout = host.game.save.rpg_state.loadouts[actor]
    return [p.equipment.equipment_id for p in loadout.equipped(slot_id)]


def test_the_paper_doll_wears_and_takes_off_what_fits(host):
    pg, game = host.pg, host.game
    host.open_equipment_screen(back="field")
    screen = host._gear_screen
    host._frame([], 1 / 60)
    places = screen.places()
    slots = [s for s, _i, _p in places]
    assert {"head", "legs", "feet", "weapon", "armor", "accessory", "form"} <= set(slots)
    assert [slots.count(s) for s in ("special", "weapon", "sub_weapon", "accessory")] == [1] * 4
    assert slots.count("arsenal") == 6  # the Brave's carried weapons (D92)
    boxes = {p.slot_id for p in host.menu_layout("equipment").element("doll").slots}
    assert boxes == set(slots)  # the demo's doll picture has a place for every slot
    (helmet,) = game.gain_equipment("hd_plate_helmet")
    game.gain_equipment("a_scale_mail")
    game.equip_offers.clear()
    screen.place = slots.index("head")
    assert [p.equipment.equipment_id for p, _ok, _why in screen.candidates()] == [
        "hd_plate_helmet"
    ]  # the armour waits for the armour slot
    defence = game.resolve_actor_build("hero_01").stats.get("defense")
    _key(host, pg.K_RETURN)
    assert screen.focus == "list"
    rows = {name: after for _s, name, _now, after in screen.stat_rows() if after is not None}
    assert rows  # the stats with the helmet on, before wearing it
    _key(host, pg.K_RETURN)
    assert _worn(host, "head") == ["hd_plate_helmet"] and screen.focus == "doll"
    assert game.resolve_actor_build("hero_01").stats.get("defense") > defence
    assert helmet not in game.save.rpg_state.equipment_bag
    _key(host, pg.K_x)
    assert _worn(host, "head") == [] and helmet in game.save.rpg_state.equipment_bag
    (ring,) = game.gain_equipment("w_demon_ring")  # the free sub-weapon hand
    game.equip_offers.clear()
    screen.place = [s for s, _n, _p in screen.places()].index("sub_weapon")
    _key(host, pg.K_RETURN)
    _key(host, pg.K_RETURN)
    assert _worn(host, "weapon") == ["w_sunbrand"] and _worn(host, "sub_weapon") == [
        "w_demon_ring"
    ]
    _key(host, pg.K_ESCAPE)
    assert host._ui_mode == "field"
    host.capture()


def test_the_enhance_screen_refines_sockets_and_grows(host):
    pg, game = host.pg, host.game
    state = game.save.rpg_state
    state.currencies["gold"] = 50000.0
    state.inventory.add("silver_ore", 4)
    state.inventory.add("ice_orb_item", 1)
    state.inventory.add("card_knight_item", 1)
    # the ring in the sub-weapon hand, the two-handed scepter carried (D92)
    for equipment_id, slot_id in (("w_demon_ring", "sub_weapon"), ("w_bone_scepter", "arsenal")):
        (piece,) = game.gain_equipment(equipment_id)
        game.wear_from_bag("hero_01", piece.instance_id, slot_id)
    game.equip_offers.clear()
    host.open_enhance_screen(back="field")
    screen = host._gear_screen
    host._frame([], 1 / 60)
    plate = screen.piece()
    assert screen.page == "refine" and game.refine_rules_for(plate) is not None
    assert plate.equipment.equipment_id == "a_warden_plate"  # the first piece it can refine
    texts = [t for t, _c, _s in screen.detail_lines()]
    assert any("150" in t for t in texts) and any("Always succeeds" in t for t in texts)
    ore = state.inventory.count("silver_ore")
    _key(host, pg.K_RETURN)
    assert plate.refine_level == 1 and state.inventory.count("silver_ore") == ore - 1
    _key(host, pg.K_TAB)  # sockets: the Demon Ring's gem and charm sockets, one by one
    assert screen.page == "sockets"
    screen.rows["gear"] = [p.equipment.equipment_id for _s, p in screen.gear()].index(
        "w_demon_ring"
    )
    _key(host, pg.K_RETURN)
    assert screen.focus == "sockets" and len(screen.sockets()) == 4
    _key(host, pg.K_RETURN)
    names = [item.item_id for item, _a, _n in screen.choices()]
    assert "ice_orb_item" in names and "card_knight_item" not in names
    screen.rows["choices"] = names.index("ice_orb_item")
    _key(host, pg.K_RETURN)
    ring = screen.piece()
    socket_id = screen.sockets()[0][0].socket_id
    assert ring.attachments[socket_id].attachment_id == "ice_orb"
    assert state.inventory.count("ice_orb_item") == 0
    _key(host, pg.K_x)
    assert socket_id not in ring.attachments and state.inventory.count("ice_orb_item") == 1
    _key(host, pg.K_ESCAPE)
    _key(host, pg.K_TAB)  # cards: the card sockets only
    assert screen.page == "cards"
    _key(host, pg.K_RETURN)
    assert len(screen.sockets()) == 3
    assert all("card" in s.accepted_tags for s, _a, _o in screen.sockets())
    _key(host, pg.K_ESCAPE)
    _key(host, pg.K_TAB)  # growth: the scepter's stages
    assert screen.page == "growth"
    scepter = screen.piece()
    assert scepter.equipment.equipment_id == "w_bone_scepter"
    _key(host, pg.K_RETURN)
    assert screen.focus == "nodes" and screen.nodes()
    host.capture()


def test_the_build_menu_waits_for_the_developer_option(host):
    pg = host.pg
    host._ui_mode = "field"
    host.settings.developer_menu = False
    _key(host, pg.K_c)
    assert host._ui_mode == "field"
    host.settings.developer_menu = True
    _key(host, pg.K_c)
    assert host._ui_mode == "build"
    _key(host, pg.K_8)  # the old workshop key opens the enhance screen
    assert host._ui_mode == "enhance"
    _key(host, pg.K_ESCAPE)
    assert host._ui_mode == "build"
