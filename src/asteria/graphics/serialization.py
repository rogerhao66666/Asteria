from .tilemap import TileChunk, TileLayer, TileMap


def tilemap_to_data(tilemap):
    tilemap.validate()
    return {
        "schema": "asteria.tilemap",
        "version": 1,
        "tileset": {
            "asset_id": tilemap.tileset.asset_id,
            "expected_kind": tilemap.tileset.expected_kind,
        },
        "tile_width": tilemap.tile_width,
        "tile_height": tilemap.tile_height,
        "chunk_width": tilemap.chunk_width,
        "chunk_height": tilemap.chunk_height,
        "layers": [
            {
                "name": layer.name,
                "order": layer.order,
                "visible": layer.visible,
                "opacity": layer.opacity,
                "collision_enabled": layer.collision_enabled,
                "chunks": [
                    {
                        "chunk_x": c.chunk_x,
                        "chunk_y": c.chunk_y,
                        "width": c.width,
                        "height": c.height,
                        "tiles": list(c.tiles),
                    }
                    for _, c in sorted(layer.chunks.items())
                ],
            }
            for layer in tilemap.ordered_layers()
        ],
    }


def tilemap_from_data(data):
    from asteria.assets.types import AssetRef
    if data["schema"] != "asteria.tilemap" or data["version"] != 1:
        raise ValueError("unsupported tilemap")
    layers = []
    for ld in data["layers"]:
        chunks = {}
        for cd in ld["chunks"]:
            c = TileChunk(
                cd["chunk_x"],
                cd["chunk_y"],
                cd["width"],
                cd["height"],
                list(cd["tiles"]),
            )
            chunks[(c.chunk_x, c.chunk_y)] = c
        layers.append(
            TileLayer(
                ld["name"],
                ld["order"],
                ld["visible"],
                ld["opacity"],
                ld["collision_enabled"],
                chunks,
            )
        )
    tm = TileMap(
        AssetRef(**data["tileset"]),
        data["tile_width"],
        data["tile_height"],
        data["chunk_width"],
        data["chunk_height"],
        layers,
    )
    tm.validate()
    return tm
