"""A new, empty record of a kind: built from the shape of a record that exists, since each
kind's rules (which fields it has, which values are allowed) live in its own class.

``blank_record`` tries, in order, a record with everything empty; one that keeps the
template's single values (a kind's enumerations, its numbers) but empties its lists; one that
keeps a single entry in each list (a kind that needs at least one member, one milestone); and
finally a plain copy. The first the kind accepts is the new record.
"""

from __future__ import annotations

import re

NAME_KEYS = ("display_name", "name", "label", "title")
_KEEP = ("schema", "version")


def id_key_of(data, record_id):
    """The key holding the record's own id in its encoded form."""
    for key, value in data.items():
        if key.endswith("_id") and value == record_id:
            return key
    return next((key for key in data if key.endswith("_id")), None)


def suggest_id(name, taken=()):
    """An internal id made from a name: ``Fire Bolt!`` -> ``fire_bolt``, kept unique."""
    base = re.sub(r"[^a-z0-9]+", "_", str(name or "").strip().lower()).strip("_") or "new"
    candidate, counter = base, 2
    while candidate in taken:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _blanked(data, tier, new_id, name, id_key):
    out = {}
    for key, value in data.items():
        if key == id_key:
            out[key] = new_id
        elif key in NAME_KEYS and isinstance(value, str):
            out[key] = name
        elif key in _KEEP or isinstance(value, bool):
            out[key] = value
        elif isinstance(value, list):
            out[key] = [] if tier < 3 else value[:1]
        elif isinstance(value, dict):
            numbers = value and all(isinstance(v, (int, float)) for v in value.values())
            out[key] = {} if (tier == 1 or numbers) else value
        elif isinstance(value, str):
            out[key] = "" if tier == 1 else value
        elif isinstance(value, (int, float)):
            out[key] = 0 if tier == 1 else value
        else:
            out[key] = value
    return out


def blank_record(adapter, template, new_id, name):
    """A decoded record for ``adapter`` named ``name`` with id ``new_id``, as empty as the kind
    allows; ``template`` is the encoded form of a record of that kind. Raises ValueError when
    even a copy will not do."""
    template = dict(template)
    id_key = id_key_of(template, None)
    for key, value in template.items():
        if key.endswith("_id") and isinstance(value, str) and value in adapter.ids():
            id_key = key
            break
    errors = []
    for tier in (1, 2, 3):
        data = _blanked(template, tier, new_id, name, id_key)
        try:
            value = adapter.decode(data)
            validate = getattr(value, "validate", None)
            if callable(validate):
                try:
                    validate()
                except TypeError:
                    pass  # needs the database: the create command checks it
            return value
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(str(exc))
    copy = dict(template)
    copy[id_key] = new_id
    for key in NAME_KEYS:
        if key in copy and isinstance(copy[key], str):
            copy[key] = name
    try:
        return adapter.decode(copy)
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    raise ValueError("; ".join(errors[-1:]) or "the kind rejected a new record")
