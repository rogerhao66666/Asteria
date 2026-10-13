"""Project-level rules a game session applies around the Battle Core."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


ACTION_TIMING_MODES = ("immediate", "timeline")
BOOST_MODES = ("repeat", "power")


@dataclass(frozen=True, slots=True)
class BattleSessionRules:
    """Names the project resources and triggers a playable battle relies on.

    The engine assigns no meaning to resource or trigger names; a project
    states here which resource knocks a combatant out, which trigger every
    hit emits into gauge compositions, and which resource powers repeated
    "boost" actions. Empty resource ids disable that behaviour.
    """

    rules_id: str
    knockout_resource_id: str = ""
    hit_trigger: str = "battle.hit"
    boost_resource_id: str = ""
    boost_cost_per_level: float = 1.0
    boost_max_level: int = 0
    # How authored ActionTimingDefinitions act in play (GP-02): "immediate" resolves every action
    # at once
    # (timings only shape the presentation); "timeline" delays resolution by startup + cast time
    # and pushes
    # the actor's next turn back by the cast and its recovery. Left out of the data while
    # "immediate".
    action_timing: str = "immediate"
    # Boost (GP-02 / BTL-03): "repeat" repeats the action once per level; "power" uses it once and
    # leaves
    # the effect to interaction rules. Either way the actor carries the tags "boost" and
    # "boost.<level>"
    # during the action, so rules can scale anything; an ability tagged "boost.repeat" or
    # "boost.power"
    # overrides the project default (e.g. attacks repeat, spells grow stronger).
    boost_mode: str = "repeat"
    # Battle screen: the battle resource shown as each enemy's shield count ("" = the first break
    # gauge's), and
    # the interaction outcome tag that marks a weakness hit (its rule is then shown as revealed for
    # that enemy).
    shield_resource_id: str = ""
    weakness_outcome_tag: str = "outcome.weak"
    OPTIONAL_DATA = {
        "action_timing": "immediate",
        "boost_mode": "repeat",
        "shield_resource_id": "",
        "weakness_outcome_tag": "outcome.weak",
    }

    def __init__(
        self,
        rules_id,
        *,
        knockout_resource_id="",
        hit_trigger="battle.hit",
        boost_resource_id="",
        boost_cost_per_level=1.0,
        boost_max_level=0,
        action_timing="immediate",
        boost_mode="repeat",
        shield_resource_id="",
        weakness_outcome_tag="outcome.weak",
    ):
        cost = float(boost_cost_per_level)
        if not isfinite(cost) or cost <= 0:
            raise ValueError("boost_cost_per_level must be finite and positive")
        max_level = int(boost_max_level)
        if max_level < 0:
            raise ValueError("boost_max_level must be >= 0")
        object.__setattr__(self, "rules_id", _id(rules_id, "rules_id"))
        object.__setattr__(self, "knockout_resource_id", str(knockout_resource_id).strip())
        object.__setattr__(self, "hit_trigger", _id(hit_trigger, "hit_trigger"))
        object.__setattr__(self, "boost_resource_id", str(boost_resource_id).strip())
        object.__setattr__(self, "boost_cost_per_level", cost)
        object.__setattr__(self, "boost_max_level", max_level)
        if action_timing not in ACTION_TIMING_MODES:
            raise ValueError(f"action_timing must be one of {ACTION_TIMING_MODES}")
        object.__setattr__(self, "action_timing", action_timing)
        if boost_mode not in BOOST_MODES:
            raise ValueError(f"boost_mode must be one of {BOOST_MODES}")
        object.__setattr__(self, "boost_mode", boost_mode)
        object.__setattr__(self, "shield_resource_id", str(shield_resource_id or "").strip())
        object.__setattr__(self, "weakness_outcome_tag", str(weakness_outcome_tag or "").strip())

    @property
    def boost_enabled(self):
        return bool(self.boost_resource_id) and self.boost_max_level > 0

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_session_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "knockout_resource_id": self.knockout_resource_id,
            "hit_trigger": self.hit_trigger,
            "boost_resource_id": self.boost_resource_id,
            "boost_cost_per_level": self.boost_cost_per_level,
            "boost_max_level": self.boost_max_level,
            **({"action_timing": self.action_timing} if self.action_timing != "immediate" else {}),
            **({"boost_mode": self.boost_mode} if self.boost_mode != "repeat" else {}),
            **({"shield_resource_id": self.shield_resource_id} if self.shield_resource_id else {}),
            **(
                {"weakness_outcome_tag": self.weakness_outcome_tag}
                if self.weakness_outcome_tag != "outcome.weak"
                else {}
            ),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.battle_session_rules" or data.get("version") != 1:
            raise ValueError("unsupported battle session rules")
        return cls(
            data["rules_id"],
            knockout_resource_id=data["knockout_resource_id"],
            hit_trigger=data["hit_trigger"],
            boost_resource_id=data["boost_resource_id"],
            boost_cost_per_level=data["boost_cost_per_level"],
            boost_max_level=data["boost_max_level"],
            action_timing=data.get("action_timing", "immediate"),
            boost_mode=data.get("boost_mode", "repeat"),
            shield_resource_id=data.get("shield_resource_id", ""),
            weakness_outcome_tag=data.get("weakness_outcome_tag", "outcome.weak"),
        )
