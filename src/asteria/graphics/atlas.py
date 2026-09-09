from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TileAtlas:
    texture_asset_id: str
    tile_width: int
    tile_height: int
    columns: int
    rows: int

    def validate(self):
        if not self.texture_asset_id:
            raise ValueError("texture asset id required")
        if min(self.tile_width, self.tile_height, self.columns, self.rows) <= 0:
            raise ValueError("positive atlas dimensions required")

    @property
    def tile_count(self):
        return self.columns * self.rows

    def source_rect(self, tile_id):
        self.validate()
        if not 0 <= tile_id < self.tile_count:
            raise IndexError("tile id outside atlas")
        return (
            (tile_id % self.columns) * self.tile_width,
            (tile_id // self.columns) * self.tile_height,
            self.tile_width,
            self.tile_height,
        )
