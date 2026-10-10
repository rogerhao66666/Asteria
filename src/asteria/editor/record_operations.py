"""Record clipboard, multi-record delete and batch edit (EDT-03, EDT-13, EDT-14).

Qt-free operations over ``AuthoringCategoryAdapter``. Each operation goes
through the adapter's own canonical controller calls (create / edit / delete,
with their validation) and runs as one undo step via ``document.group``.
Pasted records get a fresh id; references inside them are kept as they are,
so a paste into another project shows up in validation rather than being
silently rewritten.
"""

from __future__ import annotations

import copy

_MISSING = object()
FORMAT_FIELDS = frozenset({"schema", "version"})  # record format markers, never edited by hand


class _Mixed:
    def __repr__(self):
        return "<mixed>"


MIXED = _Mixed()  # common_fields value when the selected records disagree


class RecordOperationError(RuntimeError):
    pass


def id_field(data, record_id):
    """Name of the field holding ``record_id`` in encoded ``data`` (``actor_id``, ``id``, ...)."""
    for name, value in data.items():
        if value == record_id and (name == "id" or name.endswith("_id")):
            return name
    return None


def unique_id(existing, base):
    existing = set(existing)
    if base not in existing:
        return base
    stem = f"{base}_copy"
    candidate, n = stem, 2
    while candidate in existing:
        candidate = f"{stem}{n}"
        n += 1
    return candidate


def copy_records(clipboard, adapter, ids):
    ids = [str(x) for x in ids]
    if not ids:
        raise RecordOperationError("nothing selected")
    records = tuple((key, adapter.encode(adapter.get(key))) for key in ids)
    return clipboard.copy_records(adapter.category_id, records)


def paste_records(document, clipboard, adapter):
    """Create every clipboard record in ``adapter``'s category under a fresh id; returns the new ids."""
    payload = clipboard.record_payload
    if payload is None:
        raise RecordOperationError("the clipboard has no records")
    if payload.category_id != adapter.category_id:
        raise RecordOperationError(f"the clipboard holds {payload.category_id} records, not {adapter.category_id}")
    if adapter.create is None:
        raise RecordOperationError(f"{adapter.label} records cannot be pasted")
    created = []
    with document.group(f"Paste {len(payload.records)} {adapter.label}"):
        for old_id, data in payload.records:
            new_id = unique_id(adapter.ids(), old_id)
            data = copy.deepcopy(data)
            field = id_field(data, old_id)
            if field is not None:
                data[field] = new_id
            adapter.create(new_id, adapter.decode(data))
            created.append(new_id)
    return created


def delete_records(document, adapter, ids):
    ids = [str(x) for x in ids]
    if not ids:
        raise RecordOperationError("nothing selected")
    with document.group(f"Delete {len(ids)} {adapter.label}"):
        for key in ids:
            adapter.delete(key)
    return ids


def cut_records(document, clipboard, adapter, ids):
    """Copy then delete as one undo step. If any delete is refused (still referenced) nothing is removed."""
    payload = copy_records(clipboard, adapter, ids)
    delete_records(document, adapter, ids)
    return payload


def _split(path):
    return [int(p) if p.isdigit() else p for p in str(path).split(".") if p != ""]


def get_path(data, path, default=_MISSING):
    value = data
    for part in _split(path):
        try:
            value = value[part]
        except (KeyError, IndexError, TypeError):
            if default is _MISSING:
                raise RecordOperationError(f"no field {path}") from None
            return default
    return value


def set_path(data, path, value):
    parts = _split(path)
    if not parts:
        raise RecordOperationError("field path is empty")
    target = get_path(data, ".".join(str(p) for p in parts[:-1])) if len(parts) > 1 else data
    last = parts[-1]
    if isinstance(target, dict):
        if last not in target:
            raise RecordOperationError(f"no field {path}")
    elif isinstance(target, list):
        if not isinstance(last, int) or not 0 <= last < len(target):
            raise RecordOperationError(f"no field {path}")
    else:
        raise RecordOperationError(f"{path} is not editable")
    target[last] = value


def _leaves(value, prefix=""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{prefix}{key}.")
    elif isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
        for index, item in enumerate(value):
            yield from _leaves(item, f"{prefix}{index}.")
    else:
        yield prefix[:-1], value


def common_fields(adapter, ids):
    """``{path: value}`` for fields every record has (``MIXED`` where they differ); ids and format markers excluded."""
    result = None
    for key in ids:
        data = adapter.encode(adapter.get(key))
        field = id_field(data, key)
        leaves = {p: v for p, v in _leaves(data) if p and p != field and p not in FORMAT_FIELDS}
        if result is None:
            result = dict(leaves)
            continue
        result = {p: (v if leaves[p] == v else MIXED) for p, v in result.items() if p in leaves}
    return dict(sorted((result or {}).items()))


def coerce_like(raw, example):
    """Turn editor text into the type of an existing field value."""
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if isinstance(example, bool):
        if text.lower() in ("true", "1", "yes", "on"):
            return True
        if text.lower() in ("false", "0", "no", "off"):
            return False
        raise RecordOperationError(f"{raw!r} is not true/false")
    if isinstance(example, int):
        try:
            return int(text)
        except ValueError:
            raise RecordOperationError(f"{raw!r} is not a whole number") from None
    if isinstance(example, float):
        try:
            return float(text)
        except ValueError:
            raise RecordOperationError(f"{raw!r} is not a number") from None
    if isinstance(example, list):
        return [x.strip() for x in text.split(",") if x.strip()]
    return raw


def batch_set(document, adapter, ids, path, value):
    """Set field ``path`` to ``value`` on every record in ``ids`` as one undo step.

    Each record is re-decoded and saved through the adapter's normal edit
    call, so its validation applies; one failure rolls the whole batch back.
    """
    ids = [str(x) for x in ids]
    if not ids:
        raise RecordOperationError("nothing selected")
    with document.group(f"Batch Edit {path} on {len(ids)} {adapter.label}"):
        for key in ids:
            data = copy.deepcopy(adapter.encode(adapter.get(key)))
            if path == id_field(data, key) or path in FORMAT_FIELDS:
                raise RecordOperationError("record ids and format fields cannot be batch edited")
            set_path(data, path, coerce_like(value, get_path(data, path)))
            try:
                adapter.edit(key, adapter.decode(data))
            except RecordOperationError:
                raise
            except Exception as exc:  # noqa: BLE001 - controller validation, reported with the record id
                raise RecordOperationError(f"{key}: {exc}") from exc
    return ids
