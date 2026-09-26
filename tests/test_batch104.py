from asteria.presentation.actor_attachment import ActorAnimationPose, ActorAttachmentBinding
from asteria.presentation.actor_visual_layers import ActorVisualLayerTrack, FrameVisualLayer
from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.attachments import Attachment, Socket, SocketRig, Transform2D
from asteria.presentation.render_integration import PresentationRenderComposer

class Animator:
    def __init__(self, clip="one_hand_slash", frame=0): self.clip=clip; self.frame=frame
    def presentation_pose(self): return ActorAnimationPose(self.clip,self.frame)

def rig():
    r=SocketRig(); r.add(Socket("hand_r",default=Transform2D(x=24,y=20))); return r

def test_foreground_hand_layer_is_frame_aware_and_composed_over_attachment():
    rt=AttachmentRuntime(rig()); rt.attach(Attachment("held","iron_sword","hand_r",render_layer="held"))
    track=ActorVisualLayerTrack((FrameVisualLayer("hero.hand.f0","hand_foreground",20,frames=(0,),clips=("one_hand_slash",)),))
    frame=ActorAttachmentBinding("hero",Animator(frame=0),rt,track).resolve()
    packets=PresentationRenderComposer().actor_packets(frame,"hero.body",layer_z={"held":10})
    assert [p.asset_id for p in packets] == ["hero.body","iron_sword","hero.hand.f0"]

def test_foreground_layer_does_not_leak_to_other_frame():
    rt=AttachmentRuntime(rig()); rt.attach(Attachment("held","iron_sword","hand_r",render_layer="held"))
    track=ActorVisualLayerTrack((FrameVisualLayer("hero.hand.f0","hand_foreground",20,frames=(0,)),))
    frame=ActorAttachmentBinding("hero",Animator(frame=1),rt,track).resolve()
    assert [p.asset_id for p in PresentationRenderComposer().actor_packets(frame,"hero.body",layer_z={"held":10})] == ["hero.body","iron_sword"]

def test_layers_can_be_clip_specific():
    track=ActorVisualLayerTrack((FrameVisualLayer("slash.hand",clips=("slash",)),FrameVisualLayer("cast.hand",clips=("cast",))))
    assert [x.asset_id for x in track.resolve("slash",0)] == ["slash.hand"]
    assert [x.asset_id for x in track.resolve("cast",0)] == ["cast.hand"]

def test_layer_track_roundtrip():
    src=ActorVisualLayerTrack((FrameVisualLayer("hand","fg",12.5,Transform2D(x=2,y=3,rotation_deg=9),frames=(1,2),clips=("slash",)),))
    dst=ActorVisualLayerTrack.from_dict(src.to_dict())
    assert dst.layers == src.layers

def test_layer_track_is_generic_not_weapon_or_genre_specific():
    import inspect, asteria.presentation.actor_visual_layers as mod
    s=inspect.getsource(mod).lower()
    assert "if jrpg" not in s and "if arpg" not in s and "if sword" not in s
