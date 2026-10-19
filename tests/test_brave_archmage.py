"""Aldric the Brave and Archmage in the Full Verification demo: every weapon, every element,
their trees, the Demon Ring and the stronger foes."""

import sys
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402
import trial_brave as brave  # noqa: E402


def _game():
    _project, game = smoke.load()
    return game


def test_aldric_is_a_brave_with_an_archmage_sub_job():
    game = _game()
    progress = game.ensure_actor_progression(smoke.HERO)
    assert list(progress.active_class_ids[:2]) == ["brave", "archmage"]
    db = game.project.rpg_database
    weapons = {t for t in db.classes["brave"].granted_tags if t.startswith("capability.weapon.")}
    assert weapons == {f"capability.weapon.{w}" for w in brave.WEAPONS}  # every weapon
    growth = db.classes["brave"].level_growth
    assert growth["str"] > 0 and growth["int"] > 0  # STR and INT (power and magic) together
    library = game.project.gameplay_library.abilities
    for element in brave.ELEMENTS:  # every element: a bolt and a storm
        for kind in ("bolt", "storm"):
            assert f"damage.{element}" in library.get(f"{element}_{kind}").tags


def test_the_two_trees_are_built_in_every_style():
    db = _game().project.rpg_database
    brave_nodes = {n.node_id: n for n in db.progression_graphs["brave_tree"].nodes}
    masteries = [f"brave_mastery_{w}" for w in brave.WEAPONS]
    assert all(m in brave_nodes for m in masteries)
    saint = brave_nodes["brave_weapon_saint"]
    assert {r.node_id for r in saint.prerequisites} == set(masteries)  # every weapon mastered
    for suffix in ("spec_paladin", "spec_warlord_capstone", "rune_echo", "book"):
        assert f"brave_{suffix}" in brave_nodes, suffix
    assert sum(1 for n in brave_nodes.values() if n.exclusive_group == "brave_oath") == 3
    arch = {n.node_id for n in db.progression_graphs["archmage_tree"].nodes}
    for element in brave.ELEMENTS:
        for part in (f"school_{element}", f"{element}_bolt", f"{element}_storm"):
            assert f"arch_{part}" in arch, part
    assert {"arch_prismatic", "archmage_spec_destruction", "archmage_book"} <= arch
    assert len(brave_nodes) >= 35 and len(arch) >= 50
    attributes = {n.node_id for n in db.progression_graphs["attributes"].nodes}
    assert attributes == {f"attr_{a}" for a in ("str", "dex", "int", "luk", "vit")}


def test_the_demon_ring_takes_cards_gems_and_charms_and_strikes_five_times():
    game = _game()
    db = game.project.rpg_database
    ring = db.equipment["w_demon_ring"]
    kinds = [s.accepted_tags[0] for s in ring.sockets]
    assert kinds.count("card") == 3 and kinds.count("gem") == 2 and kinds.count("charm") == 2
    assert len(game.project.gameplay_library.abilities.get("attack_ring").hits) == 5
    # as the family chest does it: in Aldric's second hand
    smoke.world(game, "EQUIP_ITEM", actor_id=smoke.HERO, equipment_id="w_demon_ring", index=1)
    loadout = game.save.rpg_state.loadouts[smoke.HERO]
    weapons = loadout.equipped("weapon")
    worn = next(w for w in weapons if w.equipment.equipment_id == "w_demon_ring")
    before = game.resolve_actor_build(smoke.HERO).stats.get("power")
    game.save.rpg_state.inventory.add("charm_lion_item", 1)
    game.socket_item(smoke.HERO, worn.instance_id, "h1", "charm_lion_item")
    # the Lion Charm gives STR +15: power += 2 x STR
    assert game.resolve_actor_build(smoke.HERO).stats.get("power") == before + 30


def test_foes_are_far_stronger_and_fear_wind_and_earth():
    db = _game().project.rpg_database
    slinger = db.enemies["goblin_slinger"]
    scale = brave.FOE_SCALE
    assert slinger.resources["vitality"] == 1500 * scale["vitality"]
    assert slinger.stats["power"] == 46 * scale["stats"]["power"]
    assert "weak.wind" in slinger.tags and "weak.earth" in db.enemies["skeleton_hunter"].tags
    rule = db.interaction_rules["weak_wind"]
    assert rule.source_tags_all == ("damage.wind",) and "outcome.weak" in rule.outcome_tags
    assert db.interaction_rules["mastery_sword"].multiplier == 1.25


def test_battle_mechanics_are_felt():
    game = _game()
    db = game.project.rpg_database
    assert db.interaction_rules["weak_fire"].multiplier == 1.8
    crit = db.interaction_rules["crit_x"]  # x(2 + 1% x critical damage)
    assert crit.multiplier == 2.0 and crit.multiplier_source_terms == {"crit_damage": 0.01}
    warlord = db.enemies["crimson_warlord"]
    weak = [t for t in warlord.tags if t.startswith("weak.")]
    assert len(weak) >= 8 and warlord.resources["shield"] >= 30  # many weaknesses, thick shield
    assert {"trait.guard", "trait.dodge"} <= set(warlord.tags)
    guard = db.outcome_checks["foe_guard"]
    assert "state.broken" in guard.blocked_target_tags  # a broken foe cannot guard
    hits = game.project.gameplay_library.abilities.get("valiant_slash").hits
    assert all({"foe_guard", "foe_dodge"} <= set(h["checks"]) for h in hits)
    states = game.project.gameplay_library.states
    assert states.get("broken").duration == brave.BROKEN_TURNS
    tick = states.get("poison").periodic[0].effect.operations[0].value
    assert tick.terms[0].source.value == "target_resource_max"  # a share of max health
    assert db.classes["brave"].resource_growth["vitality"] == 160
    feedback = game.project.battle_presentation_library
    profile = feedback.get("feedback", feedback.ids("feedback")[0])
    assert dict(profile.outcome_tag_labels)["outcome.weak"] == "WEAK"
    assert dict(profile.threshold_labels)["break"] == "BREAK!"
