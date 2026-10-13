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
