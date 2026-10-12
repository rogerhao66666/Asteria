"""Projectiles in the scene (ASTERIA_SPEC §20 projectiles).

Projectiles are not entities: their numbers live in a kernel ``ProjectileStore`` (``asteria.kernels``, python or numpy)
so hundreds can fly at once; this module keeps the few per-shot facts (definition, owner, team, targets already hit).

``ProjectileSystem.fire`` / ``fire_from`` launch shots (count, spread, angle and offset turned with the shooter's
facing). Each update moves them (homing toward the nearest target in range, gravity), ends them on walls (or bounces /
stops them, as authored), tests them against hurtboxes in one batched overlap test, and hands every hit to the combat
system as a ``HitEvent`` whose ``hit_tag`` is the definition's attack — with the projectile's position and travel
direction, so knockback pushes away from the shot. ``events`` reports fired / hit / ended for presentation and game
rules; ``views()`` gives what to draw.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, radians, sin

from asteria import kernels
from asteria.core import System, world_position

from .character_control import (
    CharacterController2DComponent,
    Hitbox2DComponent,
    HitEvent,
    Hurtbox2DComponent,
    box_rows,
    turn_with_facing,
)


@dataclass(slots=True)
class _Shot:
    definition: object
    owner_id: str
    team: str
    pierce_left: int
    bounces: int = 0
    hit_ids: set = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class ProjectileEvent:
    kind: str  # fired, hit, ended
    uid: int
    projectile_id: str
    x: float
    y: float
    data: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectileView:
    uid: int
    projectile_id: str
    x: float
    y: float
    vx: float
    vy: float


def _team_of(entity):
    for component_type in (Hitbox2DComponent, Hurtbox2DComponent):
        component = entity.try_get(component_type)
        if component is not None and component.team:
            return component.team
    from .combat import CombatantComponent

    combatant = entity.try_get(CombatantComponent)
    return combatant.team if combatant is not None else ""


class ProjectileSystem(System):
    order = 62  # after HitboxSystem (60), before CombatSystem (65)

    def __init__(self, definitions, *, hits=None, combat=None, world=None, cell_size=64.0, paused=None):
        self.definitions = definitions  # mapping projectile_id -> ProjectileDefinition (GameplayLibrary.projectiles)
        self.hits = hits  # HitboxSystem: i-frames are respected
        self.combat = combat  # CombatSystem: hits are queued on combat.pending
        self.world = world  # callable() -> CollisionWorld for walls (None: no walls)
        self.cell_size = float(cell_size)
        self.paused = paused  # callable(entity_id); paused("") is True while a hitstop freezes the whole scene
        self.store = kernels.active().ProjectileStore()
        self.shots: dict[int, _Shot] = {}
        self.events: list[ProjectileEvent] = []
        self.hit_events: list[HitEvent] = []
        self.listeners = []
        self._next_uid = 1
        self._pending_events = []

    def __len__(self):
        return len(self.store)

    # -- firing ----------------------------------------------------------------------------------
    def fire(self, projectile_id, x, y, direction=(1.0, 0.0), *, owner_id="", team="", count=1, spread=0.0):
        """Launch ``count`` shots from ``(x, y)`` fanned over ``spread`` degrees around ``direction``; their uids."""
        definition = self.definitions.get(str(projectile_id))
        if definition is None:
            raise ValueError(f"unknown projectile {projectile_id}")
        dx, dy = direction
        length = hypot(dx, dy) or 1.0
        base = (dx / length, dy / length)
        count = max(1, int(count))
        rows, uids = [], []
        for k in range(count):
            offset = 0.0 if count == 1 else radians(float(spread)) * (k / (count - 1) - 0.5)
            ux = base[0] * cos(offset) - base[1] * sin(offset)
            uy = base[0] * sin(offset) + base[1] * cos(offset)
            uid = self._next_uid
            self._next_uid += 1
            rows.append(
                (
                    x,
                    y,
                    ux * definition.speed,
                    uy * definition.speed,
                    definition.gravity,
                    0.0,
                    definition.lifetime,
                    definition.width / 2,
                    definition.height / 2,
                    radians(definition.homing_turn),
                    uid,
                )
            )
            self.shots[uid] = _Shot(definition, str(owner_id), str(team), definition.pierce)
            self._pending_events.append(ProjectileEvent("fired", uid, definition.projectile_id, x, y))
            uids.append(uid)
        self.store.add(rows)
        return uids

    def fire_from(self, entity, payload):
        """Fire from an entity (action timeline ``projectile`` cue): ``projectile_id``, ``count``, ``spread`` and
        ``angle`` (degrees, authored for facing right), ``offset_x`` / ``offset_y`` (turned with the facing);
        ``direction`` (a world vector) aims the shot instead of the facing."""
        payload = dict(payload)
        controller = entity.try_get(CharacterController2DComponent)
        facing = controller.facing if controller is not None else "right"
        angle = radians(float(payload.get("angle", 0.0)))
        if payload.get("direction") is not None:  # an aimed shot (lock-on target, stick direction)
            ax, ay = payload["direction"]
            direction = (ax * cos(angle) - ay * sin(angle), ax * sin(angle) + ay * cos(angle))
        else:
            direction = turn_with_facing(cos(angle), sin(angle), facing)
        ox, oy = turn_with_facing(float(payload.get("offset_x", 0.0)), float(payload.get("offset_y", 0.0)), facing)
        x, y = world_position(entity)
        return self.fire(
            payload["projectile_id"],
            x + ox,
            y + oy,
            direction,
            owner_id=entity.id,
            team=str(payload.get("team") or _team_of(entity)),
            count=int(payload.get("count", 1)),
            spread=float(payload.get("spread", 0.0)),
        )

    def views(self):
        store = self.store
        return [
            ProjectileView(int(uid), self.shots[int(uid)].definition.projectile_id, x, y, vx, vy)
            for uid, x, y, vx, vy in zip(
                store.column("uid"),
                store.column("x"),
                store.column("y"),
                store.column("vx"),
                store.column("vy"),
                strict=True,
            )
        ]

    # -- update ----------------------------------------------------------------------------------
    def update(self, scene, dt):
        self.events, self._pending_events = self._pending_events, []
        self.hit_events = []
        if not len(self.store) or (self.paused is not None and self.paused("")):
            self._emit()
            return
        frame = None if self.hits is None else self.hits.frame_hurtboxes
        if frame is not None:
            self.hits.frame_hurtboxes = None  # taken: fresh from this frame's HitboxSystem, nothing moved since
        targets = frame if frame is not None else box_rows(scene, Hurtbox2DComponent)  # homing and hits
        uids = [int(u) for u in self.store.column("uid")]
        target_x = target_y = None
        if any(self.shots[u].definition.homing_turn > 0 for u in uids):
            target_x, target_y = self._homing_targets(uids, targets)
        self.store.step(dt, target_x, target_y)
        ended = {}  # row -> reason
        if self.world is not None:
            self._walls(uids, dt, ended)
        if targets[0]:
            self._hits(scene, uids, targets, ended)
        for row in self.store.expired():
            ended.setdefault(row, "lifetime")
        if ended:
            xs, ys = self.store.column("x"), self.store.column("y")
            for row, reason in sorted(ended.items()):
                shot = self.shots.pop(uids[row])
                event = shot.definition.on_end_event
                self.events.append(
                    ProjectileEvent(
                        "ended",
                        uids[row],
                        shot.definition.projectile_id,
                        xs[row],
                        ys[row],
                        {"reason": reason, "event": event},
                    )
                )
            self.store.keep([row for row in range(len(uids)) if row not in ended])
        if self.combat is not None:
            self.combat.pending.extend(self.hit_events)
        self._emit()

    def _emit(self):
        for event in self.events:
            for listener in tuple(self.listeners):
                listener(event)

    def _homing_targets(self, uids, targets):
        xs, ys = self.store.column("x"), self.store.column("y")
        entities, hurtboxes, (bx0, by0, bx1, by1) = targets
        centres = [
            (entity.id, hurtbox.team, (bx0[j] + bx1[j]) / 2, (by0[j] + by1[j]) / 2)
            for j, (entity, hurtbox) in enumerate(zip(entities, hurtboxes, strict=True))
        ]
        nan = float("nan")
        target_x, target_y = [nan] * len(uids), [nan] * len(uids)
        for row, uid in enumerate(uids):
            shot = self.shots[uid]
            if shot.definition.homing_turn <= 0:
                continue
            best, reach = None, shot.definition.homing_range
            for entity_id, team, cx, cy in centres:
                if entity_id == shot.owner_id or entity_id in shot.hit_ids or (shot.team and team == shot.team):
                    continue
                distance = hypot(cx - xs[row], cy - ys[row])
                if distance <= reach:
                    best, reach = (cx, cy), distance
            if best is not None:
                target_x[row], target_y[row] = best
        return target_x, target_y

    def _blocked(self, world, shot, x, y):
        for entity_id in world.query_point(x, y, mask=shot.definition.wall_mask, exclude=(shot.owner_id,)):
            if not world.shapes[entity_id].one_way:
                return True
        return False

    def _walls(self, uids, dt, ended):
        world = self.world()
        if world is None or not world.shapes:
            return
        xs, ys = self.store.column("x"), self.store.column("y")
        vxs, vys = self.store.column("vx"), self.store.column("vy")
        shapes, columns = world.solid_columns()
        points = (xs, ys, xs, ys)  # each shot's centre as a zero-size box: one batched test against every wall
        inside = set()
        for row, j in kernels.active().aabb_cross_pairs(points, columns, self.cell_size, touching=True):
            if row in inside:
                continue
            shot, shape = self.shots[uids[row]], shapes[j]
            if (
                shot.definition.wall != "pass"
                and not shape.one_way
                and shape.entity_id != shot.owner_id
                and shot.definition.wall_mask & shape.layer_bit
                and (shape.shape != "circle" or hypot(xs[row] - shape.cx, ys[row] - shape.cy) <= shape.radius)
            ):
                inside.add(row)
        for row in sorted(inside):
            shot = self.shots[uids[row]]
            behaviour = shot.definition.wall
            if behaviour == "destroy":
                ended[row] = "wall"
            elif behaviour == "stop":
                px, py = xs[row] - vxs[row] * dt, ys[row] - vys[row] * dt
                self.store.set_values(row, x=px, y=py, vx=0.0, vy=0.0, gravity=0.0)
            else:  # bounce: reflect the axis that hit, back to where it was
                px, py = xs[row] - vxs[row] * dt, ys[row] - vys[row] * dt
                hit_x = self._blocked(world, shot, xs[row], py)
                hit_y = self._blocked(world, shot, px, ys[row])
                if not hit_x and not hit_y:
                    hit_x = hit_y = True  # a corner
                self.store.set_values(
                    row, x=px, y=py, vx=-vxs[row] if hit_x else vxs[row], vy=-vys[row] if hit_y else vys[row]
                )
                shot.bounces += 1
                if shot.definition.bounce_limit and shot.bounces > shot.definition.bounce_limit:
                    ended[row] = "wall"

    def _hits(self, scene, uids, targets, ended):
        entities, hurtboxes, columns = targets
        pairs = kernels.active().aabb_cross_pairs(self.store.boxes(), columns, self.cell_size)
        if not pairs:
            return
        xs, ys = self.store.column("x"), self.store.column("y")
        vxs, vys = self.store.column("vx"), self.store.column("vy")
        for row, j in pairs:
            if row in ended:
                continue
            shot = self.shots[uids[row]]
            target, hurtbox = entities[j], hurtboxes[j]
            if target.id == shot.owner_id or target.id in shot.hit_ids:
                continue
            if shot.team and hurtbox.team == shot.team:
                continue
            if self.hits is not None and self.hits.invincible(target.id, hurtbox):
                continue
            shot.hit_ids.add(target.id)
            definition = shot.definition
            self.hit_events.append(
                HitEvent(
                    shot.owner_id,
                    target.id,
                    definition.attack_id,
                    shot.team,
                    origin=(xs[row], ys[row]),
                    direction=(vxs[row], vys[row]),
                )
            )
            self.events.append(
                ProjectileEvent("hit", uids[row], definition.projectile_id, xs[row], ys[row], {"target_id": target.id})
            )
            if shot.pierce_left == 0:
                ended[row] = "target"
            elif shot.pierce_left > 0:
                shot.pierce_left -= 1


__all__ = ["ProjectileEvent", "ProjectileSystem", "ProjectileView", "turn_with_facing"]
