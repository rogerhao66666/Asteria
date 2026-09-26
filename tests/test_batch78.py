import pytest
from asteria.presentation.actor_attachment import *
from asteria.presentation.attachments import Socket,SocketKey,SocketRig,Attachment,Transform2D
from asteria.presentation.attachment_runtime import AttachmentRuntime

class FakeAnimator:
 def __init__(self,pose): self.pose=pose
 def presentation_pose(self): return self.pose

def binding(pose):
 rig=SocketRig(); rig.add(Socket("hand",default=Transform2D(x=2),keys=(SocketKey(1,Transform2D(x=10,rotation_deg=20)),)))
 rt=AttachmentRuntime(rig);rt.attach(Attachment("held","asset.sword","hand"))
 return ActorAttachmentBinding("hero",FakeAnimator(pose),rt)

def test_existing_animator_pose_drives_socket_frame():
 b=binding(ActorAnimationPose("swing",1)); f=b.resolve(); assert f.attachments[0].transform.x==10

def test_subframe_passes_through():
 rig=SocketRig(); rig.add(Socket("x",keys=(SocketKey(0,Transform2D(x=0)),SocketKey(1,Transform2D(x=10)))))
 rt=AttachmentRuntime(rig);rt.attach(Attachment("a","asset","x"))
 b=ActorAttachmentBinding("a",FakeAnimator(ActorAnimationPose("c",0,.5)),rt)
 assert b.resolve().attachments[0].transform.x==pytest.approx(5)

def test_actor_identity_preserved():
 assert binding(ActorAnimationPose("idle",0)).resolve().actor_id=="hero"

def test_clip_is_descriptive_not_engine_semantics():
 assert binding(ActorAnimationPose("project.custom_clip",0)).resolve().pose.clip_id=="project.custom_clip"

def test_hidden_actor_suppresses_attachment_draws():
 assert binding(ActorAnimationPose("idle",0,visible=False)).resolve().attachments==()

def test_left_facing_mirrors_at_adapter_boundary():
 r=binding(ActorAnimationPose("idle",0,facing_x=-1)).resolve().attachments[0]
 assert r.transform.x==-2 and r.transform.flip_x

def test_left_facing_mirrors_rotation():
 r=binding(ActorAnimationPose("swing",1,facing_x=-1)).resolve().attachments[0]
 assert r.transform.rotation_deg==-20

def test_runtime_data_not_mutated_by_facing():
 b=binding(ActorAnimationPose("idle",0,facing_x=-1));b.resolve()
 assert b.runtime.resolve_all(0,0)[0].transform.x==2

def test_invalid_pose_validation():
 with pytest.raises(ValueError):ActorAnimationPose("x",-1)
 with pytest.raises(ValueError):ActorAnimationPose("x",0,2)
 with pytest.raises(ValueError):ActorAnimationPose("x",0,0,0)

def test_bad_animator_contract_rejected():
 class Bad:
  def presentation_pose(self): return "bad"
 rig=SocketRig()
 with pytest.raises(TypeError):ActorAttachmentBinding("a",Bad(),AttachmentRuntime(rig)).resolve()

def test_actor_id_required():
 with pytest.raises(ValueError):ActorAttachmentBinding("",FakeAnimator(ActorAnimationPose("x",0)),AttachmentRuntime(SocketRig()))
