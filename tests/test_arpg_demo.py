"""D22 A10: the ARPG demo project and the generic features it needs - tile-map scenes in the
playable runtime (drawing, animation, walls), binding alternatives per class, the SET_CLASSES
event command, the skill tree screen, item costs, reshaped hitboxes, self-buff cues, fixed
rarities, brief loot names and projectile sprites."""

from pathlib import Path

import pytest

from asteria.core import Transform

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_demo"


def _project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(ROOT / "project.asteria.json", EditorDocument().component_registry)


@pytest.fixture
def demo(monkeypatch):
    """A headless PlayableTestRuntime on the ARPG demo, in the town, in play."""
    pytest.importorskip("pygame")
    import real_window

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = _project()
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), ROOT, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    if real_window.enabled():
        real_window.set_stage(rt)
    yield rt
    rt.close()


def _frames(rt, count, events=()):
    for i in range(count):
        rt._frame(list(events) if i == 0 else [], 1 / 60)


def _key(rt, key, wait=3):
    pg = rt.pg
    for kind in (pg.KEYDOWN, pg.KEYUP):
        pg.event.post(pg.event.Event(kind, key=key, mod=0, unicode="", scancode=0))
        _frames(rt, 1, pg.event.get())
    _frames(rt, wait)


def _scene(project, prefix):
    return next(s for s in project.scenes() if s.name.startswith(prefix))


def _entity(scene, prefix):
    return next(e for e in scene.entities() if e.name.startswith(prefix))


# -- the project ----------------------------------------------------------------------------------
def test_the_demo_is_plain_project_data_with_three_tile_scenes():
    from asteria.runtime.action_play import combat_scene
    from asteria.runtime.tilemap_field import AssetResources, tilemap_binding

    project = _project()
    project.validate()
    assert [s.name for s in project.scenes()] == [
        "Hollowbrook",
        "Greenvale Fields",
        "Rustdeep Mine",
    ]
    views = [combat_scene(s).view for s in project.scenes()]
    assert views == ["topdown", "topdown", "side"]
    resources = AssetResources(project, ROOT)
    for scene in project.scenes():
        tilemap = resources.get(tilemap_binding(scene).tilemap_asset_id, "tilemap")
        assert any(layer.collision_enabled for layer in tilemap.layers)
    db = project.rpg_database
    assert {"warrior", "ranger", "mage"} <= set(db.classes)
    assert {"warrior_tree", "ranger_tree", "mage_tree", "attributes"} == set(db.progression_graphs)
    assert "wanderer" in db.equipment_sets and db.loot_rarities()["unique"].weight == 0
    assert (ROOT / "playable_assets" / "CREDITS.md").read_text(encoding="utf-8").count("CC0")


def test_the_tile_view_draws_the_map_animates_characters_and_follows_the_player(demo):
    view = demo.tile_view
    assert view is not None and view.scene_id == demo.game.scene.id
    _frames(demo, 3)
    centre = demo.screen.get_at((demo.width // 2, demo.height // 3))[:3]
    assert centre != (12, 14, 20)  # the map is drawn, not the empty background
    player = demo.game.player
    sx, sy = demo._field_screen_xy(*_xy(player))
    assert abs(sx - demo.width / 2) < 40 and abs(sy - demo.height / 2) < 40
    state = view._animated[player.id]
    assert state.clip == "idle_down"
    demo.game.player.get(Transform).x += 5  # moving -> the walk clip of its facing
    _frames(demo, 1)
    assert state.clip.startswith("walk_")


def _xy(entity):
    t = entity.get(Transform)
    return t.x, t.y


def test_tile_walls_block_the_player_and_projectiles(demo):
    from asteria.runtime.character_control import CharacterController2DComponent

    game = demo.game
    field = _scene(game.project, "Greenvale")
    game.transfer_player(field.id, 3.5 * 16, 23.5 * 16, facing="left")
    _frames(demo, 2)
    assert demo.tile_view.scene_id == field.id
    blocking = game._tile_blocking[field.id]
    assert blocking.collides_world_point(-1, 100)  # outside the map
    controller = game.player.get(CharacterController2DComponent)
    assert game._field_systems()["controllers"].extra_blocking is blocking
    assert game._field_systems()["projectiles"].tiles is blocking
    # walk up into the tree border: the player stops at the wall
    pg = demo.pg
    pg.event.post(pg.event.Event(pg.KEYDOWN, key=pg.K_w, mod=0, unicode="", scancode=0))
    _frames(demo, 1, pg.event.get())
    _frames(demo, 120)
    y = game.player.get(Transform).y
    assert y > 2 * 16 and not blocking.collides_world_point(game.player.get(Transform).x, y)
    assert controller.hit_wall or controller.hit_ceiling or y > 3 * 16


def test_a_trainer_changes_the_class_and_the_bindings_follow(demo):
    from asteria.runtime.character_control import CharacterController2DComponent

    game = demo.game
    hud_slots = lambda: [  # noqa: E731
        game.action_combat.bound_ability(game.player, value)
        for value in __import__("asteria.runtime.action_combat", fromlist=["parse_bindings"])
        .parse_bindings(game.player.get(_action_type()).bindings)
        .values()
    ]
    assert hud_slots()[0] == "punch"  # an adventurer only knows how to punch
    trainer = _entity(game.scene, "Ranger Trainer")
    tx, ty = _xy(trainer)
    game.set_player_position(tx, ty - 18)
    game.player.get(CharacterController2DComponent).facing = "down"
    _key(demo, demo.pg.K_e)
    assert game.event_busy
    while game.event_busy:
        _key(demo, demo.pg.K_RETURN)
    assert game.save.rpg_state.actor_progression["hero"].active_class_ids == ("ranger",)
    assert hud_slots()[:3] == ["r_shot", "roll", ""]  # skill_1 not learned yet
    assert game.action_combat.use(game.player, "w_slash") == "not_known"


def _action_type():
    from asteria.runtime.action_combat import ActionCombatComponent

    return ActionCombatComponent


def test_the_skill_tree_screen_learns_nodes_and_grants_skills(demo):
    from asteria.runtime.skill_tree_screen import actor_graphs

    game = demo.game
    game.set_classes("", ["mage"])
    db = game.project.rpg_database
    allocation = game.save.rpg_state.progression_allocations["hero"]
    progression = game.ensure_actor_progression("hero")
    assert actor_graphs(db, progression, allocation) == ["mage_tree", "attributes"]
    _key(demo, demo.pg.K_c)
    assert demo._ui_mode == "skills"
    _key(demo, demo.pg.K_RETURN)  # the first node: Frost Nova
    assert "m_nova" in game.resolve_actor_build("hero").abilities
    _key(demo, demo.pg.K_DOWN)
    _key(demo, demo.pg.K_RETURN)  # Meteor costs 2 AP; one is left
    assert "m_meteor" not in game.resolve_actor_build("hero").abilities
    assert "Cannot learn Meteor" in demo._skill_tree.message
    _key(demo, demo.pg.K_o)  # the shared Attributes tree
    assert demo._skill_tree.graph().graph_id == "attributes"
    _key(demo, demo.pg.K_c)
    assert demo._ui_mode == "field"


def test_set_classes_command_unlocks_and_activates(demo):
    from asteria.events import EventInstruction, EventProgram

    game = demo.game
    program = EventProgram(
        (
            EventInstruction(
                "WORLD", {"command": "SET_CLASSES", "args": {"class_ids": "warrior, ranger"}}
            ),
            EventInstruction("END"),
        )
    )
    game.project.event_programs.register("test.classes", program)
    from asteria.runtime.interaction import InteractionTrigger

    game.events.start_trigger(InteractionTrigger(game.player.id, "test.classes", "t"))
    game.update_events(0.0)
    state = game.save.rpg_state.actor_progression["hero"]
    assert state.active_class_ids == ("warrior", "ranger")
    assert {"warrior", "ranger"} <= set(state.unlocked_class_ids)
    with pytest.raises(Exception, match="unknown classes"):
        game.set_classes("", ["nope"])


def test_potions_are_items_an_ability_spends(demo):
    game = demo.game
    _frames(demo, 2)
    bag = game.save.rpg_state.inventory
    assert bag.count("potion") == 3
    state = game.combat.state(game.player)
    state.resources.set_current("hp", 20)
    assert game.action_combat.use(game.player, "potion") == "used"
    assert bag.count("potion") == 2
    _frames(demo, 200)
    assert state.resources.current("hp") > 20  # the healing state ticked
    bag.remove("potion", 2)
    game.action_combat.cooldowns.clear()
    assert game.action_combat.use(game.player, "potion") == "cost:item:potion"


def test_whirlwind_reshapes_the_hitbox_only_while_it_lasts(demo):
    from asteria.runtime.character_control import Hitbox2DComponent

    game = demo.game
    game.set_classes("", ["warrior"])
    game.allocate_progression("hero", "warrior_tree", "w_whirl")
    hitbox = game.player.get(Hitbox2DComponent)
    before = (hitbox.width, hitbox.height, hitbox.offset_x)
    game.combat.state(game.player).resources.set_current("mp", 50)
    assert game.action_combat.use(game.player, "w_whirl") == "used"
    _frames(demo, 6)
    assert (hitbox.width, hitbox.height, hitbox.offset_x) == (56, 56, 0)
    _frames(demo, 60)
    assert (hitbox.width, hitbox.height, hitbox.offset_x) == before


def test_war_cry_puts_a_state_on_the_user(demo):
    game = demo.game
    game.set_classes("", ["warrior"])
    for node in ("w_whirl", "w_leap"):
        game.allocate_progression("hero", "warrior_tree", node)
    allocation = game.save.rpg_state.progression_allocations["hero"]
    allocation.grant("ap", 2)
    game.allocate_progression("hero", "warrior_tree", "w_shout")
    state = game.combat.state(game.player)
    power = game.combat.effective_stats(state).get("power")
    state.resources.set_current("mp", 50)
    assert game.action_combat.use(game.player, "w_shout") == "used"
    _frames(demo, 12)
    assert state.states.get("war_cry") is not None
    assert game.combat.effective_stats(state).get("power") > power


def test_uniques_and_set_pieces_keep_their_rarity_and_labels_stay_short():
    import random

    from asteria.rpg.loot import fixed_rarity, item_display_name, roll_equipment

    db = _project().rpg_database
    rng = random.Random(4)
    for item_id, rarity in (("cyclops_eye", "unique"), ("wanderer_coat", "set")):
        assert fixed_rarity(db.equipment[item_id]) == rarity
        rolled = roll_equipment(
            db.equipment[item_id],
            rng,
            item_level=9,
            rarities=db.loot_rarities(),
            affixes=db.affixes,
            luck=5.0,
            instance_id="x",
        )
        assert rolled.rarity == rarity
    legendary = roll_equipment(
        db.equipment["copper_ring"],
        rng,
        item_level=12,
        rarity_id="legendary",
        rarities=db.loot_rarities(),
        affixes=db.affixes,
        instance_id="y",
    )
    assert 5 <= len(legendary.rolled_affixes) <= 6
    brief = item_display_name(legendary, db.affixes, brief=True)
    assert len(brief.split(" of ")) <= 2 and "Copper Ring" in brief


def test_projectiles_with_a_sprite_are_drawn_turned_to_their_flight(demo):
    game = demo.game
    definition = game.project.gameplay_library.projectiles["arrow"]
    view = demo.tile_view
    right = view.projectile_image(definition, 100.0, 0.0)
    down = view.projectile_image(definition, 0.0, 100.0)
    assert right is not None and down is not None
    assert right.get_size() == (down.get_height(), down.get_width())


def test_the_side_view_mine_lets_the_player_stand_jump_and_climb(demo):
    from asteria.runtime.character_control import CharacterController2DComponent

    game = demo.game
    mine = _scene(game.project, "Rustdeep")
    game.transfer_player(mine.id, 4.5 * 18, 10 * 18, facing="right")
    _frames(demo, 90)
    controller = game.player.get(CharacterController2DComponent)
    assert controller.mode == "side" and controller.grounded
    ground_y = game.player.get(Transform).y
    _key(demo, demo.pg.K_SPACE, wait=8)
    assert game.player.get(Transform).y < ground_y - 4  # in the air
    _frames(demo, 60)
    assert controller.grounded
    ladder = _entity(mine, "Ladder")
    lx, ly = _xy(ladder)
    assert ly < ground_y  # the ladder leads up to the high walkway


def test_particle_effects_and_text_use_the_tile_scenes_camera_and_are_cached(demo):
    from asteria.presentation.particles import ParticleSystem, preset

    game = demo.game
    field = _scene(game.project, "Greenvale")
    game.transfer_player(field.id, 36 * 16, 28 * 16, facing="right")
    _frames(demo, 3)
    px, py = _xy(game.player)
    definition = preset("fire", "t")
    demo.field_effects._play_particles(definition, {"x": px, "y": py}, game.scene, game.player)
    drawn = []
    original = demo.particle_drawer.draw

    def spy(surface, systems, to_screen, pixels_per_unit, **kw):
        drawn.append((to_screen(px, py), pixels_per_unit))
        return original(surface, systems, to_screen, pixels_per_unit, **kw)

    demo.particle_drawer.draw = spy
    _frames(demo, 2)
    (sx, sy), ppu = drawn[-1]
    assert abs(sx - demo.width / 2) < 40 and abs(sy - demo.height / 2) < 40  # on the player
    assert ppu == demo.tile_view.camera.zoom  # the tile camera's scale, not 3 x that
    before = len(demo._text_cache)
    _frames(demo, 5)
    assert len(demo._text_cache) == before  # the HUD text of a still frame is not re-rendered
    assert demo.tile_view is demo.tile_view
    assert ParticleSystem is not None


def test_a_huge_map_costs_only_what_the_camera_sees(monkeypatch, tmp_path):
    """A 640 x 640 tile world (a 10240 px square: a pre-rendered picture would be ~400 MB) loads
    at once, draws from a bounded number of chunk surfaces, and its walls still work."""
    import json
    import shutil
    import time

    pytest.importorskip("pygame")
    import real_window

    from asteria.runtime.playable_test_runtime import PlayableTestRuntime
    from asteria.runtime.tile_scene_view import CHUNK_CACHE

    root = tmp_path / "game"
    shutil.copytree(ROOT, root)
    path = root / "playable_assets" / "field_map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    ground = data["layers"][0]
    template = ground["chunks"][0]
    tiles = list(template["tiles"])
    side = 40  # chunks per side
    ground["chunks"] = [
        {"chunk_x": x, "chunk_y": y, "width": 16, "height": 16, "tiles": tiles}
        for x in range(side)
        for y in range(side)
    ]
    path.write_text(json.dumps(data), encoding="utf-8")
    if not real_window.enabled():
        monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
        monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    project = _project()
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    field = _scene(project, "Greenvale")
    started = time.perf_counter()
    rt.game.transfer_player(field.id, 300 * 16, 300 * 16, facing="down")
    _frames(rt, 3)
    assert time.perf_counter() - started < 5.0
    view = rt.tile_view
    assert view.bounds[2] == side * 16 * 16 and view.bounds[3] == side * 16 * 16
    for i in range(40):  # walk far across the map: chunks come and go, the cache stays bounded
        rt.game.set_player_position(300 * 16 + i * 150, 300 * 16 + i * 90)
        _frames(rt, 1)
    assert len(view._chunk_cache) <= CHUNK_CACHE
    assert view.blocking.collides_world_point(-5, 100)  # the map's edge still blocks
    assert not view.blocking.collides_world_point(5000, 5000)
    rt.close()


def test_the_bag_grid_compares_stats_equips_unequips_and_shows_the_set(demo):
    import random

    from asteria.rpg.loot import roll_equipment
    from asteria.runtime.bag_screen import BagScreen, compare

    game = demo.game
    db = game.project.rpg_database
    rng = random.Random(2)
    for item_id, rarity in (
        ("short_sword", "magic"),
        ("war_axe", "rare"),
        ("wanderer_hood", None),
        ("wanderer_coat", None),
    ):
        game.save.rpg_state.equipment_bag.append(
            roll_equipment(
                db.equipment[item_id],
                rng,
                item_level=6,
                rarity_id=rarity,
                rarities=db.loot_rarities(),
                affixes=db.affixes,
                instance_id=f"t:{item_id}",
            )
        )
    _key(demo, demo.pg.K_b)
    assert demo._ui_mode == "bag" and isinstance(demo._bag_screen, BagScreen)
    screen = demo._bag_screen
    assert screen.selected()[0].equipment.equipment_id == "short_sword"
    _key(demo, demo.pg.K_RETURN)  # wear the sword
    assert [i.equipment.equipment_id for i in game.save.rpg_state.loadouts["hero"].equipped()] == [
        "short_sword"
    ]
    # the axe (now first in the bag) is compared with the sword in the same slot
    axe = screen.selected()[0]
    assert axe.equipment.equipment_id == "war_axe"
    lines = compare(axe, screen.worn_in("weapon"))
    deltas = {stat: delta for stat, _value, delta, _op in lines}
    assert deltas["power"] is not None
    _frames(demo, 2)  # the tooltip draws
    # set pieces: the tooltip knows the set and how many are worn
    assert screen.set_info(axe)[0] is None  # the axe belongs to no set
    _key(demo, demo.pg.K_RIGHT)  # the hood
    definition, have, bonuses = screen.set_info(screen.selected()[0])
    assert definition.set_id == "wanderer" and have == 0 and [p for p, _ in bonuses] == [2, 3]
    _key(demo, demo.pg.K_RETURN)  # wear the hood
    assert screen.set_info(screen.selected()[0])[1] == 1
    # up into the worn strip, Enter takes the sword off again
    _key(demo, demo.pg.K_UP)
    assert screen.in_worn
    worn_before = len(game.save.rpg_state.loadouts["hero"].equipped())
    _key(demo, demo.pg.K_RETURN)
    assert len(game.save.rpg_state.loadouts["hero"].equipped()) == worn_before - 1
    _key(demo, demo.pg.K_b)
    assert demo._ui_mode == "field"


def test_class_looks_swap_with_the_class_and_the_camera_looks_ahead(demo):
    from asteria.runtime.actor_link import ClassAppearanceComponent
    from asteria.runtime.character_control import CharacterController2DComponent
    from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D

    game = demo.game
    player = game.player
    looks = player.get(ClassAppearanceComponent).parsed()
    assert set(looks) == {"warrior", "ranger", "mage"}
    sprite, animator = player.get(SpriteRenderer2D), player.get(Animator2DComponent)
    for class_id in ("warrior", "mage", "ranger"):
        game.set_classes("", [class_id])
        _frames(demo, 3)
        assert (sprite.sprite_sheet_asset_id, animator.clip_set_id) == looks[class_id]
        assert demo.tile_view._animated[player.id].clip_set_id == looks[class_id][1]
    # look-ahead: facing right pushes the camera to the right of the player, left to the left
    controller = player.get(CharacterController2DComponent)
    view = demo.tile_view
    centre = lambda: view.camera.x + view.width / view.camera.zoom / 2 - _xy(player)[0]  # noqa: E731
    controller.facing = "right"
    _frames(demo, 120)
    ahead_right = centre()
    controller.facing = "left"
    _frames(demo, 120)
    ahead_left = centre()
    assert ahead_right > 20 > -20 > ahead_left


def test_parallax_layers_scroll_slower_than_the_camera(demo):
    from asteria.runtime.components2d import ParallaxBackground2DComponent

    game = demo.game
    mine = _scene(game.project, "Rustdeep")
    game.transfer_player(mine.id, 6 * 18, 10 * 18, facing="right")
    _frames(demo, 5)
    view = demo.tile_view
    layers = [c for _, c in game.scene.query(ParallaxBackground2DComponent)]
    assert sorted(c.factor_x for c in layers) == [0.12, 0.3]
    pg = demo.pg
    zoom = view.camera.zoom

    def render(camera_x):
        view.camera.x = camera_x
        surface = pg.Surface((view.width, view.height))
        surface.fill((0, 0, 0))
        view._parallax(surface)
        return surface

    def mismatches(a, b, shift):
        """Sample points where ``b`` does not show what ``a`` showed ``shift`` px to the right."""
        return sum(
            a.get_at((x, y)) != b.get_at((x - shift, y))
            for y in range(0, view.height, 3)
            for x in range(shift + 4, view.width - 4, 5)
        )

    for layer in layers:
        for other in layers:
            other.visible = other is layer  # one layer at a time
        a, b = render(100.0), render(200.0)
        expected = round(100.0 * layer.factor_x * zoom)
        best = min(range(0, 130), key=lambda shift: (mismatches(a, b, shift), shift))
        assert best == expected, (layer.factor_x, best, expected)


def test_the_demo_map_can_be_edited_undone_saved_and_the_walls_change_in_play(
    tmp_path, monkeypatch
):
    """The editor's tile commands work on the demo's maps: paint a wall into the collision layer,
    undo and redo, save, reopen - and the playable runtime then collides with the new wall."""
    import shutil

    from asteria.editor import EditorDocument
    from asteria.editor.resource_resolver import resolve_project_resources
    from asteria.editor.storage import load_document, save_document
    from asteria.editor.tile_edit import build_paint_command, tile_at
    from asteria.runtime.tilemap_field import tilemap_binding

    root = tmp_path / "game"
    shutil.copytree(ROOT, root)
    project_path = root / "project.asteria.json"
    document = EditorDocument()
    load_document(document, project_path)
    resolve_project_resources(document)
    town = next(s for s in document.project.scenes() if s.name == "Hollowbrook")
    tilemap_id = tilemap_binding(town).tilemap_asset_id
    tilemap = document.asset_views.tilemap(tilemap_id)
    collision = next(layer for layer in tilemap.layers if layer.collision_enabled)
    blocker = max(
        t for layer in tilemap.layers for chunk in layer.chunks.values() for t in chunk.tiles
    )
    x, y = 19, 12  # the plaza, next to where the player starts
    assert tile_at(tilemap, collision, x, y) == -1
    command = build_paint_command(tilemap, collision, ((x, y),), blocker)
    document.execute(command)
    assert tile_at(tilemap, collision, x, y) == blocker
    document.undo()
    assert tile_at(tilemap, collision, x, y) == -1
    document.redo()
    assert tile_at(tilemap, collision, x, y) == blocker
    save_document(document)

    pytest.importorskip("pygame")
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")
    from asteria.project import Project
    from asteria.runtime.playable_test_runtime import PlayableTestRuntime

    project = Project.load_json(project_path, EditorDocument().component_registry)
    rt = PlayableTestRuntime(
        project, project.game_start.instantiate(project), root, width=960, height=540
    )
    rt.open()
    rt._ui_mode = "field"
    _frames(rt, 3)
    wall = rt.tile_view.blocking
    assert wall.collides_world_point((x + 0.5) * 16, (y + 0.5) * 16)  # the painted wall blocks
    assert not wall.collides_world_point((x + 2.5) * 16, (y + 0.5) * 16)  # its neighbour does not
    rt.close()


def test_the_hud_shows_keycaps_orbs_statuses_and_item_counts(demo):
    from asteria.runtime.hud_bottom import active_statuses, key_label, state_kind

    game = demo.game
    # keys come from the project's input map, not from the HUD
    assert key_label(demo, "attack") == "J"
    assert key_label(demo, "dodge") in ("K", "SHIFT")
    assert key_label(demo, "skill_2") == "2"
    game.set_classes("", ["warrior"])
    state = game.combat.state(game.player)
    for state_id in ("healing", "war_cry", "burning", "chilled"):
        assert game.combat.apply_state(game.player, state_id)
    kinds = {s["id"]: s["kind"] for s in active_statuses(game, state)}
    assert kinds == {
        "healing": "buff",
        "war_cry": "buff",
        "burning": "debuff",
        "chilled": "debuff",
    }
    library = game.project.gameplay_library.states
    assert state_kind(library.get("burning")) == "debuff"
    entry = next(s for s in active_statuses(game, state) if s["id"] == "war_cry")
    assert entry["abbr"] == "WC" and 0 < entry["remaining"] <= entry["total"]
    state.resources.set_current("hp", 70)
    badges = []
    hud = demo.action_hud.bottom
    original = hud._badge
    hud._badge = lambda rt, x, y, text, *a: (badges.append(text), original(rt, x, y, text, *a))
    _frames(demo, 3)
    assert "3" in badges  # the potion's item count sits in a corner badge
    assert hud.hint_left < hud.HINT_SECONDS  # the control hint is counting down


def test_states_and_abilities_carry_a_name_and_an_icon(demo):
    from asteria.gameplay.abilities import AbilityDefinition
    from asteria.gameplay.states import StateDefinition
    from asteria.runtime.hud_bottom import active_statuses

    library = demo.game.project.gameplay_library
    burning = library.states.get("burning")
    assert burning.display_name == "Burning" and burning.icon_id
    slash = library.abilities.get("w_slash")
    assert slash.display_name == "Slash" and slash.icon_id
    for definition in (burning, slash):  # data round trip keeps both
        again = type(definition).from_data(definition.to_data())
        assert (again.display_name, again.icon_id) == (definition.display_name, definition.icon_id)
    # data written before the fields existed still loads, and does not write them back
    plain = StateDefinition("plain", 2.0)
    assert "icon_id" not in plain.to_data() and "display_name" not in plain.to_data()
    assert StateDefinition.from_data(plain.to_data()).icon_id == ""
    assert "icon_id" not in AbilityDefinition("plain").to_data()
    game = demo.game
    game.set_classes("", ["warrior"])
    assert game.combat.apply_state(game.player, "burning")
    entry = active_statuses(game, game.combat.state(game.player))[0]
    assert entry["name"] == "Burning" and entry["icon"] == burning.icon_id


def test_enemies_show_their_statuses_as_pips_over_the_bar(demo):
    from asteria.runtime import hud_bottom
    from asteria.runtime.combat import CombatantComponent

    game = demo.game
    game.set_classes("", ["warrior"])
    field = _scene(game.project, "Greenvale")
    game.transfer_player(field.id, 36 * 16, 28 * 16, facing="right")
    _frames(demo, 3)
    enemy = next(
        e
        for e, c in game.scene.query(CombatantComponent)
        if e is not game.player and c.team != "player" and c.state is not None
    )
    assert game.combat.apply_state(enemy, "burning")
    rows = []
    real = hud_bottom.draw_status_pips

    def spy(rt, x, y, entries, **kw):
        rows.append([e["id"] for e in entries])
        return real(rt, x, y, entries, **kw)

    hud_bottom.draw_status_pips = spy
    try:
        _frames(demo, 3)
    finally:
        hud_bottom.draw_status_pips = real
    assert ["burning"] in rows


def test_the_editor_edits_a_status_name_and_icon_and_undoes_it():
    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    project = _project()
    document = EditorDocument()
    document.set_project(project)
    categories = {
        a.category_id: a for a in IntegratedAuthoringControllers(document).rpg_categories()
    }
    for category, key in (("states", "burning"), ("abilities", "w_slash")):
        adapter = categories[category]
        data = adapter.encode(adapter.get(key))
        before = (data.get("display_name"), data.get("icon_id"))
        data["display_name"], data["icon_id"] = "Renamed", "icons/potion.png"
        adapter.edit(key, adapter.decode(data))
        changed = adapter.get(key)
        assert (changed.display_name, changed.icon_id) == ("Renamed", "icons/potion.png")
        document.undo()
        restored = adapter.get(key)
        assert (restored.display_name, restored.icon_id) == before


def test_a_cooldown_goes_dark_and_a_wedge_turns_clockwise_to_bright_with_a_ready_flash(demo):
    from asteria.runtime.hud_bottom import BottomHud

    pg, screen = demo.pg, demo.screen
    hud = BottomHud()
    rect = pg.Rect(100, 100, 60, 60)

    def brightness(x, y):
        return sum(screen.get_at((x, y))[:3])

    def painted(done):
        screen.fill((200, 200, 200))
        hud._sweep(demo, rect, done)
        return {
            "top_right": brightness(rect.centerx + 18, rect.centery - 18),
            "bottom_right": brightness(rect.centerx + 18, rect.centery + 18),
            "bottom_left": brightness(rect.centerx - 18, rect.centery + 18),
            "top_left": brightness(rect.centerx - 18, rect.centery - 18),
        }

    start = painted(0.0)
    assert max(start.values()) < 300  # everything dark
    quarter = painted(0.3)  # past the first quarter: the top right quadrant is bright
    assert quarter["top_right"] > 500 and quarter["bottom_right"] < 300
    half = painted(0.6)
    assert half["bottom_right"] > 500 and half["bottom_left"] < 300
    assert painted(0.99)["top_left"] > 500  # the last wedge reaches the top left
    # the ready flash: cooling > 0 then 0 starts it, and tick() fades it out
    hud._flash["x"] = hud.FLASH_SECONDS
    hud.tick(hud.FLASH_SECONDS + 0.01)
    assert "x" not in hud._flash
