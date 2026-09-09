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


class Application:
    def __init__(self, backend, config=None):
        self.config = config or ApplicationConfig()
        self.backend = backend
        self.time = TimeState()
        self.services = ServiceRegistry()
        self.events = EventBus()
        self.scene = None
        self._running = False
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
