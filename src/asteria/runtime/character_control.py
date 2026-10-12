"""Character control and hit detection (ENG-02, ENG-16, ENG-17; ASTERIA_SPEC §6, §8).

Components (serializable, inspectable, script-accessible):

* ``CharacterController2D`` — moves its entity from an *intent* (``intent_x``,
  ``intent_y``, ``jump``) and resolves it against solid colliders (and any
  extra blocking query such as a tile map). ``mode="topdown"`` slides on
  both axes; ``mode="side"`` adds gravity, jumping, ground detection and
  one-way platforms (``Collider2D.one_way``). After each update the
  component reports ``grounded``, ``ground_id``, ``hit_wall``, ``hit_ceiling``.
  v2 adds ``facing`` (follows movement), an outside push (``apply_impulse``, e.g. knockback) that
  fades by ``knockback_decay``, and ``lock_control`` (hitstun / stagger: intent is ignored).
* ``PlayerInput2D`` — fills a controller's intent from the input action map.
* ``AIController2D`` — marks an entity as AI-driven; ``FieldAISystem`` (and the
  behavior-tree runtime) write the controller intent instead of moving the
  entity directly, so AI respects the same collision as the player.
* ``Hitbox2D`` / ``Hurtbox2D`` — generic hit detection: an active hitbox that
  overlaps a hurtbox of another team produces one ``HitEvent`` per target per
  activation; invincible hurtboxes (and i-frame timers) are skipped. What a hit
  *does* (damage, knockback...) is game logic attached to the events
  (``runtime.combat`` is one ready-made answer). With ``follow_facing`` the box offset
  is authored for facing right and turns with the entity's controller facing.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import exp

from asteria.core import Component, Field, System, Transform, component_schema, world_position
from asteria.core.migration import component_migration

from .collision import Collider2DComponent, CollisionWorld

GROUND_PROBE = 0.5
FACINGS = ("down", "up", "left", "right")
PUSH_EPSILON = 0.5  # pushes slower than this (world units / s) stop


@component_schema(
    type_name="asteria.CharacterController2D",
    version=2,
    fields=(
        Field("mode", str, "topdown", choices=("topdown", "side")),
        Field("speed", float, 60.0, minimum=0.0),
        Field("half_width", float, 6.0, minimum=0.0),
        Field("half_height", float, 8.0, minimum=0.0),
        Field("gravity", float, 600.0, minimum=0.0, tooltip="Side view: downward acceleration."),
        Field("jump_speed", float, 220.0, minimum=0.0, tooltip="Side view: upward speed of a jump."),
        Field("max_fall_speed", float, 400.0, minimum=0.0),
        Field("mask", int, 0xFFFFFFFF, minimum=0, maximum=0xFFFFFFFF, tooltip="Collider layers that block it."),
        Field("facing", str, "down", choices=FACINGS, tooltip="Starting facing; it then follows movement."),
        Field(
            "knockback_decay",
            float,
            10.0,
            minimum=0.0,
            tooltip="How fast an outside push (knockback) fades, per second. 0 keeps it until a wall stops it.",
        ),
        Field("enabled", bool, True),
    ),
)
class CharacterController2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.mode = "topdown"
        self.speed = 60.0
        self.half_width = 6.0
        self.half_height = 8.0
        self.gravity = 600.0
        self.jump_speed = 220.0
        self.max_fall_speed = 400.0
        self.mask = 0xFFFFFFFF
        self.facing = "down"
        self.knockback_decay = 10.0
        self.enabled = True
        # runtime (not serialized)
        self.intent_x = 0.0
        self.intent_y = 0.0
        self.jump = False
        self.velocity_y = 0.0
        self.grounded = False
        self.ground_id = None
        self.hit_wall = False
        self.hit_ceiling = False
        self.push_x = 0.0
        self.push_y = 0.0
        self.control_lock = 0.0

    def set_intent(self, x=0.0, y=0.0, *, jump=False):
        self.intent_x, self.intent_y, self.jump = float(x), float(y), bool(jump)

    def apply_impulse(self, x=0.0, y=0.0):
        """Push from outside (knockback, wind, explosions), in world units per second.

        Top-down: both axes are pushes that fade by ``knockback_decay``. Side view: ``x`` is a fading push and a
        non-zero ``y`` replaces the vertical speed (negative launches upward).
        """
        self.push_x += float(x)
        if self.mode == "side":
            if y:
                self.velocity_y = float(y)
        else:
            self.push_y += float(y)

    def lock_control(self, seconds):
        """Ignore intent (movement and jump) for ``seconds`` — hitstun, stagger, cutscene holds."""
        self.control_lock = max(self.control_lock, float(seconds))

    @property
    def controllable(self):
        return self.control_lock <= 0.0


@component_migration("asteria.CharacterController2D", from_version=1)
def _controller_v1_to_v2(fields):
    return fields  # v2 adds facing and knockback_decay; defaults keep v1 behaviour


def facing_from(dx, dy, mode="topdown", current="down"):
    """Facing for a movement direction (``current`` when standing still). Side view only turns left/right."""
    if mode == "side" or abs(dx) >= abs(dy):
        if dx > 1e-9:
            return "right"
        if dx < -1e-9:
            return "left"
        if mode == "side":
            return current
    if dy > 1e-9:
        return "down"
    if dy < -1e-9:
        return "up"
    return current


def facing_vector(facing):
    return {"down": (0.0, 1.0), "up": (0.0, -1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0)}.get(facing, (0.0, 1.0))


@component_schema(
    type_name="asteria.PlayerInput2D",
    version=1,
    fields=(
        Field("enabled", bool, True),
        Field("jump_action", str, "jump", tooltip="Input action that jumps (side view)."),
    ),
)
class PlayerInput2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.enabled = True
        self.jump_action = "jump"


@component_schema(
    type_name="asteria.AIController2D",
    version=1,
    fields=(
        Field("driver", str, "field_ai", choices=("field_ai", "behavior_tree", "none")),
        Field("tree_id", str, "", tooltip="Behavior tree id when driver is behavior_tree."),
        Field("enabled", bool, True),
    ),
)
class AIController2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.driver = "field_ai"
        self.tree_id = ""
        self.enabled = True


def _box_fields():
    return (
        Field("width", float, 16.0, minimum=0.0),
        Field("height", float, 16.0, minimum=0.0),
        Field("offset_x", float, 0.0),
        Field("offset_y", float, 0.0),
        Field("team", str, "", tooltip="Hits only land on hurtboxes of another team."),
        Field(
            "follow_facing",
            bool,
            False,
            tooltip="Offset and size are authored for facing right; they mirror for left and turn for up / down.",
        ),
    )


@component_schema(
    type_name="asteria.Hitbox2D",
    version=2,
    fields=(
        *_box_fields(),
        Field("active", bool, False, tooltip="Usually switched on by action timeline hitbox cues."),
        Field("hit_tag", str, "", tooltip="What kind of hit this is (game logic reads it)."),
        Field("enabled", bool, True),
    ),
)
class Hitbox2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.width = 16.0
        self.height = 16.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.team = ""
        self.follow_facing = False
        self.active = False
        self.hit_tag = ""
        self.enabled = True


@component_schema(
    type_name="asteria.Hurtbox2D",
    version=2,
    fields=(
        *_box_fields(),
        Field("invincible", bool, False),
        Field("enabled", bool, True),
    ),
)
class Hurtbox2DComponent(Component):
    def __init__(self):
        super().__init__()
        self.width = 16.0
        self.height = 16.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.team = ""
        self.follow_facing = False
        self.invincible = False
        self.enabled = True


@component_migration("asteria.Hitbox2D", from_version=1)
def _hitbox_v1_to_v2(fields):
    return fields  # v2 adds follow_facing (default False keeps v1 boxes)


@component_migration("asteria.Hurtbox2D", from_version=1)
def _hurtbox_v1_to_v2(fields):
    return fields


# -- systems ------------------------------------------------------------------------------------
class PlayerInputSystem(System):
    """Copies the current input snapshot into every enabled PlayerInput2D entity's controller intent."""

    order = 10

    def __init__(self, snapshot_provider):
        self.snapshot_provider = snapshot_provider

    def update(self, scene, dt):
        snapshot = self.snapshot_provider()
        if snapshot is None:
            return
        for _entity, player, controller in scene.query(PlayerInput2DComponent, CharacterController2DComponent):
            if not player.enabled:
                continue
            dx, dy = snapshot.movement_vector()
            jump = float(getattr(snapshot, "actions", {}).get(player.jump_action, 0.0)) > 0.5
            controller.set_intent(dx, dy, jump=jump)


class CharacterControllerSystem(System):
    """Moves every CharacterController2D by its intent, resolving solid and one-way colliders."""

    order = 30

    def __init__(self, extra_blocking=None, *, paused=None):
        self.extra_blocking = extra_blocking  # e.g. a tile map query (collides_world_point)
        self.paused = paused  # optional callable(entity_id) -> True while frozen (hitstop)

    def _blocked(self, world, entity_id, controller, x, y, *, falling_from=None):
        hw, hh = controller.half_width, controller.half_height
        corners = ((x - hw, y - hh), (x + hw, y - hh), (x - hw, y + hh), (x + hw, y + hh))
        for px, py in corners:
            if self.extra_blocking is not None and self.extra_blocking.collides_world_point(px, py):
                return True
            for hit in world.query_point(px, py, mask=controller.mask, exclude=(entity_id,)):
                shape = world.shapes[hit]
                if not shape.one_way:
                    return True
                # one-way platform: blocks only feet that were above its top before this move
                if falling_from is not None and py >= y + hh - 1e-6 and falling_from + hh <= shape.bounds[1] + 1e-6:
                    return True
        return False

    def _ground(self, world, entity_id, controller, x, y):
        hw, hh = controller.half_width, controller.half_height
        for px in (x - hw, x, x + hw):
            py = y + hh + GROUND_PROBE
            if self.extra_blocking is not None and self.extra_blocking.collides_world_point(px, py):
                return "__tiles__"
            for hit in world.query_point(px, py, mask=controller.mask, exclude=(entity_id,)):
                shape = world.shapes[hit]
                if not shape.one_way or y + hh <= shape.bounds[1] + 1e-6:
                    return hit
        return None

    def update(self, scene, dt):
        if dt <= 0:
            return
        world = CollisionWorld.from_scene(scene)
        for entity, controller, transform in scene.query(CharacterController2DComponent, Transform):
            if not controller.enabled or (self.paused is not None and self.paused(entity.id)):
                continue
            controller.hit_wall = controller.hit_ceiling = False
            dx, dy = controller.intent_x, controller.intent_y
            if controller.control_lock > 0.0:
                controller.control_lock -= dt
                if controller.control_lock < 1e-9:  # float steps (30 x 1/60 is not exactly 0.5)
                    controller.control_lock = 0.0
                dx = dy = 0.0
                controller.jump = False
            else:
                controller.facing = facing_from(dx, dy, controller.mode, controller.facing)
            push_x, push_y = controller.push_x, controller.push_y
            if controller.mode == "topdown":
                mag = (dx * dx + dy * dy) ** 0.5
                if mag > 1.0:
                    dx, dy = dx / mag, dy / mag
                nx = transform.x + (dx * controller.speed + push_x) * dt
                if self._blocked(world, entity.id, controller, nx, transform.y):
                    controller.hit_wall = dx != 0 or push_x != 0
                    controller.push_x = 0.0
                    transform.x = self._contact(world, entity.id, controller, transform.x, nx, transform.y, True)
                else:
                    transform.x = nx
                ny = transform.y + (dy * controller.speed + push_y) * dt
                if self._blocked(world, entity.id, controller, transform.x, ny):
                    controller.hit_wall = controller.hit_wall or dy != 0 or push_y != 0
                    controller.push_y = 0.0
                    transform.y = self._contact(world, entity.id, controller, transform.y, ny, transform.x, False)
                else:
                    transform.y = ny
                controller.grounded, controller.ground_id = True, None
                self._decay_push(controller, dt)
                continue
            # side view
            nx = transform.x + (max(-1.0, min(1.0, dx)) * controller.speed + push_x) * dt
            if self._blocked(world, entity.id, controller, nx, transform.y):
                controller.hit_wall = dx != 0 or push_x != 0
                controller.push_x = 0.0
            else:
                transform.x = nx
            self._decay_push(controller, dt)
            ground = self._ground(world, entity.id, controller, transform.x, transform.y)
            if ground is not None and controller.velocity_y >= 0:
                controller.velocity_y = 0.0
                if controller.jump:
                    controller.velocity_y = -controller.jump_speed
            controller.velocity_y = min(controller.max_fall_speed, controller.velocity_y + controller.gravity * dt)
            step = controller.velocity_y * dt
            start_y = transform.y
            ny = start_y + step
            if self._blocked(world, entity.id, controller, transform.x, ny, falling_from=start_y if step > 0 else None):
                # move to the contact in small steps so the character rests on the surface
                direction = 1.0 if step > 0 else -1.0
                moved = 0.0
                while abs(moved) < abs(step):
                    trial = start_y + moved + direction * min(0.25, abs(step) - abs(moved))
                    if self._blocked(
                        world, entity.id, controller, transform.x, trial, falling_from=start_y if step > 0 else None
                    ):
                        break
                    moved = trial - start_y
                transform.y = start_y + moved
                if step < 0:
                    controller.hit_ceiling = True
                controller.velocity_y = 0.0
            else:
                transform.y = ny
            controller.ground_id = self._ground(world, entity.id, controller, transform.x, transform.y)
            controller.grounded = controller.ground_id is not None
            controller.jump = False

    def _contact(self, world, entity_id, controller, start, end, other, horizontal):
        """Furthest free position from ``start`` toward a blocked ``end`` (fast moves, e.g. knockback, end against
        the wall instead of stopping a whole step short). Steps of 1 unit or less keep the old behaviour."""
        if abs(end - start) <= 1.0:
            return start
        free, blocked = start, end
        for _ in range(8):
            mid = (free + blocked) / 2
            x, y = (mid, other) if horizontal else (other, mid)
            if self._blocked(world, entity_id, controller, x, y):
                blocked = mid
            else:
                free = mid
        return free

    @staticmethod
    def _decay_push(controller, dt):
        if not (controller.push_x or controller.push_y):
            return
        keep = exp(-controller.knockback_decay * dt)
        controller.push_x *= keep
        controller.push_y *= keep
        if abs(controller.push_x) < PUSH_EPSILON:
            controller.push_x = 0.0
        if abs(controller.push_y) < PUSH_EPSILON:
            controller.push_y = 0.0


@dataclass(frozen=True, slots=True)
class HitEvent:
    attacker_id: str
    target_id: str
    hit_tag: str
    team: str


def facing_box(entity, spec):
    """World AABB of a hit/hurt box; with ``follow_facing`` the authored (facing right) box turns with the
    entity's controller facing: mirrored for left, rotated a quarter turn for down / up."""
    x, y = world_position(entity)
    ox, oy, w, h = spec.offset_x, spec.offset_y, spec.width, spec.height
    if getattr(spec, "follow_facing", False):
        controller = entity.try_get(CharacterController2DComponent)
        facing = controller.facing if controller is not None else "right"
        if facing == "left":
            ox = -ox
        elif facing == "down":
            ox, oy, w, h = -oy, ox, h, w
        elif facing == "up":
            ox, oy, w, h = oy, -ox, h, w
    cx, cy = x + ox, y + oy
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


_box = facing_box


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class HitboxSystem(System):
    """Reports hits of active hitboxes on hurtboxes of other teams (once per target per activation).

    ``events`` holds this update's ``HitEvent``s; ``listeners`` are called with each.
    ``grant_invincibility(entity_id, seconds)`` gives i-frames (also used by IFRAME timeline cues).
    """

    order = 60

    def __init__(self):
        self.events: list[HitEvent] = []
        self.listeners = []
        self.iframes: dict[str, float] = {}
        self._hit_this_activation: dict[str, set] = {}

    def grant_invincibility(self, entity_id, seconds):
        self.iframes[str(entity_id)] = max(self.iframes.get(str(entity_id), 0.0), float(seconds))

    def invincible(self, entity_id, hurtbox=None):
        return (hurtbox is not None and hurtbox.invincible) or self.iframes.get(str(entity_id), 0.0) > 0.0

    def update(self, scene, dt):
        self.iframes = {k: v - dt for k, v in self.iframes.items() if v - dt > 0}
        hurtboxes = [(e, h, _box(e, h)) for e, h in scene.query(Hurtbox2DComponent) if h.enabled and e.has(Transform)]
        events = []
        for attacker, hitbox in scene.query(Hitbox2DComponent):
            if not (hitbox.enabled and hitbox.active and attacker.has(Transform)):
                self._hit_this_activation.pop(attacker.id, None)  # next activation can hit again
                continue
            already = self._hit_this_activation.setdefault(attacker.id, set())
            box = _box(attacker, hitbox)
            for target, hurtbox, target_box in hurtboxes:
                if target is attacker or target.id in already:
                    continue
                if hitbox.team and hitbox.team == hurtbox.team:
                    continue
                if self.invincible(target.id, hurtbox) or not _overlaps(box, target_box):
                    continue
                already.add(target.id)
                events.append(HitEvent(attacker.id, target.id, hitbox.hit_tag, hitbox.team))
        self.events = events
        for event in events:
            for listener in tuple(self.listeners):
                listener(event)


def register_character_components(registry):
    for component in (
        CharacterController2DComponent,
        PlayerInput2DComponent,
        AIController2DComponent,
        Hitbox2DComponent,
        Hurtbox2DComponent,
    ):
        registry.register(component)
    return registry


__all__ = [
    "AIController2DComponent",
    "CharacterController2DComponent",
    "CharacterControllerSystem",
    "Collider2DComponent",
    "FACINGS",
    "HitEvent",
    "Hitbox2DComponent",
    "HitboxSystem",
    "facing_box",
    "facing_from",
    "facing_vector",
    "Hurtbox2DComponent",
    "PlayerInput2DComponent",
    "PlayerInputSystem",
    "register_character_components",
]
