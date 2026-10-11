"""Character control and hit detection (ENG-02, ENG-16, ENG-17; ASTERIA_SPEC §6, §8).

Components (serializable, inspectable, script-accessible):

* ``CharacterController2D`` — moves its entity from an *intent* (``intent_x``,
  ``intent_y``, ``jump``) and resolves it against solid colliders (and any
  extra blocking query such as a tile map). ``mode="topdown"`` slides on
  both axes; ``mode="side"`` adds gravity, jumping, ground detection and
  one-way platforms (``Collider2D.one_way``). After each update the
  component reports ``grounded``, ``ground_id``, ``hit_wall``, ``hit_ceiling``.
* ``PlayerInput2D`` — fills a controller's intent from the input action map.
* ``AIController2D`` — marks an entity as AI-driven; ``FieldAISystem`` (and the
  behavior-tree runtime) write the controller intent instead of moving the
  entity directly, so AI respects the same collision as the player.
* ``Hitbox2D`` / ``Hurtbox2D`` — generic hit detection: an active hitbox that
  overlaps a hurtbox of another team produces one ``HitEvent`` per target per
  activation; invincible hurtboxes (and i-frame timers) are skipped. What a hit
  *does* (damage, knockback...) is game logic attached to the events.
"""

from __future__ import annotations

from dataclasses import dataclass

from asteria.core import Component, Field, System, Transform, component_schema, world_position

from .collision import Collider2DComponent, CollisionWorld

GROUND_PROBE = 0.5


@component_schema(
    type_name="asteria.CharacterController2D",
    version=1,
    fields=(
        Field("mode", str, "topdown", choices=("topdown", "side")),
        Field("speed", float, 60.0, minimum=0.0),
        Field("half_width", float, 6.0, minimum=0.0),
        Field("half_height", float, 8.0, minimum=0.0),
        Field("gravity", float, 600.0, minimum=0.0, tooltip="Side view: downward acceleration."),
        Field("jump_speed", float, 220.0, minimum=0.0, tooltip="Side view: upward speed of a jump."),
        Field("max_fall_speed", float, 400.0, minimum=0.0),
        Field("mask", int, 0xFFFFFFFF, minimum=0, maximum=0xFFFFFFFF, tooltip="Collider layers that block it."),
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

    def set_intent(self, x=0.0, y=0.0, *, jump=False):
        self.intent_x, self.intent_y, self.jump = float(x), float(y), bool(jump)


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
    )


@component_schema(
    type_name="asteria.Hitbox2D",
    version=1,
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
        self.active = False
        self.hit_tag = ""
        self.enabled = True


@component_schema(
    type_name="asteria.Hurtbox2D",
    version=1,
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
        self.invincible = False
        self.enabled = True


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

    def __init__(self, extra_blocking=None):
        self.extra_blocking = extra_blocking  # e.g. a tile map query (collides_world_point)

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
            if not controller.enabled:
                continue
            controller.hit_wall = controller.hit_ceiling = False
            dx, dy = controller.intent_x, controller.intent_y
            if controller.mode == "topdown":
                mag = (dx * dx + dy * dy) ** 0.5
                if mag > 1.0:
                    dx, dy = dx / mag, dy / mag
                nx = transform.x + dx * controller.speed * dt
                if self._blocked(world, entity.id, controller, nx, transform.y):
                    controller.hit_wall = dx != 0
                else:
                    transform.x = nx
                ny = transform.y + dy * controller.speed * dt
                if self._blocked(world, entity.id, controller, transform.x, ny):
                    controller.hit_wall = controller.hit_wall or dy != 0
                else:
                    transform.y = ny
                controller.grounded, controller.ground_id = True, None
                continue
            # side view
            nx = transform.x + max(-1.0, min(1.0, dx)) * controller.speed * dt
            if self._blocked(world, entity.id, controller, nx, transform.y):
                controller.hit_wall = dx != 0
            else:
                transform.x = nx
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


@dataclass(frozen=True, slots=True)
class HitEvent:
    attacker_id: str
    target_id: str
    hit_tag: str
    team: str


def _box(entity, spec):
    x, y = world_position(entity)
    cx, cy = x + spec.offset_x, y + spec.offset_y
    return (cx - spec.width / 2, cy - spec.height / 2, cx + spec.width / 2, cy + spec.height / 2)


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
    "HitEvent",
    "Hitbox2DComponent",
    "HitboxSystem",
    "Hurtbox2DComponent",
    "PlayerInput2DComponent",
    "PlayerInputSystem",
    "register_character_components",
]
