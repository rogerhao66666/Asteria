class AssetRegistry:
    def __init__(self):
        self._by_id={}
        self._by_path={}

    def add(self, record):
        record.validate()
        if record.id in self._by_id:
            raise ValueError("duplicate asset id")
        if record.source_path in self._by_path:
            raise ValueError("duplicate source path")
        self._by_id[record.id]=record
        self._by_path[record.source_path]=record.id
        return record

    def get(self, asset_id):
        return self._by_id.get(asset_id)

    def records(self):
        return tuple(self._by_id.values())

    def validate(self):
        for r in self._by_id.values():
            r.validate()
