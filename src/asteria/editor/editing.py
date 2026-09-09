from __future__ import annotations
from asteria.core.metadata import get_component_schema
from .commands import SetAttributeCommand

class EditError(ValueError):
    pass

def _field_for(component, field_name):
    schema=get_component_schema(type(component))
    try:
        return schema.fields[field_name]
    except KeyError as exc:
        raise EditError(f"unknown component field: {field_name}") from exc

def coerce_field_value(field, value):
    typ=field.value_type
    if isinstance(value,typ) and not (typ is int and isinstance(value,bool)):
        return value
    try:
        if typ is bool:
            if isinstance(value,str):
                normalized=value.strip().lower()
                if normalized in {"true","1","yes","on"}: return True
                if normalized in {"false","0","no","off"}: return False
                raise ValueError
            return bool(value)
        if typ is int:
            if isinstance(value,bool): raise ValueError
            return int(value)
        if typ is float: return float(value)
        if typ is str: return str(value)
    except (TypeError,ValueError) as exc:
        raise EditError(f"{field.name}: cannot convert to {typ.__name__}") from exc
    raise EditError(f"{field.name}: unsupported editor field type {typ.__name__}")

def build_set_component_field_command(component, field_name, raw_value):
    field=_field_for(component,field_name)
    if not field.serialize:
        raise EditError(f"{field_name}: runtime-only field is not editable")
    value=coerce_field_value(field,raw_value)
    try:
        field.validate(value)
    except (TypeError,ValueError) as exc:
        raise EditError(str(exc)) from exc
    old=getattr(component,field_name)
    return SetAttributeCommand(component,field_name,value,old,f"Set {type(component).__name__}.{field_name}")
