from __future__ import annotations

from dataclasses import dataclass


def _id(value, name):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


@dataclass(frozen=True, slots=True)
class BattleVisualAssetSet:
    battlefield_asset_id: str
    portrait_asset_id: str | None = None
    small_portrait_asset_id: str | None = None
    icon_asset_id: str | None = None

    def __post_init__(self):
        _id(self.battlefield_asset_id, "battlefield_asset_id")
        for name in ("portrait_asset_id", "small_portrait_asset_id", "icon_asset_id"):
            value = getattr(self, name)
            if value is not None:
                _id(value, name)


@dataclass(frozen=True, slots=True)
class BattleVisualTransform:
    scale_x: float = 1.0
    scale_y: float = 1.0
    anchor_x: float = 0.5
    anchor_y: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0
    z_order: int = 0

    def __post_init__(self):
        if float(self.scale_x) <= 0 or float(self.scale_y) <= 0:
            raise ValueError("visual scale must be > 0")
        if not 0.0 <= float(self.anchor_x) <= 1.0 or not 0.0 <= float(self.anchor_y) <= 1.0:
            raise ValueError("visual anchors must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class BattleVisualStateDefinition:
    state_id: str
    clip_role: str
    fallback_state_id: str = "idle"
    persistent: bool = False
    priority: int = 0

    def __post_init__(self):
        _id(self.state_id, "state_id")
        _id(self.clip_role, "clip_role")
        _id(self.fallback_state_id, "fallback_state_id")


@dataclass(frozen=True, slots=True)
class BattleCombatantVisualProfile:
    profile_id: str
    assets: BattleVisualAssetSet
    states: tuple[BattleVisualStateDefinition, ...]
    transform: BattleVisualTransform = BattleVisualTransform()
    battlefield_visible: bool = True
    hud_visible: bool = True

    def __post_init__(self):
        _id(self.profile_id, "profile_id")
        if not isinstance(self.assets, BattleVisualAssetSet):
            raise TypeError("assets must be BattleVisualAssetSet")
        states = tuple(self.states)
        if len({x.state_id for x in states}) != len(states):
            raise ValueError("duplicate visual state")
        if "idle" not in {x.state_id for x in states}:
            raise ValueError("visual profile requires idle state")

    def state(self, state_id):
        state_id = str(state_id)
        value = next((x for x in self.states if x.state_id == state_id), None)
        if value is not None:
            return value
        idle = next(x for x in self.states if x.state_id == "idle")
        return idle


@dataclass(frozen=True, slots=True)
class BattleCombatantVisualState:
    member_id: str
    profile_id: str
    state_id: str
    clip_role: str
    battlefield_asset_id: str
    portrait_asset_id: str | None
    small_portrait_asset_id: str | None
    icon_asset_id: str | None
    transform: BattleVisualTransform
    battlefield_visible: bool
    hud_visible: bool
    revision: int


class BattleCombatantVisualRuntime:
    """Presentation-only visual profile/state resolver.

    Separates battlefield representation from portrait/small portrait/icon and
    carries scale/anchor/offset/z-order independently of gameplay semantics.
    """

    def __init__(self):
        self._profiles = {}
        self._states = {}
        self.revision = 0

    def register(self, member_id, profile):
        member_id = _id(member_id, "member_id")
        if not isinstance(profile, BattleCombatantVisualProfile):
            raise TypeError("profile must be BattleCombatantVisualProfile")
        if member_id in self._profiles:
            raise ValueError(f"duplicate visual member: {member_id}")
        self._profiles[member_id] = profile
        return self.set_state(member_id, "idle")

    def set_state(self, member_id, state_id):
        member_id = _id(member_id, "member_id")
        profile = self._profiles[member_id]
        definition = profile.state(state_id)
        self.revision += 1
        state = BattleCombatantVisualState(
            member_id,
            profile.profile_id,
            definition.state_id,
            definition.clip_role,
            profile.assets.battlefield_asset_id,
            profile.assets.portrait_asset_id,
            profile.assets.small_portrait_asset_id,
            profile.assets.icon_asset_id,
            profile.transform,
            profile.battlefield_visible,
            profile.hud_visible,
            self.revision,
        )
        self._states[member_id] = state
        return state

    def state(self, member_id):
        return self._states[str(member_id)]

    def set_visibility(self, member_id, *, battlefield_visible=None, hud_visible=None):
        member_id = _id(member_id, "member_id")
        current = self._states[member_id]
        self.revision += 1
        state = BattleCombatantVisualState(
            current.member_id,
            current.profile_id,
            current.state_id,
            current.clip_role,
            current.battlefield_asset_id,
            current.portrait_asset_id,
            current.small_portrait_asset_id,
            current.icon_asset_id,
            current.transform,
            current.battlefield_visible
            if battlefield_visible is None
            else bool(battlefield_visible),
            current.hud_visible if hud_visible is None else bool(hud_visible),
            self.revision,
        )
        self._states[member_id] = state
        return state

    def replace_profile(self, member_id, profile, *, state_id="idle"):
        member_id = _id(member_id, "member_id")
        if not isinstance(profile, BattleCombatantVisualProfile):
            raise TypeError("profile must be BattleCombatantVisualProfile")
        self._profiles[member_id] = profile
        return self.set_state(member_id, state_id)

    def snapshot(self):
        return {
            "schema": "asteria.battle_combatant_visual_runtime",
            "version": 1,
            "revision": self.revision,
            "members": {
                member_id: {
                    "profile_id": state.profile_id,
                    "state_id": state.state_id,
                    "battlefield_visible": state.battlefield_visible,
                    "hud_visible": state.hud_visible,
                }
                for member_id, state in sorted(self._states.items())
            },
        }


def default_jrpg_visual_states():
    return (
        BattleVisualStateDefinition("idle", "idle", persistent=True),
        BattleVisualStateDefinition("attack", "attack"),
        BattleVisualStateDefinition("cast", "cast"),
        BattleVisualStateDefinition("hit", "hit"),
        BattleVisualStateDefinition("guard", "guard", persistent=True),
        BattleVisualStateDefinition("ko", "ko", persistent=True, priority=100),
        BattleVisualStateDefinition("revive", "revive"),
        BattleVisualStateDefinition("status", "status"),
        BattleVisualStateDefinition("transform", "transform"),
    )
