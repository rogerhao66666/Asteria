"""Equipment sets: bonuses for wearing several pieces together (ASTERIA_SPEC §21)."""

from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import StatModifier


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


@dataclass(frozen=True, slots=True)
class EquipmentSetBonus:
    """What a set grants once ``pieces`` of its equipment are equipped."""

    pieces: int
    modifiers: tuple[StatModifier, ...] = ()
    tags: tuple[str, ...] = ()
    granted_abilities: tuple[str, ...] = ()

    def __init__(self, pieces, *, modifiers=(), tags=(), granted_abilities=()):
        pieces = int(pieces)
        if pieces < 1:
            raise ValueError("pieces must be >= 1")
        modifiers = tuple(modifiers)
        if any(not isinstance(x, StatModifier) for x in modifiers):
            raise TypeError("modifiers must be StatModifier values")
        object.__setattr__(self, "pieces", pieces)
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag") for x in tags})))
        object.__setattr__(
            self, "granted_abilities", tuple(dict.fromkeys(_id(x, "ability id") for x in granted_abilities))
        )

    def to_data(self):
        return {
            "pieces": self.pieces,
            "modifiers": [x.to_data() for x in self.modifiers],
            "tags": list(self.tags),
            "granted_abilities": list(self.granted_abilities),
        }

    @classmethod
    def from_data(cls, data):
        return cls(
            data["pieces"],
            modifiers=[StatModifier.from_data(x) for x in data["modifiers"]],
            tags=data["tags"],
            granted_abilities=data["granted_abilities"],
        )


@dataclass(frozen=True, slots=True)
class EquipmentSetDefinition:
    set_id: str
    display_name: str
    equipment_ids: tuple[str, ...]
    bonuses: tuple[EquipmentSetBonus, ...]

    def __init__(self, set_id, display_name=None, *, equipment_ids=(), bonuses=()):
        equipment_ids = tuple(dict.fromkeys(_id(x, "equipment id") for x in equipment_ids))
        bonuses = tuple(sorted(bonuses, key=lambda x: x.pieces))
        if any(not isinstance(x, EquipmentSetBonus) for x in bonuses):
            raise TypeError("bonuses must be EquipmentSetBonus values")
        if len({x.pieces for x in bonuses}) != len(bonuses):
            raise ValueError("set bonuses must have distinct piece counts")
        if bonuses and bonuses[-1].pieces > len(equipment_ids):
            raise ValueError("a set bonus needs more pieces than the set has")
        object.__setattr__(self, "set_id", _id(set_id, "set_id"))
        object.__setattr__(self, "display_name", str(display_name or set_id))
        object.__setattr__(self, "equipment_ids", equipment_ids)
        object.__setattr__(self, "bonuses", bonuses)

    def pieces_equipped(self, equipment_ids):
        return len(set(self.equipment_ids) & set(equipment_ids))

    def active_bonuses(self, equipment_ids):
        count = self.pieces_equipped(equipment_ids)
        return tuple(x for x in self.bonuses if x.pieces <= count)

    def to_data(self):
        return {
            "schema": "asteria.rpg.equipment_set",
            "version": 1,
            "set_id": self.set_id,
            "display_name": self.display_name,
            "equipment_ids": list(self.equipment_ids),
            "bonuses": [x.to_data() for x in self.bonuses],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.equipment_set" or data.get("version") != 1:
            raise ValueError("unsupported equipment set")
        return cls(
            data["set_id"],
            data["display_name"],
            equipment_ids=data["equipment_ids"],
            bonuses=[EquipmentSetBonus.from_data(x) for x in data["bonuses"]],
        )
