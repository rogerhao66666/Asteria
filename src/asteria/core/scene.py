from .columns import ColumnTable, column_spec
from .events import EventBus
from .ids import new_id, validate_id
from .system import SystemScheduler


def _order_key(entity):
    return entity._order


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
        # D22-C1: entity slots, column tables and a per-type index (query without scanning every
        # entity)
        self._slots = {}  # entity id -> slot
        self._free_slots = []
        self._slot_count = 0
        self._tables = {}  # component type -> ColumnTable
        self._index = {}  # component type -> {entity: None}
        self._index_cache = {}  # component type -> tuple of entities in scene order
        self._order_counter = 0

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
        if entity.id in self._entity_ids or any(e.id == entity.id for e in self._pending_add):
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
        self._order_counter += 1
        entity._order = self._order_counter
        if self._free_slots:
            slot = self._free_slots.pop()
        else:
            slot = self._slot_count
            self._slot_count += 1
        self._slots[entity.id] = slot
        for component in entity._components.values():
            self._component_added(entity, component)

    def _release(self, entity):
        """Take the entity's components out of the index and columns (values go back onto the
        components)."""
        for component in tuple(entity._components.values()):
            self._component_removed(entity, component)
        slot = self._slots.pop(entity.id, None)
        if slot is not None:
            self._free_slots.append(slot)

    # -- component index and column storage -------------------------------------------------------
    def _component_added(self, entity, component):
        ctype = type(component)
        self._index.setdefault(ctype, {})[entity] = None
        self._index_cache.pop(ctype, None)
        if column_spec(ctype) is not None and component._ctable is None:
            table = self._tables.get(ctype)
            if table is None:
                table = self._tables[ctype] = ColumnTable(ctype)
            table.attach(component, self._slots[entity.id])

    def _component_removed(self, entity, component):
        ctype = type(component)
        members = self._index.get(ctype)
        if members is not None:
            members.pop(entity, None)
        self._index_cache.pop(ctype, None)
        table = component._ctable
        if table is not None and table is self._tables.get(ctype):
            table.detach(component)

    def slot_of(self, entity):
        """The entity's slot in this scene's column tables (``None`` when it is not attached)."""
        return self._slots.get(entity.id)

    def columns(self, component_type):
        """The ``ColumnTable`` of a column-stored component type (``None`` until one is attached
        here)."""
        return self._tables.get(component_type)

    def _members(self, component_type):
        """Entities with ``component_type``, in scene order (cached until membership or order
        changes)."""
        cached = self._index_cache.get(component_type)
        if cached is None:
            members = self._index.get(component_type, {})
            cached = self._index_cache[component_type] = tuple(sorted(members, key=_order_key))
        return cached

    def get_entity(self, entity_id):
        return self._entity_ids.get(entity_id)

    def detach_entity(self, entity):
        if self._updating:
            raise RuntimeError("Cannot detach entity during scene update")
        if entity.scene is not self:
            raise ValueError("Entity does not belong to scene")
        self._release(entity)
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
        if entity.id in self._slots and entity._scene is self:
            self._release(entity)
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
        for position, e in enumerate(
            self._entities
        ):  # scene order changed: renumber, drop cached query orders
            e._order = position
        self._order_counter = len(self._entities)
        self._index_cache.clear()
        return old

    def entity_index(self, entity):
        if entity.scene is not self:
            raise ValueError("Entity does not belong to scene")
        return self._entities.index(entity)

    def entities(self):
        return tuple(e for e in self._entities if not e.destroy_requested)

    def query(self, *types):
        """Enabled entities that have every one of ``types``, in scene order, with those
        components."""
        if not types:
            for e in self.entities():
                if e.enabled:
                    yield (e,)
            return
        base = min(types, key=lambda t: len(self._index.get(t, ())))
        rest = tuple(t for t in types if t is not base)
        for e in self._members(base):
            if e.enabled and not e._destroy_requested and all(t in e._components for t in rest):
                components = e._components
                yield (e, *(components[t] for t in types))

    def fixed_update(self, dt):
        """Run every system's fixed-rate step (no entity add/remove flush)."""
        if self._updating:
            raise RuntimeError("Scene update is not re-entrant")
        self._updating = True
        try:
            self.scheduler.fixed_update(self, dt)
        finally:
            self._updating = False

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
