class TextureRenderer:
    def __init__(self, backend, cache, source_paths):
        self.backend = backend
        self.cache = cache
        self.source_paths = dict(source_paths)

    def render(self, draw_commands):
        for draw in draw_commands:
            try:
                source = self.source_paths[draw.texture_asset_id]
            except KeyError as exc:
                raise KeyError(
                    f"missing source path for texture {draw.texture_asset_id}"
                ) from exc
            resource = self.cache.get(draw.texture_asset_id, source)
            self.backend.draw_texture(resource, draw)
