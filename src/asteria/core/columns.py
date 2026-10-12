"""Column storage for hot component data (D22-C1).

A component class marked with ``@column_storage`` keeps its numeric fields (float, int, bool schema fields plus the
runtime fields it names) in per-scene columns instead of on the object. Each entity in a scene owns a *slot*; column
``name`` of component type ``T`` is one ``array.array`` indexed by slot, so

* game code, scripts, the inspector and serialization keep using plain attributes (``transform.x = 3``) — the
  attribute is a descriptor that reads and writes the column;
* engine systems read and write whole columns at once (``scene.columns(Transform)``): the python kernels use the
  arrays directly, numpy wraps the same memory without copying (``numpy.frombuffer``).

A component that is not in a scene (being built, detached for undo, or on an entity waiting to be added) keeps its
values on itself; attaching copies them into the scene's columns and detaching copies them back, so nothing is lost
and nothing else changes for callers. ``enabled`` and text fields stay ordinary attributes.
"""

from __future__ import annotations

from array import array

from .metadata import get_component_schema

TYPECODES = {float: "d", int: "q", bool: "b"}
_DEFAULTS = {"d": 0.0, "q": 0, "b": False}


class _Column:
    """Data descriptor for one column field."""

    __slots__ = ("name", "typecode", "convert", "default")

    def __init__(self, name, typecode, default):
        self.name = name
        self.typecode = typecode
        self.convert = {"d": float, "q": int, "b": bool}[typecode]
        self.default = default

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        table = obj._ctable
        if table is None:
            return obj._clocal.get(self.name, self.default)
        value = table.data[self.name][obj._cslot]
        return bool(value) if self.typecode == "b" else value

    def __set__(self, obj, value):
        if isinstance(value, str) or (self.typecode == "d" and isinstance(value, bool)):
            raise TypeError(f"{self.name}: invalid type")
        value = self.convert(value)
        table = obj._ctable
        if table is None:
            obj._clocal[self.name] = value
        else:
            table.data[self.name][obj._cslot] = value


def column_storage(*runtime_fields):
    """Class decorator: keep the schema's numeric fields and ``runtime_fields`` (``(name, type, default)``) in
    columns."""

    def deco(cls):
        schema = get_component_schema(cls)
        spec, defaults = {}, {}
        for name, field in schema.fields.items():
            if name != "enabled" and field.value_type in TYPECODES:
                spec[name] = TYPECODES[field.value_type]
                defaults[name] = field.default
        for name, value_type, default in runtime_fields:
            spec[name] = TYPECODES[value_type]
            defaults[name] = default
        for name, typecode in spec.items():
            setattr(cls, name, _Column(name, typecode, defaults[name]))
        cls.__columns__ = spec
        return cls

    return deco


def column_spec(component_type):
    return getattr(component_type, "__columns__", None)


class ColumnTable:
    """One component type's columns in one scene, indexed by entity slot."""

    def __init__(self, component_type):
        self.component_type = component_type
        self.spec = dict(component_type.__columns__)
        self.data = {name: array(typecode) for name, typecode in self.spec.items()}
        self.components = []  # by slot; None where the slot has no such component
        self.version = 0  # changes whenever membership changes
        self._slots = None

    def _ensure(self, slot):
        missing = slot + 1 - len(self.components)
        if missing > 0:
            grow = max(missing, len(self.components))  # double to keep appends amortised
            for name, typecode in self.spec.items():
                self.data[name].extend([_DEFAULTS[typecode]] * grow)
            self.components.extend([None] * grow)

    def attach(self, component, slot):
        self._ensure(slot)
        local = component._clocal
        cls = type(component)
        for name in self.spec:
            value = local.pop(name, getattr(cls, name).default)
            self.data[name][slot] = value
        self.components[slot] = component
        component._ctable, component._cslot = self, slot
        self.version += 1
        self._slots = None

    def detach(self, component):
        slot = component._cslot
        local = component._clocal
        for name, typecode in self.spec.items():
            value = self.data[name][slot]
            local[name] = bool(value) if typecode == "b" else value
        self.components[slot] = None
        component._ctable, component._cslot = None, -1
        self.version += 1
        self._slots = None

    def slots(self):
        """Occupied slots, ascending (cached until membership changes)."""
        if self._slots is None:
            self._slots = [s for s, c in enumerate(self.components) if c is not None]
        return self._slots

    def column(self, name):
        return self.data[name]


__all__ = ["TYPECODES", "ColumnTable", "column_spec", "column_storage"]
