from dataclasses import dataclass
from typing import Any
@dataclass(frozen=True,slots=True)
class ImageRequest: asset_id:str;uri:str;size:tuple[int,int];region:tuple[int,int,int,int]|None=None;metadata:tuple=()
@dataclass(frozen=True,slots=True)
class AudioRequest: asset_id:str;uri:str;duration_ms:float|None;channels:int|None;sample_rate:int|None;loop_region_ms:tuple|None;properties:tuple=()
@dataclass(frozen=True,slots=True)
class FontRequest: asset_id:str;uri:str;family_hint:str|None;fallback_asset_ids:tuple[str,...];properties:tuple=()
@dataclass(frozen=True,slots=True)
class MaterialRequest: asset_id:str;shader_ref:str;parameters:tuple;texture_refs:tuple;properties:tuple=()
@dataclass(frozen=True,slots=True)
class ClipRequest: asset_id:str;clip_name:str;frame_size:tuple[int,int];frame_count:int;frame_durations_ms:tuple[float,...];pivot:tuple[float,float];loop:bool;layers:tuple
@dataclass(frozen=True,slots=True)
class VFXRequest: asset_id:str;variant:str;clip:ClipRequest;anchor_mode:str;anchor_offset:tuple[float,float];socket:str|None;scale:tuple[float,float];rotation_deg:float;properties:tuple=()
def icon_request(a,variant=None):
 v=next(x for x in a.variants if x.name==(variant or a.default_variant))
 if v.atlas:return ImageRequest(a.canonical.asset_id,v.atlas.image_uri,v.size,(v.atlas.x,v.atlas.y,v.atlas.width,v.atlas.height),v.metadata)
 return ImageRequest(a.canonical.asset_id,v.image_uri,v.size,None,v.metadata)
def portrait_request(a,variant=None):
 v=next(x for x in a.variants if x.name==(variant or a.default_variant));return ImageRequest(a.canonical.asset_id,v.image_uri,v.size,None,v.metadata)
def audio_request(a):return AudioRequest(a.canonical.asset_id,a.uri,a.duration_ms,a.channels,a.sample_rate,a.loop_region_ms,a.properties)
def font_request(a):return FontRequest(a.canonical.asset_id,a.uri,a.family_hint,tuple(a.fallback_refs),a.properties)
def material_request(a):return MaterialRequest(a.canonical.asset_id,a.shader_ref,a.parameters,a.texture_refs,a.properties)
def clip_request(aid,name,c):return ClipRequest(aid,name,c.frame_size,len(c.frames),tuple(x.duration_ms for x in c.timings),c.pivot,c.loop,c.layers)
def monster_clip_request(a,animation=None):
 n=animation or a.default_animation;x=next(x for x in a.animations if x.name==n);return clip_request(a.canonical.asset_id,n,x.clip)
def vfx_request(a,variant=None):
 n=variant or a.default_variant;v=next(x for x in a.variants if x.name==n);return VFXRequest(a.canonical.asset_id,n,clip_request(a.canonical.asset_id,n,v.clip),v.anchor.mode,v.anchor.offset,v.anchor.bone_or_socket,v.scale,v.rotation_deg,v.properties)
