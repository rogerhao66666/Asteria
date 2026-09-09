from asteria.core import Entity,Transform
from asteria.runtime import Camera2DComponent,build_runtime_camera

def test_camera_authoring_builds_runtime_camera_and_follow_policy():
    e=Entity("Camera");e.add_component(Transform(10,20))
    spec=e.add_component(Camera2DComponent())
    spec.width=640;spec.height=360;spec.zoom=2
    spec.follow_entity_id="target-id"
    spec.deadzone_x=8;spec.deadzone_y=4;spec.smoothing=3
    camera,follow=build_runtime_camera(e)
    assert (camera.x,camera.y,camera.width,camera.height,camera.zoom)==(10,20,640,360,2)
    assert follow is not None
    assert (follow.deadzone_x,follow.deadzone_y,follow.smoothing)==(8,4,3)
