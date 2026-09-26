from dataclasses import replace
import pytest
from asteria.assets import *
def C(a,k): return CanonicalAsset(a,k,AssetSource("src"))
def clip(mode="screen",mat="mat/glow",size=(4096,2048)):
 return HighFidelityClip("c",size,("f0.png","f1.png"),(FrameTiming(7),FrameTiming(13)),
  (12.5,99.25),(VisualLayer("body",3,mode,.75,mat),),True)
def regs(): return install_builtin_capability_validators(CapabilityValidatorRegistry())
def test_large_image_explicit_error():
 q=ImageRequest("i","x.png",(8192,4096));x=regs().validate(q,BackendCapabilities(max_texture_size=(4096,4096)))
 assert not x.ok and x.issues[0].code=="backend.texture.too_large" and x.request.size==(8192,4096)
def test_supported_image_unchanged():
 q=ImageRequest("i","x.png",(2048,1024));x=regs().validate(q,BackendCapabilities(max_texture_size=(4096,4096)))
 assert x.ok and x.request is q and not x.fallback_applied
def test_clip_reports_blend_and_material_without_mutation():
 q=clip_request("a","custom",clip());caps=BackendCapabilities((8192,8192),frozenset({"alpha"}),frozenset({"mat/basic"}))
 x=regs().validate(q,caps);assert {i.code for i in x.issues}=={"backend.blend.unsupported","backend.material.unsupported"} and x.request is q
def test_arbitrary_blend_supported_when_declared():
 q=clip_request("a","x",clip("project.softlight",None));x=regs().validate(q,BackendCapabilities(blend_modes=frozenset({"project.softlight"})))
 assert x.ok
def test_audio_rate_error():
 q=AudioRequest("a","a.flac",1.,2,192000,None,());x=regs().validate(q,BackendCapabilities(audio_sample_rates=frozenset({48000,96000})))
 assert not x.ok and x.issues[0].required==192000
def test_audio_channels_error():
 q=AudioRequest("a","a.wav",None,8,48000,None,());assert regs().validate(q,BackendCapabilities(max_audio_channels=2)).issues[0].code=="backend.audio.channels_unsupported"
def test_material_shader():
 q=MaterialRequest("m","project/cinematic",(),(),());x=regs().validate(q,BackendCapabilities(shader_refs=frozenset({"basic"})));assert not x.ok
def test_no_caps_means_no_artificial_limits():
 q=clip_request("a","x",clip("custom-blend","custom-mat",(16384,8192)));assert regs().validate(q,BackendCapabilities()).ok
def test_fallback_requires_explicit_callback():
 q=ImageRequest("i","x.png",(8192,8192));caps=BackendCapabilities(max_texture_size=(4096,4096))
 assert not regs().validate(q,caps).fallback_applied
def test_explicit_fallback_can_transform():
 q=ImageRequest("i","x.png",(8192,8192));caps=BackendCapabilities(max_texture_size=(4096,4096))
 x=regs().validate(q,caps,fallback=lambda req,c,i:replace(req,size=(4096,4096)))
 assert x.ok and x.fallback_applied and x.request.size==(4096,4096)
def test_bad_fallback_still_fails():
 q=ImageRequest("i","x.png",(8192,8192));caps=BackendCapabilities(max_texture_size=(4096,4096))
 x=regs().validate(q,caps,fallback=lambda req,c,i:req);assert not x.ok and x.fallback_applied
def test_custom_request_validator():
 class Q: pass
 r=CapabilityValidatorRegistry();r.register(Q,lambda q,c:[CapabilityIssue("project.nope","nope")])
 assert not r.validate(Q(),BackendCapabilities()).ok
def test_checked_factory_blocks_allocation():
 calls=[];q=ImageRequest("i","x.png",(8192,8192));f=capability_checked_factory(regs(),BackendCapabilities(max_texture_size=(1024,1024)),lambda q,c:calls.append(q))
 with pytest.raises(CapabilityError):f(q,None)
 assert calls==[]
def test_checked_factory_passes_exact_request():
 calls=[];q=ImageRequest("i","x.png",(512,256));f=capability_checked_factory(regs(),BackendCapabilities(max_texture_size=(1024,1024)),lambda q,c:(calls.append(q) or "h"))
 assert f(q,None)=="h" and calls==[q]
def test_vfx_clip_validation():
 v=VFXRequest("fx","v",clip_request("fx","v",clip()),"socket",(0.,0.),"tip",(1.,1.),0.,())
 x=regs().validate(v,BackendCapabilities(blend_modes=frozenset({"alpha"})));assert x.issues[0].code=="backend.blend.unsupported"
def test_10000_validation():
 r=regs();caps=BackendCapabilities(max_texture_size=(4096,4096))
 for i in range(10000): assert r.validate(ImageRequest(str(i),"x",(1024,1024)),caps).ok
