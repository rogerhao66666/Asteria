from asteria.assets import AssetRef
from asteria.graphics import TileMap,TileLayer,EMPTY_TILE
from asteria.editor.model import EditorDocument
from asteria.editor.tile_edit import (
    tile_at,build_paint_command,world_to_tile,line_cells,
    AddTileLayerCommand,RemoveTileLayerCommand,TileEditError
)

A="123e4567-e89b-12d3-a456-426614174002"

def make():
    layer=TileLayer("Ground")
    tm=TileMap(AssetRef(A,"tileset"),16,16,4,4,[layer])
    return tm,layer

def test_paint_undo_redo_and_sparse_cleanup():
    tm,layer=make();doc=EditorDocument()
    doc.execute(build_paint_command(tm,layer,[(0,0),(1,0),(1,0)],3))
    assert tile_at(tm,layer,0,0)==3
    assert tile_at(tm,layer,1,0)==3
    assert len(layer.chunks)==1
    doc.undo()
    assert tile_at(tm,layer,0,0)==EMPTY_TILE
    assert layer.chunks=={}
    doc.redo()
    assert tile_at(tm,layer,1,0)==3

def test_erase_is_undoable_and_drops_empty_chunk():
    tm,layer=make();doc=EditorDocument()
    doc.execute(build_paint_command(tm,layer,[(-1,-1)],2))
    assert (-1,-1) in layer.chunks
    doc.execute(build_paint_command(tm,layer,[(-1,-1)],EMPTY_TILE))
    assert layer.chunks=={}
    doc.undo()
    assert tile_at(tm,layer,-1,-1)==2

def test_world_to_tile_supports_negative_coordinates():
    tm,_=make()
    assert world_to_tile(tm,0,0)==(0,0)
    assert world_to_tile(tm,15.9,15.9)==(0,0)
    assert world_to_tile(tm,-0.1,-0.1)==(-1,-1)

def test_bresenham_stroke_has_no_gaps():
    assert line_cells(0,0,3,0)==((0,0),(1,0),(2,0),(3,0))
    diag=line_cells(0,0,3,3)
    assert diag==((0,0),(1,1),(2,2),(3,3))

def test_layer_add_remove_are_undoable():
    tm,ground=make();doc=EditorDocument()
    props=TileLayer("Props",order=1)
    doc.execute(AddTileLayerCommand(tm,props))
    assert tm.layers==[ground,props]
    doc.undo();assert tm.layers==[ground]
    doc.redo()
    doc.execute(RemoveTileLayerCommand(tm,props))
    assert tm.layers==[ground]
    doc.undo();assert tm.layers==[ground,props]
