from math import floor
from asteria.graphics import EMPTY_TILE

class TileMapQuery:
    def __init__(self,tilemap):
        self.tilemap=tilemap

    def world_to_tile(self,x,y):
        return floor(x/self.tilemap.tile_width), floor(y/self.tilemap.tile_height)

    def tile_at(self,layer,tile_x,tile_y):
        cw,ch=self.tilemap.chunk_width,self.tilemap.chunk_height
        cx=floor(tile_x/cw); cy=floor(tile_y/ch)
        chunk=layer.chunks.get((cx,cy))
        if chunk is None:
            return EMPTY_TILE
        lx=tile_x-cx*cw; ly=tile_y-cy*ch
        return chunk.get(lx,ly)

    def collides_world_point(self,x,y):
        tx,ty=self.world_to_tile(x,y)
        for layer in self.tilemap.ordered_layers():
            if layer.collision_enabled and self.tile_at(layer,tx,ty)!=EMPTY_TILE:
                return True
        return False
