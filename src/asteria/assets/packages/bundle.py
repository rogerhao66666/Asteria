"""Package an asset and everything it depends on (manifests + image files) into a folder."""

from __future__ import annotations

import shutil
from pathlib import Path

IMAGE_KEYS = ("image", "image_uri", "source")


def _payload_files(data):
    """Relative file paths mentioned by an asset document's payload."""
    found = []

    def walk(value, key=""):
        if isinstance(value, dict):
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, key)
        elif isinstance(value, str) and key in IMAGE_KEYS and "." in Path(value).name:
            found.append(value)

    walk(data.get("payload", {}))
    return found


def asset_closure(documents, asset_id):
    """``documents``: ``{asset_id: (manifest_path, data)}``; returns the dependency closure in load
    order."""
    order, seen = [], set()

    def visit(key, stack=()):
        if key in seen:
            return
        if key in stack:
            raise ValueError(f"dependency cycle through {key}")
        if key not in documents:
            raise KeyError(f"missing dependency {key}")
        for dep in documents[key][1].get("dependencies", ()):
            visit(dep, stack + (key,))
        seen.add(key)
        order.append(key)

    visit(asset_id)
    return order


def package_assets(root, documents, asset_id, output):
    """Copy ``asset_id``'s closure (manifests, source and payload images) under ``output``; returns
    relative paths."""
    root, output = Path(root), Path(output)
    files = []
    for key in asset_closure(documents, asset_id):
        manifest_path, data = documents[key]
        relative = [
            Path(manifest_path).resolve().relative_to(root.resolve()).as_posix(),
            data["source"],
        ]
        relative += _payload_files(data)
        for item in dict.fromkeys(relative):
            source = root / item
            if not source.is_file():
                raise FileNotFoundError(f"{key}: {item}")
            target = output / item
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            files.append(item)
    return tuple(sorted(dict.fromkeys(files)))
