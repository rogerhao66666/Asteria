"""Generic material, shader-parameter and lighting presentation runtime."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

@dataclass(frozen=True,slots=True)
class MaterialState:
    material_asset_id:str|None=None
    shader_asset_id:str|None=None
    parameters:Mapping[str,float]=field(default_factory=dict)

@dataclass(frozen=True,slots=True)
class LightState:
    id:str
    kind:str="point"
    x:float=0; y:float=0
    intensity:float=1
    radius:float=1
    rotation_deg:float=0
    parameters:Mapping[str,float]=field(default_factory=dict)

class MaterialRuntime:
    """Mutable runtime view driven by generic `material.*` properties."""
    def __init__(self,state:MaterialState=MaterialState()):
        self.material_asset_id=state.material_asset_id
        self.shader_asset_id=state.shader_asset_id
        self.parameters=dict(state.parameters)

    def apply_properties(self,values:Mapping[str,float])->None:
        self.parameters.update(values)

    def snapshot(self)->MaterialState:
        return MaterialState(self.material_asset_id,self.shader_asset_id,dict(self.parameters))

class LightingRuntime:
    """Generic light registry; light types are project/backend vocabulary."""
    def __init__(self,lights=()):
        self._lights={}
        for light in lights:self.add(light)

    def add(self,light:LightState)->None:
        if not light.id: raise ValueError("light id required")
        if light.id in self._lights: raise ValueError("duplicate light id")
        self._lights[light.id]=light

    def remove(self,light_id:str)->None:
        self._lights.pop(light_id,None)

    def apply(self,light_id:str,values:Mapping[str,float])->None:
        old=self._lights[light_id]
        core={"x":old.x,"y":old.y,"intensity":old.intensity,"radius":old.radius,
              "rotation_deg":old.rotation_deg}
        extra=dict(old.parameters)
        for k,v in values.items():
            if k in core: core[k]=v
            else: extra[k]=v
        self._lights[light_id]=LightState(old.id,old.kind,parameters=extra,**core)

    def snapshot(self)->tuple[LightState,...]:
        return tuple(self._lights[k] for k in sorted(self._lights))

    def clear(self)->None:self._lights.clear()

class MaterialShaderBackend(Protocol):
    def resolve_material(self,asset_id:str|None)->Any: ...
    def resolve_shader(self,asset_id:str|None)->Any: ...
    def bind_material(self,material:Any,shader:Any,parameters:Mapping[str,float])->None: ...

class MaterialBackendExecutor:
    """Resolves stable refs and forwards arbitrary uniforms/parameters unchanged."""
    def __init__(self,backend:MaterialShaderBackend):
        self.backend=backend; self._materials={}; self._shaders={}

    def execute(self,state:MaterialState)->None:
        m=state.material_asset_id; s=state.shader_asset_id
        if m not in self._materials:self._materials[m]=self.backend.resolve_material(m)
        if s not in self._shaders:self._shaders[s]=self.backend.resolve_shader(s)
        self.backend.bind_material(self._materials[m],self._shaders[s],dict(state.parameters))

    def invalidate(self,asset_id:str)->None:
        self._materials.pop(asset_id,None); self._shaders.pop(asset_id,None)

    def clear_resources(self)->None:
        self._materials.clear(); self._shaders.clear()
