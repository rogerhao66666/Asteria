import math
from asteria.core import Scene,Entity,Transform
from asteria.editor.viewport import ViewportCamera,scene_markers,pick_entity

def test_camera_roundtrip_and_anchor_zoom():
    c=ViewportCamera(pan_x=100,pan_y=50,zoom=2)
    sx,sy=c.world_to_screen(10,20)
    assert (sx,sy)==(120,90)
    wx,wy=c.screen_to_world(sx,sy)
    assert (wx,wy)==(10,20)

    anchor=(240,180)
    before=c.screen_to_world(*anchor)
    c.zoom_by(1.5,anchor)
    after=c.screen_to_world(*anchor)
    assert math.isclose(before[0],after[0])
    assert math.isclose(before[1],after[1])

def test_scene_markers_use_canonical_transform_and_selection():
    s=Scene("Town")
    a=s.add_entity(Entity("A")); a.add_component(Transform(10,20))
    b=s.add_entity(Entity("B"))  # no transform -> invisible in editor world viewport
    c=ViewportCamera()
    markers=scene_markers(s,c,[a])
    assert len(markers)==1
    m=markers[0]
    assert m.entity is a and m.world_x==10 and m.world_y==20 and m.selected

def test_pick_entity_uses_screen_space_nearest():
    s=Scene()
    a=s.add_entity(Entity("A")); a.add_component(Transform(0,0))
    b=s.add_entity(Entity("B")); b.add_component(Transform(20,0))
    markers=scene_markers(s,ViewportCamera())
    assert pick_entity(markers,2,1) is a
    assert pick_entity(markers,19,0) is b
    assert pick_entity(markers,200,200) is None
