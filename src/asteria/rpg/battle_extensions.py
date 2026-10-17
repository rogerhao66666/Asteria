"""Optional battle rules layered on ``BattleRuntime`` (taunt, life steal, overkill, steal ...).

Everything is project data: the rules name the resource, stat and tag ids they act on, and an
empty id switches that rule off. ``BattleRuntime`` only calls the five hooks below; it assumes
nothing about HP, "taunt" or any game. Without extensions a battle behaves exactly as before.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from asteria.gameplay.effects import EffectOperationKind

OPENINGS = ("normal", "preemptive", "surprise")


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _fraction(value, label):
    value = float(value)
    if not isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{label} must be between 0 and 1")
    return value


def _non_negative(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class StealEntry:
    item_id: str
    chance: float = 1.0
    amount: int = 1

    def __init__(self, item_id, chance=1.0, amount=1):
        object.__setattr__(self, "item_id", _id(item_id, "item_id"))
        object.__setattr__(self, "chance", _fraction(chance, "chance"))
        amount = int(amount)
        if amount < 1:
            raise ValueError("amount must be >= 1")
        object.__setattr__(self, "amount", amount)


@dataclass(frozen=True, slots=True)
class StealTable:
    """What one kind of enemy can be robbed of. ``target_key`` matches the target's member id, its
    enemy id (the part of ``enemy:serial`` before the colon) or any of its subject tags; ``once``
    allows a single successful theft per target."""

    target_key: str
    entries: tuple[StealEntry, ...] = ()
    once: bool = True

    def __init__(self, target_key, entries=(), once=True):
        object.__setattr__(self, "target_key", _id(target_key, "target_key"))
        entries = tuple(entries)
        if any(not isinstance(x, StealEntry) for x in entries):
            raise TypeError("entries must be StealEntry values")
        object.__setattr__(self, "entries", entries)
        object.__setattr__(self, "once", bool(once))


GAIN_EVENTS = ("dealt", "taken", "kill", "action")


@dataclass(frozen=True, slots=True)
class ResourceGain:
    """A battle resource (rage, TP, momentum...) that fills when something happens.

    ``event``: ``dealt`` (the actor hurt an opponent), ``taken`` (a fighter was hurt), ``kill``
    (the actor knocked an opponent out) or ``action`` (the actor used an ability). The gain is
    ``flat`` plus ``per_damage`` x the damage, plus ``per_max_hp`` x (damage / the victim's maximum
    of the rules' ``damage_resource``). ``ability_tag`` limits it to abilities with that tag.
    """

    event: str
    resource: str
    flat: float = 0.0
    per_damage: float = 0.0
    per_max_hp: float = 0.0
    ability_tag: str = ""
    shared: bool = False
    side: str = "heroes"

    def __init__(
        self,
        event,
        resource,
        *,
        flat=0.0,
        per_damage=0.0,
        per_max_hp=0.0,
        ability_tag="",
        shared=False,
        side="heroes",
    ):
        if event not in GAIN_EVENTS:
            raise ValueError(f"event must be one of {GAIN_EVENTS}")
        s = object.__setattr__
        s(self, "event", event)
        s(self, "resource", _id(resource, "resource"))
        for name, value in (
            ("flat", flat),
            ("per_damage", per_damage),
            ("per_max_hp", per_max_hp),
        ):
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
            s(self, name, float(value))
        s(self, "ability_tag", str(ability_tag or "").strip())
        s(self, "shared", bool(shared))
        s(self, "side", str(side or "heroes").strip() or "heroes")

    def amount(self, damage=0.0, victim_max=0.0):
        share = damage / victim_max if victim_max > 0 else 0.0
        return self.flat + self.per_damage * damage + self.per_max_hp * share

    def to_data(self):
        data = {"event": self.event, "resource": self.resource}
        for name in ("flat", "per_damage", "per_max_hp"):
            if getattr(self, name):
                data[name] = getattr(self, name)
        if self.ability_tag:
            data["ability_tag"] = self.ability_tag
        if self.shared:
            data["shared"] = True
        if self.side != "heroes":
            data["side"] = self.side
        return data


@dataclass(frozen=True, slots=True)
class BattleExtensionRules:
    """Which optional battle rules a project switches on, by resource / stat / tag id.

    - ``damage_resource``: the resource whose loss counts as damage (life steal, overkill).
    - ``taunt_tag``: a subject tag; while a taunting opponent is a valid target, single-target
      actions must pick among the taunters.
    - ``lifesteal_stat``: an actor stat in 0..1; that share of damage dealt is given back to the
      actor's ``damage_resource``.
    - ``overkill_rate`` / ``overkill_cap``: ``overkill_scale`` = 1 + rate * min(overkill / max,
      cap) for a defeated target, for the reward step to multiply.
    - ``use_limits``: ability id -> uses per battle per user.
    - ``mastery``: ability id -> uses needed for each mastery level; the user carries the tags
      ``mastery.<ability>`` and ``mastery.<ability>.<level>`` so rules can scale anything.
    - ``preemptive_chance`` / ``surprise_chance``: opening odds for ``roll_opening``.
    - ``steal_tables``: see ``StealTable``.
    - ``row_tag_prefix``: when set, a member standing in a formation slot with tag ``front`` is
      given the subject tag ``<prefix>front`` (so interaction rules can key off the row).
    """

    rules_id: str
    damage_resource: str = ""
    taunt_tag: str = ""
    lifesteal_stat: str = ""
    overkill_rate: float = 0.0
    overkill_cap: float = 1.0
    use_limits: tuple[tuple[str, int], ...] = ()
    mastery: tuple[tuple[str, tuple[int, ...]], ...] = ()
    preemptive_chance: float = 0.0
    surprise_chance: float = 0.0
    steal_tables: tuple[StealTable, ...] = ()
    row_tag_prefix: str = ""
    gains: tuple[ResourceGain, ...] = ()
    shared_gauges: tuple[tuple[str, float], ...] = ()

    def __init__(
        self,
        rules_id,
        *,
        damage_resource="",
        taunt_tag="",
        lifesteal_stat="",
        overkill_rate=0.0,
        overkill_cap=1.0,
        use_limits=None,
        mastery=None,
        preemptive_chance=0.0,
        surprise_chance=0.0,
        steal_tables=(),
        row_tag_prefix="",
        gains=(),
        shared_gauges=None,
    ):
        s = object.__setattr__
        s(self, "rules_id", _id(rules_id, "rules_id"))
        s(self, "damage_resource", str(damage_resource or "").strip())
        s(self, "taunt_tag", str(taunt_tag or "").strip())
        s(self, "lifesteal_stat", str(lifesteal_stat or "").strip())
        s(self, "overkill_rate", _non_negative(overkill_rate, "overkill_rate"))
        s(self, "overkill_cap", _non_negative(overkill_cap, "overkill_cap"))
        limits = []
        for ability_id, uses in dict(use_limits or {}).items():
            if int(uses) < 1:
                raise ValueError("use limits must be >= 1")
            limits.append((_id(ability_id, "ability_id"), int(uses)))
        s(self, "use_limits", tuple(sorted(limits)))
        levels = []
        for ability_id, thresholds in dict(mastery or {}).items():
            values = tuple(int(x) for x in thresholds)
            if not values or any(x < 1 for x in values) or list(values) != sorted(set(values)):
                raise ValueError("mastery thresholds must be increasing positive use counts")
            levels.append((_id(ability_id, "ability_id"), values))
        s(self, "mastery", tuple(sorted(levels)))
        s(self, "preemptive_chance", _fraction(preemptive_chance, "preemptive_chance"))
        s(self, "surprise_chance", _fraction(surprise_chance, "surprise_chance"))
        if self.preemptive_chance + self.surprise_chance > 1.0:
            raise ValueError("preemptive and surprise chances may not exceed 1 together")
        tables = tuple(steal_tables)
        if any(not isinstance(x, StealTable) for x in tables):
            raise TypeError("steal_tables must be StealTable values")
        s(self, "steal_tables", tables)
        s(self, "row_tag_prefix", str(row_tag_prefix or "").strip())
        gains = tuple(gains)
        if any(not isinstance(x, ResourceGain) for x in gains):
            raise TypeError("gains must be ResourceGain values")
        s(self, "gains", gains)
        gauges = []
        for gauge_id, maximum in dict(shared_gauges or {}).items():
            maximum = float(maximum)
            if not isfinite(maximum) or maximum <= 0:
                raise ValueError("a shared gauge maximum must be finite and > 0")
            gauges.append((_id(gauge_id, "gauge id"), maximum))
        s(self, "shared_gauges", tuple(sorted(gauges)))

    def to_data(self):
        return {
            "schema": "asteria.rpg.battle_extension_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "damage_resource": self.damage_resource,
            "taunt_tag": self.taunt_tag,
            "lifesteal_stat": self.lifesteal_stat,
            "overkill_rate": self.overkill_rate,
            "overkill_cap": self.overkill_cap,
            "use_limits": dict(self.use_limits),
            "mastery": {key: list(value) for key, value in self.mastery},
            "preemptive_chance": self.preemptive_chance,
            "surprise_chance": self.surprise_chance,
            "steal_tables": [
                {
                    "target_key": t.target_key,
                    "once": t.once,
                    "entries": [
                        {"item_id": e.item_id, "chance": e.chance, "amount": e.amount}
                        for e in t.entries
                    ],
                }
                for t in self.steal_tables
            ],
            "row_tag_prefix": self.row_tag_prefix,
            **({"gains": [g.to_data() for g in self.gains]} if self.gains else {}),
            **({"shared_gauges": dict(self.shared_gauges)} if self.shared_gauges else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.battle_extension_rules" or data.get("version") != 1:
            raise ValueError("unsupported battle extension rules")
        return cls(
            data["rules_id"],
            damage_resource=data.get("damage_resource", ""),
            taunt_tag=data.get("taunt_tag", ""),
            lifesteal_stat=data.get("lifesteal_stat", ""),
            overkill_rate=data.get("overkill_rate", 0.0),
            overkill_cap=data.get("overkill_cap", 1.0),
            use_limits=data.get("use_limits"),
            mastery=data.get("mastery"),
            preemptive_chance=data.get("preemptive_chance", 0.0),
            surprise_chance=data.get("surprise_chance", 0.0),
            steal_tables=tuple(
                StealTable(
                    t["target_key"],
                    tuple(StealEntry(**e) for e in t.get("entries", ())),
                    t.get("once", True),
                )
                for t in data.get("steal_tables", ())
            ),
            row_tag_prefix=data.get("row_tag_prefix", ""),
            gains=tuple(ResourceGain(**x) for x in data.get("gains", ())),
            shared_gauges=data.get("shared_gauges"),
        )


@dataclass(frozen=True, slots=True)
class StealResult:
    stolen: bool
    item_id: str = ""
    amount: int = 0
    reason: str = ""


class BattleExtensionRuntime:
    """Per-battle state and hooks for ``BattleExtensionRules`` (see ``BattleRuntime``)."""

    def __init__(self, rules):
        if not isinstance(rules, BattleExtensionRules):
            raise TypeError("rules must be BattleExtensionRules")
        self.rules = rules
        self._limits = dict(rules.use_limits)
        self._mastery = dict(rules.mastery)
        self.uses = {}  # (member id, ability id) -> uses this battle
        self.mastery_uses = {}  # same key -> lifetime uses (caller may preload from the save)
        self.overkill = {}  # target id -> damage beyond what the target had left
        self.damage_dealt = {}  # actor id -> total damage dealt this battle
        self.lifesteal_healed = {}  # actor id -> total given back
        self.stolen_from = set()  # (target id, table key)
        self.opening = "normal"
        self.gained = {}  # (member id, resource id) -> total gained through ResourceGain rules
        self.shared = {}  # party-wide gauge id -> value (caller may preload from the save)
        self.on_shared_change = None  # callback(gauge_id, value) after a change
        self._raw = {}

    # -- availability --------------------------------------------------------------------------
    def uses_left(self, member_id, ability_id):
        """Uses left this battle, or ``None`` when the ability is not limited."""
        limit = self._limits.get(str(ability_id))
        if limit is None:
            return None
        return max(0, limit - self.uses.get((str(member_id), str(ability_id)), 0))

    def validate(self, battle, action):
        left = self.uses_left(action.actor_id, action.ability_id)
        if left is not None and left <= 0:
            raise ValueError(f"ability use limit reached: {action.ability_id}")

    # -- taunt ---------------------------------------------------------------------------------
    def filter_candidates(self, battle, actor_id, candidates):
        """Opponents holding the taunt tag replace the opponents list for single targeting."""
        tag = self.rules.taunt_tag
        if not tag:
            return candidates
        actor = battle.member(actor_id)
        taunters = tuple(
            x
            for x in candidates
            if battle.member(x).side != actor.side and battle.member(x).subject.tags.contains(tag)
        )
        if not taunters:
            return candidates
        kept = set(taunters)
        return tuple(x for x in candidates if battle.member(x).side == actor.side or x in kept)

    # -- action wrap ---------------------------------------------------------------------------
    def before_action(self, battle, action):
        res = self.rules.damage_resource
        self._raw = {}
        if not res:
            return {}
        snapshot = {}
        for member_id in {action.actor_id, *action.target_ids}:
            resources = battle.member(member_id).subject.resources
            if resources.contains(res):
                snapshot[member_id] = resources.current(res)
        return snapshot

    def wrap_transform(self, transform):
        """Record the damage each target is about to take (before the resource clamps it)."""
        res = self.rules.damage_resource
        if not res:
            return transform

        def observe(target_id, operation, value):
            result = value if transform is None else transform(target_id, operation, value)
            if operation.kind == EffectOperationKind.RESOURCE_DELTA and operation.target == res:
                applied = result[0] if isinstance(result, tuple) else result
                if applied < 0:
                    self._raw[target_id] = self._raw.get(target_id, 0.0) - float(applied)
            return result

        return observe

    def after_action(self, battle, action, snapshot, executed, counted=True):
        """``counted`` is false for the later hits of one cast: a cast is one use."""
        key = (action.actor_id, action.ability_id)
        if executed and counted:
            self.uses[key] = self.uses.get(key, 0) + 1
            self._count_mastery(battle, key)
        res = self.rules.damage_resource
        if executed and self.rules.gains:
            self._apply_gains(battle, action, snapshot)
        if not executed or not res:
            return
        actor = battle.member(action.actor_id)
        total = 0.0
        for target_id in action.target_ids:
            target = battle.member(target_id)
            if target.side == actor.side or target_id not in snapshot:
                continue
            resources = target.subject.resources
            lost = max(0.0, snapshot[target_id] - resources.current(res))
            total += lost
            wanted = self._raw.get(target_id, 0.0)
            if lost > 0 and wanted > lost and resources.get(res).empty:
                self.overkill[target_id] = self.overkill.get(target_id, 0.0) + (wanted - lost)
        if total <= 0:
            return
        self.damage_dealt[actor.member_id] = self.damage_dealt.get(actor.member_id, 0.0) + total
        stat = self.rules.lifesteal_stat
        if stat and actor.subject.stats.contains(stat):
            share = max(0.0, min(1.0, float(actor.subject.stats.get(stat))))
            if share > 0 and actor.subject.resources.contains(res):
                before = actor.subject.resources.current(res)
                actor.subject.resources.change(res, total * share)
                gained = actor.subject.resources.current(res) - before
                self.lifesteal_healed[actor.member_id] = (
                    self.lifesteal_healed.get(actor.member_id, 0.0) + gained
                )

    # -- party-wide gauges ---------------------------------------------------------------------
    def shared_maximum(self, gauge_id):
        return dict(self.rules.shared_gauges).get(str(gauge_id))

    def change_shared(self, gauge_id, amount):
        """Add (or, negative, spend) on a party gauge; returns the change applied."""
        maximum = self.shared_maximum(gauge_id)
        if maximum is None:
            raise KeyError(f"unknown shared gauge {gauge_id}")
        before = self.shared.get(str(gauge_id), 0.0)
        after = max(0.0, min(maximum, before + float(amount)))
        self.shared[str(gauge_id)] = after
        if after != before and self.on_shared_change is not None:
            self.on_shared_change(str(gauge_id), after)
        return after - before

    # -- resource gains ------------------------------------------------------------------------
    def _gain(self, battle, member_id, gain, damage=0.0, victim=None):
        resources = battle.battle_resources
        if gain.shared:
            if battle.member(member_id).side != gain.side:
                return
            top = 0.0
            if victim is not None and self.rules.damage_resource:
                pool = victim.subject.resources
                if pool.contains(self.rules.damage_resource):
                    top = pool.maximum(self.rules.damage_resource)
            if self.shared_maximum(gain.resource) is not None:
                self.change_shared(gain.resource, gain.amount(damage, top))
            return
        try:
            resources.get(member_id, gain.resource)
        except KeyError:
            return  # that fighter has no such resource
        top = 0.0
        if victim is not None and self.rules.damage_resource:
            pool = victim.subject.resources
            if pool.contains(self.rules.damage_resource):
                top = pool.maximum(self.rules.damage_resource)
        amount = gain.amount(damage, top)
        if amount:
            change = resources.change(
                member_id, gain.resource, amount, trigger=f"gain.{gain.event}"
            )
            self.gained[(member_id, gain.resource)] = (
                self.gained.get((member_id, gain.resource), 0.0) + change.applied_delta
            )

    def _apply_gains(self, battle, action, snapshot):
        res = self.rules.damage_resource
        actor = battle.member(action.actor_id)
        tags = battle.ability_runtime.registry.require(action.ability_id).tags
        for gain in self.rules.gains:
            if gain.ability_tag and gain.ability_tag not in tags:
                continue
            if gain.event == "action":
                self._gain(battle, actor.member_id, gain)
                continue
            for target_id in action.target_ids:
                target = battle.member(target_id)
                if target.side == actor.side or target_id not in snapshot or not res:
                    continue
                pool = target.subject.resources
                lost = max(0.0, snapshot[target_id] - pool.current(res))
                if lost <= 0:
                    continue
                if gain.event == "dealt":
                    self._gain(battle, actor.member_id, gain, lost, target)
                elif gain.event == "taken":
                    self._gain(battle, target_id, gain, lost, target)
                elif gain.event == "kill" and pool.get(res).empty:
                    self._gain(battle, actor.member_id, gain, lost, target)

    # -- mastery -------------------------------------------------------------------------------
    def mastery_level(self, member_id, ability_id):
        thresholds = self._mastery.get(str(ability_id), ())
        uses = self.mastery_uses.get((str(member_id), str(ability_id)), 0)
        return sum(1 for x in thresholds if uses >= x)

    def _count_mastery(self, battle, key):
        if key[1] not in self._mastery:
            return
        before = self.mastery_level(*key)
        self.mastery_uses[key] = self.mastery_uses.get(key, 0) + 1
        after = self.mastery_level(*key)
        self.sync_mastery_tags(battle, key[0])
        if after > before:
            from asteria.core.lifecycle import emit_hook

            emit_hook(
                battle.hooks,
                "rpg.battle.mastery_up",
                source=key[0],
                data={"member_id": key[0], "ability_id": key[1], "level": after},
            )

    def sync_mastery_tags(self, battle, member_id):
        """Put ``mastery.<ability>[.<level>]`` tags on the member for the rules to read."""
        tags = battle.member(member_id).subject.tags
        for ability_id in self._mastery:
            for tag in [t for t in tags.values() if t.startswith(f"mastery.{ability_id}")]:
                tags.remove(tag)
            level = self.mastery_level(member_id, ability_id)
            if level:
                tags.add(f"mastery.{ability_id}")
                tags.add(f"mastery.{ability_id}.{level}")

    # -- overkill ------------------------------------------------------------------------------
    def overkill_scale(self, battle, target_id):
        """Reward multiplier for a target that was knocked out with damage to spare."""
        extra = self.overkill.get(str(target_id), 0.0)
        res = self.rules.damage_resource
        if not extra or not res or not self.rules.overkill_rate:
            return 1.0
        resources = battle.member(target_id).subject.resources
        top = resources.maximum(res) if resources.contains(res) else 0.0
        ratio = extra / top if top > 0 else 0.0
        return 1.0 + self.rules.overkill_rate * min(ratio, self.rules.overkill_cap)

    # -- opening -------------------------------------------------------------------------------
    def roll_opening(self, rng):
        """``preemptive`` (the player side acts first), ``surprise`` (the foes), or ``normal``."""
        roll = rng.random()
        if roll < self.rules.preemptive_chance:
            return "preemptive"
        if roll < self.rules.preemptive_chance + self.rules.surprise_chance:
            return "surprise"
        return "normal"

    def apply_opening(self, battle, opening, player_side):
        """The side that loses the opening gives up its turns in the first round."""
        if opening not in OPENINGS:
            raise ValueError(f"opening must be one of {OPENINGS}")
        self.opening = opening
        if opening == "normal":
            return ()
        losing = {
            m.member_id
            for m in battle.members.values()
            if (m.side != player_side) == (opening == "preemptive")
        }
        removed = []
        for member_id in sorted(losing):
            queue = battle.turn_queue
            # a timeline scheduler keeps the member for later rounds; a plain queue only drops
            # it from the round being played
            getattr(queue, "sit_out_round", queue.remove_pending)(member_id)
            removed.append(member_id)
        return tuple(removed)

    # -- rows ----------------------------------------------------------------------------------
    def sync_row_tags(self, battle):
        prefix = self.rules.row_tag_prefix
        if not prefix:
            return
        for formation in battle.formations.values():
            for member_id, slot_id in ((p.member_id, p.slot_id) for p in formation.placements()):
                member = battle.member(member_id)
                slot = formation.definition.slot(slot_id)
                for tag in [t for t in member.subject.tags.values() if t.startswith(prefix)]:
                    member.subject.tags.remove(tag)
                for tag in slot.tags:
                    member.subject.tags.add(prefix + tag)

    # -- steal ---------------------------------------------------------------------------------
    def steal(self, battle, actor_id, target_id, inventory, rng, *, chance_bonus=0.0):
        """Try to rob ``target_id`` with the first matching steal table; adds to ``inventory``."""
        target = battle.member(target_id)
        if target.side == battle.member(actor_id).side:
            return StealResult(False, reason="not_an_opponent")
        table = next(
            (
                t
                for t in self.rules.steal_tables
                if t.target_key in (target.member_id, target.member_id.split(":", 1)[0])
                or target.subject.tags.contains(t.target_key)
            ),
            None,
        )
        if table is None:
            return StealResult(False, reason="nothing_to_steal")
        mark = (target.member_id, table.target_key)
        if table.once and mark in self.stolen_from:
            return StealResult(False, reason="already_stolen")
        for entry in table.entries:
            if rng.random() < min(1.0, entry.chance + float(chance_bonus)):
                inventory.add(entry.item_id, entry.amount)
                self.stolen_from.add(mark)
                return StealResult(True, entry.item_id, entry.amount)
        return StealResult(False, reason="failed")
