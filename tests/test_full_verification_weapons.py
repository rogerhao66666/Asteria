"""Full Verification weapons: whole Lucifer pictures (none cut in half) and the rarity each
picture names; Roger's Sunbrand is the Rare Greatsword."""

import sys
from pathlib import Path

from PIL import Image

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.rpg.items import EquipmentDefinition  # noqa: E402

LUCIFER = DEMO / "playable_assets" / "lucifer" / "icons"


def test_every_weapon_has_a_whole_picture_and_a_rarity():
    project, _game = smoke.load()
    db = project.rpg_database
    weapons = [e for e in db.equipment.values() if e.slot == "weapon"]
    assert len(weapons) >= 18
    for weapon in weapons:
        assert weapon.rarity in db.rarities, weapon.equipment_id
        if weapon.equipment_id in ("w_demon_ring", "w_bow", "w_longbow"):
            continue  # a ring and two drawn bows
        # Lucifer weapons are 32 x 16 pictures; the arsenal's (D61) are 7Soul's 34 x 34 icons
        size = (34, 34) if "icons_7soul/" in weapon.icon_id else (32, 16)
        assert Image.open(DEMO / weapon.icon_id).size == size, weapon.equipment_id
    sunbrand = db.equipment["w_sunbrand"]
    rare = (
        Path.home()
        / "Downloads/free_assets/Foozle_2DS0005_Lucifer_Equipment_Pixel_Art/Equipment"
        / "Weapons/Png/Rare Greatsword.png"
    )
    if rare.exists():  # the picture Roger's sword wears (the packs live outside the repo)
        mine = Image.open(DEMO / sunbrand.icon_id).convert("RGBA")
        assert mine.tobytes() == Image.open(rare).convert("RGBA").tobytes()
    assert sunbrand.rarity == "rare" and db.equipment["w_bone_scepter"].rarity == "mythic"


def test_rarity_is_equipment_data():
    sword = EquipmentDefinition("sword", slot="weapon", rarity="rare")
    assert EquipmentDefinition.from_data(sword.to_data()).rarity == "rare"
    assert "rarity" not in EquipmentDefinition("plain", slot="weapon").to_data()
