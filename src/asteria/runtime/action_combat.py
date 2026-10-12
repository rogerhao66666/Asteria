"""Real-time ability use (ASTERIA_SPEC §20: combos, cancel windows, dash / dodge, cooldowns / resources, lock-on).

``ActionCombatComponent`` binds input actions to abilities (``"attack=slash; dodge=roll; skill_1=fireball"``) and
sets how the entity aims and locks on. ``ActionCombatSystem.use(entity, ability_id)`` is the one door for players,
behaviour trees and scripts:

* the ability's ``timeline_id`` is played on the entity (``EntityActionSystem``), aimed at the lock-on target, the
  stick direction or the facing;
* while its action runs, pressing the same ability inside the timeline's combo window plays the window's ``next``
  timeline (a combo chain); inside a cancel window — or for an ability with ``interrupts_actions`` (dodges) — the new
  ability cuts the running one; otherwise the press is buffered for ``buffer_time`` and tried again;
* ``cooldown_seconds`` and the ability's ``costs`` (formulas over the user's stats, paid from its combatant
  resources) are checked and paid when a chain starts; ``move_while_acting`` scales movement during the action.

Every outcome is an ``ActionCombatEvent`` (dispatched to ``listeners`` at once; ``events`` keeps those since the
system's last update) (used, combo, buffered, denied with a reason, lock_on, lock_lost) so the
game and its presentation can react. Nothing here names a game's buttons, abilities or rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot

from asteria.core import Component, Field, System, Transform, component_schema, world_position
from asteria.gameplay.formulas import FormulaContext

from .character_control import CharacterController2DComponent, Hurtbox2DComponent, facing_from, facing_vector

AIM_MODES = ("target_input_facing", "input_facing", "facing")
LOCK_MODES = ("off", "manual", "nearest")


def parse_bindings(text):
    """``"attack=slash; dodge=roll"`` -> ``{"attack": "slash", "dodge": "roll"}`` (input action -> ability id)."""
    bindings = {}
    for chunk in str(text or "").replace(",", ";").split(";"):
        if chunk.strip():
            action, _, ability = chunk.partition("=")
            if not action.strip() or not ability.strip():
                raise ValueError(f"expected action=ability, got {chunk.strip()!r}")
            bindings[action.strip()] = ability.strip()
    return bindings


@component_schema(
    type_name="asteria.ActionCombat",
    version=1,
    fields=(
        Field(
            "bindings", str, "", tooltip="Input action = ability, e.g. 'attack=slash; dodge=roll; skill_1=fireball'."
        ),
        Field("buffer_time", float, 0.2, minimum=0.0, tooltip="How long a press waits for the running action."),
        Field(
            "lock_mode",
            str,
            "off",
            choices=LOCK_MODES,
            tooltip="manual: the lock action picks / drops a target; nearest: every use aims at the nearest foe.",
        ),
        Field("lock_range", float, 220.0, minimum=0.0),
        Field("lock_action", str, "lock_on", tooltip="Input action that locks on / off (manual mode)."),
        Field("lock_switch_action", str, "lock_switch", tooltip="Input action that moves the lock to the next foe."),
        Field(
            "aim",
            str,
            "target_input_facing",
            choices=AIM_MODES,
            tooltip="Where actions aim: the lock target, else the stick direction, else the facing.",
        ),
        Field("face_target", bool, True, tooltip="Turn toward the aim when an ability starts."),
        Field("enabled", bool, True),
    ),
)
class ActionCombatComponent(Component):
    def __init__(self):
        super().__init__()
        self.bindings = ""
        self.buffer_time = 0.2
        self.lock_mode = "off"
        self.lock_range = 220.0
        self.lock_action = "lock_on"
        self.lock_switch_action = "lock_switch"
        self.aim = "target_input_facing"
        self.face_target = True
        self.enabled = True
        # runtime
        self.lock_target_id = ""


@dataclass(frozen=True, slots=True)
class ActionCombatEvent:
    kind: str  # used, combo, buffered, denied, lock_on, lock_lost
    entity_id: str
    ability_id: str = ""
    reason: str = ""
    data: dict = field(default_factory=dict)


class ActionCombatSystem(System):
    order = 22  # after input (10) and AI (20) set intents, before action timelines (25) and controllers (30)

    def __init__(self, abilities, timelines, *, actions, combat=None, formulas=None, snapshot_provider=None):
        self.abilities = abilities  # AbilityRegistry (GameplayLibrary.abilities)
        self.timelines = timelines  # {timeline_id: ActionTimeline}
        self.actions = actions  # EntityActionSystem
        self.combat = combat  # CombatSystem: costs are paid from combatant resources
        self.formulas = formulas if formulas is not None else {}
        self.snapshot_provider = snapshot_provider  # callable() -> InputSnapshot | None (player input)
        self.cooldowns: dict[tuple, float] = {}
        self.buffered: dict[str, tuple] = {}  # entity id -> (ability id, seconds left, aim)
        self.events: list[ActionCombatEvent] = []
        self.listeners = []
        self._previous: dict[str, dict] = {}
        self._scene = None
        self._quiet = False

    # -- queries ---------------------------------------------------------------------------------
    def cooldown(self, entity, ability_id):
        return self.cooldowns.get((entity.id, str(ability_id)), 0.0)

    def lock_target(self, entity):
        spec = entity.try_get(ActionCombatComponent)
        if spec is None or not spec.lock_target_id or self._scene is None:
            return None
        return self._scene.get_entity(spec.lock_target_id)

    # -- using abilities -------------------------------------------------------------------------
    def _emit(self, kind, entity, ability_id="", reason="", **data):
        """Record and dispatch at once (``use`` may be called by behaviour trees or scripts outside ``update``)."""
        if self._quiet and kind in ("denied", "buffered"):
            return
        event = ActionCombatEvent(kind, entity.id, str(ability_id), reason, data)
        self.events.append(event)
        for listener in tuple(self.listeners):
            listener(event)

    def use(self, entity, ability_id, *, aim=None, scene=None, buffer=True):
        """Use ``ability_id`` now (or buffer it); returns ``"used"``, ``"combo"``, ``"buffered"`` or a denial
        reason (``unknown``, ``no_timeline``, ``busy``, ``cooldown``, ``cost:<resource>``)."""
        scene = scene or self._scene or entity.scene
        ability = self.abilities.get(str(ability_id))
        if ability is None:
            self._emit("denied", entity, ability_id, "unknown")
            return "unknown"
        timeline = self.timelines.get(ability.timeline_id)
        if timeline is None:
            self._emit("denied", entity, ability_id, "no_timeline")
            return "no_timeline"
        if aim is None:
            aim = self.aim_of(entity, scene)
        running = self.actions.active(entity.id)
        if running:
            if self.actions.source(entity.id) == ability.ability_id and self.actions.window_open(entity.id, "combo"):
                follow = self.timelines.get(self.actions.combo_next(entity.id) or "")
                if follow is not None:
                    self.actions.cancel(entity.id, scene, force=True)
                    self._face(entity, aim)
                    self.actions.play(entity.id, follow, aim=aim, source=ability.ability_id)
                    self._emit("combo", entity, ability_id, timeline=follow.timeline_id)
                    return "combo"
            if not (ability.interrupts_actions or self.actions.window_open(entity.id, "cancel")):
                if buffer:
                    spec = entity.try_get(ActionCombatComponent)
                    seconds = spec.buffer_time if spec is not None else 0.0
                    if seconds > 0:
                        self.buffered[entity.id] = (ability.ability_id, seconds, aim)
                        self._emit("buffered", entity, ability_id)
                        return "buffered"
                self._emit("denied", entity, ability_id, "busy")
                return "busy"
        if self.cooldown(entity, ability.ability_id) > 0:
            self._emit("denied", entity, ability_id, "cooldown")
            return "cooldown"
        prices = self._prices(entity, ability)
        if isinstance(prices, str):
            self._emit("denied", entity, ability_id, prices)
            return prices
        if prices:
            resources = self.combat.state(entity).resources
            for resource, amount in prices:
                resources.change(resource, -amount)
        if ability.cooldown_seconds > 0:
            self.cooldowns[(entity.id, ability.ability_id)] = ability.cooldown_seconds
        if running:
            self.actions.cancel(entity.id, scene, force=True)
        self._face(entity, aim)
        self.actions.play(entity.id, timeline, aim=aim, source=ability.ability_id)
        self.buffered.pop(entity.id, None)
        self._emit("used", entity, ability_id, spent=dict(prices or ()))
        return "used"

    def _prices(self, entity, ability):
        """``[(resource, amount)]`` the ability costs now, or ``"cost:<resource>"`` when it cannot be paid."""
        if not ability.costs:
            return []
        from .combat import CombatantComponent

        if self.combat is None or not entity.has(CombatantComponent):
            return f"cost:{ability.costs[0].resource}"
        state = self.combat.state(entity)
        stats = self.combat.effective_stats(state)
        context = FormulaContext(stats, state.resources, state.tags, stats, state.resources, state.tags)
        prices = []
        for cost in ability.costs:
            amount = cost.amount.evaluate(context)
            if not state.resources.contains(cost.resource) or state.resources.current(cost.resource) < amount:
                return f"cost:{cost.resource}"
            prices.append((cost.resource, amount))
        return prices

    def _face(self, entity, aim):
        spec = entity.try_get(ActionCombatComponent)
        controller = entity.try_get(CharacterController2DComponent)
        if aim is None or controller is None or (spec is not None and not spec.face_target):
            return
        controller.facing = facing_from(aim[0], aim[1], controller.mode, controller.facing)

    # -- aim and lock-on -------------------------------------------------------------------------
    def _team(self, entity):
        from .combat import CombatantComponent

        for component_type in (CombatantComponent, Hurtbox2DComponent):
            component = entity.try_get(component_type)
            if component is not None and component.team:
                return component.team
        return ""

    def foes(self, entity, scene, reach):
        """Hostile targets (hurtboxes of another team, alive) within ``reach``, nearest first."""
        from .combat import CombatantComponent

        team = self._team(entity)
        x, y = world_position(entity)
        found = []
        for other, hurtbox in scene.query(Hurtbox2DComponent):
            if other is entity or not hurtbox.enabled or (team and hurtbox.team == team) or not other.has(Transform):
                continue
            combatant = other.try_get(CombatantComponent)
            if combatant is not None and combatant.state is not None and combatant.state.dead:
                continue
            ox, oy = world_position(other)
            distance = hypot(ox - x, oy - y)
            if distance <= reach:
                found.append((distance, other))
        found.sort(key=lambda row: row[0])
        return [other for _, other in found]

    def aim_of(self, entity, scene=None, snapshot=None):
        """The aim direction for an action starting now (see ``ActionCombatComponent.aim``)."""
        scene = scene or self._scene or entity.scene
        spec = entity.try_get(ActionCombatComponent)
        mode = spec.aim if spec is not None else "facing"
        controller = entity.try_get(CharacterController2DComponent)
        if mode == "target_input_facing" and spec is not None and scene is not None:
            target = scene.get_entity(spec.lock_target_id) if spec.lock_target_id else None
            if target is None and spec.lock_mode == "nearest":
                nearest = self.foes(entity, scene, spec.lock_range)
                target = nearest[0] if nearest else None
            if target is not None:
                (x, y), (tx, ty) = world_position(entity), world_position(target)
                if hypot(tx - x, ty - y) > 1e-9:
                    return (tx - x, ty - y)
        if mode in ("target_input_facing", "input_facing"):
            snapshot = snapshot if snapshot is not None else self._snapshot()
            if snapshot is not None and entity.has(_player_input_type()):
                dx, dy = snapshot.movement_vector()
                if dx or dy:
                    return (dx, dy)
            if controller is not None and (controller.intent_x or controller.intent_y):
                return (controller.intent_x, controller.intent_y)
        return facing_vector(controller.facing) if controller is not None else (1.0, 0.0)

    def _snapshot(self):
        return self.snapshot_provider() if self.snapshot_provider is not None else None

    def _lock(self, entity, spec, scene, *, switch=False):
        foes = self.foes(entity, scene, spec.lock_range)
        if switch and spec.lock_target_id:
            ids = [f.id for f in foes]
            if spec.lock_target_id in ids and len(ids) > 1:
                spec.lock_target_id = ids[(ids.index(spec.lock_target_id) + 1) % len(ids)]
                self._emit("lock_on", entity, target_id=spec.lock_target_id)
            return
        if spec.lock_target_id and not switch:
            spec.lock_target_id = ""
            self._emit("lock_lost", entity, reason="released")
            return
        if foes:
            spec.lock_target_id = foes[0].id
            self._emit("lock_on", entity, target_id=spec.lock_target_id)

    # -- update ----------------------------------------------------------------------------------
    def update(self, scene, dt):
        self._scene = scene
        self.events = []
        self.cooldowns = {k: v - dt for k, v in self.cooldowns.items() if v - dt > 1e-9}
        snapshot = self._snapshot()
        player_input = _player_input_type()
        for entity, spec in scene.query(ActionCombatComponent):
            if not spec.enabled:
                continue
            self._check_lock(entity, spec, scene)
            if snapshot is not None and entity.has(player_input):
                self._read_input(entity, spec, scene, snapshot)
        for entity_id, (ability_id, left, aim) in tuple(self.buffered.items()):
            entity = scene.get_entity(entity_id)
            left -= dt
            if entity is None or left <= 0:
                self.buffered.pop(entity_id, None)
                continue
            self.buffered[entity_id] = (ability_id, left, aim)
            self._quiet = True  # a still-busy retry is not news
            try:
                result = self.use(entity, ability_id, aim=aim, scene=scene, buffer=False)
            finally:
                self._quiet = False
            if result in ("used", "combo"):
                self.buffered.pop(entity_id, None)
        for entity_id, run in self.actions.running.items():
            ability = self.abilities.get(run.source) if run.source else None
            if ability is None or run.move_until is not None:
                continue  # not an ability, or the timeline itself is moving the entity
            entity = scene.get_entity(entity_id)
            controller = None if entity is None else entity.try_get(CharacterController2DComponent)
            if controller is not None:
                scale = ability.move_while_acting
                controller.set_intent(controller.intent_x * scale, controller.intent_y * scale, jump=controller.jump)

    def _check_lock(self, entity, spec, scene):
        if not spec.lock_target_id:
            return
        from .combat import CombatantComponent

        target = scene.get_entity(spec.lock_target_id)
        lost = target is None or not target.enabled or not target.has(Transform)
        if not lost:
            combatant = target.try_get(CombatantComponent)
            lost = combatant is not None and combatant.state is not None and combatant.state.dead
        if not lost:
            (x, y), (tx, ty) = world_position(entity), world_position(target)
            lost = hypot(tx - x, ty - y) > spec.lock_range * 1.5
        if lost:
            spec.lock_target_id = ""
            self._emit("lock_lost", entity, reason="target")

    def _read_input(self, entity, spec, scene, snapshot):
        previous = self._previous.setdefault(entity.id, {})
        actions = snapshot.actions

        def pressed(name):
            now = float(actions.get(name, 0.0)) > 0.5
            was = previous.get(name, False)
            previous[name] = now
            return now and not was

        if spec.lock_mode == "manual":
            if pressed(spec.lock_action):
                self._lock(entity, spec, scene)
            if pressed(spec.lock_switch_action):
                self._lock(entity, spec, scene, switch=True)
        for action, ability_id in parse_bindings(spec.bindings).items():
            if pressed(action):
                self.use(entity, ability_id, aim=self.aim_of(entity, scene, snapshot), scene=scene)


def _player_input_type():
    from .character_control import PlayerInput2DComponent

    return PlayerInput2DComponent


def register_action_combat_components(registry):
    registry.register(ActionCombatComponent)
    return registry


__all__ = [
    "AIM_MODES",
    "LOCK_MODES",
    "ActionCombatComponent",
    "ActionCombatEvent",
    "ActionCombatSystem",
    "parse_bindings",
    "register_action_combat_components",
]
