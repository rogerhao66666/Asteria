"""ASTERIA_SPEC §35 (D22 A6): loot — authored rarities, random affixes, rolled equipment that joins the build and the
save, loot on the ground and picking it up."""

import json
import random
from collections import Counter

import pytest

from asteria.core import Entity, Scene, Transform
from asteria.gameplay.modifiers import StatModifier
from asteria.gameplay.stats import StatBlock
from asteria.rpg import RpgDatabase
from asteria.rpg.drop_tables import DropEntry, DropTable
from asteria.rpg.items import (
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    ItemDefinition,
)
from asteria.rpg.loot import (
    DEFAULT_RARITIES,
    AffixDefinition,
    AffixModifier,
    RarityDefinition,
    RolledAffix,
    item_display_name,
    roll_affixes,
    roll_equipment,
    roll_rarity,
)
from asteria.runtime.loot import LootComponent, LooterComponent, LootSystem


def _db():
    db = RpgDatabase()
    db.add_equipment(
        EquipmentDefinition(
            "sword",
            "Sword",
            slot="weapon",
            tags=["weapon", "blade"],
            modifiers=[StatModifier("base", "attack", "add", 5)],
        )
    )
    db.add_equipment(EquipmentDefinition("ring", "Ring", slot="ring", tags=["jewel"]))
    db.add_item(ItemDefinition("potion", "Potion"))
    for rarity in (
        RarityDefinition("plain", "Plain", "#cccccc", 0, 0, 70, 0),
        RarityDefinition("magic", "Magic", "#4488ff", 1, 2, 25, 1, max_prefixes=1, max_suffixes=1),
        RarityDefinition("relic", "Relic", "#ff8800", 3, 3, 5, 2),
        RarityDefinition("unique", "Unique", "#c8a050", 0, 0, 0, 3),
    ):
        db.add_rarity(rarity)
    db.add_affix(
        AffixDefinition(
            "sharp",
            "Sharp",
            "prefix",
            [AffixModifier("attack", "add", 2, 4, integer=True, per_level=1)],
            allowed_tags=["blade"],
            group="attack",
        )
    )
    db.add_affix(
        AffixDefinition(
            "keen",
            "Keen",
            "prefix",
            [AffixModifier("attack", "add", 6, 8, integer=True)],
            allowed_tags=["blade"],
            min_level=10,
            group="attack",
        )
    )
    db.add_affix(AffixDefinition("of_bear", "of the Bear", "suffix", [AffixModifier("hp", "add", 10, 20)]))
    db.add_affix(AffixDefinition("of_fox", "of the Fox", "suffix", [AffixModifier("speed", "multiply", 1.05, 1.1)]))
    db.add_affix(
        AffixDefinition("gleaming", "Gleaming", "prefix", [AffixModifier("luck", "add", 1, 1)], slots=["ring"])
    )
    return db


def test_records_round_trip_and_the_database_keeps_them():
    db = _db()
    data = db.to_data()
    assert data["version"] == 30
    back = RpgDatabase.from_data(json.loads(json.dumps(data)))
    assert back.rarities == db.rarities and back.affixes == db.affixes
    old = dict(data, version=29)
    old.pop("rarities")
    old.pop("affixes")
    assert RpgDatabase.from_data(old).affixes == {}
    assert RpgDatabase().loot_rarities() == {r.rarity_id: r for r in DEFAULT_RARITIES}  # nothing authored: defaults
    with pytest.raises(ValueError):
        RarityDefinition("bad", color="orange")
    assert DropEntry("anything", rarity="mythic").rarity == "mythic"  # rarities are authored ids now


def test_rarity_rolls_follow_the_weights_and_luck_shifts_them():
    rarities = _db().rarities
    rng = random.Random(7)
    counts = Counter(roll_rarity(rarities, rng) for _ in range(4000))
    assert counts["unique"] == 0  # weight 0: only given by authored drops
    assert abs(counts["plain"] / 4000 - 0.70) < 0.03 and abs(counts["magic"] / 4000 - 0.25) < 0.03
    lucky = Counter(roll_rarity(rarities, rng, luck=2.0) for _ in range(4000))
    assert lucky["relic"] > counts["relic"] * 2


def test_affixes_respect_tags_slots_levels_groups_and_position_limits():
    db = _db()
    rng = random.Random(3)
    sword, ring = db.equipment["sword"], db.equipment["ring"]
    for _ in range(300):
        rolled = roll_affixes(sword, 5, db.rarities["magic"], db.affixes, rng)
        ids = [a.affix_id for a in rolled]
        assert 1 <= len(ids) <= 2 and "keen" not in ids and "gleaming" not in ids  # level 5 < 10; ring-only
        positions = Counter(db.affixes[i].position for i in ids)
        assert positions["prefix"] <= 1 and positions["suffix"] <= 1
        for affix in rolled:
            for stat, _operation, value in affix.entries:
                if affix.affix_id == "sharp":
                    assert stat == "attack" and value in (6.0, 7.0, 8.0)  # 2..4 plus 4 levels x 1
    high = [a.affix_id for _ in range(200) for a in roll_affixes(sword, 12, db.rarities["relic"], db.affixes, rng)]
    assert "keen" in high  # level 12 unlocks the stronger tier
    for _ in range(100):  # sharp and keen share a group: never both
        ids = [a.affix_id for a in roll_affixes(sword, 12, db.rarities["relic"], db.affixes, rng)]
        assert not {"sharp", "keen"} <= set(ids)
    assert {a.affix_id for _ in range(50) for a in roll_affixes(ring, 1, db.rarities["magic"], db.affixes, rng)} <= {
        "gleaming",
        "of_bear",
        "of_fox",
    }
    assert roll_affixes(sword, 30, db.rarities["unique"], db.affixes, rng) == ()


def test_rolled_equipment_joins_the_build_and_round_trips():
    db = _db()
    item = roll_equipment(
        db.equipment["sword"],
        random.Random(1),
        item_level=3,
        rarity_id="magic",
        rarities=db.rarities,
        affixes=db.affixes,
        instance_id="sword#1",
    )
    assert item.rarity == "magic" and item.item_level == 3 and item.rolled_affixes
    fixed = EquippedItem(
        db.equipment["sword"],
        instance_id="sword#2",
        rarity="magic",
        rolled_affixes=(
            RolledAffix("sharp", (("attack", "add", 7.0),)),
            RolledAffix("of_bear", (("hp", "add", 15.0),)),
        ),
    )
    loadout = EquipmentLoadout([EquipmentSlotDefinition("weapon")])
    loadout.equip("weapon", fixed, validate_requirements=False)
    stats = loadout.modifier_set().evaluate_block(StatBlock({"attack": 10, "hp": 100}))
    assert (stats.get("attack"), stats.get("hp")) == (22.0, 115.0)  # 10 + base 5 + rolled 7; 100 + 15
    assert item_display_name(fixed, db.affixes) == "Sharp Sword of the Bear"
    data = json.loads(json.dumps(fixed.to_data()))
    back = EquippedItem.from_data(data, equipment=db.equipment, attachments={})
    assert (back.rarity, back.rolled_affixes, back.modifiers()) == (
        fixed.rarity,
        fixed.rolled_affixes,
        fixed.modifiers(),
    )
    plain = EquippedItem(db.equipment["ring"], instance_id="ring#1").to_data()
    assert "rarity" not in plain and "rolled_affixes" not in plain  # plain instances save exactly as before


def test_the_equipment_bag_is_saved():
    from asteria.rpg.save_state import RpgRuntimeState

    db = _db()
    state = RpgRuntimeState()
    state.equipment_bag.append(
        roll_equipment(
            db.equipment["sword"],
            random.Random(2),
            rarity_id="relic",
            rarities=db.rarities,
            affixes=db.affixes,
            item_level=12,
            instance_id="bag#1",
        )
    )
    data = json.loads(json.dumps(state.to_data()))
    assert data["version"] == 8
    back = RpgRuntimeState.from_data(data, db)
    assert [i.to_data() for i in back.equipment_bag] == [i.to_data() for i in state.equipment_bag]


def _loot_scene(db, **looter):
    scene = Scene("Field")
    collected = []

    def collect(entity, loot, equipment):
        if loot.item_id == "potion":
            return False  # a full bag refuses the potions
        collected.append((entity, loot, equipment))
        return True

    system = LootSystem(db, rng=random.Random(5), collect=collect)
    scene.scheduler.add(system)
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(0, 0))
    hero.add_component(_set(LooterComponent(), **looter))
    return scene, system, hero, collected


def _set(component, **fields):
    for k, v in fields.items():
        setattr(component, k, v)
    return component


def test_drops_lie_on_the_ground_until_walked_over_or_picked_up():
    db = _db()
    scene, system, hero, collected = _loot_scene(db, pickup_radius=40, auto_pickup="currency")
    dropped = system.drop(scene, 10, 0, items={"sword": 2, "potion": 3}, currencies={"gold": 12}, level=4)
    assert len(dropped) == 4 and [e.kind for e in system.events].count("dropped") == 4
    swords = [e.get(LootComponent) for e in dropped if e.get(LootComponent).kind == "equipment"]
    assert all(s.rarity in db.rarities and json.loads(s.instance)["equipment_id"] == "sword" for s in swords)
    assert {label[3] for label in system.labels(scene)} >= {"3 Potion", "12 gold"}
    scene.update(1 / 60)
    assert [(c[1].kind, c[1].amount) for c in collected] == [("currency", 12)]  # walked over: only money
    assert system.pick_up_nearest(scene, hero)
    while system.pick_up_nearest(scene, hero):
        pass
    kinds = Counter(c[1].kind for c in collected)
    assert kinds["equipment"] == 2 and all(
        isinstance(c[2], EquippedItem) for c in collected if c[1].kind == "equipment"
    )
    assert [e.get(LootComponent).item_id for e, _ in scene.query(LootComponent)] == ["potion"]  # refused: stays
    far = system.drop(scene, 500, 0, items={"potion": 1})
    assert not system.pick_up_nearest(scene, hero) and scene.get_entity(far[0].id) is not None


def test_auto_pickup_by_rarity():
    db = _db()
    scene, system, hero, collected = _loot_scene(
        db, pickup_radius=100, auto_pickup="rarity_at_least", auto_min_rarity="magic"
    )
    system.drop(scene, 0, 0, items={"sword": 40}, level=12)
    scene.update(1 / 60)
    picked = {c[1].rarity for c in collected}
    left = {e.get(LootComponent).rarity for e, _ in scene.query(LootComponent)}
    assert picked and picked <= {"magic", "relic"} and left <= {"plain"}


def test_enemies_drop_loot_in_the_game_session_and_it_reaches_the_save(runtime):
    from asteria.gameplay.attacks import AttackDefinition
    from asteria.gameplay.formulas import ValueFormula
    from asteria.runtime.character_control import HitEvent, Hurtbox2DComponent
    from asteria.runtime.combat import CombatantComponent

    game = runtime.game
    db = game.project.rpg_database
    db.add_equipment(EquipmentDefinition("test_axe", "Test Axe", slot="weapon", tags=["weapon"]))
    db.add_affix(AffixDefinition("test_heavy", "Heavy", "prefix", [AffixModifier("attack", "add", 3, 3)]))
    db.add_drop_table(DropTable("test_axe_drop", guaranteed=[DropEntry("test_axe")]))
    game.project.gameplay_library.add_attack(AttackDefinition("test_kill", damage=ValueFormula.constant(999)))
    game.set_player_position(0.0, 0.0)
    game.player.add_component(_set(LooterComponent(), pickup_radius=60, auto_pickup="currency"))
    ogre = game.scene.add_entity(Entity("TestOgre"))
    ogre.add_component(Transform(20.0, 0.0))
    ogre.add_component(_set(Hurtbox2DComponent(), team="foe"))
    ogre.add_component(
        _set(
            CombatantComponent(), team="foe", drop_table_id="test_axe_drop", currency_drop="test_gold=5-5", loot_level=7
        )
    )
    gold_before = game.save.rpg_state.currencies.get("test_gold", 0)
    game.combat.pending.append(HitEvent(game.player.id, ogre.id, "test_kill", "hero"))
    game.field_update(1 / 60)
    game.field_update(1 / 60)
    assert game.save.rpg_state.currencies.get("test_gold", 0) == gold_before + 5
    assert any(e.get(LootComponent).item_id == "test_axe" for e, _ in game.scene.query(LootComponent))
    assert game.loot.pick_up_nearest(game.scene, game.player)
    axe = game.save.rpg_state.equipment_bag[-1]
    assert axe.equipment.equipment_id == "test_axe" and axe.item_level == 7
    restored = type(game.save.rpg_state).from_data(json.loads(json.dumps(game.save.rpg_state.to_data())), db)
    assert restored.equipment_bag[-1].to_data() == axe.to_data()


def test_rarities_and_affixes_are_authored_in_the_editor(runtime):
    from asteria.editor import EditorDocument
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers

    document = EditorDocument()
    document.set_project(runtime.game.project)
    categories = {a.category_id: a for a in IntegratedAuthoringControllers(document).rpg_categories()}
    categories["rarities"].create("test_mythic", RarityDefinition("test_mythic", "Mythic", "#ff0000", 6, 6, 0.1, 9))
    affixes = categories["affixes"]
    affixes.create(
        "test_vamp", AffixDefinition("test_vamp", "Vampiric", "prefix", [AffixModifier("drain", "add", 1, 3)])
    )
    data = affixes.encode(affixes.get("test_vamp"))
    data["weight"] = 0.5
    affixes.edit("test_vamp", affixes.decode(data))
    assert runtime.game.project.rpg_database.affixes["test_vamp"].weight == 0.5
    document.undo()
    assert runtime.game.project.rpg_database.affixes["test_vamp"].weight == 1.0
