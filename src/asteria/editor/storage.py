import json
import os
import tempfile
from pathlib import Path

from asteria.graphics.serialization import tilemap_to_data
from asteria.project import Project


class EditorStorageError(RuntimeError):
    pass


def save_document(document, path=None):
    if document.project is None:
        raise EditorStorageError("No project to save")
    target = Path(path) if path is not None else document.file_path
    if target is None:
        raise EditorStorageError("Save path is required")
    target = target.expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(document.project.to_data(), indent=2, sort_keys=True) + "\n"

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, target)
    except Exception as exc:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise EditorStorageError(str(exc)) from exc

    # Persist mutable canonical TileMap sidecars resolved by the editor.
    for asset_id, tilemap in document.asset_views.tilemaps():
        record = document.project.assets.get(asset_id)
        if record is None or record.kind != "tilemap":
            continue
        sidecar = target.parent / record.source_path
        sidecar.parent.mkdir(parents=True, exist_ok=True)
        resource_payload = (
            json.dumps(tilemap_to_data(tilemap), indent=2, sort_keys=True) + "\n"
        )
        rfd, rtmp = tempfile.mkstemp(
            prefix=f".{sidecar.name}.", suffix=".tmp", dir=sidecar.parent
        )
        try:
            with os.fdopen(rfd, "w", encoding="utf-8") as rf:
                rf.write(resource_payload)
                rf.flush()
                os.fsync(rf.fileno())
            os.replace(rtmp, sidecar)
        except Exception as exc:
            try:
                os.unlink(rtmp)
            except FileNotFoundError:
                pass
            raise EditorStorageError(str(exc)) from exc

    document.file_path = target
    document.mark_saved()
    return target


def load_document(document, path):
    source = Path(path).expanduser().resolve()
    try:
        project = Project.load_json(source, document.component_registry)
    except Exception as exc:
        raise EditorStorageError(str(exc)) from exc
    document.set_project(project, file_path=source)
    return project
