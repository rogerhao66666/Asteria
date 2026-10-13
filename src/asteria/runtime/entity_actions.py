"""Entity action timelines (ANI-05, ASTERIA_SPEC §11): one timeline drives animation, movement,
hitboxes,
i-frames, cancel and combo windows, VFX/SFX/camera cues and gameplay events on a field entity.

``EntityActionSystem.play(entity_id, timeline)`` starts an ``ActionTimeline`` on
an entity; each update applies the cues it crosses:

* ``animation``      → the entity's ``Animator2D`` clip (``payload.clip`` / ``payload.role``)
* ``movement``       → the ``CharacterController2D`` intent (``x``, ``y``) for ``duration``;
  ``relative``:
  ``world`` (default), ``facing`` (authored for facing right) or ``aim`` (along the action's aim);
  ``speed``
  replaces the controller's speed meanwhile (dashes, lunges)
* ``hitbox``         → the entity's ``Hitbox2D`` is active for ``duration`` (``hit_tag`` optional)
* ``iframe``         → invincibility for ``duration`` (``HitboxSystem.grant_invincibility``)
* ``projectile``     → fires ``projectile_id`` from the entity (``projectiles.fire_from``: count,
  spread,
  angle, offset turned with the facing); ``aim: true`` shoots along the action's aim
* ``armor``          → super armor ``level`` for ``duration`` (``armor.grant_armor``, e.g.
  ``CombatSystem``); it
  ends with the action
* ``cancel_window`` / ``combo_window`` → open for ``duration``; ``cancel()`` / ``window_open()``
* ``gameplay_event``, ``gameplay_ability`` and presentation cues (vfx, audio, camera, light,
  screen_fx) → reported in ``events`` / to ``listeners`` for the game and presentation layers

Nothing here is ARPG combat: it is the generic timing layer the SPEC asks
action timelines to provide; what a hit or a combo does is game logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from asteria.core import System
from asteria.gameplay.action_timeline import ActionCueKind, ActionTimeline

from .character_control import (
    CharacterController2DComponent,
    Hitbox2DComponent,
    turn_with_aim,
    turn_with_facing,
)
from .components2d import Animator2DComponent

WINDOW_KINDS = {ActionCueKind.CANCEL_WINDOW: "cancel", ActionCueKind.COMBO_WINDOW: "combo"}


@dataclass(slots=True)
class _Running:
    timeline: ActionTimeline
    time: float = 0.0
    next_cue: int = 0
    hitbox_until: float | None = None
    move_until: float | None = None
    move_intent: tuple = (0.0, 0.0)
    move_speed: float = 0.0
    aim: tuple | None = None  # world direction the action was aimed (lock-on target, stick)
    source: str = ""  # who started it (e.g. the ability id), for the caller's bookkeeping
    armored: bool = False
    windows: dict = field(default_factory=dict)  # kind -> (start, end, payload)
    end: float = 0.0


@dataclass(frozen=True, slots=True)
class ActionEvent:
    entity_id: str
    timeline_id: str
    cue_id: str
    kind: str
    payload: dict


class EntityActionSystem(System):
    # after input (10) and AI (20), before CharacterControllerSystem (30) so cues move this frame
    order = 25

    def __init__(self, hitboxes=None, *, paused=None, armor=None, projectiles=None):
        self.hitboxes = hitboxes
        self.projectiles = projectiles  # fire_from(entity, payload), e.g. ProjectileSystem
        # grant_armor(entity_id, level, seconds) / end_armor(entity_id), e.g. CombatSystem
        self.armor = armor
        self.paused = paused  # optional callable(entity_id) -> True while frozen (hitstop)
        self.running: dict[str, _Running] = {}
        self.events: list[ActionEvent] = []
        self.listeners = []

    # -- control ---------------------------------------------------------------------------------
    def play(self, entity_id, timeline, *, aim=None, source=""):
        if not isinstance(timeline, ActionTimeline):
            raise TypeError("timeline must be ActionTimeline")
        aim = None if aim is None or not (aim[0] or aim[1]) else (float(aim[0]), float(aim[1]))
        self.running[str(entity_id)] = _Running(
            timeline, end=timeline.duration, aim=aim, source=str(source)
        )

    def source(self, entity_id):
        run = self.running.get(str(entity_id))
        return None if run is None else run.source

    def active(self, entity_id):
        return str(entity_id) in self.running

    def time(self, entity_id):
        run = self.running.get(str(entity_id))
        return None if run is None else run.time

    def window_open(self, entity_id, kind):
        run = self.running.get(str(entity_id))
        if run is None or kind not in run.windows:
            return False
        start, end, _ = run.windows[kind]
        return start <= run.time < end

    def combo_next(self, entity_id):
        """Follow-up timeline id named by the open combo window, if any."""
        run = self.running.get(str(entity_id))
        if not self.window_open(entity_id, "combo"):
            return None
        return run.windows["combo"][2].get("next")

    def cancel(self, entity_id, scene=None, *, force=False):
        """Stop the action if its cancel window is open (or ``force``); hitbox and movement end
        with it."""
        entity_id = str(entity_id)
        if entity_id not in self.running or not (force or self.window_open(entity_id, "cancel")):
            return False
        self._finish(entity_id, scene)
        return True

    def _finish(self, entity_id, scene):
        run = self.running.pop(entity_id, None)
        if run is not None and run.armored and self.armor is not None:
            self.armor.end_armor(entity_id)
        if scene is not None:
            entity = scene.get_entity(entity_id)
            if entity is not None:
                hitbox = entity.try_get(Hitbox2DComponent)
                if hitbox is not None:
                    hitbox.active = False
                controller = entity.try_get(CharacterController2DComponent)
                if controller is not None:
                    controller.set_intent(0.0, 0.0)
                    controller.speed_override = 0.0

    # -- update ----------------------------------------------------------------------------------
    def _apply(self, entity, run, cue):
        payload = dict(cue.payload)
        kind = cue.kind
        if kind == ActionCueKind.ANIMATION:
            animator = entity.try_get(Animator2DComponent)
            if animator is not None:
                animator.default_clip = str(
                    payload.get("clip") or payload.get("role") or animator.default_clip
                )
        elif kind == ActionCueKind.MOVEMENT:
            x, y = float(payload.get("x", 0.0)), float(payload.get("y", 0.0))
            relative = payload.get("relative", "world")
            controller = entity.try_get(CharacterController2DComponent)
            if relative == "aim" and run.aim is not None:
                x, y = turn_with_aim(x, y, run.aim)
            elif relative in ("facing", "aim") and controller is not None:
                x, y = turn_with_facing(x, y, controller.facing)
            run.move_intent = (x, y)
            run.move_speed = float(payload.get("speed", 0.0))
            run.move_until = cue.time + float(payload.get("duration", 0.0))
        elif kind == ActionCueKind.HITBOX:
            hitbox = entity.try_get(Hitbox2DComponent)
            if hitbox is None:
                raise ValueError(f"{entity.name} has a hitbox cue but no Hitbox2D component")
            hitbox.active = True
            if payload.get("hit_tag"):
                hitbox.hit_tag = str(payload["hit_tag"])
            run.hitbox_until = cue.time + float(payload.get("duration", 0.0))
        elif kind == ActionCueKind.IFRAME:
            if self.hitboxes is not None:
                self.hitboxes.grant_invincibility(entity.id, float(payload.get("duration", 0.0)))
        elif kind == ActionCueKind.PROJECTILE:
            if self.projectiles is None:
                raise ValueError(
                    f"{entity.name} fired a projectile cue but no projectile system is running"
                )
            if payload.get("aim") and run.aim is not None:
                payload["direction"] = run.aim
            self.projectiles.fire_from(entity, payload)
        elif kind == ActionCueKind.ARMOR:
            if self.armor is not None:
                self.armor.grant_armor(
                    entity.id, int(payload.get("level", 1)), float(payload.get("duration", 0.0))
                )
                run.armored = True
        elif kind in WINDOW_KINDS:
            duration = float(payload.get("duration", 0.0))
            run.windows[WINDOW_KINDS[kind]] = (cue.time, cue.time + duration, payload)
        if kind in WINDOW_KINDS or kind in (ActionCueKind.MOVEMENT, ActionCueKind.HITBOX):
            run.end = max(run.end, cue.time + float(payload.get("duration", 0.0)))
        event = ActionEvent(entity.id, run.timeline.timeline_id, cue.cue_id, kind.value, payload)
        self.events.append(event)
        for listener in tuple(self.listeners):
            listener(event)

    def update(self, scene, dt):
        self.events = []
        for entity_id, run in tuple(self.running.items()):
            entity = scene.get_entity(entity_id)
            if entity is None:
                self.running.pop(entity_id, None)
                continue
            if self.paused is not None and self.paused(entity_id):
                continue
            run.time += dt
            cues = run.timeline.cues
            while run.next_cue < len(cues) and cues[run.next_cue].time <= run.time + 1e-9:
                self._apply(entity, run, cues[run.next_cue])
                run.next_cue += 1
            controller = entity.try_get(CharacterController2DComponent)
            if run.move_until is not None:
                if run.time - dt < run.move_until - 1e-9 and controller is not None:
                    controller.set_intent(
                        *run.move_intent
                    )  # this frame starts inside the movement window
                    controller.speed_override = run.move_speed
                elif run.time - dt >= run.move_until - 1e-9:
                    run.move_until = None
                    if controller is not None:
                        controller.set_intent(0.0, 0.0)
                        controller.speed_override = 0.0
            if run.hitbox_until is not None and run.time >= run.hitbox_until:
                hitbox = entity.try_get(Hitbox2DComponent)
                if hitbox is not None:
                    hitbox.active = False
                run.hitbox_until = None
            if run.next_cue >= len(cues) and run.time >= run.end:
                self._finish(entity_id, scene)
