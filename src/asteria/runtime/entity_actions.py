"""Entity action timelines (ANI-05, ASTERIA_SPEC §11): one timeline drives animation, movement, hitboxes,
i-frames, cancel and combo windows, VFX/SFX/camera cues and gameplay events on a field entity.

``EntityActionSystem.play(entity_id, timeline)`` starts an ``ActionTimeline`` on
an entity; each update applies the cues it crosses:

* ``animation``      → the entity's ``Animator2D`` clip (``payload.clip`` / ``payload.role``)
* ``movement``       → the ``CharacterController2D`` intent (``x``, ``y``) for ``duration``
* ``hitbox``         → the entity's ``Hitbox2D`` is active for ``duration`` (``hit_tag`` optional)
* ``iframe``         → invincibility for ``duration`` (``HitboxSystem.grant_invincibility``)
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

from .character_control import CharacterController2DComponent, Hitbox2DComponent
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
    order = 25  # after input (10) and AI (20), before CharacterControllerSystem (30) so cues move this frame

    def __init__(self, hitboxes=None):
        self.hitboxes = hitboxes
        self.running: dict[str, _Running] = {}
        self.events: list[ActionEvent] = []
        self.listeners = []

    # -- control ---------------------------------------------------------------------------------
    def play(self, entity_id, timeline):
        if not isinstance(timeline, ActionTimeline):
            raise TypeError("timeline must be ActionTimeline")
        self.running[str(entity_id)] = _Running(timeline, end=timeline.duration)

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
        """Stop the action if its cancel window is open (or ``force``); hitbox and movement end with it."""
        entity_id = str(entity_id)
        if entity_id not in self.running or not (force or self.window_open(entity_id, "cancel")):
            return False
        self._finish(entity_id, scene)
        return True

    def _finish(self, entity_id, scene):
        self.running.pop(entity_id, None)
        if scene is not None:
            entity = scene.get_entity(entity_id)
            if entity is not None:
                hitbox = entity.try_get(Hitbox2DComponent)
                if hitbox is not None:
                    hitbox.active = False
                controller = entity.try_get(CharacterController2DComponent)
                if controller is not None:
                    controller.set_intent(0.0, 0.0)

    # -- update ----------------------------------------------------------------------------------
    def _apply(self, entity, run, cue):
        payload = dict(cue.payload)
        kind = cue.kind
        if kind == ActionCueKind.ANIMATION:
            animator = entity.try_get(Animator2DComponent)
            if animator is not None:
                animator.default_clip = str(payload.get("clip") or payload.get("role") or animator.default_clip)
        elif kind == ActionCueKind.MOVEMENT:
            run.move_intent = (float(payload.get("x", 0.0)), float(payload.get("y", 0.0)))
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
            run.time += dt
            cues = run.timeline.cues
            while run.next_cue < len(cues) and cues[run.next_cue].time <= run.time + 1e-9:
                self._apply(entity, run, cues[run.next_cue])
                run.next_cue += 1
            controller = entity.try_get(CharacterController2DComponent)
            if run.move_until is not None:
                if run.time - dt < run.move_until - 1e-9 and controller is not None:
                    controller.set_intent(*run.move_intent)  # this frame starts inside the movement window
                elif run.time - dt >= run.move_until - 1e-9:
                    run.move_until = None
                    if controller is not None:
                        controller.set_intent(0.0, 0.0)
            if run.hitbox_until is not None and run.time >= run.hitbox_until:
                hitbox = entity.try_get(Hitbox2DComponent)
                if hitbox is not None:
                    hitbox.active = False
                run.hitbox_until = None
            if run.next_cue >= len(cues) and run.time >= run.end:
                self._finish(entity_id, scene)
