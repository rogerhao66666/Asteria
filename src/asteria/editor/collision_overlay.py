from dataclasses import dataclass
from asteria.graphics import EMPTY_TILE

@dataclass(frozen=True,slots=True)
class CollisionCell:
    tile_x:int
    tile_y:int
    screen_x:float
    screen_y:float
    width:float
    height:float

def build_collision_cells(tilemap,camera,*,origin_x=0.0,origin_y=0.0):
    cells=[]
    for layer in tilemap.ordered_layers():
        if not layer.collision_enabled:
            continue
        for chunk in layer.chunks.values():
            for ly in range(chunk.height):
                for lx in range(chunk.width):
                    if chunk.get(lx,ly)==EMPTY_TILE:
                        continue
                    tx=chunk.chunk_x*tilemap.chunk_width+lx
                    ty=chunk.chunk_y*tilemap.chunk_height+ly
                    sx,sy=camera.world_to_screen(
                        origin_x+tx*tilemap.tile_width,
                        origin_y+ty*tilemap.tile_height
                    )
                    cells.append(CollisionCell(
                        tx,ty,sx,sy,
                        tilemap.tile_width*camera.zoom,
                        tilemap.tile_height*camera.zoom
                    ))
    return tuple(cells)
