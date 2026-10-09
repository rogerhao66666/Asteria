"""RPG Maker MV weapon type to independent attack overlay frames."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WeaponVisual:
    motion: str
    sheet_name: str = ""
    frames: tuple[tuple[int, int, int, int], ...] = ()


def weapon_visual_for_type(weapon_type: str, system_data: dict) -> WeaponVisual:
    """Resolve MV's attack motion and 3-frame WeaponsN sheet layout."""
    weapon_types = system_data.get("weaponTypes", ())
    motions = system_data.get("attackMotions", ())
    try:
        type_id = weapon_types.index(str(weapon_type))
        entry = motions[type_id]
        motion = {0: "thrust", 1: "swing", 2: "missile"}[int(entry["type"])]
        image_id = int(entry["weaponImageId"])
    except (AttributeError, ValueError, IndexError, KeyError, TypeError):
        return WeaponVisual("unarmed")
    if image_id <= 0:
        return WeaponVisual(motion)
    page = (image_id - 1) // 12 + 1
    index = (image_id - 1) % 12
    x = index // 6 * 3 * 96
    y = index % 6 * 64
    return WeaponVisual(motion, f"Weapons{page}", tuple((x + frame * 96, y, 96, 64) for frame in range(3)))
