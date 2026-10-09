"""RPG Maker MV weapon types translated into generic combatant overlays.

MV-specific data (``System.json`` weapon types/attack motions, the ``WeaponsN``
sheet layout and ``mv-weapon-type:`` equipment tags) stays in this adapter.
Battle Presentation only receives :class:`CombatantOverlay` values.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass

MV_WEAPON_TYPE_TAG = "mv-weapon-type:"


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


def weapon_type_for_loadout(loadout, system_data: dict) -> str:
    """Return the MV weapon type named by the equipped weapon's tag, or ``""``."""
    equipped = () if loadout is None else loadout.equipped("weapon")
    tags = () if not equipped else equipped[0].equipment.tags
    selected = next((tag.split(":", 1)[1] for tag in tags if tag.startswith(MV_WEAPON_TYPE_TAG)), "")
    names = {str(name).casefold(): str(name) for name in system_data.get("weaponTypes", ())}
    return names.get(selected.casefold(), "")


def weapon_overlay_for_loadout(loadout, system_data: dict, asset_id_for_sheet: Callable[[str], str]):
    """Translate an equipped MV weapon into a generic attack overlay (armor stays inert)."""
    from asteria.presentation import CombatantOverlay

    visual = weapon_visual_for_type(weapon_type_for_loadout(loadout, system_data), system_data)
    if not visual.frames or not visual.sheet_name:
        return None
    asset_id = asset_id_for_sheet(visual.sheet_name)
    if not asset_id:
        return None
    return CombatantOverlay(asset_id, visual.frames)


def apply_weapon_overlays(
    animation,
    member_ids: Iterable[str],
    loadouts: Mapping[str, object],
    system_data: dict,
    asset_id_for_sheet: Callable[[str], str],
) -> None:
    """Set or clear each member's overlay on a ``BattlePresentationRuntime``."""
    for member_id in member_ids:
        overlay = weapon_overlay_for_loadout(loadouts.get(member_id), system_data, asset_id_for_sheet)
        animation.set_overlay(member_id, overlay)
