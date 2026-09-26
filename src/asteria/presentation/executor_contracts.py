"""Generic material/shader, camera and audio executor contracts."""
from dataclasses import dataclass
from typing import Any,Protocol

@dataclass(frozen=True,slots=True)
class ShaderBinding:
 shader_id:str
 parameters:tuple[tuple[str,Any],...]=()
 textures:tuple[tuple[str,str],...]=()

class ShaderBackend(Protocol):
 def bind(self,binding:ShaderBinding)->None:...
 def unbind(self)->None:...

@dataclass(frozen=True,slots=True)
class CameraCommand:
 operation:str
 parameters:tuple[tuple[str,Any],...]=()
 duration_ms:float=0.
 channel:str="main"
 def __post_init__(self):
  if self.duration_ms<0:raise ValueError("duration")

class CameraBackend(Protocol):
 def execute_camera(self,command:CameraCommand)->None:...

@dataclass(frozen=True,slots=True)
class AudioCommand:
 operation:str
 asset_id:str|None=None
 bus:str="master"
 volume:float=1.
 pitch:float=1.
 pan:float=0.
 parameters:tuple[tuple[str,Any],...]=()
 def __post_init__(self):
  if self.volume<0:raise ValueError("volume")
  if not -1<=self.pan<=1:raise ValueError("pan")

class AudioBackend(Protocol):
 def execute_audio(self,command:AudioCommand)->None:...

class PresentationExecutorAdapter:
 """Maps generic Presentation events to replaceable project/backend executors."""
 def __init__(self,camera:CameraBackend|None=None,audio:AudioBackend|None=None,custom=None):
  self.camera,self.audio,self.custom=camera,audio,custom or {}
 def execute(self,track:str,action:str,payload:dict):
  if track=="camera":
   if self.camera:self.camera.execute_camera(CameraCommand(action,tuple(payload.items()),float(payload.get("duration_ms",0))))
   return
  if track=="audio":
   if self.audio:self.audio.execute_audio(AudioCommand(action,payload.get("asset_id"),payload.get("bus","master"),
      float(payload.get("volume",1)),float(payload.get("pitch",1)),float(payload.get("pan",0)),
      tuple((k,v) for k,v in payload.items() if k not in {"asset_id","bus","volume","pitch","pan"})))
   return
  fn=self.custom.get(track)
  if fn:fn(action,payload)

class RecordingCamera:
 def __init__(self):self.commands=[]
 def execute_camera(self,c):self.commands.append(c)
class RecordingAudio:
 def __init__(self):self.commands=[]
 def execute_audio(self,c):self.commands.append(c)
class RecordingShader:
 def __init__(self):self.bindings=[];self.unbinds=0
 def bind(self,b):self.bindings.append(b)
 def unbind(self):self.unbinds+=1
