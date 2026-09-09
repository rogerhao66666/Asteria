class Component:
    def __init__(self, *, enabled: bool = True):
        self._entity = None
        self._enabled = bool(enabled)
        self._created = False
        self._destroyed = False

    @property
    def entity(self):
        if self._entity is None:
            raise RuntimeError("Component is not attached")
        return self._entity

    @property
    def attached(self):
        return self._entity is not None

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        value = bool(value)
        if self._destroyed or value == self._enabled:
            return
        self._enabled = value
        if self._created:
            (self.on_enable if value else self.on_disable)()

    def _attach(self, entity):
        if self._entity is not None or self._destroyed:
            raise RuntimeError("Invalid component attach")
        self._entity = entity
        self._created = True
        self.on_create()
        if self._enabled:
            self.on_enable()

    def _detach(self):
        """Detach without destroying, so ownership edits can be reversed safely."""
        if self._entity is None or self._destroyed:
            return
        if self._created and self._enabled:
            self.on_disable()
        self.on_detach()
        self._entity = None
        self._created = False

    def _destroy(self):
        if self._destroyed:
            return
        if self._created and self._enabled:
            self.on_disable()
        self.on_destroy()
        self._destroyed = True
        self._created = False
        self._entity = None

    def on_create(self):
        pass

    def on_enable(self):
        pass

    def on_disable(self):
        pass

    def on_detach(self):
        pass

    def on_destroy(self):
        pass
