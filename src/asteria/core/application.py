from dataclasses import dataclass

from .events import EventBus
from .scene_transition import SceneTransition, _ActiveTransition, carry_persistent_entities
from .services import ServiceRegistry
from .time import TimeState


@dataclass(slots=True)
class ApplicationConfig:
    title: str = "Asteria"
    width: int = 960
    height: int = 540
    target_fps: int = 60
    max_delta_seconds: float = 0.25
    # Fixed simulation step in seconds (None disables). Systems implement fixed_update.
    fixed_timestep: float | None = None
    max_fixed_steps: int = 5


class Application:
    def __init__(self, backend, config=None):
        self.config = config or ApplicationConfig()
        self.backend = backend
        self.time = TimeState()
        self.services = ServiceRegistry()
        self.events = EventBus()
        self.scene = None
        self._running = False
        self._accumulator = 0.0
        self._transition = None
        # 0 = scene fully visible, 1 = fully covered by the transition colour.
        self.transition_cover = 0.0
        if self.config.fixed_timestep is not None and not self.config.fixed_timestep > 0:
            raise ValueError("fixed_timestep must be positive")
        self.services.add(TimeState, self.time)

    @property
    def running(self):
        return self._running

    def set_scene(self, scene):
        if self.scene is scene:
            return
        if self.scene is not None and self.scene.entered:
            self.scene.exit()
        self.scene = scene
        if self._running and scene is not None:
            scene.enter()

    @property
    def transition_color(self):
        return None if self._transition is None else self._transition.spec.color

    def change_scene(self, scene, transition: SceneTransition | None = None):
        """Switch scenes now, or fade out, switch, fade in when ``transition`` is given.

        Entities with PersistentComponent move to the new scene.
        """
        if transition is None or (transition.fade_out == 0 and transition.fade_in == 0):
            self._swap_scene(scene)
            return
        self._transition = _ActiveTransition(scene, transition)

    def _swap_scene(self, scene):
        carry_persistent_entities(self.scene, scene)
        self.set_scene(scene)

    def advance_transition(self, dt):
        """Advance an active fade; returns True while a transition is running."""
        t = self._transition
        if t is None:
            return False
        t.elapsed += max(0.0, float(dt))
        if t.phase == "out":
            self.transition_cover = (
                1.0 if t.spec.fade_out == 0 else min(1.0, t.elapsed / t.spec.fade_out)
            )
            if t.elapsed >= t.spec.fade_out:
                self._swap_scene(t.target)
                t.phase, t.elapsed = "in", 0.0
        if t.phase == "in":
            self.transition_cover = (
                0.0 if t.spec.fade_in == 0 else max(0.0, 1.0 - t.elapsed / t.spec.fade_in)
            )
            if t.elapsed >= t.spec.fade_in:
                self._transition = None
                self.transition_cover = 0.0
                return False
        return True

    def stop(self):
        self._running = False

    def step_fixed(self, dt):
        """Advance the fixed-rate simulation by ``dt`` of real time; returns steps run.

        At most ``max_fixed_steps`` run per frame; extra backlog is dropped so a
        slow frame cannot snowball into ever longer catch-up frames.
        """
        step = self.config.fixed_timestep
        if step is None:
            return 0
        self._accumulator += float(dt)
        steps = 0
        while self._accumulator >= step and steps < self.config.max_fixed_steps:
            if self.scene is not None:
                self.scene.fixed_update(step)
            self._accumulator -= step
            steps += 1
        if steps == self.config.max_fixed_steps and self._accumulator >= step:
            self._accumulator %= step
        self.time.fixed_steps += steps
        self.time.fixed_alpha = self._accumulator / step
        return steps

    def run(self, *, max_frames=None):
        if self._running:
            raise RuntimeError("application is already running")
        self._running = True
        if hasattr(self.backend, "open"):
            self.backend.open(self.config.title, self.config.width, self.config.height)
        if self.scene is not None:
            self.scene.enter()
        frames = 0
        try:
            while self._running:
                dt = (
                    self.backend.tick(self.config.target_fps)
                    if hasattr(self.backend, "tick")
                    else 1 / self.config.target_fps
                )
                dt = min(max(float(dt), 0.0), self.config.max_delta_seconds)
                self.time.advance(dt)
                self.advance_transition(dt)
                self.step_fixed(dt)
                if self.scene is not None:
                    self.scene.update(self.time.delta_seconds)
                if hasattr(self.backend, "begin_frame"):
                    self.backend.begin_frame()
                if hasattr(self.backend, "end_frame"):
                    self.backend.end_frame()
                frames += 1
                if hasattr(self.backend, "should_close") and self.backend.should_close():
                    self.stop()
                if max_frames is not None and frames >= max_frames:
                    self.stop()
        finally:
            if self.scene is not None and self.scene.entered:
                self.scene.exit()
            if hasattr(self.backend, "close"):
                self.backend.close()
            self._running = False
