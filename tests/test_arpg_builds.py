"""The ARPG demo's build content: three builds per class (skills, passives, one exclusive
keystone), skill slots chosen from them (``slot:N`` bindings), elemental / crit stats, and the
loot: many affixes, rarities, sets, uniques and a drop table per monster."""

import random
from collections import Counter
from pathlib import Path

import pytest
from test_arpg_demo import _frames, _project, demo  # noqa: F401  (the fixture)

CLASSES = ("warrior", "ranger", "mage")


def _skill_nodes(graph):
    return [n for n in graph.nodes if any(r.granted_abilities for r in n.rewards)]


def test_each_class_has_three_builds_of_five_skills_with_one_exclusive_keystone():
    db = _project().rpg_database
    for class_id in CLASSES:
        graph = db.progression_graphs[f"{class_id}_tree"]
        skills = _skill_nodes(graph)
        assert len(skills) == 15  # three builds, five skills each
        assert len({a for n in skills for r in n.rewards for a in r.granted_abilities}) == 15
        keystones = [n for n in graph.nodes if n.exclusive_group]
        assert len(keystones) == 3 and len({n.exclusive_group for n in keystones}) == 1
        assert all(n.icon_id for n in graph.nodes if n not in skills)  # every node has a picture


def test_every_tree_skill_is_defined_with_a_timeline_cost_and_name():
    project = _project()
    library = project.gameplay_library
    for class_id in CLASSES:
        for node in _skill_nodes(project.rpg_database.progression_graphs[f"{class_id}_tree"]):
            ability_id = node.rewards[0].granted_abilities[0]
            ability = library.abilities.get(ability_id)
            assert ability.timeline_id in library.timelines and ability.display_name
            assert ability.icon_id, ability_id


def test_a_keystone_closes_the_other_two(demo):  # noqa: F811
    game = demo.game
    game.set_classes("", ["mage"])
    game.save.rpg_state.progression_allocations["hero"].grant("ap", 40)
    graph = "mage_tree"
    game.allocate_progression("hero", graph, "m_flame_wave")
    for _ in range(4):
        game.allocate_progression("hero", graph, "m_focus")
    for node in ("m_fireball", "m_meteor", "m_inferno", "m_phoenix"):
        game.allocate_progression("hero", graph, node)
    game.allocate_progression("hero", graph, "m_frost_bolt")
    for _ in range(4):
        game.allocate_progression("hero", graph, "m_mana")
    for node in ("m_nova", "m_ice_spike", "m_blizzard"):
        game.allocate_progression("hero", graph, node)
    with pytest.raises(ValueError):  # the Cryomancer keystone is out once one is taken
        game.allocate_progression("hero", graph, "m_winter")


def test_skill_slots_hold_what_the_player_chooses_and_the_bar_follows(demo):  # noqa: F811
    from asteria.runtime.action_combat import ActionCombatComponent, parse_bindings

    game = demo.game
    game.set_classes("", ["warrior"])
    game.save.rpg_state.progression_allocations["hero"].grant("ap", 10)
    for node in ("w_rend", "w_whirl", "w_might", "w_might", "w_frenzy"):
        game.allocate_progression("hero", "warrior_tree", node)
    equipped, capacity = game.ability_slots("hero")
    assert capacity == 2 and equipped == ("w_rend", "w_whirl")  # two slots, the first two taken
    assert "w_frenzy" in game.slot_candidates("hero")  # learned, but not in a slot
    assert game.action_combat.use(game.player, "w_frenzy") == "not_known"
    bindings = parse_bindings(game.player.get(ActionCombatComponent).bindings)
    bound = lambda action: game.action_combat.bound_ability(game.player, bindings[action])  # noqa: E731
    assert (bound("skill_1"), bound("skill_2"), bound("skill_3")) == ("w_rend", "w_whirl", "")
    game.unequip_ability("hero", "w_whirl")
    game.equip_ability("hero", "w_frenzy")  # the player swaps one skill for another
    assert (bound("skill_1"), bound("skill_2")) == ("w_rend", "w_frenzy")
    state = game.combat.state(game.player)
    state.resources.set_current("mp", 60)
    assert game.action_combat.use(game.player, "w_frenzy") == "used"
    _frames(demo, 20)
    assert state.states.get("frenzy") is not None


def test_slot_capacity_grows_with_the_level(demo):  # noqa: F811
    game = demo.game
    assert game.ability_slots("hero")[1] == 2
    game.grant_actor_experience("hero", 3200, **game.action_progression)
    assert game.ability_slots("hero")[1] >= 3


def test_elemental_stats_raise_the_damage_of_their_element(demo):  # noqa: F811
    from asteria.runtime.combat import CombatSystem  # noqa: F401

    library = _project().gameplay_library
    attack = library.attacks.get("m_fireball")
    stats = {term.key for term in attack.damage.terms if term.source == "source_stat"}
    assert {"magic", "fire_dmg"} <= stats
    assert "cold_dmg" in {t.key for t in library.attacks.get("m_frost_bolt").damage.terms}
    assert "shock_dmg" in {t.key for t in library.attacks.get("m_chain_lightning").damage.terms}
    assert "poison_dmg" in {t.key for t in library.attacks.get("r_poison_arrow").damage.terms}


def _rolled(db, table_id, kills, level, luck, seed=5):
    from asteria.rpg.drop_tables import roll_drop_table
    from asteria.rpg.loot import roll_equipment

    rng = random.Random(seed)
    items, serial = [], 0
    for _ in range(kills):
        for item_id in roll_drop_table(db.drop_tables[table_id], rng, luck=luck):
            if item_id in db.equipment:
                serial += 1
                items.append(
                    roll_equipment(
                        db.equipment[item_id],
                        rng,
                        item_level=level,
                        rarities=db.loot_rarities(),
                        affixes=db.affixes,
                        luck=luck,
                        instance_id=f"i{serial}",
                    )
                )
    return items


def test_the_loot_has_many_bases_slots_affixes_and_rarities():
    db = _project().rpg_database
    assert len(db.affixes) >= 35
    assert {e.slot for e in db.equipment.values()} >= {
        "weapon",
        "helm",
        "armor",
        "gloves",
        "boots",
        "amulet",
        "ring",
    }
    assert len(db.equipment) >= 45 and len(db.equipment_sets) == 3
    assert {a.position for a in db.affixes.values()} == {"prefix", "suffix"}
    stats = {m.stat for a in db.affixes.values() for m in a.modifiers}
    assert {"crit", "fire_dmg", "cold_dmg", "shock_dmg", "poison_dmg", "multishot"} <= stats


def test_stronger_monsters_drop_better_rarities_and_affixes():
    db = _project().rpg_database
    weak = Counter(i.rarity for i in _rolled(db, "slime", 400, 2, 0.0))
    boss = Counter(i.rarity for i in _rolled(db, "golem", 400, 12, 2.5))
    rolled_kinds = ("common", "magic", "rare", "legendary")  # not the fixed set / unique pieces
    share = lambda c: (c["rare"] + c["legendary"]) / sum(c[k] for k in rolled_kinds)  # noqa: E731
    assert share(boss) > share(weak)
    assert boss["unique"] > 0 and weak["unique"] == 0  # uniques come from elites and bosses
    rolled = _rolled(db, "elite", 400, 6, 1.0)
    counts = {r: {len(i.rolled_affixes) for i in rolled if i.rarity == r} for r in ("rare",)}
    assert counts["rare"] <= {3, 4} and counts["rare"]
    legendary = [i for i in _rolled(db, "golem", 600, 12, 2.5) if i.rarity == "legendary"]
    assert legendary and all(5 <= len(i.rolled_affixes) <= 6 for i in legendary)


def test_each_build_has_a_unique_that_pushes_its_stat():
    db = _project().rpg_database
    boosts = {
        "bloodreaver": "crit",
        "viper_fang": "poison_dmg",
        "tempest_staff": "shock_dmg",
        "phoenix_circlet": "fire_dmg",
        "glacier_ring": "cold_dmg",
        "windrunner_boots": "multishot",
    }
    for item_id, stat in boosts.items():
        equipment = db.equipment[item_id]
        assert "rarity:unique" in equipment.tags
        assert any(m.stat == stat and m.value > 0 for m in equipment.modifiers)


def test_every_gear_icon_is_a_real_picture():
    project = _project()
    root = Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_demo"
    for item_id, equipment in project.rpg_database.equipment.items():
        uri = project.assets.resolve(equipment.icon_id).source.uri
        assert (root / uri).is_file(), item_id


# -- the skill tree view: zoom, pan, and no two nodes ever overlap ----------------------------
def _screen(demo):  # noqa: F811
    from asteria.runtime.skill_tree_screen import SkillTreeScreen

    game = demo.game
    game.set_classes("", ["warrior"])
    demo._skill_tree = SkillTreeScreen(demo)
    demo._ui_mode = "skills"
    _frames(demo, 3)
    return demo._skill_tree


def _overlaps(screen, graph):
    from asteria.runtime.skill_tree_screen import NODE_H, NODE_W

    points = [screen.node_point(graph, n.node_id) for n in graph.nodes]
    half_w, half_h = NODE_W * screen.zoom / 2, NODE_H * screen.zoom / 2
    return [
        (i, j)
        for i, (ax, ay) in enumerate(points)
        for j, (bx, by) in enumerate(points[i + 1 :], i + 1)
        if abs(ax - bx) < 2 * half_w - 0.5 and abs(ay - by) < 2 * half_h - 0.5
    ]


def test_nodes_never_overlap_at_any_zoom(demo):  # noqa: F811
    screen = _screen(demo)
    for class_id in CLASSES:
        graph = demo.project.rpg_database.progression_graphs[f"{class_id}_tree"]
        for zoom in (0.3, 0.6, 1.0, 1.7, 2.5):
            screen.zoom = zoom
            assert _overlaps(screen, graph) == [], (class_id, zoom)


def test_a_long_tree_is_spread_instead_of_overlapping():
    from asteria.rpg import ProgressionGraphDefinition, ProgressionNodeDefinition
    from asteria.runtime.skill_tree_screen import SkillTreeScreen

    nodes = [ProgressionNodeDefinition(f"n{i}", f"Node {i}") for i in range(40)]
    cramped = {n.node_id: (0.0, i * 5.0) for i, n in enumerate(nodes)}  # authored far too close
    graph = ProgressionGraphDefinition(
        "long", nodes=nodes, editor_view="graph", node_positions=cramped
    )

    class Stub:
        width, height = 960, 540

    screen = SkillTreeScreen.__new__(SkillTreeScreen)
    screen.rt, screen.zoom, screen.origin, screen._spread = Stub(), 1.0, [0.0, 0.0], {}
    screen._view_for = None
    assert screen.spread(graph) >= 12  # 5 graph units -> at least a node height apart
    assert _overlaps(screen, graph) == []


def test_the_tree_is_laid_out_once_not_per_node_and_frame(monkeypatch):
    """Drawing asks for every node's place (and twice per line): laying the whole tree out on
    each ask made a long tree without saved positions stutter. It is laid out once per graph,
    and again only for an edited graph (a new object)."""
    import asteria.runtime.skill_tree_screen as tree
    from asteria.rpg import ProgressionGraphDefinition, ProgressionNodeDefinition

    nodes = [ProgressionNodeDefinition(f"n{i}", f"Node {i}") for i in range(30)]
    graph = ProgressionGraphDefinition("plain", nodes=nodes)  # no saved positions
    calls = []
    real = tree.layout
    monkeypatch.setattr(tree, "layout", lambda g: calls.append(g) or real(g))

    class Stub:
        width, height = 960, 540

    screen = tree.SkillTreeScreen.__new__(tree.SkillTreeScreen)
    screen.rt, screen.zoom, screen.origin, screen._spread = Stub(), 1.0, [0.0, 0.0], {}
    for _frame in range(5):
        for node in graph.nodes:
            screen.node_point(graph, node.node_id)
    assert len(calls) == 1
    edited = ProgressionGraphDefinition("plain", nodes=nodes[:10])
    screen.node_point(edited, "n1")
    assert len(calls) == 2  # an edited graph is laid out again


def test_the_wheel_zooms_drag_pans_and_fit_comes_back(demo):  # noqa: F811
    pg = demo.pg
    screen = _screen(demo)
    graph = screen.graph()
    fitted = screen.zoom
    pg.mouse.set_pos((300, 300))
    screen.handle(0.0, [pg.event.Event(pg.MOUSEWHEEL, x=0, y=3)])
    assert screen.zoom > fitted
    screen.handle(0.0, [pg.event.Event(pg.MOUSEWHEEL, x=0, y=-30)])
    assert screen.zoom == pytest.approx(0.3)  # never past the smallest zoom
    origin = list(screen.origin)
    screen.handle(0.0, [pg.event.Event(pg.MOUSEBUTTONDOWN, button=1, pos=(200, 200))])
    screen.handle(
        0.0, [pg.event.Event(pg.MOUSEMOTION, pos=(260, 230), rel=(60, 30), buttons=(1, 0, 0))]
    )
    screen.handle(0.0, [pg.event.Event(pg.MOUSEBUTTONUP, button=1, pos=(260, 230))])
    assert screen.origin == [origin[0] + 60, origin[1] + 30]
    screen.handle(0.0, [pg.event.Event(pg.KEYDOWN, key=pg.K_r, mod=0, unicode="r", scancode=0)])
    assert screen.zoom == pytest.approx(fitted) and screen.origin != origin
    screen.zoom = 1.0
    screen.node_id = graph.nodes[3].node_id
    screen.reveal(graph)  # the node is on screen: a click on it chooses it
    screen.node_id = graph.nodes[0].node_id
    x, y = screen.node_point(graph, graph.nodes[3].node_id)
    screen.handle(0.0, [pg.event.Event(pg.MOUSEBUTTONDOWN, button=1, pos=(int(x), int(y)))])
    screen.handle(0.0, [pg.event.Event(pg.MOUSEBUTTONUP, button=1, pos=(int(x), int(y)))])
    assert screen.node_id == graph.nodes[3].node_id  # a click chooses the node


def test_choosing_a_node_scrolls_it_into_view(demo):  # noqa: F811
    screen = _screen(demo)
    graph = screen.graph()
    screen.zoom = 1.6
    left, top, width, height = screen.area()
    screen.node_id = graph.nodes[0].node_id
    screen.origin[0] += 5000  # the tree is panned far away
    screen.reveal(graph)
    x, y = screen.node_point(graph, screen.node_id)
    assert left <= x <= left + width and top <= y <= top + height


def test_a_skill_plays_its_picture_effects_in_the_world(demo):  # noqa: F811
    game = demo.game
    game.set_classes("", ["mage"])
    game.allocate_progression("hero", "mage_tree", "m_flame_wave")
    game.combat.state(game.player)  # the fighter exists
    _frames(demo, 3)
    game.combat.state(game.player).resources.set_current("mp", 60)
    assert game.action_combat.use(game.player, "m_flame_wave") == "used"
    _frames(demo, 12)
    assert demo.action_hud.effects  # the flame arcs are playing
    _frames(demo, 90)
    assert demo.action_hud.effects == []  # and are gone when their frames are over


def test_every_effect_cue_names_a_real_sheet():
    project = _project()
    for timeline in project.gameplay_library.timelines.values():
        for cue in timeline.cues:
            if cue.kind.value == "vfx":
                sheet = project.assets.get(cue.payload["effect"])
                assert sheet is not None and sheet.kind == "sprite_sheet", timeline.timeline_id


# -- the editor reaches the new options -------------------------------------------------------
def _category(project, group, name):
    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    document = EditorDocument(project)
    controllers = IntegratedAuthoringControllers(document)
    categories = getattr(controllers, group)()
    return document, next(c for c in categories if c.category_id == name)


def test_the_layout_form_shows_every_option_even_at_its_default():
    from asteria.presentation.battle_ui import BattleUiLayoutProfile

    project = _project()
    library = project.battle_presentation_library
    library.set("ui_layout", "plain", BattleUiLayoutProfile())
    _document, category = _category(project, "presentation_categories", "ui_layout")
    data = category.encode(category.get("plain"))
    for key in ("menu_over_stage", "row_buttons", "overhead_below", "stage_front_right"):
        assert key in data, key
    data["menu_over_stage"] = True
    data["overhead_below"] = False
    value = category.decode(data)
    assert value.menu_over_stage and not value.overhead_below
    assert value.stage_front_right is None  # equal to the front: no separate right side


def test_the_skill_tree_form_shows_each_nodes_icon_field():
    _document, category = _category(_project(), "rpg_categories", "graphs")
    nodes = category.encode(category.get("mage_tree"))["nodes"]
    assert all("icon_id" in node for node in nodes)
    nodes[0]["icon_id"] = "playable_assets/lucifer/icons/skill_m_bolt.png"
    graph = category.decode({**category.encode(category.get("mage_tree")), "nodes": nodes})
    assert graph.nodes[0].icon_id.endswith("skill_m_bolt.png")


def test_every_skill_animation_exists_for_every_facing_of_every_class_look():
    import json

    from asteria.runtime.actor_link import ClassAppearanceComponent

    project = _project()
    root = Path(__file__).resolve().parents[1] / "reference_projects" / "arpg_demo"
    scene = _scene_with_player(project)
    looks = scene.get(ClassAppearanceComponent).parsed()
    assert set(looks) == {"warrior", "ranger", "mage"}
    roles = {
        cue.payload["clip"]
        for timeline in project.gameplay_library.timelines.values()
        for cue in timeline.cues
        if cue.kind.value == "animation"
    }
    assert {"attack", "attack2", "attack3", "jump"} <= roles  # the strips are all in use
    for class_id, (_sheet, clip_set) in looks.items():
        record = project.assets.get(clip_set)
        clips = json.loads((root / record.source_path).read_text(encoding="utf-8"))["clips"]
        for role in roles:
            for facing in ("down", "up", "left", "right"):
                assert f"{role}_{facing}" in clips, (class_id, role, facing)


def _scene_with_player(project):
    for scene in project.scenes():
        for entity in scene.entities():
            if entity.name == "Player":
                return entity
    raise AssertionError("no player")
