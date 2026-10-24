"""Map area rules: floor damage, slippery floors, footsteps, region events, restrictions, stealth,
area music and names, and random encounters a step may start.

An area is named by a key - ``region:<id>`` (the id painted on the map's region layer) or
``tag:<name>`` (a tag on the tile under the feet). Project data attaches an ``AreaRule`` to a key;
``MapRulesRuntime`` turns "where is this entity" into events (enter / leave / step / damage /
footstep), blocking, sliding and a visibility scale for field enemies. Nothing here knows tiles
or renderers: the caller supplies ``keys_at(x, y)``.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite


def _text(value):
    return str(value or "").strip()


def _non_negative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


FALSE_WORDS = ("0", "false", "off", "no")
AUTORUN_WHEN = ("always", "enter")


@dataclass(frozen=True, slots=True)
class AreaRule:
    """What happens in one kind of area (every part is optional)."""

    key: str
    damage_resource: str = ""
    damage_per_second: float = 0.0
    can_kill: bool = False
    slippery: bool = False
    slip_seconds: float = 0.6
    footstep_cue: str = ""
    step_distance: float = 28.0
    blocks: tuple[str, ...] = ()
    visibility: float = 1.0
    on_enter: str = ""
    on_leave: str = ""
    on_step: str = ""
    switch: str = ""
    battle_background: str = ""
    music: str = ""
    title: str = ""
    encounters: tuple[tuple[str, float], ...] = ()
    encounter_chance: float = 0.0
    encounter_first_step: float = 1.0
    # programs run while the player is in the area and nothing else runs, the first whose
    # condition holds: ({"switch"|"variable": name, "value": v, "program": id}, ...) - a
    # condition of a variable compares equal, of a switch to ``value`` (default true); the
    # program must change what it tests, or it runs again; ``"when": "enter"`` runs it once
    # on coming into the area instead (after ``on_enter``)
    autorun: tuple[dict, ...] = ()

    def __init__(
        self,
        key,
        *,
        damage_resource="",
        damage_per_second=0.0,
        can_kill=False,
        slippery=False,
        slip_seconds=0.6,
        footstep_cue="",
        step_distance=28.0,
        blocks=(),
        visibility=1.0,
        on_enter="",
        on_leave="",
        on_step="",
        switch="",
        battle_background="",
        music="",
        title="",
        encounters=(),
        encounter_chance=0.0,
        encounter_first_step=1.0,
        autorun=(),
    ):
        key = _text(key)
        if not key.startswith(("region:", "tag:")) or key.endswith(":"):
            raise ValueError("an area key is 'region:<id>' or 'tag:<name>'")
        s = object.__setattr__
        s(self, "key", key)
        s(self, "damage_resource", _text(damage_resource))
        s(self, "damage_per_second", _non_negative(damage_per_second, "damage_per_second"))
        s(self, "can_kill", bool(can_kill))
        s(self, "slippery", bool(slippery))
        s(self, "slip_seconds", _non_negative(slip_seconds, "slip_seconds"))
        s(self, "footstep_cue", _text(footstep_cue))
        distance = float(step_distance)
        if not isfinite(distance) or distance <= 0:
            raise ValueError("step_distance must be finite and > 0")
        s(self, "step_distance", distance)
        s(self, "blocks", tuple(sorted({_text(x) for x in blocks if _text(x)})))
        visibility = _non_negative(visibility, "visibility")
        s(self, "visibility", visibility)
        s(self, "on_enter", _text(on_enter))
        s(self, "on_leave", _text(on_leave))
        s(self, "on_step", _text(on_step))
        s(self, "switch", _text(switch))
        s(self, "battle_background", _text(battle_background))
        s(self, "music", _text(music))
        s(self, "title", str(title or ""))
        pairs = encounters.items() if isinstance(encounters, dict) else encounters
        table = []
        for encounter_id, weight in pairs:
            weight = _non_negative(weight, "encounter weight")
            if _text(encounter_id) and weight > 0:
                table.append((_text(encounter_id), weight))
        s(self, "encounters", tuple(table))
        chance = _non_negative(encounter_chance, "encounter_chance")
        if chance > 1:
            raise ValueError("encounter_chance must be between 0 and 1")
        s(self, "encounter_chance", chance)
        first = _non_negative(encounter_first_step, "encounter_first_step")
        if first > 1:
            raise ValueError("encounter_first_step must be between 0 and 1")
        s(self, "encounter_first_step", first)
        entries = []
        for entry in autorun:
            entry = dict(entry)
            if not _text(entry.get("program")):
                raise ValueError("an autorun entry needs a program")
            if bool(_text(entry.get("switch"))) == bool(_text(entry.get("variable"))):
                raise ValueError("an autorun entry tests one switch or one variable")
            if entry.get("when", "always") not in AUTORUN_WHEN:
                raise ValueError("an autorun entry runs 'always' or on 'enter'")
            entries.append(entry)
        s(self, "autorun", tuple(entries))

    def autorun_program(self, get_switch, get_variable, when="always"):
        """The program of the first autorun entry of ``when`` ("always": while the player is
        here and nothing runs; "enter": once, on coming into the area) whose condition holds
        now ('' for none)."""
        for entry in self.autorun:
            if entry.get("when", "always") != when:
                continue
            value = entry.get("value")
            if entry.get("switch"):
                wanted = True if value in (None, "") else str(value).lower() not in FALSE_WORDS
                held = bool(get_switch(entry["switch"])) == wanted
            else:  # compared as text: 1 and "1" are the same value
                held = str(get_variable(entry["variable"])) == str(0 if value is None else value)
            if held:
                return entry["program"]
        return ""

    def pick_encounter(self, rng):
        """One encounter id of this area's table by weight ('' when it has none)."""
        total = sum(weight for _, weight in self.encounters)
        if total <= 0:
            return ""
        roll = rng.random() * total
        for encounter_id, weight in self.encounters:
            roll -= weight
            if roll < 0:
                return encounter_id
        return self.encounters[-1][0]

    def to_data(self):
        data = {"key": self.key}
        defaults = AreaRule(self.key)
        for name in (
            "damage_resource",
            "damage_per_second",
            "can_kill",
            "slippery",
            "slip_seconds",
            "footstep_cue",
            "step_distance",
            "blocks",
            "visibility",
            "on_enter",
            "on_leave",
            "on_step",
            "switch",
            "battle_background",
            "music",
            "title",
            "encounter_chance",
            "encounter_first_step",
        ):
            value = getattr(self, name)
            if value != getattr(defaults, name):
                data[name] = list(value) if isinstance(value, tuple) else value
        if self.encounters:
            data["encounters"] = dict(self.encounters)
        if self.autorun:
            data["autorun"] = [dict(entry) for entry in self.autorun]
        return data

    @classmethod
    def from_data(cls, data):
        data = dict(data)
        return cls(data.pop("key"), **data)


@dataclass(frozen=True, slots=True)
class MapRuleSet:
    """The project's area rules plus the stealth multipliers that do not depend on the area.

    ``region_layer`` names the tile layer whose tile ids are region ids. ``crouch_visibility`` and
    ``still_visibility`` scale how far enemies notice a player who is crouching / standing still.
    """

    rules_id: str
    rules: tuple[AreaRule, ...] = ()
    region_layer: str = "regions"
    crouch_visibility: float = 1.0
    still_visibility: float = 1.0

    def __init__(
        self,
        rules_id,
        rules=(),
        *,
        region_layer="regions",
        crouch_visibility=1.0,
        still_visibility=1.0,
    ):
        s = object.__setattr__
        s(self, "rules_id", _text(rules_id) or _raise("rules_id is required"))
        rules = tuple(rules)
        if any(not isinstance(x, AreaRule) for x in rules):
            raise TypeError("rules must be AreaRule values")
        if len({x.key for x in rules}) != len(rules):
            raise ValueError("duplicate area rule key")
        s(self, "rules", rules)
        s(self, "region_layer", _text(region_layer) or "regions")
        s(self, "crouch_visibility", _non_negative(crouch_visibility, "crouch_visibility"))
        s(self, "still_visibility", _non_negative(still_visibility, "still_visibility"))

    def rule(self, key):
        return next((x for x in self.rules if x.key == key), None)

    def to_data(self):
        return {
            "schema": "asteria.rpg.map_rule_set",
            "version": 1,
            "rules_id": self.rules_id,
            "region_layer": self.region_layer,
            "crouch_visibility": self.crouch_visibility,
            "still_visibility": self.still_visibility,
            "rules": [x.to_data() for x in self.rules],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.map_rule_set" or data.get("version") != 1:
            raise ValueError("unsupported map rule set")
        return cls(
            data["rules_id"],
            tuple(AreaRule.from_data(x) for x in data.get("rules", ())),
            region_layer=data.get("region_layer", "regions"),
            crouch_visibility=data.get("crouch_visibility", 1.0),
            still_visibility=data.get("still_visibility", 1.0),
        )


def _raise(message):
    raise ValueError(message)


@dataclass(frozen=True, slots=True)
class MapEvent:
    """``kind``: enter, leave, step, damage or footstep; ``rule`` is the AreaRule it came from."""

    kind: str
    entity_id: str
    rule: AreaRule
    amount: float = 0.0


class MapRulesRuntime:
    """Applies a ``MapRuleSet`` to entities moving around a map.

    ``keys_at(x, y)`` returns the area keys under a point; ``switches(name) -> bool`` gates rules
    that name a switch (default: all on).
    """

    def __init__(self, ruleset, keys_at, switches=None):
        if not isinstance(ruleset, MapRuleSet):
            raise TypeError("ruleset must be MapRuleSet")
        self.ruleset = ruleset
        self.keys_at = keys_at
        self.switches = switches or (lambda name: True)
        self._inside = {}  # entity id -> frozenset of rule keys it is in
        self._last = {}  # entity id -> last (x, y)
        self._walked = {}  # (entity id, rule key) -> distance since the last step
        self._slide = {}  # entity id -> (dx, dy, seconds left)

    def rules_at(self, x, y):
        found = []
        for key in self.keys_at(x, y):
            rule = self.ruleset.rule(key)
            if rule is not None and (not rule.switch or self.switches(rule.switch)):
                found.append(rule)
        return tuple(found)

    def roll_encounter(self, x, y, rng, before=()):
        """A step at ``(x, y)``: the encounter it starts, or ''. Each area there with an
        encounter table rolls its ``encounter_chance`` - times ``encounter_first_step`` when the
        step came from outside it (``before``: the area keys of the cell the step left); the
        first that hits picks from its table by weight."""
        for rule in self.rules_at(x, y):
            if not rule.encounters or rule.encounter_chance <= 0:
                continue
            chance = rule.encounter_chance
            if rule.key not in before:
                chance *= rule.encounter_first_step
            if rng.random() < chance:
                return rule.pick_encounter(rng)
        return ""

    def battle_background(self, x, y):
        """The battle background asset of the first area at the point that names one."""
        return next((r.battle_background for r in self.rules_at(x, y) if r.battle_background), "")

    # -- restrictions --------------------------------------------------------------------------
    def blocked(self, group, x, y):
        """True when an area at the point bars entities of ``group`` (or ``all``)."""
        return any(group in rule.blocks or "all" in rule.blocks for rule in self.rules_at(x, y))

    # -- events --------------------------------------------------------------------------------
    def advance(self, entity_id, x, y, dt):
        """Move ``entity_id`` to ``(x, y)`` after ``dt`` seconds; returns the ``MapEvent`` list."""
        entity_id, dt = str(entity_id), max(0.0, float(dt))
        events = []
        now = self.rules_at(x, y)
        keys = frozenset(rule.key for rule in now)
        before = self._inside.get(entity_id, frozenset())
        for rule in now:
            if rule.key not in before:
                events.append(MapEvent("enter", entity_id, rule))
        for key in sorted(before - keys):
            rule = self.ruleset.rule(key)
            if rule is not None:
                events.append(MapEvent("leave", entity_id, rule))
                self._walked.pop((entity_id, key), None)
        previous = self._last.get(entity_id)
        moved = 0.0 if previous is None else hypot(x - previous[0], y - previous[1])
        for rule in now:
            if rule.damage_resource and rule.damage_per_second and dt:
                events.append(MapEvent("damage", entity_id, rule, rule.damage_per_second * dt))
            if moved and (rule.footstep_cue or rule.on_step):
                walked = self._walked.get((entity_id, rule.key), 0.0) + moved
                while walked >= rule.step_distance:
                    walked -= rule.step_distance
                    events.append(
                        MapEvent("footstep" if rule.footstep_cue else "step", entity_id, rule)
                    )
                    if rule.footstep_cue and rule.on_step:
                        events.append(MapEvent("step", entity_id, rule))
                self._walked[(entity_id, rule.key)] = walked
        self._inside[entity_id] = keys
        self._last[entity_id] = (float(x), float(y))
        return tuple(events)

    # -- sliding -------------------------------------------------------------------------------
    def shape_movement(self, entity_id, dx, dy, x, y):
        """The direction to move: on a slippery floor the last direction carries on briefly."""
        entity_id = str(entity_id)
        slippery = [r for r in self.rules_at(x, y) if r.slippery]
        if not slippery:
            self._slide.pop(entity_id, None)
            return dx, dy
        seconds = max(r.slip_seconds for r in slippery)
        if dx or dy:
            self._slide[entity_id] = (dx, dy, seconds)
            return dx, dy
        state = self._slide.get(entity_id)
        return (0.0, 0.0) if state is None else (state[0], state[1])

    def settle_slide(self, entity_id, dt, *, blocked=False):
        """Count the slide down after a move (or end it when the entity ran into something)."""
        entity_id = str(entity_id)
        state = self._slide.get(entity_id)
        if state is None:
            return
        left = state[2] - max(0.0, float(dt))
        if blocked or left <= 0:
            del self._slide[entity_id]
        else:
            self._slide[entity_id] = (state[0], state[1], left)

    def sliding(self, entity_id):
        return str(entity_id) in self._slide

    # -- stealth -------------------------------------------------------------------------------
    def visibility(self, x, y, *, crouching=False, moving=True):
        """How noticeable an entity at ``(x, y)`` is, as a multiplier on enemy sight radii."""
        scale = 1.0
        for rule in self.rules_at(x, y):
            scale = min(scale, rule.visibility)
        if crouching:
            scale *= self.ruleset.crouch_visibility
        if not moving:
            scale *= self.ruleset.still_visibility
        return scale
