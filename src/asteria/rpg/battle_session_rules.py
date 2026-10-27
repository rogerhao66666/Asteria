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
    # counters every combatant carries for one battle (stat stages, a charge...): name ->
    # [minimum, maximum, start]; effects change them like any resource, expressions read them
    battle_counters: dict = None
    # turn order from an expression of the combatant (``self``) instead of its speed stat:
    # e.g. a speed scaled by a stage counter and halved by a state (gameplay/expressions.py)
    initiative_expression: str = ""
    # the stat whose value orders the turns when no expression is given (D91: the Speed stat
    # was the engine's own choice; an author may name SPD, AGI or any stat)
    initiative_stat: str = "speed"
    # every hit's damage after the interaction rules (weakness, resistance...), from an
    # expression of ``value`` (that damage), ``source`` and ``target``: a last random spread,
    # whole numbers, a floor of 1... ("" = the damage as it is)
    final_damage_expression: str = ""
    # the attacker's stat (a percentage) that pierces the target's stats in damage formulas:
    # 30 leaves 70% of the defence a formula subtracts (D89; "" = none)
    penetration_stat: str = ""
    # every battle rolls its own dice (seeded from the save's battle count) instead of the
    # same fixed sequence each time
    vary_seed: bool = False
    # losing a battle: "game_over", or "respawn" - healed back at the last respawn point
    # (SET_RESPAWN), losing ``defeat_currency_loss`` of ``defeat_currency``, then the event
    # ``defeat_event`` runs (someone who looked after the party)
    defeat: str = "game_over"
    defeat_currency: str = ""
    defeat_currency_loss: float = 0.0
    defeat_event: str = ""
    OPTIONAL_DATA = {
        "defeat": "game_over",
        "defeat_currency": "",
        "defeat_currency_loss": 0.0,
        "defeat_event": "",
        "action_timing": "immediate",
        "boost_mode": "repeat",
        "shield_resource_id": "",
        "weakness_outcome_tag": "outcome.weak",
        "battle_counters": {},
        "initiative_expression": "",
        "initiative_stat": "speed",
        "final_damage_expression": "",
        "penetration_stat": "",
        "vary_seed": False,
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
        battle_counters=None,
        initiative_expression="",
        final_damage_expression="",
        penetration_stat="",
        vary_seed=False,
        initiative_stat="speed",
        defeat="game_over",
        defeat_currency="",
        defeat_currency_loss=0.0,
        defeat_event="",
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
        counters = {}
        for name, values in dict(battle_counters or {}).items():
            low, high, start = (float(x) for x in values)
            if not (isfinite(low) and isfinite(high) and low <= start <= high):
                raise ValueError(f"battle counter {name} needs minimum <= start <= maximum")
            counters[_id(name, "battle counter")] = [low, high, start]
        object.__setattr__(self, "battle_counters", dict(sorted(counters.items())))
        initiative_expression = str(initiative_expression or "").strip()
        if initiative_expression:
            from asteria.gameplay.expressions import check_expression

            check_expression(initiative_expression, ("self",))
        object.__setattr__(self, "initiative_expression", initiative_expression)
        object.__setattr__(self, "initiative_stat", str(initiative_stat or "").strip())
        final_damage_expression = str(final_damage_expression or "").strip()
        if final_damage_expression:
            from asteria.gameplay.expressions import check_expression

            check_expression(final_damage_expression, ("value", "source", "target"))
        object.__setattr__(self, "final_damage_expression", final_damage_expression)
        object.__setattr__(self, "penetration_stat", str(penetration_stat or "").strip())
        object.__setattr__(self, "vary_seed", bool(vary_seed))
        if defeat not in ("game_over", "respawn"):
            raise ValueError("defeat must be game_over or respawn")
        loss = float(defeat_currency_loss)
        if not 0 <= loss <= 1:
            raise ValueError("defeat_currency_loss must be between 0 and 1")
        object.__setattr__(self, "defeat", defeat)
        object.__setattr__(self, "defeat_currency", str(defeat_currency or "").strip())
        object.__setattr__(self, "defeat_currency_loss", loss)
        object.__setattr__(self, "defeat_event", str(defeat_event or "").strip())

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
            **({"battle_counters": dict(self.battle_counters)} if self.battle_counters else {}),
            **(
                {"initiative_expression": self.initiative_expression}
                if self.initiative_expression
                else {}
            ),
            **(
                {"initiative_stat": self.initiative_stat}
                if self.initiative_stat != "speed"
                else {}
            ),
            **(
                {"final_damage_expression": self.final_damage_expression}
                if self.final_damage_expression
                else {}
            ),
            **({"penetration_stat": self.penetration_stat} if self.penetration_stat else {}),
            **({"vary_seed": True} if self.vary_seed else {}),
            **({"defeat": self.defeat} if self.defeat != "game_over" else {}),
            **({"defeat_currency": self.defeat_currency} if self.defeat_currency else {}),
            **(
                {"defeat_currency_loss": self.defeat_currency_loss}
                if self.defeat_currency_loss
                else {}
            ),
            **({"defeat_event": self.defeat_event} if self.defeat_event else {}),
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
            battle_counters=data.get("battle_counters"),
            initiative_expression=data.get("initiative_expression", ""),
            initiative_stat=data.get("initiative_stat", "speed"),
            final_damage_expression=data.get("final_damage_expression", ""),
            penetration_stat=data.get("penetration_stat", ""),
            vary_seed=data.get("vary_seed", False),
            defeat=data.get("defeat", "game_over"),
            defeat_currency=data.get("defeat_currency", ""),
            defeat_currency_loss=data.get("defeat_currency_loss", 0.0),
            defeat_event=data.get("defeat_event", ""),
        )
