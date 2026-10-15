"""The project adapter loads the file selected by the editor, including copied projects."""

import json
from pathlib import Path

from asteria.multiplayer.persistence import SQLiteMultiplayerStore
from asteria.multiplayer.server import _load_adapter


def test_project_factory_uses_selected_file_outside_reference_demo(tmp_path):
    source = (
        Path(__file__).resolve().parents[1]
        / "reference_projects/diablo_multiplayer_demo/project.asteria.json"
    )
    data = json.loads(source.read_text())
    data["name"] = "My copied online game"
    chosen = tmp_path / "my-game.asteria.json"
    chosen.write_text(json.dumps(data))
    with SQLiteMultiplayerStore(tmp_path / "world.sqlite3") as store:
        adapter = _load_adapter(
            "asteria.multiplayer.project_demo:build_project_adapter",
            store=store,
            project_path=chosen,
        )
        assert adapter.project.name == "My copied online game"
        assert adapter.project_root == tmp_path
