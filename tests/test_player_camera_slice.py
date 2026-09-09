from asteria.assets import AssetRef
from asteria.core import Entity,Transform
from asteria.graphics import SpriteClip,SpriteKeyframe,DirectionalClips
from asteria.runtime import (
    SpriteRenderer2D,AnimatorState,CharacterAnimationController,CharacterController2D,
    Camera2D,CameraFollow2D,InputSnapshot,PlayerCameraSlice
)

class OpenWorld:
    def collides_world_point(self,x,y):return False

def clip(name,frame):
    return SpriteClip(name,[SpriteKeyframe(frame,0.1)],True)

def test_player_slice_moves_animates_and_follows_camera():
    idle={d:clip("idle_"+d,0) for d in ("down","up","left","right")}
    walk={d:clip("walk_"+d,1) for d in ("down","up","left","right")}
    directional=DirectionalClips(idle,walk)
    animator=AnimatorState(idle["down"])
    anim=CharacterAnimationController(directional,animator)
    e=Entity("Hero");e.add_component(Transform(0,0));sprite=e.add_component(SpriteRenderer2D())
    controller=CharacterController2D(0,0,speed=10)
    camera=Camera2D(0,0,100,100,1)
    follow=CameraFollow2D(camera,smoothing=0)
    slice=PlayerCameraSlice(e,controller,anim,follow,sprite)
    dx,dy,moving=slice.step(InputSnapshot({"move_right":1}),0.5,OpenWorld())
    assert moving and dx==5 and dy==0
    assert e.get(Transform).x==5
    assert sprite.frame_index==1
    # Camera2D stores the world-space top-left, so centering on x=5 in a 100px view gives -45.
    assert camera.x==-45 and camera.y==-50
