from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite


def _positive(value, label):
    value = float(value)
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be finite and > 0")
    return value


@dataclass(frozen=True, slots=True)
class BattlePartyPlacement:
    member_id: str
    zone: str
    index: int
    density: str
    visible: bool


@dataclass(frozen=True, slots=True)
class BattlePartyZoneLayout:
    zone: str
    density: str
    visible_member_ids: tuple[str, ...]
    hidden_member_ids: tuple[str, ...]

    @property
    def overflow_count(self):
        return len(self.hidden_member_ids)


@dataclass(frozen=True, slots=True)
class BattlePartyLayoutResult:
    placements: tuple[BattlePartyPlacement, ...]
    zones: tuple[BattlePartyZoneLayout, ...]

    def placement_for(self, member_id):
        member_id = str(member_id)
        return next(x for x in self.placements if x.member_id == member_id)

    def zone(self, zone):
        zone = str(zone)
        return next(x for x in self.zones if x.zone == zone)


@dataclass(frozen=True, slots=True)
class BattlePartyLayoutPolicy:
    """Presentation-only density/overflow policy for arbitrary combatant counts.

    It never limits party membership. When screen space cannot display every
    member at the requested detail, it reduces visual density and finally uses an
    overflow summary while keeping canonical members untouched.
    """

    expanded_row_height: float = 42.0
    compact_row_height: float = 29.0
    minimal_row_height: float = 19.0
    compact_resource_limit: int = 3
    minimal_resource_limit: int = 1
    compact_status_limit: int = 4
    minimal_status_limit: int = 2
    default_zone: str = "left"

    SCHEMA = "asteria.battle_party_layout_policy"
    VERSION = 1

    def __post_init__(self):
        _positive(self.expanded_row_height, "expanded_row_height")
        _positive(self.compact_row_height, "compact_row_height")
        _positive(self.minimal_row_height, "minimal_row_height")
        if not (self.expanded_row_height >= self.compact_row_height >= self.minimal_row_height):
            raise ValueError("party row heights must satisfy expanded >= compact >= minimal")
        for name in (
            "compact_resource_limit", "minimal_resource_limit",
            "compact_status_limit", "minimal_status_limit",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} must be >= 0")
        if not str(self.default_zone).strip():
            raise ValueError("default_zone is required")

    def _density(self, count, available_height):
        if count <= 0:
            return "expanded", 0
        available_height = max(0.0, float(available_height))
        if count * self.expanded_row_height <= available_height:
            return "expanded", count
        if count * self.compact_row_height <= available_height:
            return "compact", count
        capacity = max(1, floor(available_height / self.minimal_row_height)) if available_height > 0 else 1
        return "minimal", min(count, capacity)

    def resolve(self, member_ids, *, zone_by_member=None, focus_member_id=None, available_height=130.0):
        member_ids = tuple(str(x) for x in member_ids)
        if len(member_ids) != len(set(member_ids)):
            raise ValueError("duplicate party layout member")
        zone_by_member = {str(k): str(v) for k, v in dict(zone_by_member or {}).items()}
        focus_member_id = None if focus_member_id is None else str(focus_member_id)

        grouped = {}
        zone_order = []
        for member_id in member_ids:
            zone = zone_by_member.get(member_id, self.default_zone)
            if not zone:
                zone = self.default_zone
            if zone not in grouped:
                grouped[zone] = []
                zone_order.append(zone)
            grouped[zone].append(member_id)

        placements = []
        zones = []
        for zone in zone_order:
            values = list(grouped[zone])
            density, capacity = self._density(len(values), available_height)
            visible = values[:capacity]
            if focus_member_id in values and focus_member_id not in visible and visible:
                visible[-1] = focus_member_id
            visible_set = set(visible)
            hidden = [x for x in values if x not in visible_set]

            for index, member_id in enumerate(values):
                is_visible = member_id in visible_set
                visible_index = visible.index(member_id) if is_visible else index
                placements.append(BattlePartyPlacement(
                    member_id, zone, visible_index, density, is_visible
                ))
            zones.append(BattlePartyZoneLayout(
                zone, density, tuple(visible), tuple(hidden)
            ))
        return BattlePartyLayoutResult(tuple(placements), tuple(zones))

    def resource_limit(self, density):
        density = str(density)
        if density == "minimal":
            return self.minimal_resource_limit
        if density == "compact":
            return self.compact_resource_limit
        return None

    def status_limit(self, density):
        density = str(density)
        if density == "minimal":
            return self.minimal_status_limit
        if density == "compact":
            return self.compact_status_limit
        return None

    def row_height(self, density):
        density = str(density)
        if density == "minimal":
            return self.minimal_row_height
        if density == "compact":
            return self.compact_row_height
        return self.expanded_row_height

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "expanded_row_height": self.expanded_row_height,
            "compact_row_height": self.compact_row_height,
            "minimal_row_height": self.minimal_row_height,
            "compact_resource_limit": self.compact_resource_limit,
            "minimal_resource_limit": self.minimal_resource_limit,
            "compact_status_limit": self.compact_status_limit,
            "minimal_status_limit": self.minimal_status_limit,
            "default_zone": self.default_zone,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle party layout policy")
        return cls(**{
            key: value for key, value in data.items()
            if key not in {"schema", "version"}
        })
