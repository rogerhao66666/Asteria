import pytest
from asteria.presentation.render_integration import *
from asteria.presentation.actor_attachment import ActorAnimationPose,ActorAttachmentBinding
from asteria.presentation.attachments import Socket,SocketRig,Attachment,Transform2D
from asteria.presentation.attachment_runtime import AttachmentRuntime
class A:
 def presentation_pose(self):return ActorAnimationPose("idle",0)
def frame():
 rig=SocketRig();rig.add(Socket("hand",default=Transform2D(x=5,y=2,z_offset=1)))
 rt=AttachmentRuntime(rig);rt.attach(Attachment("held","sword","hand"))
 return ActorAttachmentBinding("hero",A(),rt).resolve()
def test_actor_and_attachment_packets():
 p=PresentationRenderComposer().actor_packets(frame(),"hero.sprite")
 assert [x.asset_id for x in p]==["hero.sprite","sword"]
def test_actor_transform_propagates():
 p=PresentationRenderComposer().actor_packets(frame(),"hero",RenderTransform(x=100,y=50))
 assert p[1].transform.x==105 and p[1].transform.y==52
def test_z_order():
 p=PresentationRenderComposer().actor_packets(frame(),"hero")
 assert p[0].z==0 and p[1].z==1
def test_continuous_modifier_not_sprite_frame_bound():
 c=PresentationRenderComposer(); vib=Vibration(amplitude_x=4,frequency_hz=10,duration_ms=500)
 a=c.actor_packets(frame(),"hero",modifier=vib.sample,render_time_ms=12.5)[0].transform.x
 b=c.actor_packets(frame(),"hero",modifier=vib.sample,render_time_ms=13.5)[0].transform.x
 assert a!=b
def test_vibration_decays_and_ends():
 v=Vibration(amplitude_x=5,frequency_hz=10,duration_ms=100,decay=1)
 assert v.sample(100)==RenderTransform()
def test_vibration_can_rotate():
 v=Vibration(rotation_amplitude_deg=2,frequency_hz=5,duration_ms=1000)
 assert v.sample(50).rotation_deg!=0
def test_invalid_vibration():
 with pytest.raises(ValueError):Vibration(duration_ms=0)
def test_hidden_attachment_filtered():
 rig=SocketRig();rig.add(Socket("x",default=Transform2D(visible=False)))
 rt=AttachmentRuntime(rig);rt.attach(Attachment("a","hidden","x"))
 f=ActorAttachmentBinding("x",A(),rt).resolve()
 assert [p.asset_id for p in PresentationRenderComposer().actor_packets(f,"actor")]==["actor"]
def test_opacity_composes():
 p=PresentationRenderComposer().actor_packets(frame(),"hero",RenderTransform(opacity=.5))
 assert p[1].transform.opacity==pytest.approx(.5)
def test_modifier_layers_over_base():
 c=PresentationRenderComposer()
 p=c.actor_packets(frame(),"hero",RenderTransform(x=10),lambda _:RenderTransform(x=3),1)
 assert p[0].transform.x==13 and p[1].transform.x==18
