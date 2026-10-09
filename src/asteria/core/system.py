class System:
    order = 0
    enabled = True

    def update(self, scene, dt):
        raise NotImplementedError

    def fixed_update(self, scene, dt):
        """Deterministic simulation step at the application's fixed rate (optional)."""


class SystemScheduler:
    def __init__(self):
        self._systems = []
        self._running = False

    def add(self, system):
        if self._running:
            raise RuntimeError("Cannot mutate scheduler while running")
        if system in self._systems:
            raise ValueError("System already registered")
        self._systems.append(system)
        self._systems.sort(key=lambda s: s.order)

    def update(self, scene, dt):
        if self._running:
            raise RuntimeError("Scheduler update is not re-entrant")
        self._running = True
        try:
            for system in tuple(self._systems):
                if system.enabled:
                    system.update(scene, dt)
        finally:
            self._running = False

    def fixed_update(self, scene, dt):
        if self._running:
            raise RuntimeError("Scheduler update is not re-entrant")
        self._running = True
        try:
            for system in tuple(self._systems):
                if system.enabled:
                    system.fixed_update(scene, dt)
        finally:
            self._running = False
