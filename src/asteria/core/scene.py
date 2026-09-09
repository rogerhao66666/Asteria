from .events import EventBus
from .ids import new_id, validate_id
from .system import SystemScheduler


class Scene:
    def __init__(self, name="Scene", *, scene_id=None):
        self.id = validate_id(scene_id) if scene_id is not None else new_id()
        self.name = str(name)
        self.scheduler = SystemScheduler()
        self.events = EventBus()
        self._entities = []
        self._entity_ids = {}
        self._updating = False
        self._pending_add = []
        self._pending_remove = []
        self._entered = False

    @property
    def entered(self):
        return self._entered

    def enter(self):
        self._entered = True

    def exit(self):
        self._entered = False

    def add_entity(self, entity):
        if entity.scene is not None and entity.scene is not self:
            raise RuntimeError("Entity already belongs to another scene")
        if entity.id in self._entity_ids or any(
            e.id == entity.id for e in self._pending_add
        ):
            raise ValueError(f"Duplicate entity ID in scene: {entity.id}")
        if self._updating:
            self._pending_add.append(entity)
        else:
            self._attach_now(entity)
        return entity

    def _attach_now(self, entity):
        entity._scene = self
        self._entities.append(entity)
        self._entity_ids[entity.id] = entity

    def get_entity(self, entity_id):
        return self._entity_ids.get(entity_id)

    def detach_entity(self, entity):
        if self._updating:
            raise RuntimeError("Cannot detach entity during scene update")
        if entity.scene is not self:
            raise ValueError("Entity does not belong to scene")
        self._entities.remove(entity)
        self._entity_ids.pop(entity.id, None)
        entity._scene = None
        entity._destroy_requested = False
        return entity

    def remove_entity(self, entity):
        if entity.scene is not self and entity not in self._pending_add:
            return
        entity._destroy_requested = True
        if self._updating:
            if entity not in self._pending_remove:
                self._pending_remove.append(entity)
        else:
            self._remove_now(entity)

    def _remove_now(self, entity):
        if entity in self._entities:
            self._entities.remove(entity)
        self._entity_ids.pop(entity.id, None)
        if entity in self._pending_add:
            self._pending_add.remove(entity)
        for c in tuple(entity._components.values()):
            c._destroy()
        entity._components.clear()
        entity._scene = None
        entity._destroy_requested = True

    def move_entity(self, entity, new_index):
        if self._updating:
            raise RuntimeError("Cannot reorder entity during scene update")
        if entity.scene is not self:
            raise ValueError("Entity does not belong to scene")
        count = len(self._entities)
        if count <= 1:
            return 0
        old = self._entities.index(entity)
        new_index = max(0, min(int(new_index), count - 1))
        if old == new_index:
            return old
        self._entities.pop(old)
        self._entities.insert(new_index, entity)
        return old

    def entity_index(self, entity):
        if entity.scene is not self:
            raise ValueError("Entity does not belong to scene")
        return self._entities.index(entity)

    def entities(self):
        return tuple(e for e in self._entities if not e.destroy_requested)

    def query(self, *types):
        for e in self.entities():
            if e.enabled and all(e.has(t) for t in types):
                yield (e, *(e.get(t) for t in types))

    def update(self, dt):
        if self._updating:
            raise RuntimeError("Scene update is not re-entrant")
        self._updating = True
        try:
            self.scheduler.update(self, dt)
        finally:
            self._updating = False
            for e in tuple(self._pending_remove):
                self._remove_now(e)
            self._pending_remove.clear()
            for e in tuple(self._pending_add):
                if not e.destroy_requested:
                    self._attach_now(e)
            self._pending_add.clear()
