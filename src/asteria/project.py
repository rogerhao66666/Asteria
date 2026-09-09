from pathlib import Path
import json
from asteria.core.ids import new_id,validate_id
from asteria.assets import AssetRegistry,serialize_asset_registry,deserialize_asset_registry
from asteria.core.serialization import serialize_scene,deserialize_scene

class Project:
    SCHEMA="asteria.project"
    VERSION=2

    def __init__(self,name,*,project_id=None,startup_scene_id=None,assets=None):
        self.id=validate_id(project_id) if project_id else new_id()
        self.name=str(name)
        self.startup_scene_id=startup_scene_id
        self.assets=assets or AssetRegistry()
        self._scenes={}

    def add_scene(self,scene):
        if scene.id in self._scenes:
            raise ValueError("duplicate scene id")
        self._scenes[scene.id]=scene
        if self.startup_scene_id is None:
            self.startup_scene_id=scene.id
        return scene

    def scenes(self):
        return tuple(self._scenes.values())

    def scene(self,scene_id):
        return self._scenes.get(scene_id)

    def scene_index(self,scene):
        if scene.id not in self._scenes:
            raise ValueError("Scene does not belong to project")
        return list(self._scenes).index(scene.id)

    def move_scene(self,scene,new_index):
        if scene.id not in self._scenes:
            raise ValueError("Scene does not belong to project")
        items=list(self._scenes.items())
        count=len(items)
        if count<=1:
            return 0
        old=self.scene_index(scene)
        new_index=max(0,min(int(new_index),count-1))
        if old==new_index:
            return old
        item=items.pop(old)
        items.insert(new_index,item)
        self._scenes=dict(items)
        return old

    def detach_scene(self,scene):
        if scene.id not in self._scenes:
            raise ValueError("Scene does not belong to project")
        if len(self._scenes)<=1:
            raise ValueError("Project must keep at least one scene")
        idx=self.scene_index(scene)
        del self._scenes[scene.id]
        if self.startup_scene_id==scene.id:
            self.startup_scene_id=next(iter(self._scenes))
        return idx

    def validate(self):
        if not self._scenes:
            raise ValueError("project requires scene")
        if self.startup_scene_id not in self._scenes:
            raise ValueError("invalid startup scene")
        self.assets.validate()

    def to_data(self):
        self.validate()
        return {
            "schema":self.SCHEMA,"version":self.VERSION,"id":self.id,"name":self.name,
            "startup_scene_id":self.startup_scene_id,
            "assets":serialize_asset_registry(self.assets),
            "scenes":[serialize_scene(s) for s in self.scenes()]
        }

    @classmethod
    def from_data(cls,data,registry):
        expected={"schema","version","id","name","startup_scene_id","assets","scenes"}
        if set(data)!=expected:
            raise ValueError("invalid project record")
        if data["schema"]!=cls.SCHEMA or data["version"]!=cls.VERSION:
            raise ValueError("unsupported project")
        p=cls(data["name"],project_id=data["id"],startup_scene_id=data["startup_scene_id"],
              assets=deserialize_asset_registry(data["assets"]))
        for sd in data["scenes"]:
            p.add_scene(deserialize_scene(sd,registry))
        p.validate()
        return p

    def save_json(self,path):
        Path(path).write_text(json.dumps(self.to_data(),indent=2,sort_keys=True)+"\n",encoding="utf-8")

    @classmethod
    def load_json(cls,path,registry):
        return cls.from_data(json.loads(Path(path).read_text(encoding="utf-8")),registry)
