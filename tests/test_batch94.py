import pytest
from asteria.presentation.audio_runtime import *
from asteria.presentation.property_animation import split_channels
from asteria.presentation.channel_backend import PresentationChannelExecutor
def test_cues_fire_in_timeline_order_with_subframe_offset():
 a=AudioRuntime([AudioCue("b","hit",10.25),AudioCue("a","cast",5.5)])
 cmds=a.advance(0,11)
 assert [x.cue.id for x in cmds]==["a","b"]
 assert [x.offset_ms for x in cmds]==pytest.approx([5.5,.75])
def test_zero_time_cue_fires_once():
 a=AudioRuntime([AudioCue("a","start",0)])
 assert len(a.advance(0,0))==1 and a.advance(0,1)==()
def test_audio_channel_preserves_generic_properties():
 a=AudioRuntime();PresentationChannelExecutor(audio=a).execute(
  split_channels({"audio.volume":.7,"audio.project_filter":.25}))
 assert a.properties=={"volume":.7,"project_filter":.25}
def test_seek_reconstructs_fired_boundary():
 a=AudioRuntime([AudioCue("a","x",5),AudioCue("b","y",10)])
 a.seek(10)
 assert [c.cue.id for c in a.advance(10,11)]==[]
 a.seek(5)
 assert [c.cue.id for c in a.advance(5,10)]==["b"]
def test_invalid_clock_rejected():
 with pytest.raises(ValueError):AudioRuntime().advance(2,1)
class B:
 def __init__(self):self.calls=[]
 def resolve_audio(self,a):self.calls.append(("r",a));return "R:"+a
 def play(self,r,c,p):self.calls.append(("p",r,c.cue.id,p))
def test_backend_caches_stable_asset_refs_and_forwards_properties():
 b=B();e=AudioBackendExecutor(b);a=AudioRuntime([AudioCue("a","sfx",1),AudioCue("b","sfx",2)])
 cmds=a.advance(0,3);e.execute(cmds,{"volume":.5})
 assert b.calls.count(("r","sfx"))==1
 assert ("p","R:sfx","a",{"volume":.5}) in b.calls
def test_hot_reload_invalidation_resolves_again():
 b=B();e=AudioBackendExecutor(b);cmd=AudioCommand(AudioCue("a","x",0),0)
 e.execute([cmd]);e.invalidate("x");e.execute([cmd])
 assert b.calls.count(("r","x"))==2
def test_duplicate_cue_rejected():
 with pytest.raises(ValueError):AudioRuntime([AudioCue("x","a",0),AudioCue("x","b",1)])
