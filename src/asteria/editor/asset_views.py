class EditorAssetViews:
    """Resolved canonical asset resources keyed by stable AssetRecord IDs.

    These are in-memory views of project assets, not a second persistent editor model.
    """

    def __init__(self):
        self._sprite_sheets = {}
        self._tilesets = {}
        self._tilemaps = {}
        self._clip_sets = {}

    def set_sprite_sheet(self, asset_id, sprite_sheet):
        self._sprite_sheets[str(asset_id)] = sprite_sheet

    def remove_sprite_sheet(self, asset_id):
        self._sprite_sheets.pop(str(asset_id), None)

    def sprite_sheet(self, asset_id):
        return self._sprite_sheets.get(str(asset_id))

    def set_tileset(self, asset_id, tileset):
        self._tilesets[str(asset_id)] = tileset

    def tileset(self, asset_id):
        return self._tilesets.get(str(asset_id))

    def set_tilemap(self, asset_id, tilemap):
        self._tilemaps[str(asset_id)] = tilemap

    def tilemap(self, asset_id):
        return self._tilemaps.get(str(asset_id))

    def tilemaps(self):
        return tuple(self._tilemaps.items())

    def set_clip_set(self, clip_set_id, clip_set):
        self._clip_sets[str(clip_set_id)] = clip_set

    def clip_set(self, clip_set_id):
        return self._clip_sets.get(str(clip_set_id))

    def sprite_sheet_ids(self):
        return tuple(sorted(self._sprite_sheets))

    def clip_set_ids(self):
        return tuple(sorted(self._clip_sets))

    def clear(self):
        self._sprite_sheets.clear()
        self._tilesets.clear()
        self._tilemaps.clear()
        self._clip_sets.clear()
