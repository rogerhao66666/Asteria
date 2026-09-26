
import json
from asteria.assets.usability_gate import StarterPackUsabilityGate
def add(r,aid,t,src,**kw):
 p=r/src;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b"x")
 (r/(aid.replace(".","_")+".asset.json")).write_text(json.dumps({"asset_id":aid,"source":src,"payload":{"asset_type":t,**kw}}))
def complete(r):
 for c in ["idle","walk","run","attack","hurt","death"]:add(r,"c."+c,"character_animation",c+".png",clip=c,frame_size=[64,64],grid=[4,4],frame_ms=[100]*4)
 for t in ["monster","vfx","tileset","prop","icon","portrait","background"]:add(r,t,t,t+".png")
def test_empty(tmp_path):
 assert not StarterPackUsabilityGate().validate(tmp_path,0,0,0).ok
def test_count(tmp_path):
 complete(tmp_path);n=len(list(tmp_path.glob("*.asset.json")));assert not StarterPackUsabilityGate().validate(tmp_path,n,n,n-1).ok
def test_missing_clips(tmp_path):
 complete(tmp_path)
 for p in list(tmp_path.glob("c_idle.asset.json"))+list(tmp_path.glob("c_run.asset.json")):p.unlink()
 n=len(list(tmp_path.glob("*.asset.json")));assert not StarterPackUsabilityGate().validate(tmp_path,n,n,n).ok
def test_pass(tmp_path):
 complete(tmp_path);n=len(list(tmp_path.glob("*.asset.json")));assert StarterPackUsabilityGate().validate(tmp_path,n,n,n).ok
