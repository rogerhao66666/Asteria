import math
import pytest
from asteria.presentation.attachments import Attachment, GripTransform, Socket, SocketRig, Transform2D
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.actor_attachment import ActorAnimationPose, ActorAttachmentBinding
from asteria.presentation.actor_visual_layers import ActorVisualLayerTrack, FrameVisualLayer


def grip_world(t, g):
    dx=g.x*t.scale_x*(-1 if t.flip_x else 1)
    dy=g.y*t.scale_y*(-1 if t.flip_y else 1)
    a=math.radians(t.rotation_deg)
    return (t.x+dx*math.cos(a)-dy*math.sin(a), t.y+dx*math.sin(a)+dy*math.cos(a), t.rotation_deg + (-g.rotation_deg if t.flip_x else g.rotation_deg))

class Animator:
    def __init__(self,facing): self.facing=facing
    def presentation_pose(self): return ActorAnimationPose('slash',0,facing_x=self.facing)

def make_runtime(grip=GripTransform(8,3,15)):
    rig=SocketRig(); rig.add(Socket('hand_r',default=Transform2D(x=31,y=20,rotation_deg=30)))
    rt=AttachmentRuntime(rig); rt.attach(Attachment('held','blade','hand_r',grip=grip,render_layer='held'))
    return rt

def test_flip_aware_grip_placement_preserves_target():
    # Direct flipped socket target must still place the authored grip exactly.
    rig=SocketRig(); rig.add(Socket('hand',default=Transform2D(x=17,y=9,rotation_deg=-20,flip_x=True)))
    g=GripTransform(7,2,0); rt=AttachmentRuntime(rig); rt.attach(Attachment('a','asset','hand',grip=g))
    out=rt.resolve('a',0).transform
    x,y,_=grip_world(out,g)
    assert (x,y)==pytest.approx((17,9))

def test_facing_mirror_uses_actor_axis_and_preserves_grip_position():
    g=GripTransform(8,3,0); rt=make_runtime(g)
    right=ActorAttachmentBinding('hero',Animator(1),rt,mirror_axis_x=24).resolve().attachments[0]
    left=ActorAttachmentBinding('hero',Animator(-1),rt,mirror_axis_x=24).resolve().attachments[0]
    rx,ry,_=grip_world(right.transform,g); lx,ly,_=grip_world(left.transform,g)
    assert (rx,ry)==pytest.approx((31,20))
    assert (lx,ly)==pytest.approx((17,20))
    assert lx==pytest.approx(48-rx)

def test_facing_mirror_preserves_render_layer_and_asset_identity():
    rt=make_runtime(GripTransform(2,1,0))
    out=ActorAttachmentBinding('hero',Animator(-1),rt,mirror_axis_x=24).resolve().attachments[0]
    assert out.asset_id=='blade' and out.render_layer=='held' and out.transform.flip_x

def test_frame_visual_occlusion_layers_mirror_with_actor():
    rt=make_runtime(GripTransform())
    track=ActorVisualLayerTrack((FrameVisualLayer('hand.mask','hand_foreground',20,Transform2D(x=30,y=4),frames=(0,),clips=('slash',)),))
    frame=ActorAttachmentBinding('hero',Animator(-1),rt,track,mirror_axis_x=24).resolve()
    layer=frame.visual_layers[0]
    assert layer.transform.x==pytest.approx(18)
    assert layer.transform.flip_x is True

def test_default_mirror_axis_keeps_legacy_origin_semantics():
    rt=make_runtime(GripTransform())
    out=ActorAttachmentBinding('hero',Animator(-1),rt).resolve().attachments[0]
    x,_,_=grip_world(out.transform,GripTransform())
    assert x==pytest.approx(-31)
