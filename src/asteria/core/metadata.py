from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

@dataclass(frozen=True, slots=True)
class Field:
    name: str
    value_type: type
    default: Any
    label: str | None = None
    category: str = "General"
    level: str = "basic"
    minimum: int | float | None = None
    maximum: int | float | None = None
    choices: tuple | None = None
    tooltip: str = ""
    serialize: bool = True

    def validate(self, value):
        if not isinstance(value, self.value_type):
            raise TypeError(f"{self.name}: invalid type")
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{self.name}: below minimum")
        if self.maximum is not None and value > self.maximum:
            raise ValueError(f"{self.name}: above maximum")
        if self.choices is not None and value not in self.choices:
            raise ValueError(f"{self.name}: invalid choice")

@dataclass(frozen=True, slots=True)
class ComponentSchema:
    type_name: str
    version: int
    fields: object

def component_schema(*, type_name=None, version=1, fields=()):
    if version < 1:
        raise ValueError("Schema version must be >= 1")
    if len({f.name for f in fields}) != len(fields):
        raise ValueError("Duplicate field names")
    def deco(cls):
        cls.__asteria_schema__ = ComponentSchema(
            type_name or f"{cls.__module__}.{cls.__qualname__}",
            version,
            MappingProxyType({f.name: f for f in fields}),
        )
        return cls
    return deco

def get_component_schema(component_type):
    try:
        return component_type.__asteria_schema__
    except AttributeError as exc:
        raise TypeError(f"{component_type.__name__} has no Asteria schema") from exc
