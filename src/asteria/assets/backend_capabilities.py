"""Backend capability validation. Never silently degrades high-fidelity requests."""
from dataclasses import dataclass, replace
from typing import Any, Callable

@dataclass(frozen=True, slots=True)
class CapabilityIssue:
 code:str; message:str; field:str=""; required:Any=None; supported:Any=None
 severity:str="error"

@dataclass(frozen=True, slots=True)
class BackendCapabilities:
 max_texture_size:tuple[int,int]|None=None
 blend_modes:frozenset[str]|None=None
 shader_refs:frozenset[str]|None=None
 max_audio_channels:int|None=None
 audio_sample_rates:frozenset[int]|None=None
 features:frozenset[str]=frozenset()

@dataclass(frozen=True, slots=True)
class CapabilityResult:
 request:Any
 issues:tuple[CapabilityIssue,...]=()
 fallback_applied:bool=False
 @property
 def ok(self): return not any(x.severity=="error" for x in self.issues)

Fallback = Callable[[Any,BackendCapabilities,tuple[CapabilityIssue,...]],Any]

class CapabilityValidatorRegistry:
 def __init__(self): self._validators={}
 def register(self,request_type,validator,*,replace_existing=False):
  if request_type in self._validators and not replace_existing: raise ValueError("validator exists")
  self._validators[request_type]=validator
 def validate(self,request,caps,*,fallback:Fallback|None=None):
  fn=None
  for cls in type(request).__mro__:
   if cls in self._validators: fn=self._validators[cls]; break
  if fn is None: return CapabilityResult(request)
  issues=tuple(fn(request,caps))
  if not issues: return CapabilityResult(request)
  if fallback is None: return CapabilityResult(request,issues,False)
  candidate=fallback(request,caps,issues)
  if candidate is None: return CapabilityResult(request,issues,False)
  remaining=tuple(fn(candidate,caps))
  return CapabilityResult(candidate,remaining,True)

def _texture(size,caps,field="size"):
 if caps.max_texture_size and (size[0]>caps.max_texture_size[0] or size[1]>caps.max_texture_size[1]):
  return [CapabilityIssue("backend.texture.too_large",
   f"texture {size} exceeds backend maximum {caps.max_texture_size}",field,size,caps.max_texture_size)]
 return []

def image_validator(q,caps):
 return _texture(q.size,caps)

def clip_validator(q,caps):
 out=_texture(q.frame_size,caps,"frame_size")
 if caps.blend_modes is not None:
  for layer in q.layers:
   mode=layer.blend_mode
   if mode not in caps.blend_modes:
    out.append(CapabilityIssue("backend.blend.unsupported",
     f"blend mode {mode!r} is unsupported","layers.blend_mode",mode,tuple(sorted(caps.blend_modes))))
 if caps.shader_refs is not None:
  for layer in q.layers:
   if layer.material and layer.material not in caps.shader_refs:
    out.append(CapabilityIssue("backend.material.unsupported",
     f"material {layer.material!r} is unsupported","layers.material",layer.material,tuple(sorted(caps.shader_refs))))
 return out

def vfx_validator(q,caps):
 return clip_validator(q.clip,caps)

def material_validator(q,caps):
 if caps.shader_refs is not None and q.shader_ref not in caps.shader_refs:
  return [CapabilityIssue("backend.shader.unsupported",
   f"shader {q.shader_ref!r} is unsupported","shader_ref",q.shader_ref,tuple(sorted(caps.shader_refs)))]
 return []

def audio_validator(q,caps):
 out=[]
 if caps.max_audio_channels is not None and q.channels is not None and q.channels>caps.max_audio_channels:
  out.append(CapabilityIssue("backend.audio.channels_unsupported","audio channel count unsupported",
   "channels",q.channels,caps.max_audio_channels))
 if caps.audio_sample_rates is not None and q.sample_rate is not None and q.sample_rate not in caps.audio_sample_rates:
  out.append(CapabilityIssue("backend.audio.sample_rate_unsupported","audio sample rate unsupported",
   "sample_rate",q.sample_rate,tuple(sorted(caps.audio_sample_rates))))
 return out

def install_builtin_capability_validators(r):
 from .runtime_adapters import ImageRequest,ClipRequest,VFXRequest,MaterialRequest,AudioRequest
 for t,fn in ((ImageRequest,image_validator),(ClipRequest,clip_validator),(VFXRequest,vfx_validator),
              (MaterialRequest,material_validator),(AudioRequest,audio_validator)):
  r.register(t,fn,replace_existing=True)
 return r

class CapabilityError(RuntimeError):
 def __init__(self,issues):
  self.issues=tuple(issues)
  super().__init__("; ".join(x.message for x in self.issues))

def capability_checked_factory(validators,caps,backend_factory,*,fallback=None):
 """Wrap a resource factory. Unsupported requests fail before backend allocation."""
 def create(request,context=None):
  result=validators.validate(request,caps,fallback=fallback)
  if not result.ok: raise CapabilityError(result.issues)
  return backend_factory(result.request,context)
 return create
