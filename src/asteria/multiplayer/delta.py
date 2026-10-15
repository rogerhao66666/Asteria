"""State deltas: send only what changed between two JSON states.

``diff(old, new)`` returns a patch (or ``None`` when nothing changed) and ``apply(old, patch)``
rebuilds ``new`` exactly. A patch is plain JSON:

- a dict of the keys that changed, each holding a patch of its own; ``{"$del": [keys]}`` lists
  removed keys;
- ``{"$set": value}`` replaces a value whole (used for scalars, type changes and when a replacement
  is smaller than a patch);
- ``{"$append": [items]}`` for a list that only grew at the end;
- ``{"$keyed": {...}}`` for a list of objects that carry an ``id`` / ``player_id`` style key: each
  object is patched by its key and the order is kept.

``apply`` never mutates its input.
"""

from __future__ import annotations

import copy
import json
from typing import Any

KEY_NAMES = ("player_id", "id", "instance_id", "slot_id")
_SENTINELS = {"$set", "$append", "$keyed", "$del"}


class DeltaError(ValueError):
    """A patch does not fit the state it was applied to."""


def _size(value):
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False))


def _list_key(old, new):
    """The object key shared by every item of both lists (and unique in each), or ``None``."""
    if not old or not new or not all(isinstance(x, dict) for x in (*old, *new)):
        return None
    for name in KEY_NAMES:
        old_ids = [x.get(name) for x in old]
        new_ids = [x.get(name) for x in new]
        if None in old_ids or None in new_ids:
            continue
        if len(set(old_ids)) == len(old_ids) and len(set(new_ids)) == len(new_ids):
            if all(isinstance(i, str | int) for i in (*old_ids, *new_ids)):
                return name
    return None


def diff(old: Any, new: Any):
    """A patch that turns ``old`` into ``new``, or ``None`` if they are equal."""
    if old == new and type(old) is type(new):
        return None
    patch = _diff(old, new)
    full = {"$set": new}
    return patch if _size(patch) < _size(full) else full


def _diff(old, new):
    if isinstance(old, dict) and isinstance(new, dict):
        patch = {}
        removed = sorted(k for k in old if k not in new)
        if removed:
            patch["$del"] = removed
        for key, value in new.items():
            if key not in old:
                patch[key] = {"$set": value}
            else:
                child = diff(old[key], value)
                if child is not None:
                    patch[key] = child
        return patch
    if isinstance(old, list) and isinstance(new, list):
        if len(new) > len(old) and new[: len(old)] == old:
            return {"$append": new[len(old) :]}
        name = _list_key(old, new)
        if name is not None:
            before = {item[name]: item for item in old}
            changes = {}
            for item in new:
                key = item[name]
                if key not in before:
                    changes[str(key)] = {"$set": item}
                else:
                    child = diff(before[key], item)
                    if child is not None:
                        changes[str(key)] = child
            return {
                "$keyed": {
                    "key": name,
                    "order": [item[name] for item in new],
                    "changes": changes,
                }
            }
    return {"$set": new}


def apply(old: Any, patch: Any):
    """The state ``patch`` produces from ``old`` (``old`` is left alone)."""
    if patch is None:
        return copy.deepcopy(old)
    if not isinstance(patch, dict):
        raise DeltaError("a patch is an object")
    if "$set" in patch and len(patch) == 1:
        return copy.deepcopy(patch["$set"])
    if "$append" in patch and len(patch) == 1:
        if not isinstance(old, list) or not isinstance(patch["$append"], list):
            raise DeltaError("$append needs a list")
        return [*copy.deepcopy(old), *copy.deepcopy(patch["$append"])]
    if "$keyed" in patch and len(patch) == 1:
        return _apply_keyed(old, patch["$keyed"])
    if not isinstance(old, dict):
        raise DeltaError("a key patch needs an object to patch")
    result = copy.deepcopy(old)
    for key in patch.get("$del", ()):
        result.pop(key, None)
    for key, child in patch.items():
        if key in _SENTINELS:
            continue
        if key not in result and not (isinstance(child, dict) and "$set" in child):
            raise DeltaError(f"patch touches missing key {key!r}")
        result[key] = apply(result.get(key), child)
    return result


def _apply_keyed(old, spec):
    if not isinstance(old, list) or not isinstance(spec, dict):
        raise DeltaError("$keyed needs a list")
    try:
        name, order, changes = spec["key"], spec["order"], spec["changes"]
    except KeyError as exc:
        raise DeltaError("$keyed is missing a part") from exc
    before = {item[name]: item for item in old if isinstance(item, dict) and name in item}
    result = []
    for key in order:
        change = changes.get(str(key))
        if key in before:
            result.append(apply(before[key], change) if change is not None else before[key])
        elif change is not None and "$set" in change:
            result.append(copy.deepcopy(change["$set"]))
        else:
            raise DeltaError(f"patch refers to unknown item {key!r}")
    return copy.deepcopy(result)
