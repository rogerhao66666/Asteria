"""Real-time combat resolution (ASTERIA_SPEC §20): what a landed hit does.

``HitboxSystem`` only reports overlaps (``HitEvent``). ``CombatSystem`` turns every hit whose ``hit_tag`` names an
``AttackDefinition`` into results on the target's ``CombatantComponent``:

* damage — the attack's ``ValueFormula`` over the attacker's and target's stats, resources and tags (the attack's own
  tags join the attacker's, so ``Element.Fire`` multipliers work), optional critical hits, lowering the resource the
  attack names (a negative amount restores it)
* poise and stagger — poise damage; at zero the target is staggered (control locked, its action cancelled) and the
  poise refills
* hitstun, knockback (direction mode, angle, side-view lift, the target's resistance), hitstop (attacker and target, or
  the whole scene), i-frames after the hit
* super armor — an armor level (always on the combatant, or for a while from an action timeline ``armor`` cue);
  while it is above the attack's ``armor_break`` the hit only does damage (times ``armor_damage_multiplier``): no
  hitstun, knockback, stagger or knockdown
* knockdown — from the attack, or from a poise break when ``stagger_result`` is ``knocked_down``: down for a while
  (optionally invincible), then getting up (optional i-frames); ``knocked_down`` and ``got_up`` events
* death — when the combatant's life resource is empty: an event, the drop table rolled, then the authored death
  behaviour (remove, disable, keep)

Everything is reported as ``CombatEvent``s (``events`` for this update, ``listeners``) so presentation (numbers,
flashes, sounds), game rules and event programs can react. Nothing here knows any particular game: stats, resources
and tags are whatever the project defines, inline on the component or from ``stats_provider`` (for example an RPG
actor build).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from math import cos, hypot, radians, sin

from asteria.core import Component, Field, System, Transform, component_schema, world_position
from asteria.gameplay.formulas import FormulaContext
from asteria.gameplay.stats import ResourcePool, StatBlock
from asteria.gameplay.tags import TagSet

from .character_control import (
    CharacterController2DComponent,
    Hitbox2DComponent,
    Hurtbox2DComponent,
    facing_vector,
)

DEATH_BEHAVIOURS = ("remove", "disable", "keep")
HITSTUN_RULES = ("unless_poise", "always", "never")
STAGGER_RESULTS = ("staggered", "knocked_down")


def parse_values(text):
    """``"hp=100; attack=12"`` (``;`` or ``,`` between pairs) -> ``{"hp": 100.0, "attack": 12.0}``."""
    values = {}
    for chunk in str(text or "").replace(",", ";").split(";"):
        if chunk.strip():
            key, _, value = chunk.partition("=")
            if not key.strip() or not value.strip():
                raise ValueError(f"expected name=value, got {chunk.strip()!r}")
            values[key.strip()] = float(value)
    return values


def parse_tags(text):
    return tuple(t for t in str(text or "").replace(",", " ").replace(";", " ").split() if t)


@component_schema(
    type_name="asteria.Combatant",
    version=1,
    fields=(
        Field("team", str, "", tooltip="Free text; hitboxes already skip hurtboxes of the same team."),
        Field("resources", str, "hp=100", tooltip="Resources and their maximum, e.g. 'hp=120; mp=40; shield=30'."),
        Field("life_resource", str, "hp", tooltip="The resource whose emptying means death. Empty: never dies."),
        Field("stats", str, "", tooltip="Stats the formulas read, e.g. 'attack=12; defense=4'."),
        Field("regen", str, "", tooltip="Resources regained per second, e.g. 'mp=2; stamina=15' (negative drains)."),
        Field("tags", str, "", tooltip="Gameplay tags, e.g. 'Creature.Undead Element.Ice'."),
        Field("poise", float, 0.0, minimum=0.0, tooltip="Poise damage it takes before being staggered. 0: no poise."),
        Field("poise_recovery", float, 0.0, minimum=0.0, tooltip="Poise regained per second."),
        Field("stagger_time", float, 0.6, minimum=0.0),
        Field("stagger_result", str, "staggered", choices=STAGGER_RESULTS, tooltip="What a poise break causes."),
        Field("armor", int, 0, minimum=0, tooltip="Permanent super armor level. 0: none."),
        Field(
            "armor_damage_multiplier",
            float,
            1.0,
            minimum=0.0,
            tooltip="Damage taken while super armor holds (1 = full damage).",
        ),
        Field("knockdown_time", float, 1.0, minimum=0.0, tooltip="Seconds on the ground after a knockdown."),
        Field("getup_time", float, 0.5, minimum=0.0, tooltip="Seconds spent getting up (cannot act)."),
        Field("down_invincible", bool, True, tooltip="Hits pass over it while it is down."),
        Field("getup_iframes", float, 0.3, minimum=0.0, tooltip="Invincible seconds from the start of getting up."),
        Field(
            "hitstun_rule",
            str,
            "unless_poise",
            choices=HITSTUN_RULES,
            tooltip="When an attack's hitstun interrupts it: unless it still has poise, always, or never.",
        ),
        Field("knockback_resistance", float, 0.0, minimum=0.0, maximum=1.0, tooltip="1 ignores knockback."),
        Field("hurt_iframes", float, 0.0, minimum=0.0, tooltip="Invincible seconds after every hit it takes."),
        Field("death", str, "remove", choices=DEATH_BEHAVIOURS, tooltip="What happens to the entity when it dies."),
        Field("drop_table_id", str, "", tooltip="Drop table rolled when it dies."),
        Field("currency_drop", str, "", tooltip="Currencies dropped when it dies, e.g. 'gold=5-12; gems=0-1'."),
        Field(
            "loot_level", int, 1, minimum=0, tooltip="Item level of the equipment it drops (which affixes can roll)."
        ),
        Field("loot_luck", float, 0.0, minimum=0.0, tooltip="Makes rarer drops more likely (elites, bosses)."),
        Field("death_event", str, "", tooltip="Gameplay event reported when it dies."),
        Field("enabled", bool, True),
    ),
)
class CombatantComponent(Component):
    def __init__(self):
        super().__init__()
        self.team = ""
        self.resources = "hp=100"
        self.life_resource = "hp"
        self.stats = ""
        self.regen = ""
        self.tags = ""
        self.poise = 0.0
        self.poise_recovery = 0.0
        self.stagger_time = 0.6
        self.stagger_result = "staggered"
        self.armor = 0
        self.armor_damage_multiplier = 1.0
        self.knockdown_time = 1.0
        self.getup_time = 0.5
        self.down_invincible = True
        self.getup_iframes = 0.3
        self.hitstun_rule = "unless_poise"
        self.knockback_resistance = 0.0
        self.hurt_iframes = 0.0
        self.death = "remove"
        self.drop_table_id = ""
        self.currency_drop = ""
        self.loot_level = 1
        self.loot_luck = 0.0
        self.death_event = ""
        self.enabled = True
        # runtime (not serialized)
        self.state = None  # CombatantState, built on first use

    def reset_state(self):
        """Forget runtime values so they are rebuilt from the authored fields (e.g. after editing them)."""
        self.state = None


@dataclass(slots=True)
class CombatantState:
    stats: StatBlock
    resources: ResourcePool
    tags: TagSet
    poise: float = 0.0
    dead: bool = False
    armor_level: int = 0  # timed super armor (action cue), on top of the component's permanent level
    armor_left: float = 0.0
    down_phase: str = ""  # "", "down", "getting_up"
    down_left: float = 0.0
    states: object = None  # gameplay StateRuntime (poison, burn, buffs...) ticking in real time
    regen: dict | None = None  # parsed CombatantComponent.regen


def _inline_state(combatant):
    pool = ResourcePool()
    for name, maximum in parse_values(combatant.resources).items():
        pool.define(name, maximum)
    return CombatantState(StatBlock(parse_values(combatant.stats)), pool, TagSet(parse_tags(combatant.tags)))


@dataclass(frozen=True, slots=True)
class CombatEvent:
    kind: str  # damage, staggered, knocked_down, got_up, death, drop, hit_event, state_applied, state_ended
    target_id: str
    attacker_id: str = ""
    attack_id: str = ""
    amount: float = 0.0
    critical: bool = False
    x: float = 0.0
    y: float = 0.0
    data: dict = field(default_factory=dict)


class CombatSystem(System):
    """Resolves this update's ``HitEvent``s from ``hits`` (a ``HitboxSystem``) with the project's attacks."""

    order = 65  # after HitboxSystem (60)

    def __init__(
        self,
        attacks,
        *,
        hits=None,
        formulas=None,
        actions=None,
        drop_tables=None,
        rng=None,
        stats_provider=None,
        counters=None,
        switches=None,
        states=None,
    ):
        self.state_registry = states  # gameplay StateRegistry (GameplayLibrary.states) for real-time states
        self.attacks = attacks  # mapping attack_id -> AttackDefinition (e.g. GameplayLibrary.attacks)
        self.hits = hits
        self.formulas = formulas if formulas is not None else {}
        self.actions = actions  # EntityActionSystem: stagger / hitstun cancel the target's action
        self.drop_tables = drop_tables if drop_tables is not None else {}
        self.rng = rng or random.Random(0)
        self.stats_provider = stats_provider  # callable(entity, combatant) -> CombatantState | None
        self.counters = counters if counters is not None else {}  # drop table pity counters
        self.switches = switches
        self.events: list[CombatEvent] = []
        self.listeners = []
        self.pending = []  # extra HitEvents to resolve (from projectiles, scripts)
        self.global_hitstop = 0.0
        self._frozen: dict[str, float] = {}
        self._landed: dict[str, int] = {}
        self._armor_requests: dict[str, tuple] = {}

    # -- queries ---------------------------------------------------------------------------------
    def state(self, entity):
        """The combatant's runtime state (stats, resources, tags, poise), built on first use."""
        combatant = entity.get(CombatantComponent)
        if combatant.state is None:
            provided = self.stats_provider(entity, combatant) if self.stats_provider is not None else None
            state = combatant.state = provided if provided is not None else _inline_state(combatant)
            state.poise = combatant.poise
            state.regen = parse_values(combatant.regen)
            if self.state_registry is not None:
                from asteria.gameplay.states import StateRuntime

                state.states = StateRuntime(self.state_registry, state.stats, state.resources, state.tags)
        return combatant.state

    def apply_state(self, entity, state_id, *, duration=None, source_id=None):
        """Put a gameplay state (poison, haste...) on a combatant; it ticks in real time. False if it cannot."""
        state = self.state(entity)
        if state.states is None or state.dead or self.state_registry.get(state_id) is None:
            return False
        state.states.apply(state_id, duration=duration, source_id=source_id)
        self._emit("state_applied", entity, data={"state": str(state_id)})
        return True

    @staticmethod
    def effective_stats(state):
        """Stats with the active states' modifiers applied (what formulas read)."""
        runtime = state.states
        modifiers = runtime.modifiers() if runtime is not None and runtime.has_active else None
        if not modifiers or not modifiers.modifiers():
            return state.stats
        return StatBlock(
            {name: modifiers.evaluate(name, state.stats.get(name), tags=state.tags) for name in state.stats.names()}
        )

    def armor_level(self, entity):
        combatant = entity.get(CombatantComponent)
        state = self.state(entity)
        return max(combatant.armor, state.armor_level if state.armor_left > 0 else 0)

    def grant_armor(self, entity_id, level, seconds, scene=None):
        """Super armor ``level`` for ``seconds`` (action timeline ``armor`` cues call this)."""
        self._armor_requests[str(entity_id)] = (int(level), float(seconds))

    def end_armor(self, entity_id):
        self._armor_requests[str(entity_id)] = (0, 0.0)

    def down_phase(self, entity):
        """``""`` (standing), ``"down"`` or ``"getting_up"``."""
        return self.state(entity).down_phase

    def paused(self, entity_id):
        """True while hitstop freezes this entity (pass to controllers and action timelines)."""
        return self.global_hitstop > 0.0 or self._frozen.get(str(entity_id), 0.0) > 0.0

    # -- update ----------------------------------------------------------------------------------
    def update(self, scene, dt):
        self.events = []
        self.global_hitstop = max(0.0, self.global_hitstop - dt)
        self._frozen = {k: v - dt for k, v in self._frozen.items() if v - dt > 0}
        for attacker_id in tuple(self._landed):
            entity = scene.get_entity(attacker_id)
            hitbox = None if entity is None else entity.try_get(Hitbox2DComponent)
            if hitbox is None or not hitbox.active:
                self._landed.pop(attacker_id)  # the activation ended; the next one counts afresh
        for entity_id, (level, seconds) in self._armor_requests.items():
            entity = scene.get_entity(entity_id)
            if entity is not None and entity.has(CombatantComponent):
                state = self.state(entity)
                state.armor_level, state.armor_left = level, seconds
        self._armor_requests = {}
        removed = []
        for entity, combatant in scene.query(CombatantComponent):
            state = combatant.state
            if state is None or state.dead:
                continue
            if state.regen:
                for resource, rate in state.regen.items():
                    if state.resources.contains(resource):
                        state.resources.change(resource, rate * dt)
            if state.states is not None and state.states.has_active:
                for state_id in state.states.update(dt):
                    self._emit("state_ended", entity, data={"state": state_id})
                self._check_death(scene, entity, combatant, state, removed, {})
                if state.dead:
                    continue
            if combatant.poise_recovery:
                state.poise = min(combatant.poise, state.poise + combatant.poise_recovery * dt)
            state.armor_left = max(0.0, state.armor_left - dt)
            if state.down_phase:
                state.down_left -= dt
                if state.down_left <= 0 and state.down_phase == "down":
                    state.down_phase, state.down_left = "getting_up", combatant.getup_time
                    if combatant.getup_iframes > 0 and self.hits is not None:
                        self.hits.grant_invincibility(entity.id, combatant.getup_iframes)
                    self._emit("got_up", entity)
                if state.down_left <= 0 and state.down_phase == "getting_up":
                    state.down_phase, state.down_left = "", 0.0
        hits = list(self.hits.events) if self.hits is not None else []
        hits += self.pending
        self.pending = []
        for hit in hits:
            self._resolve(scene, hit, removed)
        for entity in removed:
            scene.remove_entity(entity)
        for event in self.events:
            for listener in tuple(self.listeners):
                listener(event)

    def _emit(self, kind, target, **values):
        x, y = world_position(target) if target is not None and target.has(Transform) else (0.0, 0.0)
        self.events.append(CombatEvent(kind, "" if target is None else target.id, x=x, y=y, **values))

    def _resolve(self, scene, hit, removed):
        attack = self.attacks.get(hit.hit_tag)
        if attack is None:
            return
        attacker = scene.get_entity(hit.attacker_id)
        target = scene.get_entity(hit.target_id)
        if target is None or not target.has(CombatantComponent):
            return
        combatant = target.get(CombatantComponent)
        if not combatant.enabled:
            return
        state = self.state(target)
        if state.dead:
            return
        if attack.max_targets and hit.origin is None:  # projectiles count targets with their own pierce
            landed = self._landed.get(hit.attacker_id, 0)
            if landed >= attack.max_targets:
                return
            self._landed[hit.attacker_id] = landed + 1

        source = self.state(attacker) if attacker is not None and attacker.has(CombatantComponent) else None
        source_tags = TagSet(source.tags.values() if source is not None else ())
        for tag in attack.tags:
            source_tags.add(tag)
        formula = self.formulas.get(attack.damage_formula_id) if attack.damage_formula_id else attack.damage
        amount = 0.0
        critical = False
        if formula is not None:
            context = FormulaContext(
                self.effective_stats(source) if source is not None else StatBlock(),
                source.resources if source is not None else ResourcePool(),
                source_tags,
                self.effective_stats(state),
                state.resources,
                state.tags,
            )
            amount = formula.evaluate(context)
        chance = attack.critical_chance
        if attack.critical_chance_stat and source is not None:
            chance += source.stats.get(attack.critical_chance_stat) / 100.0
        if chance > 0 and self.rng.random() < chance:
            critical = True
            amount *= attack.critical_multiplier
        armored = self.armor_level(target) > attack.armor_break
        if armored:
            amount *= combatant.armor_damage_multiplier
        common = {"attacker_id": hit.attacker_id, "attack_id": attack.attack_id}
        if state.resources.contains(attack.damage_resource):
            state.resources.change(attack.damage_resource, -amount)
        self._emit(
            "damage",
            target,
            amount=amount,
            critical=critical,
            data={"resource": attack.damage_resource, "armored": armored},
            **common,
        )

        controller = target.try_get(CharacterController2DComponent)
        react = not armored and not state.down_phase  # super armor and lying down take damage only
        staggered = knocked_down = False
        if react and combatant.poise > 0 and attack.poise_damage > 0:
            state.poise -= attack.poise_damage
            if state.poise <= 0:
                state.poise = combatant.poise
                if combatant.stagger_result == "knocked_down":
                    knocked_down = True
                else:
                    staggered = True
                    if controller is not None:
                        controller.lock_control(combatant.stagger_time)
                    if self.actions is not None:
                        self.actions.cancel(target.id, scene, force=True)
                    self._emit("staggered", target, data={"seconds": combatant.stagger_time}, **common)
        if react and (knocked_down or attack.knockdown):
            seconds = attack.knockdown_time or combatant.knockdown_time
            state.down_phase, state.down_left = "down", seconds
            if controller is not None:
                controller.lock_control(seconds + combatant.getup_time)
            if self.actions is not None:
                self.actions.cancel(target.id, scene, force=True)
            if combatant.down_invincible and self.hits is not None:
                self.hits.grant_invincibility(target.id, seconds)
            self._emit("knocked_down", target, data={"seconds": seconds}, **common)
        flinch = combatant.hitstun_rule == "always" or (
            combatant.hitstun_rule == "unless_poise" and (combatant.poise <= 0 or staggered)
        )
        if react and attack.hitstun > 0 and flinch and not state.down_phase:
            if controller is not None:
                controller.lock_control(attack.hitstun)
            if self.actions is not None:
                self.actions.cancel(target.id, scene, force=True)

        if react and controller is not None and (attack.knockback or attack.knockback_lift):
            scale = 1.0 - combatant.knockback_resistance
            dx, dy = self._knock_direction(attack, attacker, target, hit)
            controller.apply_impulse(
                dx * attack.knockback * scale, (dy * attack.knockback - attack.knockback_lift) * scale
            )

        if attack.hitstop > 0:
            if attack.hitstop_scope == "global":
                self.global_hitstop = max(self.global_hitstop, attack.hitstop)
            else:
                for entity_id in (hit.attacker_id, target.id):
                    self._frozen[entity_id] = max(self._frozen.get(entity_id, 0.0), attack.hitstop)
        iframes = max(attack.target_iframes, combatant.hurt_iframes)
        if iframes > 0 and self.hits is not None:
            self.hits.grant_invincibility(target.id, iframes)
        if attack.on_hit_event:
            self._emit("hit_event", target, data={"event": attack.on_hit_event}, **common)

        for entry in attack.apply_states:
            if entry["chance"] >= 1.0 or self.rng.random() < entry["chance"]:
                if self.apply_state(target, entry["state"], duration=entry.get("duration"), source_id=hit.attacker_id):
                    continue
                self._emit("state_unknown", target, data={"state": entry["state"]}, **common)
        self._check_death(scene, target, combatant, state, removed, common)

    def _check_death(self, scene, entity, combatant, state, removed, common):
        life = combatant.life_resource
        resources = state.resources
        if life and resources.contains(life) and resources.current(life) <= resources.get(life).minimum:
            self._die(scene, entity, combatant, state, removed, common)

    @staticmethod
    def _knock_direction(attack, attacker, target, hit=None):
        if attack.knockback_direction == "fixed":
            angle = radians(attack.knockback_angle)
            return cos(angle), sin(angle)
        dx = dy = 0.0
        origin = getattr(hit, "origin", None)
        direction = getattr(hit, "direction", None)
        if attack.knockback_direction == "away" and (origin is not None or attacker is not None):
            ax, ay = origin if origin is not None else world_position(attacker)
            tx, ty = world_position(target)
            dx, dy = tx - ax, ty - ay
        elif attack.knockback_direction == "attacker_facing" and direction is not None:
            dx, dy = direction  # a projectile pushes along its flight
        if hypot(dx, dy) < 1e-9 and direction is not None:
            dx, dy = direction
        if hypot(dx, dy) < 1e-9 and attacker is not None:
            controller = attacker.try_get(CharacterController2DComponent)
            dx, dy = facing_vector(controller.facing if controller is not None else "right")
        length = hypot(dx, dy) or 1.0
        dx, dy = dx / length, dy / length
        if attack.knockback_angle:
            a = radians(attack.knockback_angle)
            dx, dy = dx * cos(a) - dy * sin(a), dx * sin(a) + dy * cos(a)
        return dx, dy

    def _die(self, scene, target, combatant, state, removed, common):
        state.dead = True
        self._emit("death", target, data={"event": combatant.death_event}, **common)
        table = self.drop_tables.get(combatant.drop_table_id) if combatant.drop_table_id else None
        items = {}
        if table is not None:
            from asteria.rpg.drop_tables import roll_drop_table

            items = roll_drop_table(
                table, self.rng, counters=self.counters, luck=combatant.loot_luck, switches=self.switches
            )
        currencies = {}
        for chunk in str(combatant.currency_drop or "").replace(",", ";").split(";"):
            if chunk.strip():
                name, _, span = chunk.partition("=")
                low, _, high = span.strip().partition("-")
                low = int(float(low))
                amount = self.rng.randint(low, int(float(high)) if high.strip() else low)
                if amount > 0:
                    currencies[name.strip()] = currencies.get(name.strip(), 0) + amount
        if items or currencies:
            data = {
                "items": items,
                "currencies": currencies,
                "table_id": table.table_id if table is not None else "",
                "level": combatant.loot_level,
                "luck": combatant.loot_luck,
            }
            self._emit("drop", target, data=data, **common)
        if combatant.death == "remove":
            removed.append(target)
        elif combatant.death == "disable":
            for component_type in (Hurtbox2DComponent, Hitbox2DComponent, CharacterController2DComponent):
                component = target.try_get(component_type)
                if component is not None:
                    component.enabled = False
            if self.actions is not None:
                self.actions.cancel(target.id, scene, force=True)


def register_combat_components(registry):
    registry.register(CombatantComponent)
    return registry


__all__ = [
    "DEATH_BEHAVIOURS",
    "HITSTUN_RULES",
    "STAGGER_RESULTS",
    "CombatEvent",
    "CombatSystem",
    "CombatantComponent",
    "CombatantState",
    "parse_tags",
    "parse_values",
    "register_combat_components",
]
