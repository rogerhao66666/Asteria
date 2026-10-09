from dataclasses import dataclass

from .events import EventBus
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
                self.step_fixed(dt)
                if self.scene is not None:
                    self.scene.update(self.time.delta_seconds)
                if hasattr(self.backend, "begin_frame"):
                    self.backend.begin_frame()
                if hasattr(self.backend, "end_frame"):
                    self.backend.end_frame()
                frames += 1
                if (
                    hasattr(self.backend, "should_close")
                    and self.backend.should_close()
                ):
                    self.stop()
                if max_frames is not None and frames >= max_frames:
                    self.stop()
        finally:
            if self.scene is not None and self.scene.entered:
                self.scene.exit()
            if hasattr(self.backend, "close"):
                self.backend.close()
            self._running = False
