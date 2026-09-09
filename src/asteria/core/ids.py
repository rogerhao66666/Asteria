from __future__ import annotations
from uuid import UUID, uuid4

def new_id() -> str:
    return str(uuid4())

def validate_id(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("ID must be a string")
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ValueError(f"Invalid UUID: {value}") from exc
    canonical = str(parsed)
    if value != canonical:
        raise ValueError(f"ID must use canonical UUID string form: {canonical}")
    return value
