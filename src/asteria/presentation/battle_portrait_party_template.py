from __future__ import annotations

from dataclasses import dataclass


def _id(value, name):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattlePortraitPartyZone:
    zone_id: str
    x: float
    y_start: float
    y_step: float
    facing: str = "left"
    depth_start: float = 0.0
    depth_step: float = 0.01

    def __post_init__(self):
        _id(self.zone_id, "zone_id")
        _id(self.facing, "facing")


@dataclass(frozen=True, slots=True)
class BattlePortraitPartyPlacement:
    member_id: str
    battlefield_visible: bool
    hud_visible: bool
    battlefield_zone_id: str | None
    hud_zone_id: str
    x: float | None = None
    y: float | None = None
    facing: str | None = None
    depth: float | None = None


@dataclass(frozen=True, slots=True)
class BattlePortraitPartyTemplateProfile:
    template_id: str
    battlefield_zone: BattlePortraitPartyZone
    portrait_hud_zone_id: str = "hud.party"
    battlefield_hud_zone_id: str = "hud.battlefield"
    hide_portrait_party_bodies: bool = True
    max_visible_battlefield_members: int | None = None

    def __post_init__(self):
        _id(self.template_id, "template_id")
        if not isinstance(self.battlefield_zone, BattlePortraitPartyZone):
            raise TypeError("battlefield_zone must be BattlePortraitPartyZone")
        _id(self.portrait_hud_zone_id, "portrait_hud_zone_id")
        _id(self.battlefield_hud_zone_id, "battlefield_hud_zone_id")
        if self.max_visible_battlefield_members is not None and int(self.max_visible_battlefield_members) <= 0:
            raise ValueError("max_visible_battlefield_members must be > 0 or None")


@dataclass(frozen=True, slots=True)
class BattlePortraitPartyTemplateResult:
    template_id: str
    placements: tuple[BattlePortraitPartyPlacement, ...]
    portrait_party_ids: tuple[str, ...]
    battlefield_member_ids: tuple[str, ...]
    overflow_battlefield_ids: tuple[str, ...]


class BattlePortraitPartyTemplateRuntime:
    """Presentation grammar with portrait/HUD party and battlefield opponents.

    Membership is explicitly supplied by the project/controller. The template
    does not infer player/enemy semantics from IDs and does not change gameplay.
    """

    def __init__(self, profile=None):
        self.profile = profile or default_dungeon_portrait_party_profile()
        if not isinstance(self.profile, BattlePortraitPartyTemplateProfile):
            raise TypeError("profile must be BattlePortraitPartyTemplateProfile")

    def resolve(self, *, portrait_party_ids, battlefield_member_ids):
        portrait_party = tuple(str(x) for x in portrait_party_ids)
        battlefield = tuple(str(x) for x in battlefield_member_ids)
        all_ids = portrait_party + battlefield
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("duplicate member across portrait/battlefield roles")

        placements = []
        for member_id in portrait_party:
            placements.append(
                BattlePortraitPartyPlacement(
                    member_id,
                    battlefield_visible=not self.profile.hide_portrait_party_bodies,
                    hud_visible=True,
                    battlefield_zone_id=None if self.profile.hide_portrait_party_bodies else "battle.party",
                    hud_zone_id=self.profile.portrait_hud_zone_id,
                )
            )

        zone = self.profile.battlefield_zone
        cap = self.profile.max_visible_battlefield_members
        visible = battlefield if cap is None else battlefield[:cap]
        overflow = battlefield[len(visible) :]
        for index, member_id in enumerate(battlefield):
            is_visible = member_id in visible
            placements.append(
                BattlePortraitPartyPlacement(
                    member_id,
                    battlefield_visible=is_visible,
                    hud_visible=True,
                    battlefield_zone_id=zone.zone_id,
                    hud_zone_id=self.profile.battlefield_hud_zone_id,
                    x=float(zone.x),
                    y=float(zone.y_start + index * zone.y_step),
                    facing=zone.facing,
                    depth=float(zone.depth_start + index * zone.depth_step),
                )
            )

        return BattlePortraitPartyTemplateResult(
            self.profile.template_id,
            tuple(placements),
            portrait_party,
            battlefield,
            tuple(overflow),
        )


def default_dungeon_portrait_party_profile():
    return BattlePortraitPartyTemplateProfile(
        "asteria.dungeon_portrait_party.default",
        BattlePortraitPartyZone("battle.front", 160.0, 68.0, 28.0, "left", 0.20, 0.01),
        portrait_hud_zone_id="hud.party",
        battlefield_hud_zone_id="hud.enemy",
        hide_portrait_party_bodies=True,
        max_visible_battlefield_members=None,
    )
