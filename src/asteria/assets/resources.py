from dataclasses import dataclass

@dataclass(frozen=True,slots=True)
class TextureResource:
    asset_id:str
    width:int
    height:int
    backend_handle:object

class TextureResourceCache:
    def __init__(self, loader):
        self._loader=loader
        self._items={}

    def get(self,asset_id,source_path):
        if asset_id in self._items:
            return self._items[asset_id]
        resource=self._loader(asset_id,source_path)
        if resource.asset_id!=asset_id:
            raise ValueError("loader returned mismatched asset id")
        self._items[asset_id]=resource
        return resource

    def contains(self,asset_id):
        return asset_id in self._items

    def remove(self,asset_id):
        return self._items.pop(asset_id,None)

    def clear(self):
        self._items.clear()

    def __len__(self):
        return len(self._items)
