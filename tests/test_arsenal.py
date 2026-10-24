"""The Full Verification demo's arsenal (D61 G1): nine weapon kinds, five rarities each, the
new kinds' attacks, 7Soul pictures, refining and sockets."""

import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import trial_arsenal as arsenal  # noqa: E402

KINDS = ("sword", "axe", "spear", "bow", "dagger", "staff", "book", "fist", "throw")
RARITIES = ("common", "magic", "rare", "legendary", "mythic")


@pytest.fixture(scope="module")
def project():
    from asteria.editor import EditorDocument
    from asteria.project import Project

    return Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)


def _weapons(project):
    by_kind = defaultdict(list)
    for weapon in project.rpg_database.equipment.values():
        if weapon.slot == "weapon":
            kind = next((t[6:] for t in weapon.tags if t.startswith("equip.")), "")
            by_kind[kind].append(weapon)
    return by_kind


def test_every_kind_has_five_or_more_weapons_in_every_rarity(project):
    by_kind = _weapons(project)
    for kind in KINDS:
        assert len(by_kind[kind]) >= 5, kind
        assert set(RARITIES) <= {w.rarity for w in by_kind[kind]}, kind


def test_the_new_kinds_fight_with_their_own_attack(project):
    abilities = project.gameplay_library.abilities
    targeting = project.rpg_database.battle_targeting
    for kind in ("book", "fist", "throw"):
        attack = abilities.require(f"attack_{kind}")
        assert f"weapon.{kind}" in attack.tags and attack.hits  # weaknesses read the tag
        assert not any(t in attack.tags for t in ("weapon.staff", "weapon.dagger", "weapon.bow"))
        assert f"attack_{kind}" in targeting
        assert attack.display_name == f"Attack ({kind})" and attack.icon_id
        for weapon in _weapons(project)[kind]:
            assert weapon.granted_abilities == (f"attack_{kind}",)


def test_rarity_sets_the_stats_and_sockets(project):
    db = project.rpg_database
    for weapons in arsenal.WEAPONS.values():
        for weapon_id, _name, rarity, element, _picture in weapons:
            weapon = db.equipment[weapon_id]
            stats = {m.stat: m.value for m in weapon.modifiers}
            main = arsenal.TIERS[rarity][0]
            assert main in stats.values()
            if element and rarity in ("rare", "legendary", "mythic"):
                assert stats[f"{element}_attack"] == arsenal.TIERS[rarity][1]
            sockets = [s.socket_id for s in weapon.sockets]
            assert sockets == {
                "common": [],
                "magic": ["g1"],
            }.get(rarity, ["g1", "g2", "c1"])
            assert "weapon" in weapon.tags  # the workshop's +N refine takes it
    refine = db.refine_rules["plus"]
    assert "weapon" in refine.equipment_tags


def test_the_pictures_are_the_libraries_cc0_icons_copied_into_the_demo(project):
    library = REPO / "asset_library" / "opengameart" / "7Soul_496_RPG_Icons"
    assert "CC0" in (library / "Readme.txt").read_text(encoding="utf-8")
    for weapons in arsenal.WEAPONS.values():
        for weapon_id, _name, _rarity, _element, picture in weapons:
            icon = project.rpg_database.equipment[weapon_id].icon_id
            assert icon == f"playable_assets/icons_7soul/{picture}"
            assert (DEMO / icon).read_bytes() == (library / picture).read_bytes()
    credits = (DEMO / "playable_assets" / "CREDITS.md").read_text(encoding="utf-8")
    assert "7Soul1" in credits and "icons_7soul" in credits
    third_party = (REPO / "THIRD_PARTY_ASSETS.md").read_text(encoding="utf-8")
    assert "7Soul_496_RPG_Icons" in third_party


def test_applying_again_adds_nothing_and_every_name_has_chinese(project, tmp_path):
    import trial_zh_data

    assert arsenal.apply(project, DEMO) == 0
    table = dict(project.rpg_database.locale_tables["zh-TW"].entries)
    for weapon_id in arsenal.weapon_ids():
        assert f"data.equipment.{weapon_id}.name" in table
    assert trial_zh_data.missing(project) == []


def test_a_new_weapon_is_worn_and_its_attack_lands(project, monkeypatch):
    pytest.importorskip("pygame")
    from asteria.events.world_commands import WorldCommand
    from asteria.runtime.game_session import GameSessionRuntime

    stats = {}
    for weapon_id in ("w_leather_wraps", "w_titan_fists"):
        game = GameSessionRuntime(project, project.game_start.instantiate(project))
        for name, args in (
            ("GIVE_EQUIPMENT", {"equipment_id": weapon_id}),
            (
                "EQUIP_ITEM",
                {"actor_id": "hero_01", "equipment_id": weapon_id, "slot_id": "weapon"},
            ),
        ):
            game.world_commands.dispatch(WorldCommand(name, args))
        worn = game.save.rpg_state.loadouts["hero_01"].equipped("weapon")
        assert weapon_id in {w.equipment.equipment_id for w in worn}
        stats[weapon_id] = game.resolve_actor_build("hero_01").stats.get("power")
        game.start_encounter("woods_patrol")
        foe = game.active_enemy_ids()[0]
        start = game.battle.member(foe).subject.resources.current("vitality")
        for _ in range(4):
            game.use_ability("hero_01", "attack_fist", (foe,))
        assert game.battle.member(foe).subject.resources.current("vitality") < start
    assert stats["w_titan_fists"] - stats["w_leather_wraps"] == 65 - 12
