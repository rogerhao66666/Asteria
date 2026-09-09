class EditorAssetViews:
    """Runtime/editor resolved asset views keyed only by canonical asset IDs."""

    def __init__(self):
        self._sprite_sheets = {}
        self._clip_sets = {}

    def set_sprite_sheet(self, asset_id, sprite_sheet):
        self._sprite_sheets[str(asset_id)] = sprite_sheet

    def remove_sprite_sheet(self, asset_id):
        self._sprite_sheets.pop(str(asset_id), None)

    def sprite_sheet(self, asset_id):
        return self._sprite_sheets.get(str(asset_id))

    def set_clip_set(self, clip_set_id, clip_set):
        self._clip_sets[str(clip_set_id)] = clip_set

    def clip_set(self, clip_set_id):
        return self._clip_sets.get(str(clip_set_id))

    def clear(self):
        self._sprite_sheets.clear()
        self._clip_sets.clear()
