"""Field AI, spawn zones and visible encounters (ASTERIA_SPEC §28).

``FieldAIComponent`` gives an entity a basic behaviour (idle, patrol, wander,
chase, flee) toward a target entity; ``FieldAISystem`` moves it with
:class:`CharacterController2D` against an optional blocking query (tile map,
collision world). ``SpawnZoneComponent`` keeps prefab instances alive inside
a radius, in waves, with respawn timers, an optional rare prefab and an
optional event switch condition; ``SpawnSystem`` performs the spawning.
``VisibleEncounterComponent`` marks a field entity that starts an encounter
when the player touches it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from math import cos, hypot, pi, sin

from asteria.core import Component, Field, System, Transform, component_schema
from asteria.core.prefab import instantiate

from .character import CharacterController2D

FIELD_AI_BEHAVIOURS = ("idle", "patrol", "wander", "chase", "flee")


def parse_path(text):
    """``"x1,y1; x2,y2"`` -> ``((x1, y1), (x2, y2))``."""
    points = []
    for chunk in str(text or "").split(";"):
        if chunk.strip():
            x, y = chunk.split(",")
            points.append((float(x), float(y)))
    return tuple(points)


@component_schema(
    type_name="asteria.FieldAI",
    version=1,
    fields=(
        Field(
            "behaviour",
            str,
            "idle",
            choices=FIELD_AI_BEHAVIOURS,
            tooltip="Resting behaviour; chase/flee react to the target inside detect_radius.",
        ),
        Field("speed", float, 48.0, minimum=0.0),
        Field("detect_radius", float, 96.0, minimum=0.0),
        Field("lose_radius", float, 160.0, minimum=0.0, tooltip="Distance at which a chase or flee gives up."),
        Field("target_entity_id", str, "", tooltip="Entity to chase or flee from (usually the player)."),
        Field("patrol_path", str, "", tooltip="Patrol points as 'x1,y1; x2,y2'."),
        Field("wander_radius", float, 48.0, minimum=0.0),
        Field("arrive_distance", float, 2.0, minimum=0.0),
    ),
)
class FieldAIComponent(Component):
    def __init__(self):
        super().__init__()
        self.behaviour = "idle"
        self.speed = 48.0
        self.detect_radius = 96.0
        self.lose_radius = 160.0
        self.target_entity_id = ""
        self.patrol_path = ""
        self.wander_radius = 48.0
        self.arrive_distance = 2.0


@dataclass(slots=True)
class FieldAIState:
    mode: str = "idle"  # current mode: idle, patrol, wander, chase, flee, return
    home: tuple = (0.0, 0.0)
    patrol_index: int = 0
    wander_goal: tuple | None = None


class FieldAISystem(System):
    """Runs every FieldAIComponent.

    ``blocking`` is any ``collides_world_point`` query, or a callable
    ``entity -> query`` (so an entity's own collider can be excluded).
    ``default_target_id`` is chased / fled when a component names no target.
    """

    order = 20

    def __init__(self, blocking=None, rng=None, *, default_target_id=""):
        self.blocking = blocking
        self.rng = rng or random.Random(0)
        self.default_target_id = str(default_target_id or "")
        self.states: dict[str, FieldAIState] = {}
        self._query = None
        self._controller = None

    def state(self, entity_id):
        return self.states.get(str(entity_id))

    def _step_toward(self, transform, spec, goal, dt, away=False):
        dx, dy = goal[0] - transform.x, goal[1] - transform.y
        if away:
            dx, dy = -dx, -dy
        distance = hypot(dx, dy)
        if distance <= (0.0 if away else spec.arrive_distance):
            return True
        if self._controller is not None:
            # ENG-02: an AI entity with a CharacterController2D moves through it (same collision as the player)
            scale = min(1.0, distance / max(self._controller.speed * dt, 1e-9)) if not away else 1.0
            self._controller.set_intent(dx / distance * scale, dy / distance * scale)
            return False
        step = spec.speed * dt
        if not away and step > distance:  # land exactly on the goal
            dx, dy = dx * distance / step, dy * distance / step
        mover = CharacterController2D(transform.x, transform.y, speed=spec.speed, half_width=0.0, half_height=0.0)
        mover.move(dx / distance, dy / distance, dt, self._query or _Open())
        transform.x, transform.y = mover.x, mover.y
        return False

    def update(self, scene, dt):
        for entity, spec, transform in scene.query(FieldAIComponent, Transform):
            from asteria.runtime.character_control import AIController2DComponent, CharacterController2DComponent

            ai = entity.try_get(AIController2DComponent)
            if ai is not None and (not ai.enabled or ai.driver != "field_ai"):
                continue  # another driver (behavior tree) or none owns this entity
            controller = entity.try_get(CharacterController2DComponent)
            self._controller = controller if controller is not None and controller.enabled else None
            if self._controller is not None:
                self._controller.set_intent(0.0, 0.0)
            state = self.states.get(entity.id)
            if state is None:
                state = self.states[entity.id] = FieldAIState(spec.behaviour, (transform.x, transform.y))
            # the blocking query is only needed for entities without a controller (controllers do their own collision)
            self._query = (
                self.blocking(entity)
                if self._controller is None
                and callable(self.blocking)
                and not hasattr(self.blocking, "collides_world_point")
                else self.blocking
                if self._controller is None
                else None
            )
            target_id = spec.target_entity_id or self.default_target_id
            target = scene.get_entity(target_id) if target_id else None
            distance = None
            if target is not None and target.has(Transform):
                t = target.get(Transform)
                distance = hypot(t.x - transform.x, t.y - transform.y)
            reacting = spec.behaviour in ("chase", "flee")
            if reacting and distance is not None:
                if state.mode in ("chase", "flee"):
                    if distance > spec.lose_radius:
                        state.mode = "return"
                elif distance <= spec.detect_radius:
                    state.mode = spec.behaviour
            if state.mode == "chase":
                t = target.get(Transform)
                self._step_toward(transform, spec, (t.x, t.y), dt)
            elif state.mode == "flee":
                t = target.get(Transform)
                self._step_toward(transform, spec, (t.x, t.y), dt, away=True)
            elif state.mode == "return":
                if self._step_toward(transform, spec, state.home, dt):
                    state.mode = "idle"
            elif spec.behaviour == "patrol":
                path = parse_path(spec.patrol_path)
                state.mode = "patrol"
                if path and self._step_toward(transform, spec, path[state.patrol_index % len(path)], dt):
                    state.patrol_index = (state.patrol_index + 1) % len(path)
            elif spec.behaviour == "wander":
                state.mode = "wander"
                if state.wander_goal is None:
                    angle = self.rng.uniform(0, 2 * pi)
                    reach = self.rng.uniform(0, spec.wander_radius)
                    state.wander_goal = (state.home[0] + cos(angle) * reach, state.home[1] + sin(angle) * reach)
                if self._step_toward(transform, spec, state.wander_goal, dt):
                    state.wander_goal = None
            else:
                state.mode = "idle"


class _Open:
    def collides_world_point(self, x, y):
        return False


@component_schema(
    type_name="asteria.SpawnZone",
    version=1,
    fields=(
        Field("prefab_id", str, "", tooltip="Prefab spawned in this zone."),
        Field("rare_prefab_id", str, "", tooltip="Optional rare variant."),
        Field("rare_chance", float, 0.0, minimum=0.0, maximum=1.0),
        Field("radius", float, 64.0, minimum=0.0),
        Field("max_alive", int, 3, minimum=0),
        Field("respawn_seconds", float, 10.0, minimum=0.0),
        Field("waves", str, "", tooltip="Wave sizes as '3, 5, 8'; empty spawns continuously."),
        Field("condition_switch", str, "", tooltip="Spawn only while this event switch is on."),
    ),
)
class SpawnZoneComponent(Component):
    def __init__(self):
        super().__init__()
        self.prefab_id = ""
        self.rare_prefab_id = ""
        self.rare_chance = 0.0
        self.radius = 64.0
        self.max_alive = 3
        self.respawn_seconds = 10.0
        self.waves = ""
        self.condition_switch = ""


@dataclass(slots=True)
class SpawnZoneState:
    alive: list = field(default_factory=list)
    cooldown: float = 0.0
    wave_index: int = 0
    finished: bool = False


class SpawnSystem(System):
    """Spawns prefab instances for every SpawnZoneComponent.

    ``switches`` is a ``name -> bool`` callable for condition switches;
    ``spawned`` lists ``(zone_id, entity_id, prefab_id)`` for this update.
    """

    order = 10

    def __init__(self, prefabs, registry, *, switches=None, rng=None):
        self.prefabs = prefabs
        self.registry = registry
        self.switches = switches or (lambda name: False)
        self.rng = rng or random.Random(0)
        self.states: dict[str, SpawnZoneState] = {}
        self.spawned: list[tuple[str, str, str]] = []

    def state(self, zone_id):
        return self.states.get(str(zone_id))

    def _spawn(self, scene, zone_entity, spec, state):
        prefab_id = spec.prefab_id
        if spec.rare_prefab_id and self.rng.random() < spec.rare_chance:
            prefab_id = spec.rare_prefab_id
        entity = instantiate(self.prefabs, prefab_id, self.registry)
        origin = zone_entity.get(Transform)
        angle, reach = self.rng.uniform(0, 2 * pi), self.rng.uniform(0, spec.radius)
        if not entity.has(Transform):
            entity.add_component(Transform())
        transform = entity.get(Transform)
        transform.x, transform.y = origin.x + cos(angle) * reach, origin.y + sin(angle) * reach
        scene.add_entity(entity)
        state.alive.append(entity.id)
        self.spawned.append((zone_entity.id, entity.id, prefab_id))

    def update(self, scene, dt):
        self.spawned = []
        for zone_entity, spec, _ in scene.query(SpawnZoneComponent, Transform):
            state = self.states.setdefault(zone_entity.id, SpawnZoneState())
            state.alive = [x for x in state.alive if scene.get_entity(x) is not None]
            if state.finished or not spec.prefab_id:
                continue
            if spec.condition_switch and not self.switches(spec.condition_switch):
                continue
            waves = [int(x) for x in str(spec.waves).replace(";", ",").split(",") if x.strip()]
            if waves:
                if state.alive:
                    continue
                if state.wave_index >= len(waves):
                    state.finished = True
                    continue
                state.cooldown -= dt
                if state.wave_index and state.cooldown > 0:
                    continue
                for _ in range(waves[state.wave_index]):
                    self._spawn(scene, zone_entity, spec, state)
                state.wave_index += 1
                state.cooldown = spec.respawn_seconds
                continue
            if len(state.alive) >= spec.max_alive:
                state.cooldown = spec.respawn_seconds
                continue
            state.cooldown -= dt
            if state.cooldown <= 0:
                while len(state.alive) < spec.max_alive:
                    self._spawn(scene, zone_entity, spec, state)
                state.cooldown = spec.respawn_seconds


@component_schema(
    type_name="asteria.VisibleEncounter",
    version=1,
    fields=(
        Field("encounter_id", str, "", tooltip="Encounter started when the player touches this entity."),
        Field("touch_radius", float, 12.0, minimum=0.0),
        Field("remove_on_start", bool, True),
    ),
)
class VisibleEncounterComponent(Component):
    def __init__(self):
        super().__init__()
        self.encounter_id = ""
        self.touch_radius = 12.0
        self.remove_on_start = True


def touched_encounter(scene, player):
    """The first VisibleEncounterComponent entity within touch range of ``player``, or None."""
    p = player.get(Transform)
    for entity, spec, transform in scene.query(VisibleEncounterComponent, Transform):
        if spec.encounter_id and hypot(transform.x - p.x, transform.y - p.y) <= spec.touch_radius:
            return entity
    return None
