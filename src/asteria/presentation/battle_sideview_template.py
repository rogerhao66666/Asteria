from __future__ import annotations

from dataclasses import dataclass


def _id(value, name):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleSideviewZone:
    zone_id: str
    x: float
    y_start: float
    y_step: float
    facing: str
    depth_start: float = 0.0
    depth_step: float = 0.01

    def __post_init__(self):
        _id(self.zone_id, "zone_id")
        _id(self.facing, "facing")


@dataclass(frozen=True, slots=True)
class BattleSideviewPlacement:
    member_id: str
    zone_id: str
    x: float
    y: float
    facing: str
    depth: float
    visible: bool = True


@dataclass(frozen=True, slots=True)
class BattleSideviewTemplateProfile:
    template_id: str
    left_zone: BattleSideviewZone
    right_zone: BattleSideviewZone
    left_hud_zone_id: str = "hud.left"
    right_hud_zone_id: str = "hud.right"
    battlefield_center_x: float = 160.0
    max_visible_per_zone: int | None = None

    def __post_init__(self):
        _id(self.template_id, "template_id")
        if not isinstance(self.left_zone, BattleSideviewZone) or not isinstance(
            self.right_zone, BattleSideviewZone
        ):
            raise TypeError("left_zone/right_zone must be BattleSideviewZone")
        if self.left_zone.zone_id == self.right_zone.zone_id:
            raise ValueError("left/right zone ids must differ")
        if self.max_visible_per_zone is not None and int(self.max_visible_per_zone) <= 0:
            raise ValueError("max_visible_per_zone must be > 0 or None")


@dataclass(frozen=True, slots=True)
class BattleSideviewTemplateResult:
    template_id: str
    placements: tuple[BattleSideviewPlacement, ...]
    zone_by_member: tuple[tuple[str, str], ...]
    hud_zone_by_member: tuple[tuple[str, str], ...]
    overflow_member_ids: tuple[str, ...]


class BattleSideviewTemplateRuntime:
    """Presentation preset for classic side-view JRPG staging.

    Projects explicitly bind opaque canonical members/sides to left or right.
    The template never infers player/enemy semantics from IDs.
    """

    def __init__(self, profile=None):
        self.profile = profile or default_sideview_jrpg_profile()
        if not isinstance(self.profile, BattleSideviewTemplateProfile):
            raise TypeError("profile must be BattleSideviewTemplateProfile")

    def resolve(self, *, left_member_ids, right_member_ids):
        left = tuple(str(x) for x in left_member_ids)
        right = tuple(str(x) for x in right_member_ids)
        all_ids = left + right
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("duplicate member across side-view zones")

        placements = []
        zone_by_member = []
        hud_zone_by_member = []
        overflow = []
        for values, zone, hud_zone in (
            (left, self.profile.left_zone, self.profile.left_hud_zone_id),
            (right, self.profile.right_zone, self.profile.right_hud_zone_id),
        ):
            cap = self.profile.max_visible_per_zone
            visible_values = values if cap is None else values[:cap]
            overflow.extend(values[len(visible_values) :])
            for index, member_id in enumerate(values):
                visible = member_id in visible_values
                placements.append(
                    BattleSideviewPlacement(
                        member_id,
                        zone.zone_id,
                        float(zone.x),
                        float(zone.y_start + index * zone.y_step),
                        zone.facing,
                        float(zone.depth_start + index * zone.depth_step),
                        visible,
                    )
                )
                zone_by_member.append((member_id, zone.zone_id))
                hud_zone_by_member.append((member_id, hud_zone))
        return BattleSideviewTemplateResult(
            self.profile.template_id,
            tuple(placements),
            tuple(zone_by_member),
            tuple(hud_zone_by_member),
            tuple(overflow),
        )


def default_sideview_jrpg_profile():
    # Visual grammar only:
    # left-side bodies face right; right-side bodies face left.
    return BattleSideviewTemplateProfile(
        "asteria.sideview_jrpg.default",
        BattleSideviewZone("battle.left", 72.0, 82.0, 24.0, "right", 0.20, 0.01),
        BattleSideviewZone("battle.right", 248.0, 82.0, 24.0, "left", 0.20, 0.01),
        left_hud_zone_id="hud.left",
        right_hud_zone_id="hud.right",
        battlefield_center_x=160.0,
        max_visible_per_zone=None,
    )
