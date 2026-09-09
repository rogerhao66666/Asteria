from pathlib import Path

from asteria.editor.model import EditorDocument
from asteria.editor.tile_edit import build_paint_command, tile_at
from asteria.reference_world import build_reference_world
from asteria.runtime import ReferenceRuntime, TileMapQuery


def test_phase4_reference_world_roundtrip_and_runtime_load():
    root = Path(__file__).resolve().parents[1]
    bundle = build_reference_world()
    runtime = ReferenceRuntime.load(bundle.project, bundle.scene, root)
    assert runtime.hero.name == "Hero"
    assert runtime.camera_follow is not None
    assert len(runtime.draw_commands(960, 540)) > 20


def test_phase4_tile_edit_stress_undo_redo():
    b = build_reference_world()
    layer = b.tilemap.layers[0]
    doc = EditorDocument()
    cells = [(x, y) for y in range(10) for x in range(20)]
    doc.execute(build_paint_command(b.tilemap, layer, cells, 3))
    assert sum(tile_at(b.tilemap, layer, x, y) == 3 for x, y in cells) == len(cells)
    doc.undo()
    assert sum(tile_at(b.tilemap, layer, x, y) == 3 for x, y in cells) == 0
    doc.redo()
    assert sum(tile_at(b.tilemap, layer, x, y) == 3 for x, y in cells) == len(cells)


def test_phase4_collision_bridge_contract():
    b = build_reference_world()
    q = TileMapQuery(b.tilemap)
    # River blocked, bridge passable, outer edge blocked.
    assert q.collides_world_point(33 * 16 + 8, 6 * 16 + 8)
    assert not q.collides_world_point(33 * 16 + 8, 12 * 16 + 8)
    assert q.collides_world_point(8, 8)
