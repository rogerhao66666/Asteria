"""Typed codecs for Tileset, Monster and VFX, including HighFidelityClip."""
from .codecs import AssetCodec,AssetDocument
from .tileset import *
from .monster import *
from .vfx import *
from asteria.presentation.fidelity import HighFidelityClip,FrameTiming,VisualLayer

def _pairs(d):return tuple(sorted((d or {}).items()))
def _clip_dec(p):
 return HighFidelityClip(
  p["name"],tuple(p["frame_size"]),tuple(p["frames"]),
  tuple(FrameTiming(x["duration_ms"]) for x in p["timings"]),
  pivot=tuple(p.get("pivot",(0,0))),
  layers=tuple(VisualLayer(x["name"],x.get("z",0),x.get("blend_mode","normal"),x.get("opacity",1.0),x.get("material")) for x in p.get("layers",())),
  loop=p.get("loop",False))
def _clip_enc(c):
 return {"name":c.id,"frame_size":list(c.frame_size),"frames":list(c.frames),
 "timings":[{"duration_ms":x.duration_ms} for x in c.timings],"pivot":list(c.pivot),
 "layers":[{"name":x.asset_id,"z":x.z,"blend_mode":x.blend_mode,"opacity":x.opacity,"material":x.material} for x in c.layers],
 "loop":c.loop}

def tileset_codec():
 def dec(d):
  p=d.payload
  ts=[]
  for x in p.get("tiles",()):
   c=x.get("collision",{});col=TileCollision(c.get("kind","none"),tuple(tuple(q) for q in c.get("points",())))
   ts.append(TileDef(x["tile_id"],x.get("terrain"),col,_pairs(x.get("properties")),tuple(x.get("animation",())),x.get("frame_ms")))
  return TilesetAsset(d.manifest.canonical(),tuple(p["image_size"]),tuple(p["tile_size"]),p["columns"],p["rows"],tuple(ts),p.get("margin",0),p.get("spacing",0))
 def enc(a):
  return {"image_size":list(a.image_size),"tile_size":list(a.tile_size),"columns":a.columns,"rows":a.rows,"margin":a.margin,"spacing":a.spacing,
  "tiles":[{"tile_id":x.tile_id,"terrain":x.terrain,"collision":{"kind":x.collision.kind,"points":[list(q) for q in x.collision.points]},"properties":dict(x.properties),"animation":list(x.animation),"frame_ms":x.frame_ms} for x in a.tiles]}
 return AssetCodec("tileset",dec,enc)

def monster_codec():
 def dec(d):
  p=d.payload
  aa=tuple(MonsterAnimation(x["name"],_clip_dec(x["clip"]),tuple(x.get("directions",()))) for x in p.get("animations",()))
  return MonsterAsset(d.manifest.canonical(),aa,p.get("default_animation"),tuple(p["collision_bounds"]) if p.get("collision_bounds") else None,tuple(p["anchor"]) if p.get("anchor") else None)
 def enc(a):
  return {"animations":[{"name":x.name,"clip":_clip_enc(x.clip),"directions":list(x.directions)} for x in a.animations],"default_animation":a.default_animation,
  "collision_bounds":list(a.collision_bounds) if a.collision_bounds else None,"anchor":list(a.anchor) if a.anchor else None}
 return AssetCodec("monster",dec,enc)

def vfx_codec():
 def dec(d):
  p=d.payload;vs=[]
  for x in p["variants"]:
   an=x.get("anchor",{})
   vs.append(VFXVariant(x["name"],_clip_dec(x["clip"]),VFXAnchor(an.get("mode","local"),tuple(an.get("offset",(0,0))),an.get("bone_or_socket")),tuple(x.get("scale",(1,1))),x.get("rotation_deg",0),_pairs(x.get("properties"))))
  return VFXAsset(d.manifest.canonical(),tuple(vs),p["default_variant"],frozenset(p.get("presentation_tags",())),_pairs(p.get("properties")))
 def enc(a):
  return {"variants":[{"name":x.name,"clip":_clip_enc(x.clip),"anchor":{"mode":x.anchor.mode,"offset":list(x.anchor.offset),"bone_or_socket":x.anchor.bone_or_socket},"scale":list(x.scale),"rotation_deg":x.rotation_deg,"properties":dict(x.properties)} for x in a.variants],
  "default_variant":a.default_variant,"presentation_tags":sorted(a.presentation_tags),"properties":dict(a.properties)}
 return AssetCodec("vfx",dec,enc)

def install_complex_typed_codecs(r):
 for c in (tileset_codec(),monster_codec(),vfx_codec()):r.register(c,replace=True)
 return r
