from asteria.assets.rpg_maker_mv_weapon import weapon_visual_for_type


def test_weapon_type_selects_mv_attack_motion_and_three_separate_frames():
    system = {
        "weaponTypes": ["", "Dagger", "Sword", "Bow"],
        "attackMotions": [
            {"type": 0, "weaponImageId": 0},
            {"type": 1, "weaponImageId": 1},
            {"type": 1, "weaponImageId": 2},
            {"type": 2, "weaponImageId": 13},
        ],
    }

    sword = weapon_visual_for_type("Sword", system)
    bow = weapon_visual_for_type("Bow", system)

    assert sword.motion == "swing"
    assert sword.sheet_name == "Weapons1"
    assert sword.frames == ((0, 64, 96, 64), (96, 64, 96, 64), (192, 64, 96, 64))
    assert bow.motion == "missile"
    assert bow.sheet_name == "Weapons2"
    assert len(bow.frames) == 3
    assert weapon_visual_for_type("Unknown", system).motion == "unarmed"
