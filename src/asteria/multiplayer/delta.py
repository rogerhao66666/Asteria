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


def _key_size(key):
    """Length of ``key`` written as a JSON object key (quotes included)."""
    return _size(key) if isinstance(key, str) else _size({key: 0}) - 4


def _container_size(sizes):
    """Length of a JSON object / array whose members (``"k":v`` or items) have ``sizes``."""
    return 1 + sum(sizes) + len(sizes) if sizes else 2


# '{"$set":' + value + '}', '{"$append":' + items + '}' and
# '{"$keyed":{"key":' + name + ',"order":' + order + ',"changes":' + changes + '}}'
_SET_EXTRA, _APPEND_EXTRA, _KEYED_EXTRA, _DEL_KEY = 9, 12, 39, 6


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
    child = _child(old, new)
    return None if child is None else child[0]


def _child(old, new):
    """``(patch, patch size, size of new)`` or ``None`` when equal.

    The patch is the smaller of the structural patch and ``{"$set": new}`` by JSON length;
    lengths are built bottom-up so every value is serialised once, not once per level.
    """
    if old == new and type(old) is type(new):
        return None
    patch, patch_size, new_size = _diff(old, new)
    full_size = new_size + _SET_EXTRA
    if patch_size < full_size:
        return patch, patch_size, new_size
    return {"$set": new}, full_size, new_size


def _diff(old, new):
    """``(patch, patch size, size of new)`` for values that differ."""
    if isinstance(old, dict) and isinstance(new, dict):
        patch, patch_sizes, new_sizes = {}, {}, []
        removed = sorted(k for k in old if k not in new)
        if removed:
            patch["$del"] = removed
            patch_sizes["$del"] = _DEL_KEY + 1 + _size(removed)
        for key, value in new.items():
            key_size = _key_size(key) + 1
            if key not in old:
                value_size = _size(value)
                patch[key] = {"$set": value}
                patch_sizes[key] = key_size + value_size + _SET_EXTRA
            else:
                child = _child(old[key], value)
                if child is None:
                    value_size = _size(value)
                else:
                    patch[key], child_size, value_size = child
                    patch_sizes[key] = key_size + child_size
            new_sizes.append(key_size + value_size)
        return patch, _container_size(list(patch_sizes.values())), _container_size(new_sizes)
    if isinstance(old, list) and isinstance(new, list):
        if len(new) > len(old) and new[: len(old)] == old:
            tail = new[len(old) :]
            return {"$append": tail}, _size(tail) + _APPEND_EXTRA, _size(new)
        name = _list_key(old, new)
        if name is not None:
            before = {item[name]: item for item in old}
            changes, change_sizes, item_sizes = {}, {}, []
            for item in new:
                key = item[name]
                if key not in before:
                    item_size = _size(item)
                    changes[str(key)] = {"$set": item}
                    change_sizes[str(key)] = item_size + _SET_EXTRA
                else:
                    child = _child(before[key], item)
                    if child is None:
                        item_size = _size(item)
                    else:
                        changes[str(key)], change_sizes[str(key)], item_size = child
                item_sizes.append(item_size)
            order = [item[name] for item in new]
            changes_size = _container_size(
                [_size(k) + 1 + size for k, size in change_sizes.items()]
            )
            patch_size = _KEYED_EXTRA + _size(name) + _size(order) + changes_size
            return (
                {"$keyed": {"key": name, "order": order, "changes": changes}},
                patch_size,
                _container_size(item_sizes),
            )
    new_size = _size(new)
    return {"$set": new}, new_size + _SET_EXTRA, new_size


def apply(old: Any, patch: Any):
    """The state ``patch`` produces from ``old`` (``old`` is left alone)."""
    if patch is None:
        return copy.deepcopy(old)
    if not isinstance(patch, dict):
        raise DeltaError("a patch is an object")
    if "$set" in patch and len(patch) == 1:
        return copy.deepcopy(patch["$set"])
    # One private copy of ``old``; below it, only the patched path is rebuilt (shallow copies)
    # and only the payloads the patch inserts are copied.
    return _apply(copy.deepcopy(old), patch)


def _apply(old, patch):
    """``apply`` on a value the caller owns: ``old`` is not mutated, but the result may share
    its unpatched parts."""
    if patch is None:
        return old
    if not isinstance(patch, dict):
        raise DeltaError("a patch is an object")
    if "$set" in patch and len(patch) == 1:
        return copy.deepcopy(patch["$set"])
    if "$append" in patch and len(patch) == 1:
        if not isinstance(old, list) or not isinstance(patch["$append"], list):
            raise DeltaError("$append needs a list")
        return [*old, *copy.deepcopy(patch["$append"])]
    if "$keyed" in patch and len(patch) == 1:
        return _apply_keyed(old, patch["$keyed"])
    if not isinstance(old, dict):
        raise DeltaError("a key patch needs an object to patch")
    result = dict(old)
    for key in patch.get("$del", ()):
        result.pop(key, None)
    for key, child in patch.items():
        if key in _SENTINELS:
            continue
        if key not in result and not (isinstance(child, dict) and "$set" in child):
            raise DeltaError(f"patch touches missing key {key!r}")
        result[key] = _apply(result.get(key), child)
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
            result.append(_apply(before[key], change) if change is not None else before[key])
        elif change is not None and "$set" in change:
            result.append(copy.deepcopy(change["$set"]))
        else:
            raise DeltaError(f"patch refers to unknown item {key!r}")
    return result
