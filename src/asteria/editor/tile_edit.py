from __future__ import annotations
from dataclasses import dataclass
from math import floor
from asteria.graphics import EMPTY_TILE,TileChunk,TileLayer
from .commands import CommandTransaction

class TileEditError(ValueError):
    pass

def world_to_tile(tilemap,world_x,world_y,origin_x=0.0,origin_y=0.0):
    return (
        floor((float(world_x)-origin_x)/tilemap.tile_width),
        floor((float(world_y)-origin_y)/tilemap.tile_height),
    )

def _chunk_address(tilemap,tile_x,tile_y):
    cx=floor(tile_x/tilemap.chunk_width)
    cy=floor(tile_y/tilemap.chunk_height)
    lx=tile_x-cx*tilemap.chunk_width
    ly=tile_y-cy*tilemap.chunk_height
    return cx,cy,lx,ly

def tile_at(tilemap,layer,tile_x,tile_y):
    cx,cy,lx,ly=_chunk_address(tilemap,tile_x,tile_y)
    chunk=layer.chunks.get((cx,cy))
    return EMPTY_TILE if chunk is None else chunk.get(lx,ly)

def _chunk_is_empty(chunk):
    return all(v==EMPTY_TILE for v in chunk.tiles)

@dataclass(slots=True)
class SetTileCommand:
    tilemap:object
    layer:object
    tile_x:int
    tile_y:int
    new_tile_id:int
    old_tile_id:int|None=None

    @property
    def label(self):
        return "Erase Tile" if self.new_tile_id==EMPTY_TILE else "Paint Tile"

    def _set(self,value):
        cx,cy,lx,ly=_chunk_address(self.tilemap,self.tile_x,self.tile_y)
        key=(cx,cy)
        chunk=self.layer.chunks.get(key)
        if value==EMPTY_TILE and chunk is None:
            return
        if chunk is None:
            chunk=TileChunk.empty(cx,cy,self.tilemap.chunk_width,self.tilemap.chunk_height)
            self.layer.chunks[key]=chunk
        chunk.set(lx,ly,value)
        if value==EMPTY_TILE and _chunk_is_empty(chunk):
            del self.layer.chunks[key]

    def redo(self):
        if self.layer not in self.tilemap.layers:
            raise TileEditError("Layer no longer belongs to TileMap")
        if not isinstance(self.new_tile_id,int) or self.new_tile_id<EMPTY_TILE:
            raise TileEditError("Invalid tile id")
        if self.old_tile_id is None:
            self.old_tile_id=tile_at(self.tilemap,self.layer,self.tile_x,self.tile_y)
        self._set(self.new_tile_id)

    def undo(self):
        if self.old_tile_id is None:
            raise RuntimeError("Command was never executed")
        self._set(self.old_tile_id)

@dataclass(slots=True)
class AddTileLayerCommand:
    tilemap:object
    layer:TileLayer
    index:int|None=None

    @property
    def label(self): return f"Add Tile Layer {self.layer.name}"

    def redo(self):
        if self.layer in self.tilemap.layers:
            raise TileEditError("Layer already attached")
        if any(x.name==self.layer.name for x in self.tilemap.layers):
            raise TileEditError("Duplicate layer name")
        idx=len(self.tilemap.layers) if self.index is None else max(0,min(self.index,len(self.tilemap.layers)))
        self.tilemap.layers.insert(idx,self.layer)

    def undo(self):
        self.tilemap.layers.remove(self.layer)

@dataclass(slots=True)
class RemoveTileLayerCommand:
    tilemap:object
    layer:object
    old_index:int|None=None

    @property
    def label(self): return f"Remove Tile Layer {self.layer.name}"

    def redo(self):
        if len(self.tilemap.layers)<=1:
            raise TileEditError("TileMap must keep at least one layer")
        if self.layer not in self.tilemap.layers:
            raise TileEditError("Layer does not belong to TileMap")
        if self.old_index is None:
            self.old_index=self.tilemap.layers.index(self.layer)
        self.tilemap.layers.remove(self.layer)

    def undo(self):
        idx=max(0,min(self.old_index,len(self.tilemap.layers)))
        self.tilemap.layers.insert(idx,self.layer)

def build_paint_command(tilemap,layer,cells,tile_id):
    if tile_id==EMPTY_TILE:
        label="Erase Tiles"
    else:
        label="Paint Tiles"
    tx=CommandTransaction(label)
    seen=set()
    for tile_x,tile_y in cells:
        key=(int(tile_x),int(tile_y))
        if key in seen:
            continue
        seen.add(key)
        old=tile_at(tilemap,layer,*key)
        if old==tile_id:
            continue
        tx.add(SetTileCommand(tilemap,layer,key[0],key[1],int(tile_id),old))
    if not tx.commands:
        raise TileEditError("No tile changes")
    return tx

def line_cells(x0,y0,x1,y1):
    """Integer Bresenham cells for gap-free mouse painting."""
    x0=int(x0);y0=int(y0);x1=int(x1);y1=int(y1)
    cells=[]
    dx=abs(x1-x0); sx=1 if x0<x1 else -1
    dy=-abs(y1-y0); sy=1 if y0<y1 else -1
    err=dx+dy
    while True:
        cells.append((x0,y0))
        if x0==x1 and y0==y1: break
        e2=2*err
        if e2>=dy: err+=dy;x0+=sx
        if e2<=dx: err+=dx;y0+=sy
    return tuple(cells)


def rectangle_cells(x0,y0,x1,y1):
    left,right=sorted((int(x0),int(x1)))
    top,bottom=sorted((int(y0),int(y1)))
    return tuple((x,y) for y in range(top,bottom+1) for x in range(left,right+1))

def occupied_bounds(tilemap,layer):
    found=[]
    for chunk in layer.chunks.values():
        for ly in range(chunk.height):
            for lx in range(chunk.width):
                if chunk.get(lx,ly)!=EMPTY_TILE:
                    found.append((
                        chunk.chunk_x*tilemap.chunk_width+lx,
                        chunk.chunk_y*tilemap.chunk_height+ly
                    ))
    if not found:
        return None
    xs=[x for x,_ in found];ys=[y for _,y in found]
    return min(xs),min(ys),max(xs),max(ys)

def flood_fill_cells(tilemap,layer,start_x,start_y,*,bounds=None,max_cells=10000):
    """Finite flood fill over a sparse TileMap.

    The default editable region is the active layer's occupied bounds.
    This intentionally rejects an empty, unbounded sparse world.
    """
    if bounds is None:
        bounds=occupied_bounds(tilemap,layer)
    if bounds is None:
        raise TileEditError("Fill requires existing map bounds or explicit bounds")
    left,top,right,bottom=map(int,bounds)
    sx,sy=int(start_x),int(start_y)
    if not (left<=sx<=right and top<=sy<=bottom):
        raise TileEditError("Fill start is outside editable bounds")
    target=tile_at(tilemap,layer,sx,sy)
    stack=[(sx,sy)]
    seen=set()
    result=[]
    while stack:
        x,y=stack.pop()
        if (x,y) in seen:
            continue
        seen.add((x,y))
        if not (left<=x<=right and top<=y<=bottom):
            continue
        if tile_at(tilemap,layer,x,y)!=target:
            continue
        result.append((x,y))
        if len(result)>max_cells:
            raise TileEditError("Fill exceeds safety limit")
        stack.extend(((x+1,y),(x-1,y),(x,y+1),(x,y-1)))
    return tuple(result)

@dataclass(slots=True)
class SetTileLayerPropertyCommand:
    layer:object
    attribute:str
    new_value:object
    old_value:object=None
    _captured:bool=False

    @property
    def label(self): return f"Set Layer {self.attribute}"

    def redo(self):
        if self.attribute not in {"name","visible","opacity","collision_enabled","order"}:
            raise TileEditError("Unsupported layer property")
        if not self._captured:
            self.old_value=getattr(self.layer,self.attribute)
            self._captured=True
        value=self.new_value
        if self.attribute=="opacity":
            value=float(value)
            if not 0.0<=value<=1.0:
                raise TileEditError("Opacity must be 0..1")
        if self.attribute=="name" and not str(value).strip():
            raise TileEditError("Layer name required")
        setattr(self.layer,self.attribute,value)

    def undo(self):
        if not self._captured:
            raise RuntimeError("Command was never executed")
        setattr(self.layer,self.attribute,self.old_value)

@dataclass(slots=True)
class ReorderTileLayerCommand:
    tilemap:object
    layer:object
    new_index:int
    old_index:int|None=None

    @property
    def label(self): return f"Reorder Tile Layer {self.layer.name}"

    def _normalize_order(self):
        for i,item in enumerate(self.tilemap.layers):
            item.order=i

    def redo(self):
        if self.layer not in self.tilemap.layers:
            raise TileEditError("Layer does not belong to TileMap")
        if self.old_index is None:
            self.old_index=self.tilemap.layers.index(self.layer)
        self.tilemap.layers.remove(self.layer)
        idx=max(0,min(int(self.new_index),len(self.tilemap.layers)))
        self.tilemap.layers.insert(idx,self.layer)
        self._normalize_order()

    def undo(self):
        if self.layer in self.tilemap.layers:
            self.tilemap.layers.remove(self.layer)
        idx=max(0,min(int(self.old_index),len(self.tilemap.layers)))
        self.tilemap.layers.insert(idx,self.layer)
        self._normalize_order()
