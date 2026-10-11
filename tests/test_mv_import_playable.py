"""W-18: an RPG Maker MV project imports into canonical Asteria assets and plays as a native project.

Uses the local (git-ignored) MV reference: the parallax DLC sample project has real tile maps,
an NPC with dialogue and a player-touch door that transfers to the next map.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.mv_reference

REPO = Path(__file__).resolve().parents[1]
SAMPLE = "parallax_Resource_Pack/sample_project"


def _layout():
    from asteria.assets.local_reference import discover_mv_projects, resolve_rpg_maker_mv_root

    return next(l for l in discover_mv_projects(resolve_rpg_maker_mv_root(REPO)) if l.relative_path.endswith(SAMPLE))


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    from asteria.assets.rpg_maker_mv_project import RPGMakerMVProjectImporter

    out = tmp_path_factory.mktemp("mv_project")
    result = RPGMakerMVProjectImporter.import_project(_layout(), map_ids=(1, 2), output_root=out)
    result.project.save_json(out / "project.asteria.json")
    return out, result


def _field(root):
    from asteria.project_tools import load_project
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.tilemap_field import TileMapField

    project = load_project(root / "project.asteria.json")  # reloaded from disk: no in-memory MV data
    return TileMapField(GameSessionRuntime(project, project.game_start.instantiate(project)), root)


def _walk(field, action, seconds, dt=1 / 60):
    for _ in range(int(seconds / dt)):
        field.step({action: 1.0}, dt)


def _blocked(field, cx, cy):
    walk = next(layer for layer in field.tilemap.layers if layer.name == "Walkability")
    return field.query.tile_at(walk, cx, cy) != -1


def test_maps_become_canonical_assets_that_survive_save_and_reload(imported):
    root, result = imported
    from asteria.project_tools import load_project
    from asteria.runtime import TileMap2DComponent
    from asteria.runtime.tilemap_field import AssetResources

    project = load_project(root / "project.asteria.json")
    resources = AssetResources(project, root)
    assert len(project.scenes()) == 2
    for scene in project.scenes():
        binding = next(e.get(TileMap2DComponent) for e in scene.entities() if e.has(TileMap2DComponent))
        tilemap = resources.get(binding.tilemap_asset_id, "tilemap")  # resolves; no dangling mv.tileset.N id
        tileset = resources.get(tilemap.tileset.asset_id, "tileset")
        sheet = resources.get(tileset.sprite_sheet.asset_id, "sprite_sheet")
        tileset.validate(len(sheet.frames))
        resources.texture_path(sheet.texture.asset_id)
        names = [layer.name for layer in tilemap.layers]
        assert "Walkability" in names and names.index("Walkability") == len(names) - 1
        assert not any(hasattr(e, "rpg_maker_mv_map") for e in scene.entities())
    meta = result.source_metadata["maps"][1]
    assert meta["blocked_cells"] > 0 and project.game_start.player_entity_id


def test_the_reloaded_project_plays_without_loading_any_mv_code(imported, tmp_path):
    root, _ = imported
    script = f"""
import sys
from pathlib import Path
from asteria.project_tools import load_project
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.tilemap_field import TileMapField
root = Path({str(root)!r})
project = load_project(root / "project.asteria.json")
field = TileMapField(GameSessionRuntime(project, project.game_start.instantiate(project)), root)
for _ in range(30):
    field.step({{"move_up": 1.0}}, 1 / 60)
draws = field.draw_commands()
print("DRAWS", len(draws), len({{d.texture_asset_id for d in draws}}))
print("MV", sorted(m for m in sys.modules if "rpg_maker" in m))
"""
    out = subprocess.run([sys.executable, "-c", script], cwd=tmp_path, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-1500:]
    draws = int(out.stdout.split("DRAWS ")[1].split()[0])
    assert draws > 100 and "MV []" in out.stdout


def test_player_walks_collides_talks_and_transfers_through_the_door(imported):
    root, _ = imported
    from asteria.core import Transform

    field = _field(root)
    session = field.session
    start_scene = session.scene.id
    player = session.player.get(Transform)
    cx, cy = int(player.x // 48), int(player.y // 48)
    # collision: walk toward a blocked neighbour and stop before it
    _walk(field, "move_left", 2.0)  # along the row until the wall
    t = session.player.get(Transform)
    stop = int(t.x // 48)
    assert stop < cx and not _blocked(field, stop, cy) and _blocked(field, stop - 1, cy)
    _walk(field, "move_right", (cx - stop) * 48 / 180 + 0.05)  # back to the start column
    # talk: walk up to the NPC two cells above the door path and press interact
    while not session.pending_dialogue and session.player.get(Transform).y > 9 * 48 + 20:
        field.step({"move_up": 1.0}, 1 / 60)
    field.step({}, 1 / 60)
    field.step({"interact": 1.0}, 1 / 60)
    assert field.dialogue and "アウト" in field.dialogue
    field.step({}, 1 / 60)
    field.step({"interact": 1.0}, 1 / 60)  # acknowledge
    field.step({}, 1 / 60)
    assert session.pending_dialogue is None
    # the door (player touch) on the path above transfers to map 2 at (8, 23) facing up
    for _ in range(600):
        if session.scene.id != start_scene:
            break
        field.step({"move_up": 1.0}, 1 / 60)
    assert session.scene.id != start_scene and session.scene is field.session.scene
    t = session.player.get(Transform)
    assert (int(t.x // 48), int(t.y // 48)) == (8, 23) and session.facing == "up"
    assert field.tilemap is not None and field.draw_commands()  # the new map is bound and drawn
    assert not session.event_errors


def test_save_and_reload_keep_the_transferred_position(imported, tmp_path):
    root, _ = imported
    from asteria.core import Transform
    from asteria.project_tools import load_project
    from asteria.runtime.game_save import GameRuntimeSave
    from asteria.runtime.game_session import GameSessionRuntime
    from asteria.runtime.tilemap_field import TileMapField

    field = _field(root)
    for _ in range(900):
        if field.session.scene.id != field.session.project.startup_scene_id:
            break
        field.step({"move_up": 1.0, "interact": 0.0}, 1 / 60)
        if field.session.pending_dialogue:
            field.step({"interact": 1.0}, 1 / 60)
            field.step({}, 1 / 60)
    field.session.sync_world_state() if hasattr(field.session, "sync_world_state") else None
    field.session.save.save_json(tmp_path / "save.json")
    project = load_project(root / "project.asteria.json")
    save = GameRuntimeSave.load_json(tmp_path / "save.json", project)
    again = TileMapField(GameSessionRuntime(project, save), root)
    t = again.session.player.get(Transform)
    assert again.session.scene.id == field.session.scene.id
    assert (t.x, t.y) == tuple(field.session.save.player_position)


def test_preview_runs_the_imported_project_in_its_own_process(imported, tmp_path):
    pytest.importorskip("pygame")
    root, _ = imported
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    out = subprocess.run(
        [sys.executable, "-m", "asteria.runtime.preview", str(root / "project.asteria.json"), "--frames", "20"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert out.returncode == 0, out.stderr[-1500:]


def test_unconverted_mv_content_is_reported_not_dropped(imported):
    _, result = imported
    codes = {issue.code for issue in result.issues}
    assert "event.unsupported_commands" in codes  # e.g. Play SE, Common Event, Self Switch
    data = json.loads((imported[0] / "project.asteria.json").read_text())
    assert data["event_programs"]


def test_cli_and_editor_import_open_a_playable_project(tmp_path):
    from asteria.assets.rpg_maker_mv_project import import_mv_main

    source = _layout().root
    assert import_mv_main([str(source), str(tmp_path / "cli"), "--maps", "1", "2"]) == 0
    assert (tmp_path / "cli" / "project.asteria.json").is_file()
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.runtime.tilemap_field import can_play

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow(None)
    assert window.import_mv_action.text() == "Import RPG Maker MV Project…"
    path, result = window.import_mv_project(source, tmp_path / "editor")
    assert window.document.file_path == path and len(window.document.project.scenes()) == len(result.project.scenes())
    assert can_play(window.document.project, path.parent)
    window.close()
    app.processEvents()
